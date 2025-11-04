"""
API Security Utilities
Professional API security implementation with secure key validation,
rate limiting, and comprehensive audit logging.
Authors: @Meher_Mankar, @Gutkesh
Repository: https://github.com/mehermankar/teleguard
"""
import hashlib
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from ..core.mongo_database import mongodb
logger = logging.getLogger(__name__)
class APISecurityError(Exception):
    """Custom exception for API security operations"""
    pass
class APIKeyManager:
    """
    Professional API key management system.
    Handles API key generation, validation, and security features
    including rate limiting and audit logging.
    """
    # Security constants
    KEY_LENGTH = 32
    HASH_ALGORITHM = 'sha256'
    RATE_LIMIT_WINDOW = 3600  # 1 hour
    MAX_REQUESTS_PER_HOUR = 1000
    @classmethod
    def generate_api_key(cls, user_id: int) -> str:
        """
        Generate a secure API key for a user.
        Args:
            user_id: User's Telegram ID
        Returns:
            Generated API key in format: user_id:hash
        """
        import secrets
        # Generate secure random token
        token = secrets.token_urlsafe(cls.KEY_LENGTH)
        timestamp = str(int(time.time()))
        hash_input = f"{user_id}:{token}:{timestamp}".encode()
        key_hash = hashlib.new(cls.HASH_ALGORITHM, hash_input).hexdigest()
        return f"{user_id}:{key_hash}"
    @classmethod
    def parse_api_key(cls, api_key: str) -> Optional[tuple]:
        """
        Parse API key and extract components.
        Args:
            api_key: API key string
        Returns:
            Tuple of (user_id, key_hash) or None if invalid
        """
        try:
            parts = api_key.split(":", 1)
            if len(parts) != 2:
                return None
            user_id_str, key_hash = parts
            user_id = int(user_id_str)
            if len(key_hash) != 64:  # SHA256 hex length
                return None
            return user_id, key_hash
        except (ValueError, TypeError):
            return None
class RateLimiter:
    """
    API rate limiting implementation.
    Tracks API usage per user and enforces rate limits
    to prevent abuse and ensure fair usage.
    """
    def __init__(self):
        self._usage_cache: Dict[int, Dict[str, Any]] = {}
    async def check_rate_limit(self, user_id: int) -> tuple:
        """
        Check if user has exceeded rate limit.
        Args:
            user_id: User's Telegram ID
        Returns:
            Tuple of (allowed: bool, remaining: int, reset_time: int)
        """
        current_time = int(time.time())
        window_start = current_time - APIKeyManager.RATE_LIMIT_WINDOW
        if user_id not in self._usage_cache:
            self._usage_cache[user_id] = {
                'requests': [],
                'last_cleanup': current_time
            }
        user_data = self._usage_cache[user_id]
        # Clean old requests
        user_data['requests'] = [
            req_time for req_time in user_data['requests'] 
            if req_time > window_start
        ]
        current_requests = len(user_data['requests'])
        allowed = current_requests < APIKeyManager.MAX_REQUESTS_PER_HOUR
        if allowed:
            user_data['requests'].append(current_time)
        remaining = max(0, APIKeyManager.MAX_REQUESTS_PER_HOUR - current_requests)
        reset_time = current_time + APIKeyManager.RATE_LIMIT_WINDOW
        return allowed, remaining, reset_time
    def cleanup_old_data(self) -> None:
        """Clean up old rate limiting data"""
        current_time = int(time.time())
        cutoff_time = current_time - (APIKeyManager.RATE_LIMIT_WINDOW * 2)
        for user_id in list(self._usage_cache.keys()):
            user_data = self._usage_cache[user_id]
            user_data['requests'] = [
                req_time for req_time in user_data['requests'] 
                if req_time > cutoff_time
            ]
            if not user_data['requests'] and user_data['last_cleanup'] < cutoff_time:
                del self._usage_cache[user_id]
# Global instances
rate_limiter = RateLimiter()
async def validate_api_key(api_key: str) -> Optional[int]:
    """
    Validate API key and return user_id if valid.
    Args:
        api_key: API key string to validate
    Returns:
        User ID if valid, None otherwise
    """
    try:
        # Parse API key
        parsed = APIKeyManager.parse_api_key(api_key)
        if not parsed:
            logger.warning(f"Invalid API key format: {api_key[:10]}...")
            return None
        user_id, key_hash = parsed
        allowed, remaining, reset_time = await rate_limiter.check_rate_limit(user_id)
        if not allowed:
            logger.warning(f"Rate limit exceeded for user {user_id}")
            await _log_security_event(user_id, "rate_limit_exceeded", {
                'remaining': remaining,
                'reset_time': reset_time
            })
            return None
        account = await mongodb.db.accounts.find_one({
            "user_id": user_id,
            "api_access_enabled": True,
            "api_key_hash": key_hash
        })
        if account:
            await _log_security_event(user_id, "api_access_granted", {
                'account_id': str(account['_id']),
                'remaining_requests': remaining
            })
            return user_id
        else:
            logger.warning(f"Invalid API key for user {user_id}")
            await _log_security_event(user_id, "invalid_api_key", {
                'key_hash': key_hash[:16] + "..."  # Log partial hash for debugging
            })
            return None
    except Exception as e:
        logger.error(f"API key validation error: {e}")
        return None
async def generate_user_api_key(user_id: int, account_id: str) -> Optional[str]:
    """
    Generate and store API key for user account.
    Args:
        user_id: User's Telegram ID
        account_id: Account ID to enable API access for
    Returns:
        Generated API key or None if failed
    """
    try:
        # Generate new API key
        api_key = APIKeyManager.generate_api_key(user_id)
        _, key_hash = APIKeyManager.parse_api_key(api_key)
        # Store in database
        result = await mongodb.db.accounts.update_one(
            {"_id": account_id, "user_id": user_id},
            {
                "$set": {
                    "api_access_enabled": True,
                    "api_key_hash": key_hash,
                    "api_key_created": datetime.utcnow()
                }
            }
        )
        if result.modified_count > 0:
            await _log_security_event(user_id, "api_key_generated", {
                'account_id': account_id
            })
            logger.info(f"API key generated for user {user_id}, account {account_id}")
            return api_key
        else:
            logger.error(f"Failed to store API key for user {user_id}")
            return None
    except Exception as e:
        logger.error(f"API key generation error for user {user_id}: {e}")
        return None
async def revoke_user_api_key(user_id: int, account_id: str) -> bool:
    """
    Revoke API key for user account.
    Args:
        user_id: User's Telegram ID
        account_id: Account ID to revoke API access for
    Returns:
        True if successful, False otherwise
    """
    try:
        result = await mongodb.db.accounts.update_one(
            {"_id": account_id, "user_id": user_id},
            {
                "$set": {
                    "api_access_enabled": False,
                    "api_key_revoked": datetime.utcnow()
                },
                "$unset": {
                    "api_key_hash": ""
                }
            }
        )
        if result.modified_count > 0:
            await _log_security_event(user_id, "api_key_revoked", {
                'account_id': account_id
            })
            logger.info(f"API key revoked for user {user_id}, account {account_id}")
            return True
        else:
            logger.warning(f"No API key found to revoke for user {user_id}")
            return False
    except Exception as e:
        logger.error(f"API key revocation error for user {user_id}: {e}")
        return False
async def get_api_usage_stats(user_id: int) -> Dict[str, Any]:
    """
    Get API usage statistics for user.
    Args:
        user_id: User's Telegram ID
    Returns:
        Dictionary containing usage statistics
    """
    try:
        allowed, remaining, reset_time = await rate_limiter.check_rate_limit(user_id)
        account = await mongodb.db.accounts.find_one({
            "user_id": user_id,
            "api_access_enabled": True
        })
        if not account:
            return {
                'api_enabled': False,
                'error': 'No API access enabled'
            }
        return {
            'api_enabled': True,
            'account_id': str(account['_id']),
            'key_created': account.get('api_key_created'),
            'requests_remaining': remaining,
            'rate_limit_reset': reset_time,
            'max_requests_per_hour': APIKeyManager.MAX_REQUESTS_PER_HOUR
        }
    except Exception as e:
        logger.error(f"Error getting API usage stats for user {user_id}: {e}")
        return {
            'api_enabled': False,
            'error': f'Failed to get usage stats: {str(e)}'
        }
async def _log_security_event(user_id: int, event_type: str, details: Dict[str, Any]) -> None:
    """
    Log security event to audit trail.
    Args:
        user_id: User's Telegram ID
        event_type: Type of security event
        details: Additional event details
    """
    try:
        await mongodb.db.security_audit.insert_one({
            'user_id': user_id,
            'event_type': event_type,
            'details': details,
            'timestamp': datetime.utcnow(),
            'source': 'api_security'
        })
    except Exception as e:
        logger.error(f"Failed to log security event: {e}")
# Periodic cleanup task
async def cleanup_rate_limit_data() -> None:
    """Clean up old rate limiting data periodically"""
    try:
        rate_limiter.cleanup_old_data()
        logger.debug("Rate limit data cleanup completed")
    except Exception as e:
        logger.error(f"Rate limit cleanup error: {e}")
