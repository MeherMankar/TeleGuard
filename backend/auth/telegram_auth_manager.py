import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from teleguard.core.config import config

logger = logging.getLogger(__name__)

API_ID = config.telegram.api_id
API_HASH = config.telegram.api_hash


class TelegramAuthManager:
    """Manages temporary Telethon clients during the multi-step login process."""

    def __init__(self):
        self.pending_logins: Dict[str, Dict[str, Any]] = {}
        self.cleanup_task = None
        self._lock = asyncio.Lock()

    def _start_cleanup_task(self):
        if not self.cleanup_task or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(60)
            now = time.time()
            async with self._lock:
                expired = [
                    sid for sid, data in self.pending_logins.items()
                    if now - data.get("timestamp", now) > 600
                ]
                for sid in expired:
                    try:
                        await self.pending_logins[sid]["client"].disconnect()
                    except Exception:
                        pass
                    del self.pending_logins[sid]

    async def start_phone_login(self, phone: str):
        if not API_ID or not API_HASH:
            raise ValueError("API_ID and API_HASH not configured")

        session_id = str(uuid.uuid4())
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()

        try:
            result = await client.send_code_request(phone)
            async with self._lock:
                self.pending_logins[session_id] = {
                    "client": client,
                    "phone": phone,
                    "phone_code_hash": result.phone_code_hash,
                    "timestamp": time.time(),
                }
            self._start_cleanup_task()
            return session_id, result.phone_code_hash
        except Exception as e:
            await client.disconnect()
            raise e

    async def verify_code(self, session_id: str, code: str) -> Dict[str, Any]:
        async with self._lock:
            login_data = self.pending_logins.get(session_id)
        if not login_data:
            raise ValueError("Invalid or expired session_id")

        client: TelegramClient = login_data["client"]
        login_data["timestamp"] = time.time()

        try:
            user = await client.sign_in(
                phone=login_data["phone"],
                code=code,
                phone_code_hash=login_data["phone_code_hash"],
            )
            session_string = client.session.save()
            return {"status": "success", "session": session_string, "user": user}
        except SessionPasswordNeededError:
            return {"status": "requires_2fa"}
        except Exception as e:
            raise e

    async def verify_password(self, session_id: str, password: str) -> Dict[str, Any]:
        async with self._lock:
            login_data = self.pending_logins.get(session_id)
        if not login_data:
            raise ValueError("Invalid or expired session_id")

        client: TelegramClient = login_data["client"]
        login_data["timestamp"] = time.time()

        try:
            user = await client.sign_in(password=password)
            session_string = client.session.save()
            return {"status": "success", "session": session_string, "user": user}
        except Exception as e:
            raise e

    async def start_qr_login(self) -> Dict[str, Any]:
        if not API_ID or not API_HASH:
            raise ValueError("API_ID and API_HASH not configured")

        session_id = str(uuid.uuid4())
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()

        try:
            qr_login = await client.qr_login()
            async with self._lock:
                self.pending_logins[session_id] = {
                    "client": client,
                    "qr_login": qr_login,
                    "status": "pending",
                    "timestamp": time.time(),
                }
            asyncio.create_task(self._wait_for_qr(session_id, qr_login))
            self._start_cleanup_task()
            return {"session_id": session_id, "url": qr_login.url}
        except Exception as e:
            await client.disconnect()
            raise e

    async def _wait_for_qr(self, session_id: str, qr_login):
        try:
            user = await qr_login.wait(timeout=120)
            async with self._lock:
                if session_id in self.pending_logins:
                    client = self.pending_logins[session_id]["client"]
                    session_string = client.session.save()
                    self.pending_logins[session_id].update({
                        "status": "success",
                        "session": session_string,
                        "user": user,
                    })
        except Exception as e:
            async with self._lock:
                if session_id in self.pending_logins:
                    self.pending_logins[session_id].update({
                        "status": "failed",
                        "error": str(e),
                    })

    async def get_qr_status(self, session_id: str) -> Dict[str, Any]:
        async with self._lock:
            login_data = self.pending_logins.get(session_id)
        if not login_data:
            raise ValueError("Invalid or expired session_id")

        login_data["timestamp"] = time.time()
        status = login_data.get("status")

        if status == "success":
            return {
                "status": "success",
                "session": login_data.get("session"),
                "user": login_data.get("user"),
            }
        elif status == "failed":
            return {"status": "failed", "error": login_data.get("error")}
        return {"status": "pending"}

    async def finish_login(self, session_id: str):
        async with self._lock:
            if session_id in self.pending_logins:
                try:
                    await self.pending_logins[session_id]["client"].disconnect()
                except Exception:
                    pass
                del self.pending_logins[session_id]


telegram_auth_manager = TelegramAuthManager()
