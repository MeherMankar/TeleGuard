"""Centralized 2FA Helper for consistent password handling across all features"""
import logging
from typing import Optional, Tuple
from telethon import TelegramClient
from telethon.errors import PasswordHashInvalidError
from ..core.mongo_database import mongodb
from ..utils.data_encryption import decrypt_string, encrypt_string

logger = logging.getLogger(__name__)


class TwoFAHelper:
    """Centralized 2FA password management"""
    
    @staticmethod
    async def get_stored_password(user_id: int, phone: str) -> Optional[str]:
        """Get stored 2FA password for account by phone"""
        try:
            if not mongodb.db:
                return None
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "phone": phone})
            if account and account.get("twofa_password"):
                return decrypt_string(account["twofa_password"])
            return None
        except Exception as e:
            logger.debug(f"No stored 2FA password found: {e}")
            return None
    
    @staticmethod
    async def store_password(user_id: int, phone: str, password: str) -> bool:
        """Store 2FA password for account"""
        try:
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "phone": phone})
            if not account:
                return False
            
            encrypted = encrypt_string(password)
            await mongodb.db.accounts.update_one(
                {"_id": account["_id"]},
                {"$set": {"twofa_password": encrypted}}
            )
            logger.info(f"Stored 2FA password for {phone}")
            return True
        except Exception as e:
            logger.error(f"Failed to store 2FA password: {e}")
            return False
    
    @staticmethod
    async def remove_password(user_id: int, phone: str) -> bool:
        """Remove stored 2FA password (when it's wrong)"""
        try:
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "phone": phone})
            if not account:
                return False
            
            await mongodb.db.accounts.update_one(
                {"_id": account["_id"]},
                {"$unset": {"twofa_password": ""}}
            )
            logger.info(f"Removed invalid 2FA password for {phone}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove 2FA password: {e}")
            return False
    
    @staticmethod
    async def try_sign_in_with_2fa(
        client: TelegramClient, 
        user_id: int, 
        phone: str,
        stored_password: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Try to sign in with 2FA password
        
        Returns:
            (success, session_string, error_message)
        """
        try:
            # Get stored password if not provided
            if not stored_password:
                stored_password = await TwoFAHelper.get_stored_password(user_id, phone)
            
            if stored_password:
                try:
                    await client.sign_in(password=stored_password)
                    from telethon.sessions import StringSession
                    session_string = StringSession.save(client.session)
                    return (True, session_string, None)
                except PasswordHashInvalidError:
                    # Password is wrong - remove it
                    await TwoFAHelper.remove_password(user_id, phone)
                    return (False, None, "stored_password_invalid")
                except Exception as e:
                    logger.error(f"2FA sign in error: {e}")
                    return (False, None, str(e))
            else:
                return (False, None, "no_stored_password")
        except Exception as e:
            logger.error(f"2FA helper error: {e}")
            return (False, None, str(e))


# Global instance
twofa_helper = TwoFAHelper()
