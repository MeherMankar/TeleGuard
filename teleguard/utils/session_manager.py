"""Unified session management and utilities"""

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Tuple

from telethon import TelegramClient
from telethon.sessions import StringSession

from ..core.config import FERNET
from ..core.exceptions import SessionError

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self):
        sessions_dir_path = os.getenv(
            "SESSIONS_DIR", str(Path.home() / ".teleguard" / "sessions")
        )
        self.sessions_dir = Path(sessions_dir_path)
        self.sessions_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    def get_session_path(self, user_id: int, account_name: str) -> Path:
        """Get secure session file path"""
        filename = f"user_{user_id}_{account_name}.session"
        return self.sessions_dir / filename

    def cleanup_old_sessions(self):
        """Remove old session files from project root"""
        project_root = Path(__file__).parent.parent.parent.parent
        for session_file in project_root.glob("*.session*"):
            try:
                secure_path = self.sessions_dir / session_file.name
                if not secure_path.exists():
                    shutil.move(str(session_file), str(secure_path))
                else:
                    session_file.unlink()
            except Exception:
                pass

    def encrypt_session_data(self, data: str) -> str:
        """Encrypt session data"""
        try:
            return FERNET.encrypt(data.encode()).decode()
        except Exception as e:
            raise SessionError(f"Failed to encrypt session: {e}")

    def decrypt_session_data(self, encrypted_data: str) -> str:
        """Decrypt session data"""
        try:
            return FERNET.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            raise SessionError(f"Failed to decrypt session: {e}")


async def validate_string_session(
    session_string: str, api_id: int, api_hash: str
) -> Tuple[bool, Any]:
    """Validate a Telethon StringSession.
    Returns (True, info_dict) on success where info_dict contains id, phone and name.
    Returns (False, error_message) on failure.
    """
    if (
        not session_string
        or not isinstance(session_string, str)
        or len(session_string) < 32
    ):
        return False, "Invalid session string format"

    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "Session is not authorized"
        me = await client.get_me()
        name = f"{me.first_name or ''} {me.last_name or ''}".strip() or f"User_{me.id}"
        info = {"id": me.id, "phone": getattr(me, "phone", None), "name": name}
        await client.disconnect()
        return True, info
    except Exception as e:
        logger.debug("String session validation failed: %s", e)
        try:
            await client.disconnect()
        except Exception:
            pass
        return False, str(e)


async def str_to_session_file(
    session_string: str, file_path: str, api_id: int, api_hash: str
) -> Tuple[bool, str]:
    """Convert a Telethon StringSession to a file-backed session (.session).
    Returns (True, file_path) on success or (False, error_message) on failure.
    """
    if not session_string or not file_path:
        return False, "Invalid arguments"
    
    session_name = _get_session_name(file_path)
    string_client = TelegramClient(StringSession(session_string), api_id, api_hash)
    
    try:
        auth_key = await _extract_auth_key(string_client)
        if not auth_key:
            return False, "Session auth_key unavailable; cannot create file session"
        
        return await _create_file_session(session_name, api_id, api_hash, string_client, auth_key)
    except Exception as e:
        try:
            await string_client.disconnect()
        except Exception:
            pass
        return False, str(e)


def _get_session_name(file_path: str) -> str:
    """Extract session name from file path"""
    if file_path.endswith(".session"):
        return file_path[:-8]
    return file_path


async def _extract_auth_key(string_client):
    """Extract auth key from string client"""
    auth_key = getattr(string_client.session, "auth_key", None)
    if not auth_key:
        try:
            await string_client.connect()
            auth_key = getattr(string_client.session, "auth_key", None)
        except Exception:
            pass
        finally:
            try:
                await string_client.disconnect()
            except Exception:
                pass
    return auth_key


async def _create_file_session(session_name: str, api_id: int, api_hash: str, string_client, auth_key) -> Tuple[bool, str]:
    """Create file-backed session from string session"""
    dc_id = getattr(string_client.session, "dc_id", None)
    server_address = getattr(string_client.session, "server_address", None)
    port = getattr(string_client.session, "port", None)
    
    file_client = TelegramClient(session_name, api_id, api_hash)
    try:
        try:
            if hasattr(file_client.session, "set_dc") and dc_id is not None:
                file_client.session.set_dc(dc_id, server_address or "", port or 0)
            if hasattr(file_client.session, "auth_key"):
                file_client.session.auth_key = auth_key
            file_client.session.save()
            return True, f"{session_name}.session"
        except Exception as e:
            return False, f"Failed to write session file: {e}"
    finally:
        try:
            await file_client.disconnect()
        except Exception:
            pass
