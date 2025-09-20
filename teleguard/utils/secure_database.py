"""
Secure Database Operations for TeleGuard
Prevents NoSQL injection and improves security
"""

from typing import Dict, Any, Optional, List
from bson import ObjectId
from bson.errors import InvalidId
from .input_validator import InputValidator

class SecureDatabase:
    """Secure database operations wrapper"""
    
    def __init__(self, db_instance):
        self.db = db_instance
        self.validator = InputValidator()
    
    async def find_user_account(self, user_id: int, account_id: str) -> Optional[Dict]:
        """Securely find user account by ID"""
        # Validate inputs
        clean_user_id = self.validator.validate_user_id(user_id)
        clean_account_id = self.validator.validate_object_id(account_id)
        
        if not clean_user_id or not clean_account_id:
            return None
        
        try:
            return await self.db.accounts.find_one({
                "user_id": clean_user_id,
                "_id": ObjectId(clean_account_id)
            })
        except Exception:
            return None
    
    async def update_user_account(self, user_id: int, account_id: str, 
                                update_data: Dict[str, Any]) -> bool:
        """Securely update user account"""
        # Validate inputs
        clean_user_id = self.validator.validate_user_id(user_id)
        clean_account_id = self.validator.validate_object_id(account_id)
        
        if not clean_user_id or not clean_account_id:
            return False
        
        # Sanitize update data
        safe_update = self._sanitize_update_data(update_data)
        if not safe_update:
            return False
        
        try:
            result = await self.db.accounts.update_one(
                {
                    "user_id": clean_user_id,
                    "_id": ObjectId(clean_account_id)
                },
                {"$set": safe_update}
            )
            return result.modified_count > 0
        except Exception:
            return False
    
    async def find_user_accounts(self, user_id: int) -> List[Dict]:
        """Securely find all user accounts"""
        clean_user_id = self.validator.validate_user_id(user_id)
        if not clean_user_id:
            return []
        
        try:
            cursor = self.db.accounts.find({"user_id": clean_user_id})
            return await cursor.to_list(length=None)
        except Exception:
            return []
    
    async def create_audit_entry(self, user_id: int, account_id: str, 
                               action: str, details: Dict[str, Any]) -> bool:
        """Securely create audit log entry"""
        # Validate inputs
        clean_user_id = self.validator.validate_user_id(user_id)
        clean_account_id = self.validator.validate_object_id(account_id)
        clean_action = self.validator.sanitize_text_input(action, 100)
        
        if not clean_user_id or not clean_account_id or not clean_action:
            return False
        
        # Sanitize details
        safe_details = self._sanitize_dict(details)
        
        try:
            from datetime import datetime, timezone
            
            audit_entry = {
                "user_id": clean_user_id,
                "account_id": clean_account_id,
                "action": clean_action,
                "details": safe_details,
                "timestamp": datetime.now(timezone.utc),
                "ip_address": None  # Add if available
            }
            
            await self.db.audit_logs.insert_one(audit_entry)
            return True
        except Exception:
            return False
    
    def _sanitize_update_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Sanitize update data to prevent injection"""
        if not isinstance(data, dict):
            return None
        
        safe_data = {}
        allowed_fields = {
            'otp_destroyer_enabled', 'otp_forward_enabled', 'auto_reply_enabled',
            'online_maker_enabled', 'simulation_enabled', 'display_name',
            'last_activity', 'is_active', 'settings'
        }
        
        for key, value in data.items():
            # Validate field name
            if not self.validator.validate_database_field(key):
                continue
            
            # Only allow whitelisted fields
            if key not in allowed_fields:
                continue
            
            # Sanitize value based on type
            if isinstance(value, str):
                safe_data[key] = self.validator.sanitize_text_input(value)
            elif isinstance(value, (bool, int, float)):
                safe_data[key] = value
            elif isinstance(value, dict):
                safe_data[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                safe_data[key] = self._sanitize_list(value)
        
        return safe_data if safe_data else None
    
    def _sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively sanitize dictionary"""
        if not isinstance(data, dict):
            return {}
        
        safe_dict = {}
        for key, value in data.items():
            if not self.validator.validate_database_field(key):
                continue
            
            if isinstance(value, str):
                safe_dict[key] = self.validator.sanitize_text_input(value)
            elif isinstance(value, (bool, int, float)):
                safe_dict[key] = value
            elif isinstance(value, dict):
                safe_dict[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                safe_dict[key] = self._sanitize_list(value)
        
        return safe_dict
    
    def _sanitize_list(self, data: List[Any]) -> List[Any]:
        """Sanitize list items"""
        if not isinstance(data, list):
            return []
        
        safe_list = []
        for item in data[:100]:  # Limit list size
            if isinstance(item, str):
                safe_list.append(self.validator.sanitize_text_input(item))
            elif isinstance(item, (bool, int, float)):
                safe_list.append(item)
            elif isinstance(item, dict):
                safe_list.append(self._sanitize_dict(item))
        
        return safe_list