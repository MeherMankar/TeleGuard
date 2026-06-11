import asyncio
import logging
import random
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

# Android device profiles — matches the bot's DeviceSnooper
_DEVICES = [
    {"device_model": "Samsung SM-G991B", "system_version": "Android 12", "app_version": "10.14.5", "lang_code": "en", "system_lang_code": "en-US"},
    {"device_model": "Samsung SM-G998B", "system_version": "Android 13", "app_version": "10.14.5", "lang_code": "en", "system_lang_code": "en-US"},
    {"device_model": "Google Pixel 7",   "system_version": "Android 14", "app_version": "10.14.5", "lang_code": "en", "system_lang_code": "en-US"},
    {"device_model": "OnePlus 11",       "system_version": "Android 13", "app_version": "10.14.5", "lang_code": "en", "system_lang_code": "en-US"},
    {"device_model": "Xiaomi 13 Pro",    "system_version": "Android 13", "app_version": "10.14.5", "lang_code": "en", "system_lang_code": "en-US"},
    {"device_model": "Samsung SM-S908B", "system_version": "Android 13", "app_version": "10.14.5", "lang_code": "en", "system_lang_code": "en-US"},
]


def _make_client() -> TelegramClient:
    """Create a Telethon client with random Android device spoofing."""
    device = random.choice(_DEVICES)
    return TelegramClient(
        StringSession(),
        API_ID,
        API_HASH,
        device_model=device["device_model"],
        system_version=device["system_version"],
        app_version=device["app_version"],
        lang_code=device["lang_code"],
        system_lang_code=device["system_lang_code"],
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
        client = _make_client()
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
            # Keep client alive — will be handed to bot_manager
            login_data["session"] = session_string
            login_data["user"] = user
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
            login_data["session"] = session_string
            login_data["user"] = user
            return {"status": "success", "session": session_string, "user": user}
        except Exception as e:
            raise e

    async def start_qr_login(self) -> Dict[str, Any]:
        if not API_ID or not API_HASH:
            raise ValueError("API_ID and API_HASH not configured")

        session_id = str(uuid.uuid4())
        client = _make_client()
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

    def get_connected_client(self, session_id: str) -> Optional[TelegramClient]:
        """
        Return the already-connected client after successful login.
        Used by accounts.py to hand to bot_manager WITHOUT disconnecting/reconnecting.
        """
        data = self.pending_logins.get(session_id)
        if data and data.get("status") in ("success", None):
            return data.get("client")
        return None

    async def finish_login(self, session_id: str, keep_client: bool = False):
        """
        Clean up pending login state.
        If keep_client=True, do NOT disconnect — bot_manager owns it now.
        """
        async with self._lock:
            if session_id in self.pending_logins:
                if not keep_client:
                    try:
                        await self.pending_logins[session_id]["client"].disconnect()
                    except Exception:
                        pass
                del self.pending_logins[session_id]


telegram_auth_manager = TelegramAuthManager()
