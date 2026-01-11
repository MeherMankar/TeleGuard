"""Redis Cache Manager for TeleGuard - Enhanced Caching Layer"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self):
        self.client: Optional[Redis] = None
        self.connected = False

    async def connect(self):
        """Connect to Redis"""
        if self.connected:
            return
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        # Skip Redis if URL is empty or disabled
        if not redis_url or redis_url.strip() == "":
            logger.info("Redis disabled (REDIS_URL not set)")
            return
        try:
            # Enhanced connection parameters
            self.client = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=int(os.getenv("REDIS_CONNECT_TIMEOUT", "10")),
                socket_timeout=int(os.getenv("REDIS_SOCKET_TIMEOUT", "10")),
                retry_on_timeout=os.getenv("REDIS_RETRY_ON_TIMEOUT", "true").lower()
                == "true",
                health_check_interval=int(
                    os.getenv("REDIS_HEALTH_CHECK_INTERVAL", "30")
                ),
                max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "10")),
                retry_on_error=[redis.ConnectionError, redis.TimeoutError],
            )
            # Test connection with timeout
            await asyncio.wait_for(self.client.ping(), timeout=15.0)
            self.connected = True
            logger.info("✅ Connected to Redis cache successfully")
        except asyncio.TimeoutError:
            logger.warning("Redis connection timed out, continuing without cache")
            self.connected = False
            self.client = None
        except Exception as e:
            logger.warning(f"Redis unavailable, continuing without cache: {e}")
            self.connected = False
            self.client = None

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            await self.client.close()
            self.connected = False

    # Rate Limiting Operations
    async def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        """Check and update rate limit using sliding window"""
        if not self.connected:
            return True  # Allow if Redis unavailable
        try:
            import time

            pipe = self.client.pipeline()
            now = int(time.time())
            pipe.zremrangebyscore(f"rate_limit:{key}", 0, now - window)
            # Count current requests
            pipe.zcard(f"rate_limit:{key}")
            pipe.zadd(f"rate_limit:{key}", {str(now): now})
            pipe.expire(f"rate_limit:{key}", window)
            results = await pipe.execute()
            current_count = results[1]
            return current_count < limit
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return True  # Allow on error

    async def get_rate_limit_remaining(self, key: str, limit: int, window: int) -> int:
        """Get remaining requests for rate limit"""
        if not self.connected:
            return limit
        try:
            import time

            now = int(time.time())
            # Clean expired and count
            pipe = self.client.pipeline()
            pipe.zremrangebyscore(f"rate_limit:{key}", 0, now - window)
            pipe.zcard(f"rate_limit:{key}")
            results = await pipe.execute()
            current_count = results[1]
            return max(0, limit - current_count)
        except Exception as e:
            logger.error(f"Rate limit remaining check failed: {e}")
            return limit

    # Session Token Operations
    async def store_session_token(self, user_id: int, token: str, ttl: int = 3600):
        """Store temporary session token"""
        if not self.connected:
            return
        try:
            await self.client.setex(f"session_token:{user_id}", ttl, token)
        except Exception as e:
            logger.error(f"Failed to store session token: {e}")

    async def get_session_token(self, user_id: int) -> Optional[str]:
        """Get session token"""
        if not self.connected:
            return None
        try:
            return await self.client.get(f"session_token:{user_id}")
        except Exception as e:
            logger.error(f"Failed to get session token: {e}")
            return None

    async def delete_session_token(self, user_id: int):
        """Delete session token"""
        if not self.connected:
            return
        try:
            await self.client.delete(f"session_token:{user_id}")
        except Exception as e:
            logger.error(f"Failed to delete session token: {e}")

    # OTP Operations
    async def store_otp_code(self, phone: str, code: str, ttl: int = 300):
        """Store OTP code temporarily"""
        if not self.connected:
            return
        try:
            await self.client.setex(f"otp:{phone}", ttl, code)
        except Exception as e:
            logger.error(f"Failed to store OTP: {e}")

    async def get_otp_code(self, phone: str) -> Optional[str]:
        """Get OTP code"""
        if not self.connected:
            return None
        try:
            return await self.client.get(f"otp:{phone}")
        except Exception as e:
            logger.error(f"Failed to get OTP: {e}")
            return None

    async def delete_otp_code(self, phone: str):
        """Delete OTP code"""
        if not self.connected:
            return
        try:
            await self.client.delete(f"otp:{phone}")
        except Exception as e:
            logger.error(f"Failed to delete OTP: {e}")

    # Temporary Data Operations
    async def set_temp_data(self, key: str, value: Any, ttl: int = 3600):
        """Store temporary data"""
        if not self.connected:
            return
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            await self.client.setex(key, ttl, value)
        except Exception as e:
            logger.error(f"Failed to set temp data: {e}")

    async def get_temp_data(self, key: str) -> Optional[Any]:
        """Get temporary data"""
        if not self.connected:
            return None
        try:
            value = await self.client.get(key)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            logger.error(f"Failed to get temp data: {e}")
            return None

    async def delete_temp_data(self, key: str):
        """Delete temporary data"""
        if not self.connected:
            return
        try:
            await self.client.delete(key)
        except Exception as e:
            logger.error(f"Failed to delete temp data: {e}")

    # Enhanced Cache Operations
    async def cache_set(self, key: str, value: Any, ttl: int = 3600):
        """Set cache value with metadata"""
        if not self.connected:
            return
        try:
            cache_data = {"value": value, "timestamp": int(time.time()), "ttl": ttl}
            await self.set_temp_data(key, cache_data, ttl)
        except Exception as e:
            logger.error(f"Cache set failed for {key}: {e}")

    async def cache_get(self, key: str) -> Optional[Any]:
        """Get cache value with hit tracking"""
        if not self.connected:
            return None
        try:
            cache_data = await self.get_temp_data(key)
            if cache_data and isinstance(cache_data, dict) and "value" in cache_data:
                await self._track_cache_hit(key)
                return cache_data["value"]
            return cache_data
        except Exception as e:
            logger.error(f"Cache get failed for {key}: {e}")
            return None

    async def cache_delete(self, key: str):
        """Delete cache value"""
        await self.delete_temp_data(key)

    async def _track_cache_hit(self, key: str):
        """Track cache hit for analytics"""
        try:
            hit_key = f"cache_hits:{key}"
            await self.client.incr(hit_key)
            await self.client.expire(hit_key, 86400)
        except Exception:
            pass

    # Frequently Accessed Data Caching
    async def cache_user_data(self, user_id: int, data: Dict, ttl: int = 1800):
        """Cache user data with 30min TTL"""
        key = f"user_data:{user_id}"
        await self.cache_set(key, data, ttl)

    async def get_cached_user_data(self, user_id: int) -> Optional[Dict]:
        """Get cached user data"""
        key = f"user_data:{user_id}"
        return await self.cache_get(key)

    async def cache_user_accounts(
        self, user_id: int, accounts: List[Dict], ttl: int = 900
    ):
        """Cache user accounts with 15min TTL"""
        key = f"user_accounts:{user_id}"
        await self.cache_set(key, accounts, ttl)

    async def get_cached_user_accounts(self, user_id: int) -> Optional[List[Dict]]:
        """Get cached user accounts"""
        key = f"user_accounts:{user_id}"
        return await self.cache_get(key)

    async def cache_account_data(self, account_id: str, data: Dict, ttl: int = 1200):
        """Cache account data with 20min TTL"""
        key = f"account_data:{account_id}"
        await self.cache_set(key, data, ttl)

    async def get_cached_account_data(self, account_id: str) -> Optional[Dict]:
        """Get cached account data"""
        key = f"account_data:{account_id}"
        return await self.cache_get(key)

    async def cache_user_settings(self, user_id: int, settings: Dict, ttl: int = 3600):
        """Cache user settings with 1hr TTL"""
        key = f"user_settings:{user_id}"
        await self.cache_set(key, settings, ttl)

    async def get_cached_user_settings(self, user_id: int) -> Optional[Dict]:
        """Get cached user settings"""
        key = f"user_settings:{user_id}"
        return await self.cache_get(key)

    async def invalidate_user_cache(self, user_id: int):
        """Invalidate all user-related cache"""
        patterns = [
            f"user_data:{user_id}",
            f"user_accounts:{user_id}",
            f"user_settings:{user_id}",
            f"session_token:{user_id}",
        ]
        for pattern in patterns:
            await self.cache_delete(pattern)

    async def invalidate_account_cache(self, account_id: str):
        """Invalidate account-related cache"""
        await self.cache_delete(f"account_data:{account_id}")

    # Bulk Cache Operations
    async def cache_multiple(
        self, cache_items: Dict[str, tuple], default_ttl: int = 3600
    ):
        """Cache multiple items at once"""
        if not self.connected:
            return
        try:
            pipe = self.client.pipeline()
            for key, (value, ttl) in cache_items.items():
                cache_data = {
                    "value": value,
                    "timestamp": int(time.time()),
                    "ttl": ttl or default_ttl,
                }
                serialized = json.dumps(cache_data)
                pipe.setex(key, ttl or default_ttl, serialized)
            await pipe.execute()
        except Exception as e:
            logger.error(f"Bulk cache operation failed: {e}")

    async def get_multiple(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple cache values at once"""
        if not self.connected:
            return {}
        try:
            pipe = self.client.pipeline()
            for key in keys:
                pipe.get(key)
            results = await pipe.execute()

            cache_results = {}
            for key, result in zip(keys, results):
                if result:
                    try:
                        cache_data = json.loads(result)
                        if isinstance(cache_data, dict) and "value" in cache_data:
                            cache_results[key] = cache_data["value"]
                            await self._track_cache_hit(key)
                        else:
                            cache_results[key] = cache_data
                    except json.JSONDecodeError:
                        cache_results[key] = result
            return cache_results
        except Exception as e:
            logger.error(f"Bulk cache get failed: {e}")
            return {}

    # Cache Analytics
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        if not self.connected:
            return {}
        try:
            info = await self.client.info("memory")
            stats = {
                "memory_used": info.get("used_memory_human", "N/A"),
                "memory_peak": info.get("used_memory_peak_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
            }

            hit_keys = await self.client.keys("cache_hits:*")
            if hit_keys:
                pipe = self.client.pipeline()
                for key in hit_keys[:10]:
                    pipe.get(key)
                hits = await pipe.execute()
                stats["top_cache_hits"] = dict(
                    zip([k.replace("cache_hits:", "") for k in hit_keys[:10]], hits)
                )

            return stats
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}

    # Utility Operations
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.connected:
            return False
        try:
            return bool(await self.client.exists(key))
        except Exception as e:
            logger.error(f"Failed to check key existence: {e}")
            return False

    async def expire(self, key: str, ttl: int):
        """Set expiry for key"""
        if not self.connected:
            return
        try:
            await self.client.expire(key, ttl)
        except Exception as e:
            logger.error(f"Failed to set expiry: {e}")

    async def ttl(self, key: str) -> int:
        """Get TTL for key"""
        if not self.connected:
            return -1
        try:
            return await self.client.ttl(key)
        except Exception as e:
            logger.error(f"Failed to get TTL: {e}")
            return -1

    async def flush_all(self):
        """Flush all cache data (use with caution)"""
        if not self.connected:
            return
        try:
            await self.client.flushdb()
            logger.warning("Redis cache flushed")
        except Exception as e:
            logger.error(f"Failed to flush cache: {e}")


# Global Redis cache instance
redis_cache = RedisCache()


async def init_redis():
    """Initialize Redis connection"""
    if not redis_cache.connected:
        await redis_cache.connect()


async def get_redis() -> RedisCache:
    """Get Redis cache instance"""
    return redis_cache
