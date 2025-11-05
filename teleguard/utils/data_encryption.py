"""Data encryption utilities for TeleGuard."""

import base64
import hashlib
import os
from cryptography.fernet import Fernet
from typing import Optional, Union


class DataEncryption:
    """Handles data encryption and decryption for TeleGuard."""
    
    def __init__(self, key: Optional[bytes] = None):
        """Initialize encryption with a key."""
        if key is None:
            key = self._generate_key()
        elif isinstance(key, str):
            key = key.encode()
        
        self.fernet = Fernet(key)
        self._key = key
    
    @staticmethod
    def _generate_key() -> bytes:
        """Generate a new encryption key."""
        return Fernet.generate_key()
    
    @staticmethod
    def generate_key_from_password(password: str, salt: Optional[bytes] = None) -> bytes:
        """Generate encryption key from password."""
        if salt is None:
            salt = os.urandom(16)
        
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return base64.urlsafe_b64encode(key)
    
    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """Encrypt data."""
        if isinstance(data, str):
            data = data.encode()
        return self.fernet.encrypt(data)
    
    def decrypt(self, encrypted_data: bytes) -> bytes:
        """Decrypt data."""
        return self.fernet.decrypt(encrypted_data)
    
    def encrypt_string(self, text: str) -> str:
        """Encrypt string and return base64 encoded result."""
        encrypted = self.encrypt(text)
        return base64.b64encode(encrypted).decode()
    
    def decrypt_string(self, encrypted_text: str) -> str:
        """Decrypt base64 encoded string."""
        encrypted_data = base64.b64decode(encrypted_text.encode())
        decrypted = self.decrypt(encrypted_data)
        return decrypted.decode()
    
    @property
    def key(self) -> bytes:
        """Get the encryption key."""
        return self._key
    
    @staticmethod
    def decrypt_account_data(encrypted_data: str) -> dict:
        """Decrypt account data - uses global encryption."""
        try:
            decrypted = decrypt_string(encrypted_data)
            import json
            return json.loads(decrypted)
        except:
            return {}
    
    @staticmethod
    def encrypt_settings_data(data: dict) -> str:
        """Encrypt settings data - uses global encryption."""
        import json
        json_str = json.dumps(data)
        return encrypt_string(json_str)
    
    @staticmethod
    def decrypt_settings_data(encrypted_data: dict) -> dict:
        """Decrypt settings data - uses global encryption."""
        try:
            if isinstance(encrypted_data, dict):
                return encrypted_data
            decrypted = decrypt_string(encrypted_data)
            import json
            return json.loads(decrypted)
        except:
            return {}


# Global encryption instance
_global_encryption: Optional[DataEncryption] = None


def get_encryption() -> DataEncryption:
    """Get global encryption instance."""
    global _global_encryption
    if _global_encryption is None:
        _global_encryption = DataEncryption()
    return _global_encryption


def set_encryption_key(key: Union[str, bytes]) -> None:
    """Set global encryption key."""
    global _global_encryption
    _global_encryption = DataEncryption(key)


def encrypt_data(data: Union[str, bytes]) -> bytes:
    """Encrypt data using global encryption."""
    return get_encryption().encrypt(data)


def decrypt_data(encrypted_data: bytes) -> bytes:
    """Decrypt data using global encryption."""
    return get_encryption().decrypt(encrypted_data)


def encrypt_string(text: str) -> str:
    """Encrypt string using global encryption."""
    return get_encryption().encrypt_string(text)


def decrypt_string(encrypted_text: str) -> str:
    """Decrypt string using global encryption."""
    return get_encryption().decrypt_string(encrypted_text)