"""
Account Cache - Reduce redundant database queries
Caches frequently accessed account data with TTL
"""

import asyncio
import logging
import time
from typing import Dict, Optional

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class AccountCache:
    """Cache for account data to reduce database queries"""
    
    def __init__(self, ttl: int = 300):
        """
        Initialize account cache
        
        Args:
            ttl: Time to live in seconds (default: 5 minutes)
        """
        self.ttl = ttl
        self._cache: Dict[str, Dict] = {}
        self._timestamps: Dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    def _make_key(self, user_id: int, account_name: str) -> str:
        """Generate cache key"""
        return f"{user_id}:{account_name}"
    
    def _is_expired(self, key: str) -> bool:
        """Check if cache entry is expired"""
        if key not in self._timestamps:
            return True
        return time.time() - self._timestamps[key] > self.ttl
    
    async def get(self, user_id: int, account_name: str) -> Optional[Dict]:
        """Get account from cache or database"""
        key = self._make_key(user_id, account_name)
        
        async with self._lock:
            # Check cache
            if key in self._cache and not self._is_expired(key):
                logger.debug(f"Cache hit for {account_name}")
                return self._cache[key]
            
            # Fetch from database
            try:
                account = await mongodb.db.accounts.find_one({
                    "user_id": user_id,
                    "name": account_name
                })
                
                if account:
                    # Store in cache
                    self._cache[key] = account
                    self._timestamps[key] = time.time()
                    logger.debug(f"Cached account {account_name}")
                    return account
                
                return None
                
            except Exception as e:
                logger.error(f"Failed to fetch account from database: {e}")
                return None
    
    async def get_phone(self, user_id: int, account_name: str) -> str:
        """Get phone number for account (cached)"""
        account = await self.get(user_id, account_name)
        return account.get("phone", "Unknown") if account else "Unknown"
    
    async def get_telegram_id(self, user_id: int, account_name: str) -> Optional[int]:
        """Get Telegram ID for account (cached)"""
        account = await self.get(user_id, account_name)
        return account.get("telegram_id") if account else None
    
    async def invalidate(self, user_id: int, account_name: str):
        """Invalidate cache entry"""
        key = self._make_key(user_id, account_name)
        async with self._lock:
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)
            logger.debug(f"Invalidated cache for {account_name}")
    
    async def invalidate_user(self, user_id: int):
        """Invalidate all cache entries for a user"""
        async with self._lock:
            keys_to_remove = [
                key for key in self._cache.keys()
                if key.startswith(f"{user_id}:")
            ]
            for key in keys_to_remove:
                self._cache.pop(key, None)
                self._timestamps.pop(key, None)
            logger.debug(f"Invalidated {len(keys_to_remove)} cache entries for user {user_id}")
    
    async def clear(self):
        """Clear entire cache"""
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()
            logger.info("Cache cleared")
    
    async def cleanup_expired(self):
        """Remove expired entries from cache"""
        async with self._lock:
            expired_keys = [
                key for key in self._cache.keys()
                if self._is_expired(key)
            ]
            for key in expired_keys:
                self._cache.pop(key, None)
                self._timestamps.pop(key, None)
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "entries": len(self._cache),
            "ttl": self.ttl,
            "memory_kb": sum(
                len(str(v)) for v in self._cache.values()
            ) / 1024
        }


# Global cache instance
account_cache = AccountCache(ttl=300)  # 5 minutes TTL


async def start_cache_cleanup_task():
    """Background task to cleanup expired cache entries"""
    while True:
        try:
            await asyncio.sleep(60)  # Run every minute
            await account_cache.cleanup_expired()
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
