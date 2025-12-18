"""
Rate Limiter for Account Operations
Prevents Telegram anti-spam detection by tracking and limiting operations
"""
import logging
import time
from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

class RateLimiter:
    """Track and limit operations per account to prevent spam detection"""
    
    # Operation limits per hour
    LIMITS = {
        'message': 30,      # Max 30 messages per hour
        'join': 10,         # Max 10 channel joins per hour
        'leave': 15,        # Max 15 channel leaves per hour
        'cleanup': 50,      # Max 50 cleanup operations per hour
        'appeal': 2,        # Max 2 appeals per hour
        'bulk_send': 1      # Max 1 bulk send per hour
    }
    
    # Cooldown periods in seconds
    COOLDOWNS = {
        'bulk_send': 3600,  # 1 hour between bulk sends
        'cleanup': 1800,    # 30 minutes between cleanups
        'appeal': 7200      # 2 hours between appeals
    }
    
    def __init__(self):
        # {account_phone: {operation: [(timestamp, count)]}}
        self.operations: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
        # {account_phone: {operation: last_timestamp}}
        self.last_operation: Dict[str, Dict[str, float]] = defaultdict(dict)
    
    def can_perform(self, account_phone: str, operation: str) -> tuple[bool, Optional[str]]:
        """Check if operation can be performed"""
        # Check cooldown
        if operation in self.COOLDOWNS:
            last_time = self.last_operation.get(account_phone, {}).get(operation)
            if last_time:
                elapsed = time.time() - last_time
                cooldown = self.COOLDOWNS[operation]
                if elapsed < cooldown:
                    remaining = int(cooldown - elapsed)
                    minutes = remaining // 60
                    seconds = remaining % 60
                    return False, f"⏳ Cooldown active. Wait {minutes}m {seconds}s"
        
        # Check rate limit
        if operation in self.LIMITS:
            self._cleanup_old_operations(account_phone, operation)
            count = self._get_operation_count(account_phone, operation)
            limit = self.LIMITS[operation]
            
            if count >= limit:
                return False, f"⚠️ Rate limit reached: {count}/{limit} {operation}s per hour"
        
        return True, None
    
    def record_operation(self, account_phone: str, operation: str, count: int = 1):
        """Record an operation"""
        current_time = time.time()
        self.operations[account_phone][operation].append((current_time, count))
        self.last_operation[account_phone][operation] = current_time
        logger.info(f"Recorded {operation} for {account_phone}: {count} operations")
    
    def get_stats(self, account_phone: str) -> Dict[str, dict]:
        """Get operation statistics for an account"""
        stats = {}
        for operation in self.LIMITS.keys():
            self._cleanup_old_operations(account_phone, operation)
            count = self._get_operation_count(account_phone, operation)
            limit = self.LIMITS[operation]
            
            # Get cooldown info
            cooldown_remaining = 0
            if operation in self.COOLDOWNS:
                last_time = self.last_operation.get(account_phone, {}).get(operation)
                if last_time:
                    elapsed = time.time() - last_time
                    cooldown = self.COOLDOWNS[operation]
                    if elapsed < cooldown:
                        cooldown_remaining = int(cooldown - elapsed)
            
            stats[operation] = {
                'count': count,
                'limit': limit,
                'remaining': limit - count,
                'cooldown_remaining': cooldown_remaining
            }
        
        return stats
    
    def reset_account(self, account_phone: str):
        """Reset all limits for an account"""
        if account_phone in self.operations:
            del self.operations[account_phone]
        if account_phone in self.last_operation:
            del self.last_operation[account_phone]
        logger.info(f"Reset rate limits for {account_phone}")
    
    def _cleanup_old_operations(self, account_phone: str, operation: str):
        """Remove operations older than 1 hour"""
        cutoff_time = time.time() - 3600  # 1 hour ago
        if account_phone in self.operations and operation in self.operations[account_phone]:
            self.operations[account_phone][operation] = [
                (ts, count) for ts, count in self.operations[account_phone][operation]
                if ts > cutoff_time
            ]
    
    def _get_operation_count(self, account_phone: str, operation: str) -> int:
        """Get total operation count in the last hour"""
        if account_phone not in self.operations or operation not in self.operations[account_phone]:
            return 0
        return sum(count for _, count in self.operations[account_phone][operation])

# Global rate limiter instance
rate_limiter = RateLimiter()
