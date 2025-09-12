"""Secure password hashing utilities using Argon2"""

import logging

from argon2 import PasswordHasher
from argon2.exceptions import HashingError, VerifyMismatchError

logger = logging.getLogger(__name__)


class SecurePasswordHasher:
    """Secure password hashing using Argon2"""

    def __init__(self):
        self.ph = PasswordHasher(
            time_cost=3,  # Number of iterations
            memory_cost=65536,  # Memory usage in KiB (64 MB)
            parallelism=1,  # Number of parallel threads
            hash_len=32,  # Hash length
            salt_len=16,  # Salt length
        )

    def hash_password(self, password: str) -> str:
        """Hash password using Argon2"""
        try:
            return self.ph.hash(password)
        except HashingError as e:
            logger.error(f"Password hashing failed: {e}")
            raise

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        try:
            self.ph.verify(hashed, password)
            return True
        except VerifyMismatchError:
            return False
        except Exception as e:
            logger.error(f"Password verification failed: {e}")
            return False

    def needs_rehash(self, hashed: str) -> bool:
        """Check if password needs rehashing"""
        try:
            return self.ph.check_needs_rehash(hashed)
        except Exception:
            return True


# Global instance
password_hasher = SecurePasswordHasher()
