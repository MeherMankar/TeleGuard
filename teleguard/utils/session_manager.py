"""Secure session management"""

import os
import shutil
from pathlib import Path

from ..core.config import FERNET
from ..core.exceptions import SessionError


class SessionManager:
    def __init__(self):
        self.sessions_dir = Path.home() / ".teleguard" / "sessions"
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
