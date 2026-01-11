"""Redis-based rate limiting system"""

import time

from ..core.exceptions import RateLimitError
from ..core.redis_cache import redis_cache


class RateLimiter:
    def __init__(self):
        self.fallback_requests = {}  # Fallback for when Redis unavailable

    async def check_rate_limit(
        self, user_id: int, endpoint: str = "default", limit: int = 30, window: int = 60
    ) -> bool:
        """Check if user is within rate limits using Redis"""
        key = f"{user_id}:{endpoint}"
        # Try Redis first
        if redis_cache.connected:
            try:
                allowed = await redis_cache.check_rate_limit(key, limit, window)
                if not allowed:
                    remaining = await redis_cache.get_rate_limit_remaining(
                        key, limit, window
                    )
                    raise RateLimitError(
                        f"Rate limit exceeded. {remaining} requests remaining. Try again in {window} seconds."
                    )
                return True
            except RateLimitError:
                raise
            except Exception:
                # Fall back to memory-based limiting
                pass
        # Fallback to memory-based rate limiting
        return await self._memory_rate_limit(key, limit, window)

    async def _memory_rate_limit(self, key: str, limit: int, window: int) -> bool:
        """Memory-based fallback rate limiting"""
        current_time = time.time()
        if key not in self.fallback_requests:
            self.fallback_requests[key] = []
        # Clean old requests
        self.fallback_requests[key] = [
            req for req in self.fallback_requests[key] if current_time - req < window
        ]
        if len(self.fallback_requests[key]) >= limit:
            raise RateLimitError(f"Rate limit exceeded. Try again in {window} seconds.")
        self.fallback_requests[key].append(current_time)
        return True

    async def get_remaining_requests(
        self, user_id: int, endpoint: str = "default", limit: int = 30, window: int = 60
    ) -> int:
        """Get remaining requests for user"""
        key = f"{user_id}:{endpoint}"
        if redis_cache.connected:
            try:
                return await redis_cache.get_rate_limit_remaining(key, limit, window)
            except Exception:
                pass
        # Fallback calculation
        if key not in self.fallback_requests:
            return limit
        current_time = time.time()
        recent_requests = [
            req for req in self.fallback_requests[key] if current_time - req < window
        ]
        return max(0, limit - len(recent_requests))


# Global rate limiter instance
rate_limiter = RateLimiter()
