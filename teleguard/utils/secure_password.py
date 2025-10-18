"""Unified secure password hashing utilities using Argon2"""
import argon2
from argon2 import PasswordHasher
from argon2.exceptions import HashingError, VerifyMismatchError
import hashlib
import logging
logger = logging.getLogger(__name__)

class SecurePasswordManager:
    """Secure password hashing and verification with migration support"""
    def __init__(self):
        self.ph = PasswordHasher(
            time_cost=3,
            memory_cost=65536,
            parallelism=1,
            hash_len=32,
            salt_len=16
        )

    def hash_password(self, password: str) -> str:
        """Hash password using Argon2"""
        try:
            return self.ph.hash(password)
        except (HashingError, Exception) as e:
            logger.error(f"Password hashing failed: {e}")
            raise

    def verify_password(self, hashed_password: str, password: str) -> bool:
        """Verify password against hash with migration support"""
        try:
            self.ph.verify(hashed_password, password)
            return True
        except VerifyMismatchError:
            return False
        except (argon2.exceptions.InvalidHash, ValueError):
            # Fallback to SHA-256 for existing hashes (migration period)
            try:
                sha256_hash = hashlib.sha256(password.encode()).hexdigest()
                return sha256_hash == hashed_password
            except Exception as e:
                logger.error(f"Error verifying password: {e}")
                return False
        except Exception as e:
            logger.error(f"Password verification failed: {e}")
            return False

    def needs_rehash(self, hashed_password: str) -> bool:
        """Check if password hash needs to be updated to Argon2"""
        try:
            return self.ph.check_needs_rehash(hashed_password)
        except (argon2.exceptions.InvalidHash, ValueError):
            return True
        except Exception:
            return True

# Alias for backward compatibility
SecurePasswordHasher = SecurePasswordManager
password_hasher = SecurePasswordManager()
password_manager = password_hasher
