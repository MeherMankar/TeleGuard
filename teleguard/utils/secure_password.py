"""Secure password hashing utilities"""

import argon2
from argon2 import PasswordHasher
import hashlib
import logging

logger = logging.getLogger(__name__)

class SecurePasswordManager:
    """Secure password hashing and verification"""
    
    def __init__(self):
        self.ph = PasswordHasher(
            time_cost=3,      # Number of iterations
            memory_cost=65536, # Memory usage in KiB
            parallelism=1,    # Number of parallel threads
            hash_len=32,      # Hash length
            salt_len=16       # Salt length
        )
    
    def hash_password(self, password: str) -> str:
        """Hash password using Argon2"""
        try:
            return self.ph.hash(password)
        except Exception as e:
            logger.error(f"Error hashing password: {e}")
            raise
    
    def verify_password(self, hashed_password: str, password: str) -> bool:
        """Verify password against hash with migration support"""
        try:
            # Try Argon2 verification first (new format)
            self.ph.verify(hashed_password, password)
            return True
        except (argon2.exceptions.VerifyMismatchError, argon2.exceptions.InvalidHash):
            # Fallback to SHA-256 for existing hashes (migration period)
            try:
                sha256_hash = hashlib.sha256(password.encode()).hexdigest()
                return sha256_hash == hashed_password
            except Exception as e:
                logger.error(f"Error verifying password: {e}")
                return False
        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False
    
    def needs_rehash(self, hashed_password: str) -> bool:
        """Check if password hash needs to be updated to Argon2"""
        try:
            # If it's not a valid Argon2 hash, it needs rehashing
            self.ph.check_needs_rehash(hashed_password)
            return False
        except (argon2.exceptions.InvalidHash, ValueError):
            # Not an Argon2 hash, needs rehashing
            return True
        except Exception:
            return True

# Global instance
password_manager = SecurePasswordManager()