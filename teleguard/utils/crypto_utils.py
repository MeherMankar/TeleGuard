"""Encryption utilities for session backup system

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import hashlib
import logging
import os

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# Get encryption key from environment or KMS
FERNET_KEY = os.environ.get("FERNET_KEY")
if not FERNET_KEY:
    # Fallback to existing key file for compatibility
    try:
        from pathlib import Path

        key_path = Path(__file__).parent.parent.parent / "config" / "secret.key"
        with open(key_path, "rb") as f:
            FERNET_KEY = f.read()
    except FileNotFoundError:
        raise RuntimeError("FERNET_KEY missing and no secret.key file found")

if isinstance(FERNET_KEY, str):
    FERNET_KEY = FERNET_KEY.encode()

try:
    fernet = Fernet(FERNET_KEY)
except Exception as e:
    raise ValueError(f"Invalid FERNET_KEY format: {e}")


def encrypt_bytes(raw: bytes) -> bytes:
    """Encrypt raw bytes using Fernet"""
    return fernet.encrypt(raw)


def decrypt_bytes(enc: bytes) -> bytes:
    """Decrypt encrypted bytes using Fernet"""
    return fernet.decrypt(enc)


def sha256_bytes(b: bytes) -> str:
    """Calculate SHA256 hash of bytes"""
    return hashlib.sha256(b).hexdigest()


def encrypt_session_string(session_str: str) -> tuple[bytes, str]:
    """Encrypt session string and return (encrypted_bytes, sha256_hash)"""
    raw_bytes = session_str.encode("utf-8")
    encrypted = encrypt_bytes(raw_bytes)
    sha256_hash = sha256_bytes(encrypted)
    return encrypted, sha256_hash


def decrypt_session_bytes(encrypted_bytes: bytes) -> str:
    """Decrypt session bytes back to string"""
    raw_bytes = decrypt_bytes(encrypted_bytes)
    return raw_bytes.decode("utf-8")
