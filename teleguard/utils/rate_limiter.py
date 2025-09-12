"""Advanced rate limiting system"""

import asyncio
import time
from typing import Dict, Optional

from ..core.exceptions import RateLimitError


class RateLimiter:
    def __init__(self):
        self.user_requests: Dict[int, list] = {}
        self.global_requests: list = []
        self.lock = asyncio.Lock()

    async def check_rate_limit(
        self, user_id: int, endpoint: str = "default", limit: int = 30, window: int = 60
    ) -> bool:
        """Check if user is within rate limits"""
        async with self.lock:
            current_time = time.time()

            # Clean old requests
            self._cleanup_old_requests(current_time, window)

            # Check user-specific limits
            user_key = f"{user_id}:{endpoint}"
            if user_key not in self.user_requests:
                self.user_requests[user_key] = []

            user_reqs = self.user_requests[user_key]
            user_reqs = [req for req in user_reqs if current_time - req < window]

            if len(user_reqs) >= limit:
                raise RateLimitError(
                    f"Rate limit exceeded. Try again in {window} seconds."
                )

            # Add current request
            user_reqs.append(current_time)
            self.user_requests[user_key] = user_reqs

            return True

    def _cleanup_old_requests(self, current_time: float, window: int):
        """Clean up old requests to prevent memory leaks"""
        for key in list(self.user_requests.keys()):
            self.user_requests[key] = [
                req for req in self.user_requests[key] if current_time - req < window
            ]
            if not self.user_requests[key]:
                del self.user_requests[key]


# Global rate limiter instance
rate_limiter = RateLimiter()
