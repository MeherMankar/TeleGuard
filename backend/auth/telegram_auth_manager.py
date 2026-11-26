import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from typing import Dict, Any, Optional
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from teleguard.core.config import config
from teleguard.data.device_profiles import get_random_device

logger = logging.getLogger(__name__)

API_ID = config.telegram.api_id
API_HASH = config.telegram.api_hash

MAX_PENDING_LOGINS_PER_USER = 3
MAX_PENDING_LOGINS = 200
MAX_LOGIN_STARTS_PER_MINUTE = 5
PENDING_LOGIN_TTL_SECONDS = 600


class LoginCapacityError(ValueError):
    pass


def _make_client() -> TelegramClient:
    """Create a Telethon client with random Android device spoofing from central profiles."""
    device = get_random_device()
    return TelegramClient(
        StringSession(),
        API_ID,
        API_HASH,
        **device,
        connection_retries=3,
        retry_delay=2,
    )


class TelegramAuthManager:
    """
    Manages temporary Telethon clients during multi-step webapp login.

    Key design:
    - Uses Android device params (not PC) to avoid "PC 64bit" login notifications
    - After successful login, hands the already-connected client directly to
      bot_manager instead of disconnecting it and creating a second one.
      This prevents the double-login-notification problem.
    """

    def __init__(self):
        self.pending_logins: Dict[str, Dict[str, Any]] = {}
        self.cleanup_task = None
        self._lock = asyncio.Lock()
        self._login_starts = defaultdict(deque)
        self._inflight_by_user = defaultdict(int)

    async def _reserve_login_slot(self, user_id: int) -> None:
        now = time.monotonic()
        async with self._lock:
            starts = self._login_starts[user_id]
            while starts and now - starts[0] >= 60:
                starts.popleft()

            active_for_user = sum(
                1
                for data in self.pending_logins.values()
                if data.get("user_id") == user_id
                and data.get("status") != "failed"
            )
            total_inflight = sum(self._inflight_by_user.values())
            if (
                active_for_user + self._inflight_by_user[user_id]
                >= MAX_PENDING_LOGINS_PER_USER
            ):
                raise LoginCapacityError(
                    "Too many pending login attempts; finish or wait for one to expire"
                )
            if len(self.pending_logins) + total_inflight >= MAX_PENDING_LOGINS:
                raise LoginCapacityError("Login capacity is temporarily full")
            if len(starts) >= MAX_LOGIN_STARTS_PER_MINUTE:
                raise LoginCapacityError(
                    "Too many login attempts; wait before trying again"
                )

            starts.append(now)
            self._inflight_by_user[user_id] += 1

    async def _release_login_slot(self, user_id: int) -> None:
        async with self._lock:
            remaining = self._inflight_by_user.get(user_id, 0) - 1
            if remaining > 0:
                self._inflight_by_user[user_id] = remaining
            else:
                self._inflight_by_user.pop(user_id, None)

    def _start_cleanup_task(self):
        if not self.cleanup_task or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())

    def _get_login_data(self, session_id: str, user_id: int) -> Dict[str, Any]:
        login_data = self.pending_logins.get(session_id)
        if not login_data or login_data.get("user_id") != user_id:
            raise ValueError("Invalid or expired session_id")
        created_at = login_data.get("created_at_monotonic")
        if (
            created_at is not None
            and time.monotonic() - created_at > PENDING_LOGIN_TTL_SECONDS
        ):
            raise ValueError("Invalid or expired session_id")
        return login_data

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(60)
            now = time.monotonic()
            expired_clients = []
            async with self._lock:
                expired = [
                    sid for sid, data in self.pending_logins.items()
                    if now - data.get(
                        "created_at_monotonic",
                        data.get("timestamp_monotonic", now),
                    ) > PENDING_LOGIN_TTL_SECONDS
                ]
                for sid in expired:
                    login_data = self.pending_logins.pop(sid)
                    expired_clients.append(login_data["client"])
                for user_id, starts in list(self._login_starts.items()):
                    while starts and now - starts[0] >= 60:
                        starts.popleft()
                    if not starts and user_id not in self._inflight_by_user:
                        self._login_starts.pop(user_id, None)
            for client in expired_clients:
                try:
                    await client.disconnect()
                except Exception:
                    logger.exception("Could not disconnect expired login client")

    async def start_phone_login(self, user_id: int, phone: str):
        if not API_ID or not API_HASH:
            raise ValueError("API_ID and API_HASH not configured")

        await self._reserve_login_slot(user_id)
        self._start_cleanup_task()
        session_id = str(uuid.uuid4())
        client = None
        try:
            client = _make_client()
            await client.connect()
            result = await client.send_code_request(phone)
            async with self._lock:
                self.pending_logins[session_id] = {
                    "user_id": user_id,
                    "client": client,
                    "phone": phone,
                    "phone_code_hash": result.phone_code_hash,
                    "timestamp": time.time(),
                    "created_at_monotonic": time.monotonic(),
                }
            self._start_cleanup_task()
            return session_id, result.phone_code_hash
        except Exception:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    logger.exception("Could not disconnect failed phone-login client")
            raise
        except asyncio.CancelledError:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    logger.exception("Could not disconnect cancelled phone login")
            raise
        finally:
            await self._release_login_slot(user_id)

    async def verify_code(
        self, user_id: int, session_id: str, code: str
    ) -> Dict[str, Any]:
        async with self._lock:
            login_data = self._get_login_data(session_id, user_id)

        client: TelegramClient = login_data["client"]
        login_data["timestamp"] = time.time()

        try:
            user = await client.sign_in(
                phone=login_data["phone"],
                code=code,
                phone_code_hash=login_data["phone_code_hash"],
            )
            session_string = client.session.save()
            # Keep client alive — will be handed to bot_manager
            login_data["session"] = session_string
            login_data["user"] = user
            return {"status": "success", "session": session_string, "user": user}
        except SessionPasswordNeededError:
            return {"status": "requires_2fa"}
        except Exception as e:
            raise e

    async def verify_password(
        self, user_id: int, session_id: str, password: str
    ) -> Dict[str, Any]:
        async with self._lock:
            login_data = self._get_login_data(session_id, user_id)

        client: TelegramClient = login_data["client"]
        login_data["timestamp"] = time.time()

        try:
            user = await client.sign_in(password=password)
            session_string = client.session.save()
            login_data["session"] = session_string
            login_data["user"] = user
            return {"status": "success", "session": session_string, "user": user}
        except Exception as e:
            raise e

    async def start_qr_login(self, user_id: int) -> Dict[str, Any]:
        if not API_ID or not API_HASH:
            raise ValueError("API_ID and API_HASH not configured")

        await self._reserve_login_slot(user_id)
        self._start_cleanup_task()
        session_id = str(uuid.uuid4())
        client = None
        try:
            client = _make_client()
            await client.connect()
            qr_login = await client.qr_login()
            async with self._lock:
                self.pending_logins[session_id] = {
                    "user_id": user_id,
                    "client": client,
                    "qr_login": qr_login,
                    "status": "pending",
                    "timestamp": time.time(),
                    "created_at_monotonic": time.monotonic(),
                }
            asyncio.create_task(self._wait_for_qr(session_id, qr_login))
            self._start_cleanup_task()
            return {"session_id": session_id, "url": qr_login.url}
        except Exception:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    logger.exception("Could not disconnect failed QR-login client")
            raise
        except asyncio.CancelledError:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    logger.exception("Could not disconnect cancelled QR login")
            raise
        finally:
            await self._release_login_slot(user_id)

    async def _wait_for_qr(self, session_id: str, qr_login):
        try:
            user = await qr_login.wait(timeout=115)
            async with self._lock:
                if session_id in self.pending_logins:
                    client = self.pending_logins[session_id]["client"]
                    session_string = client.session.save()
                    self.pending_logins[session_id].update({
                        "status": "success",
                        "session": session_string,
                        "user": user,
                    })
        except SessionPasswordNeededError:
            # 2FA is enabled — keep the client alive so the frontend can submit the password
            async with self._lock:
                if session_id in self.pending_logins:
                    self.pending_logins[session_id].update({
                        "status": "requires_2fa",
                    })
            logger.info(f"QR login requires 2FA for session {session_id}")
        except Exception as e:
            client = None
            async with self._lock:
                if session_id in self.pending_logins:
                    client = self.pending_logins[session_id]["client"]
                    self.pending_logins[session_id].update({
                        "status": "failed",
                        "error": str(e),
                    })
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    logger.exception("Could not disconnect failed QR-login client")

    async def get_qr_status(self, user_id: int, session_id: str) -> Dict[str, Any]:
        async with self._lock:
            login_data = self._get_login_data(session_id, user_id)

        status = login_data.get("status")

        if status == "success":
            return {
                "status": "success",
                "session": login_data.get("session"),
                "user": login_data.get("user"),
            }
        elif status == "requires_2fa":
            return {"status": "requires_2fa"}
        elif status == "failed":
            return {"status": "failed", "error": login_data.get("error")}
        return {"status": "pending"}

    async def verify_qr_password(
        self, user_id: int, session_id: str, password: str
    ) -> Dict[str, Any]:
        """Verify 2FA password after QR scan when 2FA is enabled."""
        async with self._lock:
            login_data = self._get_login_data(session_id, user_id)
        if login_data.get("status") != "requires_2fa":
            raise ValueError("Session is not awaiting 2FA password")

        client: TelegramClient = login_data["client"]
        login_data["timestamp"] = time.time()

        try:
            user = await client.sign_in(password=password)
            session_string = client.session.save()
            login_data["session"] = session_string
            login_data["user"] = user
            login_data["status"] = "success"
            return {"status": "success", "session": session_string, "user": user}
        except Exception as e:
            raise e

    def get_connected_client(
        self, session_id: str, user_id: int
    ) -> Optional[TelegramClient]:
        """
        Return the already-connected client after successful login.
        Used by accounts.py to hand to bot_manager WITHOUT disconnecting/reconnecting.
        """
        data = self.pending_logins.get(session_id)
        if (
            data
            and data.get("user_id") == user_id
            and data.get("status") in ("success", None)
        ):
            return data.get("client")
        return None

    async def finish_login(
        self, session_id: str, user_id: int, keep_client: bool = False
    ):
        """
        Clean up pending login state.
        If keep_client=True, do NOT disconnect — bot_manager owns it now.
        """
        async with self._lock:
            if session_id in self.pending_logins:
                login_data = self._get_login_data(session_id, user_id)
                if not keep_client:
                    try:
                        await login_data["client"].disconnect()
                    except Exception:
                        pass
                del self.pending_logins[session_id]


telegram_auth_manager = TelegramAuthManager()
