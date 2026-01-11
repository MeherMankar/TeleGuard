"""Unified Database Manager - Coordinates Redis Cache and MongoDB Storage"""

import logging
from typing import Any, Dict, List, Optional

from ..utils.rate_limiter import rate_limiter
from .mongo_database import mongodb
from .redis_cache import init_redis, redis_cache

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Unified database manager coordinating Redis and MongoDB"""

    def __init__(self):
        self.redis = redis_cache
        self.mongo = mongodb
        self.rate_limiter = rate_limiter
        self.initialized = False

    async def initialize(self):
        """Initialize both Redis and MongoDB connections"""
        if self.initialized:
            return
        try:
            await init_redis()
        except Exception:
            pass
        try:
            from .mongo_database import init_db as mongo_init_db

            await mongo_init_db()
        except Exception as e:
            logger.error(f"MongoDB initialization failed: {e}")
            raise
        self.initialized = True

    async def shutdown(self):
        """Shutdown database connections"""
        if self.redis.connected:
            await self.redis.disconnect()
        if self.mongo.client:
            await self.mongo.disconnect()

    # Rate Limiting (Redis)
    async def check_rate_limit(
        self, user_id: int, endpoint: str = "default", limit: int = 30, window: int = 60
    ) -> bool:
        """Check rate limit using Redis cache"""
        return await self.rate_limiter.check_rate_limit(
            user_id, endpoint, limit, window
        )

    async def get_rate_limit_remaining(
        self, user_id: int, endpoint: str = "default", limit: int = 30, window: int = 60
    ) -> int:
        """Get remaining rate limit requests"""
        return await self.rate_limiter.get_remaining_requests(
            user_id, endpoint, limit, window
        )

    # Session Tokens (Redis - Ephemeral)
    async def store_session_token(self, user_id: int, token: str, ttl: int = 3600):
        """Store temporary session token in Redis"""
        await self.redis.store_session_token(user_id, token, ttl)

    async def get_session_token(self, user_id: int) -> Optional[str]:
        """Get session token from Redis"""
        return await self.redis.get_session_token(user_id)

    async def delete_session_token(self, user_id: int):
        """Delete session token from Redis"""
        await self.redis.delete_session_token(user_id)

    # OTP Codes (Redis - Ephemeral)
    async def store_otp_code(self, phone: str, code: str, ttl: int = 300):
        """Store OTP code temporarily in Redis"""
        await self.redis.store_otp_code(phone, code, ttl)

    async def get_otp_code(self, phone: str) -> Optional[str]:
        """Get OTP code from Redis"""
        return await self.redis.get_otp_code(phone)

    async def delete_otp_code(self, phone: str):
        """Delete OTP code from Redis"""
        await self.redis.delete_otp_code(phone)

    # Enhanced Cache Operations (Redis)
    async def cache_set(self, key: str, value: Any, ttl: int = 3600):
        """Set cache value in Redis with metadata"""
        await self.redis.cache_set(key, value, ttl)

    async def cache_get(self, key: str) -> Optional[Any]:
        """Get cache value from Redis with hit tracking"""
        return await self.redis.cache_get(key)

    async def cache_delete(self, key: str):
        """Delete cache value from Redis"""
        await self.redis.cache_delete(key)

    async def cache_exists(self, key: str) -> bool:
        """Check if cache key exists"""
        return await self.redis.exists(key)

    async def cache_ttl(self, key: str) -> int:
        """Get TTL for cache key"""
        return await self.redis.ttl(key)

    # User Management (MongoDB + Redis Cache)
    async def create_user(self, telegram_id: int, **kwargs):
        """Create user in MongoDB and invalidate cache"""
        await self.mongo.create_user(telegram_id, **kwargs)
        await self.redis.invalidate_user_cache(telegram_id)

        # Trigger auto backup
        try:
            from ..utils.backups import backup_user_change

            user_data = {"telegram_id": telegram_id, **kwargs}
            backup_user_change("user_created", telegram_id, user_data)
        except Exception as e:
            logger.warning(f"Auto backup failed: {e}")

    async def get_user(self, telegram_id: int):
        """Get user from cache or MongoDB"""
        cached_user = await self.redis.get_cached_user_data(telegram_id)
        if cached_user:
            return cached_user

        user = await self.mongo.get_user(telegram_id)
        if user:
            await self.redis.cache_user_data(telegram_id, user)
        return user

    async def update_user(self, telegram_id: int, **kwargs):
        """Update user in MongoDB and invalidate cache"""
        await self.mongo.create_user(telegram_id, **kwargs)
        await self.redis.invalidate_user_cache(telegram_id)

        # Trigger auto backup
        try:
            from ..utils.backups import backup_user_change

            user_data = {"telegram_id": telegram_id, **kwargs}
            backup_user_change("user_updated", telegram_id, user_data)
        except Exception as e:
            logger.warning(f"Auto backup failed: {e}")

    # Account Management (MongoDB + Redis Cache)
    async def create_account(self, user_id: int, phone: str, **kwargs):
        """Create account in MongoDB and invalidate cache"""
        result = await self.mongo.create_account(user_id, phone, **kwargs)
        await self.redis.invalidate_user_cache(user_id)

        # Trigger auto backup
        try:
            from ..utils.backups import backup_account_change

            account_data = {"phone": phone, "user_id": user_id, **kwargs}
            backup_account_change("account_added", user_id, account_data)
        except Exception as e:
            logger.warning(f"Auto backup failed: {e}")

        return result

    async def get_user_accounts(self, user_id: int):
        """Get user accounts from cache or MongoDB"""
        cached_accounts = await self.redis.get_cached_user_accounts(user_id)
        if cached_accounts:
            return cached_accounts

        accounts = await self.mongo.get_user_accounts(user_id)
        if accounts:
            await self.redis.cache_user_accounts(user_id, accounts)
        return accounts

    async def get_account(self, account_id: str):
        """Get account from cache or MongoDB"""
        cached_account = await self.redis.get_cached_account_data(account_id)
        if cached_account:
            return cached_account

        account = await self.mongo.get_account(account_id)
        if account:
            await self.redis.cache_account_data(account_id, account)
        return account

    async def update_account(self, account_id: str, **kwargs):
        """Update account in MongoDB and invalidate cache"""
        await self.mongo.update_account(account_id, **kwargs)
        await self.redis.invalidate_account_cache(account_id)
        # Also invalidate user cache if user_id is available
        account = await self.mongo.get_account(account_id)
        if account and "user_id" in account:
            await self.redis.invalidate_user_cache(account["user_id"])

    async def delete_account(self, account_id: str):
        """Delete account from MongoDB and invalidate cache"""
        account = await self.mongo.get_account(account_id)

        # Remove stored 2FA password for security
        if account and "user_id" in account:
            try:
                await self.remove_2fa_password(account["user_id"], account_id)
                logger.info(f"Removed stored 2FA password for account {account_id}")
            except Exception as e:
                logger.warning(
                    f"Failed to remove 2FA password for account {account_id}: {e}"
                )

        await self.mongo.delete_account(account_id)
        await self.redis.invalidate_account_cache(account_id)

        if account and "user_id" in account:
            await self.redis.invalidate_user_cache(account["user_id"])

            # Trigger auto backup
            try:
                from ..utils.backups import backup_account_change

                backup_account_change("account_removed", account["user_id"], account)
            except Exception as e:
                logger.warning(f"Auto backup failed: {e}")

    async def get_account_by_phone(self, user_id: int, phone: str):
        """Get account by phone from MongoDB"""
        return await self.mongo.get_account_by_phone(user_id, phone)

    async def get_active_accounts(self, user_id: int):
        """Get active accounts from MongoDB"""
        return await self.mongo.get_active_accounts(user_id)

    # Session Storage (MongoDB - Durable)
    async def store_session(self, user_id: int, account_id: str, session_data: dict):
        """Store session data in MongoDB"""
        await self.mongo.store_session(user_id, account_id, session_data)

    async def get_session(self, user_id: int, account_id: str) -> Optional[dict]:
        """Get session data from MongoDB"""
        return await self.mongo.get_session(user_id, account_id)

    async def delete_session(self, user_id: int, account_id: str):
        """Delete session data from MongoDB"""
        await self.mongo.delete_session(user_id, account_id)

    async def get_user_sessions(self, user_id: int) -> List[dict]:
        """Get all user sessions from MongoDB"""
        return await self.mongo.get_user_sessions(user_id)

    # User Settings (MongoDB + Redis Cache)
    async def store_user_settings(self, user_id: int, settings: dict):
        """Store user settings in MongoDB and cache"""
        await self.mongo.store_user_settings(user_id, settings)
        await self.redis.cache_user_settings(user_id, settings)

    async def get_user_settings(self, user_id: int) -> Optional[dict]:
        """Get user settings from cache or MongoDB"""
        cached_settings = await self.redis.get_cached_user_settings(user_id)
        if cached_settings:
            return cached_settings

        settings = await self.mongo.get_user_settings(user_id)
        if settings:
            await self.redis.cache_user_settings(user_id, settings)
        return settings

    async def delete_user_settings(self, user_id: int):
        """Delete user settings from MongoDB and cache"""
        await self.mongo.delete_user_settings(user_id)
        await self.redis.invalidate_user_cache(user_id)

    # 2FA Management (MongoDB - Durable)
    async def store_2fa_password(self, user_id: int, account_id: str, password: str):
        """Store 2FA password for account"""
        await self.mongo.store_2fa_password(user_id, account_id, password)

    async def get_2fa_password(self, user_id: int, account_id: str) -> Optional[str]:
        """Get 2FA password for account"""
        return await self.mongo.get_2fa_password(user_id, account_id)

    async def get_2fa_password_by_phone(
        self, user_id: int, phone: str
    ) -> Optional[str]:
        """Get 2FA password by phone number"""
        return await self.mongo.get_2fa_password_by_phone(user_id, phone)

    async def remove_2fa_password(self, user_id: int, account_id: str):
        """Remove 2FA password from account"""
        await self.mongo.remove_2fa_password(user_id, account_id)

    # Audit Logging (MongoDB - Durable)
    async def add_audit_log(self, user_id: int, action: str, details: dict = None):
        """Add audit log entry to MongoDB"""
        await self.mongo.add_audit_log(user_id, action, details)

    async def get_audit_logs(self, user_id: int, limit: int = 100) -> List[dict]:
        """Get audit logs from MongoDB"""
        return await self.mongo.get_audit_logs(user_id, limit)

    # Backup and Recovery (MongoDB - Durable)
    async def create_backup_snapshot(self, user_id: int) -> dict:
        """Create backup snapshot"""
        return await self.mongo.create_backup_snapshot(user_id)

    async def restore_from_snapshot(self, user_id: int, snapshot: dict):
        """Restore from backup snapshot"""
        await self.mongo.restore_from_snapshot(user_id, snapshot)

    # Maintenance
    async def cleanup_old_data(self):
        """Cleanup old data from both databases"""
        await self.mongo.cleanup_old_audit_logs()
        # Redis data expires automatically

    # Enhanced Cache Methods
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get Redis cache performance statistics"""
        return await self.redis.get_cache_stats()

    async def cache_multiple_items(
        self, items: Dict[str, tuple], default_ttl: int = 3600
    ):
        """Cache multiple items at once for better performance"""
        await self.redis.cache_multiple(items, default_ttl)

    async def get_multiple_cached_items(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple cached items at once"""
        return await self.redis.get_multiple(keys)

    # Health Check
    async def health_check(self) -> Dict[str, Any]:
        """Check health of both databases with cache stats"""
        health = {
            "redis": self.redis.connected,
            "mongodb": self.mongo.client is not None,
            "initialized": self.initialized,
        }

        if self.mongo.client:
            try:
                await self.mongo.client.admin.command("ping")
                health["mongodb_ping"] = True
            except Exception:
                health["mongodb_ping"] = False

        if self.redis.connected:
            try:
                await self.redis.client.ping()
                health["redis_ping"] = True
                health["cache_stats"] = await self.get_cache_stats()
            except Exception:
                health["redis_ping"] = False

        return health


# Global database manager instance
db_manager = DatabaseManager()


async def init_database_manager():
    """Initialize the unified database manager"""
    if not db_manager.initialized:
        await db_manager.initialize()


async def get_db_manager() -> DatabaseManager:
    """Get the database manager instance"""
    return db_manager
