"""Utility functions for callback handlers"""
import logging
from typing import Dict, Any, Optional, Tuple
from ...core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class CallbackUtils:
    """Utility class for common callback operations"""
    
    @staticmethod
    async def get_account_by_id(user_id: int, account_id: str) -> Optional[Dict[str, Any]]:
        """Get account by ID with user validation"""
        try:
            from bson import ObjectId
            return await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id), 
                "user_id": user_id
            })
        except Exception as e:
            logger.error(f"Error getting account {account_id}: {e}")
            return None
    
    @staticmethod
    async def update_account_setting(user_id: int, account_id: str, setting: str, value: Any) -> bool:
        """Update a single account setting"""
        try:
            from bson import ObjectId
            result = await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id), "user_id": user_id},
                {"$set": {setting: value}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating account setting {setting}: {e}")
            return False
    
    @staticmethod
    async def log_account_action(user_id: int, account_id: str, action: str, details: str = "") -> bool:
        """Log an action to account audit log"""
        try:
            from bson import ObjectId
            import time
            
            log_entry = {
                "action": action,
                "details": details,
                "timestamp": int(time.time())
            }
            
            result = await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id), "user_id": user_id},
                {"$push": {"audit_log": log_entry}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error logging action {action}: {e}")
            return False
    
    @staticmethod
    def parse_callback_data(data: str) -> Tuple[str, str, str]:
        """Parse callback data into components"""
        parts = data.split(":")
        prefix = parts[0] if len(parts) > 0 else ""
        action = parts[1] if len(parts) > 1 else ""
        account_id = parts[2] if len(parts) > 2 else "0"
        return prefix, action, account_id
    
    @staticmethod
    async def validate_user_account_access(user_id: int, account_id: str) -> bool:
        """Validate that user has access to the account"""
        account = await CallbackUtils.get_account_by_id(user_id, account_id)
        return account is not None
    
    @staticmethod
    def format_account_display_name(account: Dict[str, Any]) -> str:
        """Format account display name consistently"""
        name = account.get('name', '')
        username = account.get('username', '')
        phone = account.get('phone', '')
        
        if name:
            return name
        elif username:
            return f"@{username}"
        elif phone:
            return phone
        else:
            return "Unknown Account"
    
    @staticmethod
    async def get_user_accounts_count(user_id: int) -> int:
        """Get count of user's accounts"""
        try:
            return await mongodb.db.accounts.count_documents({"user_id": user_id})
        except Exception as e:
            logger.error(f"Error counting user accounts: {e}")
            return 0
    
    @staticmethod
    async def check_account_limits(user_id: int) -> Tuple[bool, str]:
        """Check if user can add more accounts"""
        try:
            from ...core.config import MAX_ACCOUNTS
            current_count = await CallbackUtils.get_user_accounts_count(user_id)
            
            if current_count >= MAX_ACCOUNTS:
                return False, f"Maximum account limit ({MAX_ACCOUNTS}) reached"
            
            return True, f"Can add {MAX_ACCOUNTS - current_count} more accounts"
        except Exception as e:
            logger.error(f"Error checking account limits: {e}")
            return False, "Error checking account limits"