"""Authorization utilities"""

import logging
from typing import List, Optional
from functools import wraps

logger = logging.getLogger(__name__)

class AuthorizationManager:
    """Secure authorization management"""
    
    def __init__(self):
        self.admin_cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    async def is_admin(self, user_id: int, admin_ids: List[int]) -> bool:
        """Check if user is admin using server-side validation"""
        try:
            # Validate input
            if not isinstance(user_id, int) or not isinstance(admin_ids, list):
                return False
            
            # Server-side check only - never trust client input
            return user_id in admin_ids
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False
    
    async def validate_account_ownership(self, user_id: int, account_user_id: int) -> bool:
        """Validate that user owns the account"""
        try:
            if not isinstance(user_id, int) or not isinstance(account_user_id, int):
                return False
            
            return user_id == account_user_id
        except Exception as e:
            logger.error(f"Error validating account ownership: {e}")
            return False
    
    async def check_rate_limit(self, user_id: int, action: str, limit: int = 10, window: int = 60) -> bool:
        """Check rate limiting for actions"""
        try:
            # Implementation would use Redis or similar for distributed rate limiting
            # For now, return True (implement based on your rate limiting strategy)
            return True
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return False

def require_admin(admin_ids: List[int]):
    """Decorator to require admin privileges"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, event, *args, **kwargs):
            user_id = event.sender_id
            auth_manager = AuthorizationManager()
            
            if not await auth_manager.is_admin(user_id, admin_ids):
                await event.reply("❌ Access denied. Admin privileges required.")
                return
            
            return await func(self, event, *args, **kwargs)
        return wrapper
    return decorator

def require_account_ownership():
    """Decorator to require account ownership"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, event, account_user_id, *args, **kwargs):
            user_id = event.sender_id
            auth_manager = AuthorizationManager()
            
            if not await auth_manager.validate_account_ownership(user_id, account_user_id):
                await event.reply("❌ Access denied. You don't own this account.")
                return
            
            return await func(self, event, account_user_id, *args, **kwargs)
        return wrapper
    return decorator

# Global instance
auth_manager = AuthorizationManager()