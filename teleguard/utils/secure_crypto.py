"""
Secure Cryptography Utilities for TeleGuard
Replaces weak encryption with secure algorithms
"""

import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import bytes, str, Optional

class SecureCrypto:
    """Secure encryption/decryption using AEAD ciphers"""
    
    def __init__(self, key: Optional[bytes] = None):
        """Initialize with AES-GCM cipher"""
        if key is None:
            key = AESGCM.generate_key(bit_length=256)
        elif isinstance(key, str):
            key = base64.b64decode(key.encode())
        
        self.cipher = AESGCM(key)
        self.key = key
    
    def get_key_b64(self) -> str:
        """Get base64 encoded key for storage"""
        return base64.b64encode(self.key).decode()
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext with AES-GCM"""
        if not isinstance(plaintext, str):
            plaintext = str(plaintext)
        
        data = plaintext.encode('utf-8')
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        
        ciphertext = self.cipher.encrypt(nonce, data, None)
        
        # Combine nonce + ciphertext and encode
        encrypted_data = nonce + ciphertext
        return base64.b64encode(encrypted_data).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt ciphertext with AES-GCM"""
        try:
            data = base64.b64decode(encrypted_data.encode())
            
            # Extract nonce and ciphertext
            nonce = data[:12]
            ciphertext = data[12:]
            
            plaintext = self.cipher.decrypt(nonce, ciphertext, None)
            return plaintext.decode('utf-8')
            
        except Exception:
            raise ValueError("Decryption failed - invalid or corrupted data")

class SecureKeyDerivation:
    """Secure key derivation from passwords"""
    
    @staticmethod
    def derive_key(password: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
        """Derive encryption key from password using PBKDF2"""
        if salt is None:
            salt = os.urandom(32)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,  # OWASP recommended minimum
        )
        
        key = kdf.derive(password.encode('utf-8'))
        return key, salt
    
    @staticmethod
    def verify_key(password: str, salt: bytes, expected_key: bytes) -> bool:
        """Verify password against derived key"""
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            kdf.verify(password.encode('utf-8'), expected_key)
            return True
        except Exception:
            return False

# Legacy compatibility wrapper
class DataEncryption:
    """Wrapper for backward compatibility"""
    
    def __init__(self, key: Optional[str] = None):
        self.crypto = SecureCrypto(key.encode() if key else None)
    
    def encrypt_data(self, data: any) -> str:
        """Encrypt data (backward compatible)"""
        import json
        json_data = json.dumps(data, default=str)
        return self.crypto.encrypt(json_data)
    
    def decrypt_data(self, encrypted_data: str) -> any:
        """Decrypt data (backward compatible)"""
        import json
        json_data = self.crypto.decrypt(encrypted_data)
        return json.loads(json_data)