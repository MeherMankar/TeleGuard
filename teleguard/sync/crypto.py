"""AES-GCM encryption for public snapshots"""

import os
import base64
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

def _get_key_bytes():
    """Get encryption key bytes"""
    if not ENCRYPTION_KEY:
        raise RuntimeError("ENCRYPTION_KEY not set")
    return base64.b64decode(ENCRYPTION_KEY)

def encrypt_bytes(plaintext: bytes) -> bytes:
    """Encrypt bytes using AES-GCM"""
    key = _get_key_bytes()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 12 bytes for GCM
    ct = aesgcm.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ct)

def decrypt_bytes(encrypted_data: bytes) -> bytes:
    """Decrypt bytes using AES-GCM"""
    key = _get_key_bytes()
    data = base64.b64decode(encrypted_data)
    nonce, ct = data[:12], data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None)