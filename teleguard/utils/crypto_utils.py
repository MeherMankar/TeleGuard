"""Unified encryption utilities for TeleGuard
Developed by:
- @Meher_Mankar
- @Gutkesh
GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import base64
import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# Fernet encryption key from environment
FERNET_KEY = os.environ.get("FERNET_KEY")
if not FERNET_KEY:
    # Fallback to key file for backward compatibility
    try:
        from pathlib import Path

        key_path = Path(__file__).parent.parent.parent / "config" / "secret.key"
        if key_path.exists():
            with open(key_path, "rb") as f:
                FERNET_KEY = f.read()
        else:
            logger.warning(
                "No FERNET_KEY environment variable or secret.key file found"
            )
            FERNET_KEY = None
    except Exception as e:
        logger.error(f"Failed to load encryption key: {e}")
        FERNET_KEY = None

fernet = None
if FERNET_KEY:
    try:
        if isinstance(FERNET_KEY, str):
            FERNET_KEY = FERNET_KEY.encode()
        fernet = Fernet(FERNET_KEY)
    except Exception as e:
        logger.error(f"Invalid FERNET_KEY format: {e}")
        fernet = None


# Legacy functions
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


class SecureCrypto:
    """Secure encryption/decryption using AEAD ciphers"""

    def __init__(self, key: Optional[bytes] = None):
        if key is None:
            key = AESGCM.generate_key(bit_length=256)
        elif isinstance(key, str):
            key = base64.b64decode(key.encode())
        self.cipher = AESGCM(key)
        self.key = key

    def get_key_b64(self) -> str:
        return base64.b64encode(self.key).decode()

    def encrypt(self, plaintext: str) -> str:
        if not isinstance(plaintext, str):
            plaintext = str(plaintext)
        data = plaintext.encode("utf-8")
        nonce = os.urandom(12)
        ciphertext = self.cipher.encrypt(nonce, data, None)
        encrypted_data = nonce + ciphertext
        return base64.b64encode(encrypted_data).decode()

    def decrypt(self, encrypted_data: str) -> str:
        try:
            data = base64.b64decode(encrypted_data.encode())
            nonce = data[:12]
            ciphertext = data[12:]
            plaintext = self.cipher.decrypt(nonce, ciphertext, None)
            return plaintext.decode("utf-8")
        except Exception:
            raise ValueError("Decryption failed - invalid or corrupted data")


class SecureKeyDerivation:
    """Secure key derivation from passwords"""

    @staticmethod
    def derive_key(password: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
        if salt is None:
            salt = os.urandom(32)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(password.encode("utf-8"))
        return key, salt

    @staticmethod
    def verify_key(password: str, salt: bytes, expected_key: bytes) -> bool:
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            kdf.verify(password.encode("utf-8"), expected_key)
            return True
        except Exception:
            return False


class DataEncryption:
    """Comprehensive data encryption system"""

    @staticmethod
    def encrypt_field(data: Any) -> Any:
        if data is None or fernet is None:
            return data
        try:
            json_str = json.dumps(data, default=str)
            encrypted_bytes = fernet.encrypt(json_str.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Failed to encrypt field: {e}")
            return data

    @staticmethod
    def decrypt_field(encrypted_data: Any) -> Any:
        if encrypted_data is None or fernet is None:
            return encrypted_data
        try:
            if not isinstance(encrypted_data, str):
                return encrypted_data
            decrypted_bytes = fernet.decrypt(encrypted_data.encode())
            json_str = decrypted_bytes.decode()
            return json.loads(json_str)
        except Exception as e:
            logger.debug(f"Failed to decrypt field, returning as-is: {e}")
            return encrypted_data

    @staticmethod
    def encrypt_user_data(user_data: Dict) -> Dict:
        if fernet is None:
            return user_data.copy()
        encrypted_data = user_data.copy()
        sensitive_fields = [
            "developer_mode",
            "settings",
            "preferences",
            "auto_reply_settings",
            "otp_settings",
        ]
        for field in sensitive_fields:
            if field in encrypted_data:
                encrypted_data[f"{field}_enc"] = DataEncryption.encrypt_field(
                    encrypted_data[field]
                )
                del encrypted_data[field]
        return encrypted_data

    @staticmethod
    def decrypt_user_data(encrypted_data: Dict) -> Dict:
        if not encrypted_data:
            return {}
        decrypted_data = encrypted_data.copy()
        encrypted_fields = [
            key for key in decrypted_data.keys() if key.endswith("_enc")
        ]
        for enc_field in encrypted_fields:
            original_field = enc_field[:-4]
            try:
                decrypted_value = DataEncryption.decrypt_field(
                    decrypted_data[enc_field]
                )
                if decrypted_value is not None:
                    decrypted_data[original_field] = decrypted_value
                del decrypted_data[enc_field]
            except Exception as e:
                logger.error(f"Failed to decrypt field {enc_field}: {e}")
                del decrypted_data[enc_field]
        return decrypted_data

    @staticmethod
    def encrypt_account_data(account_data: Dict) -> Dict:
        """Encrypt sensitive account fields before storing in MongoDB.

        Only ``session_string`` is truly secret and needs encryption.
        All other fields (name, phone, flags, etc.) are stored plain so
        they can be used directly in MongoDB query filters without
        encrypt/decrypt gymnastics.
        """
        if fernet is None:
            return account_data.copy()
        encrypted_data = account_data.copy()
        sensitive_fields = [
            "session_string",
        ]
        for field in sensitive_fields:
            if field in encrypted_data:
                encrypted_data[f"{field}_enc"] = DataEncryption.encrypt_field(
                    encrypted_data[field]
                )
                del encrypted_data[field]
        return encrypted_data

    @staticmethod
    def decrypt_account_data(encrypted_data: Dict) -> Dict:
        """Decrypt an account document fetched from MongoDB.

        Handles legacy documents that may have ``_enc``-suffixed fields
        from an older encryption scheme, and passes plain documents
        through unchanged.
        """
        if not encrypted_data:
            return {}
        decrypted_data = encrypted_data.copy()
        encrypted_fields = [
            key for key in decrypted_data.keys() if key.endswith("_enc")
        ]
        for enc_field in encrypted_fields:
            original_field = enc_field[:-4]
            # Don't overwrite a plain field that already exists
            if original_field in decrypted_data:
                del decrypted_data[enc_field]
                continue
            try:
                decrypted_value = DataEncryption.decrypt_field(
                    decrypted_data[enc_field]
                )
                decrypted_data[original_field] = decrypted_value
                del decrypted_data[enc_field]
            except Exception as e:
                logger.debug(f"Failed to decrypt field {enc_field}: {e}")
                decrypted_data[original_field] = decrypted_data[enc_field]
                del decrypted_data[enc_field]
        return decrypted_data

    @staticmethod
    def encrypt_data(data: str) -> str:
        return DataEncryption.encrypt_field(data)

    @staticmethod
    def decrypt_data(encrypted_data: str) -> str:
        return DataEncryption.decrypt_field(encrypted_data)
