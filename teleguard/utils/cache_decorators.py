"""Cache Decorators for TeleGuard - Simplified Caching"""

import functools
import hashlib
import json
import logging
from typing import Any, Callable, Optional

from ..core.database_manager import db_manager

logger = logging.getLogger(__name__)


def cache_result(ttl: int = 3600, key_prefix: str = "", use_args: bool = True):
    """
    Decorator to cache function results in Redis

    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
        use_args: Whether to include function arguments in cache key
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if use_args:
                key_data = {"func": func.__name__, "args": args, "kwargs": kwargs}
                key_hash = hashlib.md5(
                    json.dumps(key_data, sort_keys=True, default=str).encode()
                ).hexdigest()
                cache_key = (
                    f"{key_prefix}:{func.__name__}:{key_hash}"
                    if key_prefix
                    else f"{func.__name__}:{key_hash}"
                )
            else:
                cache_key = (
                    f"{key_prefix}:{func.__name__}" if key_prefix else func.__name__
                )

            # Try to get from cache
            try:
                cached_result = await db_manager.cache_get(cache_key)
                if cached_result is not None:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cached_result
            except Exception as e:
                logger.warning(f"Cache get failed for {func.__name__}: {e}")

            # Execute function and cache result
            try:
                result = await func(*args, **kwargs)
                if result is not None:
                    await db_manager.cache_set(cache_key, result, ttl)
                    logger.debug(f"Cached result for {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Function execution failed for {func.__name__}: {e}")
                raise

        return wrapper

    return decorator


def cache_user_data(ttl: int = 1800):
    """Cache decorator specifically for user data (30min default TTL)"""
    return cache_result(ttl=ttl, key_prefix="user_data", use_args=True)


def cache_account_data(ttl: int = 1200):
    """Cache decorator specifically for account data (20min default TTL)"""
    return cache_result(ttl=ttl, key_prefix="account_data", use_args=True)


def cache_settings(ttl: int = 3600):
    """Cache decorator specifically for settings (1hr default TTL)"""
    return cache_result(ttl=ttl, key_prefix="settings", use_args=True)


def invalidate_cache(key_pattern: str):
    """
    Decorator to invalidate cache after function execution

    Args:
        key_pattern: Pattern to match cache keys for invalidation
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            # Invalidate cache based on pattern
            try:
                if "user_id" in key_pattern and len(args) > 0:
                    user_id = (
                        args[0] if isinstance(args[0], int) else kwargs.get("user_id")
                    )
                    if user_id:
                        await db_manager.redis.invalidate_user_cache(user_id)

                if "account_id" in key_pattern and len(args) > 0:
                    account_id = (
                        args[0]
                        if isinstance(args[0], str)
                        else kwargs.get("account_id")
                    )
                    if account_id:
                        await db_manager.redis.invalidate_account_cache(account_id)

                logger.debug(f"Cache invalidated for pattern: {key_pattern}")
            except Exception as e:
                logger.warning(f"Cache invalidation failed: {e}")

            return result

        return wrapper

    return decorator


class CacheManager:
    """Utility class for advanced cache operations"""

    @staticmethod
    async def warm_user_cache(user_id: int):
        """Pre-load user data into cache"""
        try:
            # Load user data
            user = await db_manager.mongo.get_user(user_id)
            if user:
                await db_manager.redis.cache_user_data(user_id, user)

            # Load user accounts
            accounts = await db_manager.mongo.get_user_accounts(user_id)
            if accounts:
                await db_manager.redis.cache_user_accounts(user_id, accounts)

            # Load user settings
            settings = await db_manager.mongo.get_user_settings(user_id)
            if settings:
                await db_manager.redis.cache_user_settings(user_id, settings)

            logger.info(f"Cache warmed for user {user_id}")
        except Exception as e:
            logger.error(f"Cache warming failed for user {user_id}: {e}")

    @staticmethod
    async def bulk_cache_accounts(account_ids: list):
        """Cache multiple accounts at once"""
        try:
            cache_items = {}
            for account_id in account_ids:
                account = await db_manager.mongo.get_account(account_id)
                if account:
                    cache_items[f"account_data:{account_id}"] = (
                        account,
                        1200,
                    )  # 20min TTL

            if cache_items:
                await db_manager.cache_multiple_items(cache_items)
                logger.info(f"Bulk cached {len(cache_items)} accounts")
        except Exception as e:
            logger.error(f"Bulk cache operation failed: {e}")

    @staticmethod
    async def get_cache_performance() -> dict:
        """Get cache performance metrics"""
        try:
            stats = await db_manager.get_cache_stats()
            return {
                "status": "healthy" if db_manager.redis.connected else "disconnected",
                "stats": stats,
                "recommendations": CacheManager._get_cache_recommendations(stats),
            }
        except Exception as e:
            logger.error(f"Failed to get cache performance: {e}")
            return {"status": "error", "error": str(e)}

    @staticmethod
    def _get_cache_recommendations(stats: dict) -> list:
        """Generate cache optimization recommendations"""
        recommendations = []

        if stats.get("memory_used", "0B").endswith("MB"):
            memory_mb = float(stats["memory_used"].replace("MB", ""))
            if memory_mb > 100:
                recommendations.append("Consider reducing cache TTL values")

        if stats.get("top_cache_hits"):
            hit_counts = list(stats["top_cache_hits"].values())
            if hit_counts and max(hit_counts) < 10:
                recommendations.append("Low cache hit rates - consider warming cache")

        return recommendations


# Convenience functions for common cache operations
async def cache_telegram_data(user_id: int, data_type: str, data: Any, ttl: int = 1800):
    """Cache Telegram-specific data"""
    key = f"telegram:{data_type}:{user_id}"
    await db_manager.cache_set(key, data, ttl)


async def get_cached_telegram_data(user_id: int, data_type: str) -> Optional[Any]:
    """Get cached Telegram-specific data"""
    key = f"telegram:{data_type}:{user_id}"
    return await db_manager.cache_get(key)


async def cache_api_response(
    endpoint: str, params: dict, response: Any, ttl: int = 300
):
    """Cache API response data"""
    key_hash = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()
    key = f"api:{endpoint}:{key_hash}"
    await db_manager.cache_set(key, response, ttl)


async def get_cached_api_response(endpoint: str, params: dict) -> Optional[Any]:
    """Get cached API response"""
    key_hash = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()
    key = f"api:{endpoint}:{key_hash}"
    return await db_manager.cache_get(key)
