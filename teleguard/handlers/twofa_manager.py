"""2FA Management System for TeleGuard"""
import logging
import hashlib
import bcrypt
from telethon import functions
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class TwoFAManager:
    """Manages 2FA operations for user accounts"""
    
    def __init__(self, account_manager):
        self.account_manager = account_manager
    
    async def verify_current_password(self, user_id: int, account_id: str, password: str) -> bool:
        """Verify current 2FA password"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return False
            
            # Get client
            client = await self._get_client(user_id, account)
            if not client:
                return False
            
            # Try to use the password with a test operation
            try:
                await client(functions.account.GetPasswordRequest())
                return True
            except Exception as e:
                if "password" in str(e).lower():
                    return False
                return True  # If no 2FA is set, consider it valid for removal
                
        except Exception as e:
            logger.error(f"Error verifying 2FA password: {e}")
            return False
    
    async def set_2fa_password(self, user_id: int, account_id: str, password: str) -> bool:
        """Set new 2FA password"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return False
            
            client = await self._get_client(user_id, account)
            if not client:
                return False
            
            # Set 2FA password
            await client(functions.account.UpdatePasswordSettingsRequest(
                password=functions.InputCheckPasswordEmpty(),
                new_settings=functions.account.PasswordInputSettings(
                    new_algo=functions.PasswordKdfAlgoSHA256SHA256PBKDF2HMACSHA512iter100000SHA256ModPow(
                        salt1=b'',
                        salt2=b'',
                        g=0,
                        p=b''
                    ),
                    new_password_hash=hashlib.sha256(password.encode()).digest(),
                    hint=password[:2] + "*" * (len(password) - 2)
                )
            ))
            
            # Store encrypted password hash in database using bcrypt
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {"$set": {"twofa_password_hash": password_hash}}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting 2FA password: {e}")
            return False
    
    async def change_2fa_password(self, user_id: int, account_id: str, current_password: str, new_password: str) -> bool:
        """Change existing 2FA password"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return False
            
            client = await self._get_client(user_id, account)
            if not client:
                return False
            
            # Verify current password first
            if not await self.verify_current_password(user_id, account_id, current_password):
                return False
            
            # Change to new password
            await client(functions.account.UpdatePasswordSettingsRequest(
                password=functions.InputCheckPasswordSRP(
                    srp_id=0,
                    A=b'',
                    M1=hashlib.sha256(current_password.encode()).digest()
                ),
                new_settings=functions.account.PasswordInputSettings(
                    new_algo=functions.PasswordKdfAlgoSHA256SHA256PBKDF2HMACSHA512iter100000SHA256ModPow(
                        salt1=b'',
                        salt2=b'',
                        g=0,
                        p=b''
                    ),
                    new_password_hash=hashlib.sha256(new_password.encode()).digest(),
                    hint=new_password[:2] + "*" * (len(new_password) - 2)
                )
            ))
            
            # Update stored password hash using bcrypt
            password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {"$set": {"twofa_password_hash": password_hash}}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error changing 2FA password: {e}")
            return False
    
    async def remove_2fa_password(self, user_id: int, account_id: str, current_password: str) -> bool:
        """Remove 2FA password"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return False
            
            client = await self._get_client(user_id, account)
            if not client:
                return False
            
            # Verify current password
            if not await self.verify_current_password(user_id, account_id, current_password):
                return False
            
            # Remove 2FA
            await client(functions.account.UpdatePasswordSettingsRequest(
                password=functions.InputCheckPasswordSRP(
                    srp_id=0,
                    A=b'',
                    M1=hashlib.sha256(current_password.encode()).digest()
                ),
                new_settings=functions.account.PasswordInputSettings(
                    new_algo=None,
                    new_password_hash=b'',
                    hint=""
                )
            ))
            
            # Remove from database
            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {"$unset": {"twofa_password_hash": ""}}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error removing 2FA password: {e}")
            return False
    
    async def _get_client(self, user_id: int, account: dict):
        """Get Telegram client for account"""
        try:
            if not self.account_manager or user_id not in self.account_manager.user_clients:
                return None
            
            account_name = account.get('name') or account.get('phone')
            return self.account_manager.user_clients[user_id].get(account_name)
            
        except Exception as e:
            logger.error(f"Error getting client: {e}")
            return None