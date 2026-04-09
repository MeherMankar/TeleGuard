"""
Common Session Utilities - Shared functions for session management
Eliminates code duplication across handlers
"""

import logging
from typing import Dict, Optional

from ..core.mongo_database import mongodb
from ..utils.account_cache import account_cache

logger = logging.getLogger(__name__)


class SessionUtils:
    """Common utilities for session management"""
    
    @staticmethod
    async def get_phone_for_account(user_id: int, account_name: str) -> str:
        """Get phone number for an account (cached)"""
        return await account_cache.get_phone(user_id, account_name)
    
    @staticmethod
    async def get_telegram_id_for_account(user_id: int, account_name: str) -> Optional[int]:
        """Get Telegram ID for an account (cached)"""
        return await account_cache.get_telegram_id(user_id, account_name)
    
    @staticmethod
    async def notify_session_conflict(
        bot,
        user_id: int,
        account_name: str,
        phone: str,
        error_reason: str = ""
    ):
        """Notify user about session conflicts (DRY)"""
        try:
            error_type = (
                "AUTH_KEY_UNREGISTERED (401)"
                if "401" in error_reason or "unregistered" in error_reason.lower()
                else (
                    "AUTH_KEY_DUPLICATED (406)"
                    if "406" in error_reason or "duplicated" in error_reason.lower()
                    else "Session Conflict"
                )
            )
            
            message = (
                f"⚠️ **Session Conflict Detected**\n\n"
                f"📱 **Account:** {account_name} ({phone})\n"
                f"🔴 **Error:** {error_type}\n\n"
                f"**🤖 Likely Cause: Another Bot/Client**\n"
                f"• This account is being used by another bot or Telegram client\n"
                f"• Telegram only allows one active session per account\n"
                f"• When multiple bots use the same account, sessions get invalidated\n\n"
                f"**🔧 Solutions:**\n"
                f"1. **Stop other bots** using this account\n"
                f"2. **Use different accounts** for different bots\n"
                f"3. **Re-add account** after stopping conflicts\n"
                f"4. **Check for duplicate logins** on other devices\n\n"
                f"🚨 **Important:** Multiple bots on same account = constant session conflicts\n\n"
                f"💡 **Tip:** Use /start → Account Settings to manage accounts"
            )
            await bot.send_message(user_id, message)
            logger.info(f"Notified user {user_id} about session conflict for {account_name}")
        except Exception as e:
            logger.error(f"Failed to notify user about session conflict: {e}")
    
    @staticmethod
    async def notify_reauth_needed(
        bot,
        user_id: int,
        account_name: str,
        phone: str,
        error_reason: str = ""
    ):
        """Notify user that account needs re-authentication (DRY)"""
        try:
            error_type = (
                "AUTH_KEY_UNREGISTERED"
                if "401" in error_reason or "unregistered" in error_reason.lower()
                else (
                    "AUTH_KEY_DUPLICATED"
                    if "406" in error_reason or "duplicated" in error_reason.lower()
                    else "Session Error"
                )
            )
            
            message = (
                f"🔄 **Account Re-authentication Required**\n\n"
                f"📱 **Account:** {account_name} ({phone})\n"
                f"❌ **Error:** {error_type}\n\n"
                f"**What happened:**\n"
                f"• Your session has been invalidated by Telegram\n"
                f"• This can happen due to security checks, session expiry, or duplicate logins\n\n"
                f"**To fix this:**\n"
                f"1. Go to Account Settings\n"
                f"2. Remove the affected account\n"
                f"3. Add it again using phone number login\n"
                f"4. Or import a fresh session string\n\n"
                f"💡 **Tip:** Use /start → Account Settings to manage accounts"
            )
            await bot.send_message(user_id, message)
            logger.info(f"Notified user {user_id} about reauth needed for {account_name}")
        except Exception as e:
            logger.error(f"Failed to notify user about reauth: {e}")
    
    @staticmethod
    async def handle_session_conflict(
        user_id: int,
        account_name: str,
        error_reason: str,
        bot = None
    ):
        """Handle session conflicts (DRY)"""
        try:
            # Update database with conflict status
            await mongodb.db.accounts.update_one(
                {"user_id": user_id, "name": account_name},
                {
                    "$set": {
                        "session_conflict": True,
                        "is_active": False,
                        "last_error": error_reason,
                        "error_time": int(__import__("time").time()),
                    },
                    "$inc": {"conflict_count": 1}
                }
            )
            
            # Invalidate cache
            await account_cache.invalidate(user_id, account_name)
            
            # Get phone for notification
            phone = await SessionUtils.get_phone_for_account(user_id, account_name)
            
            # Notify user if bot provided
            if bot:
                await SessionUtils.notify_session_conflict(
                    bot, user_id, account_name, phone, error_reason
                )
            
            logger.warning(f"Session conflict detected for {account_name}: {error_reason}")
            
        except Exception as e:
            logger.error(f"Failed to handle session conflict: {e}")
    
    @staticmethod
    async def mark_account_for_reauth(
        user_id: int,
        account_name: str,
        error_reason: str,
        bot = None
    ):
        """Mark account for re-authentication (DRY)"""
        try:
            # Update database
            await mongodb.db.accounts.update_one(
                {"user_id": user_id, "name": account_name},
                {
                    "$set": {
                        "needs_reauth": True,
                        "is_active": False,
                        "last_error": error_reason,
                        "error_time": int(__import__("time").time()),
                    }
                }
            )
            
            # Invalidate cache
            await account_cache.invalidate(user_id, account_name)
            
            # Get phone for notification
            phone = await SessionUtils.get_phone_for_account(user_id, account_name)
            
            # Notify user if bot provided
            if bot:
                await SessionUtils.notify_reauth_needed(
                    bot, user_id, account_name, phone, error_reason
                )
            
            logger.info(f"Marked account {account_name} for reauth: {error_reason}")
            
        except Exception as e:
            logger.error(f"Failed to mark account for reauth: {e}")
    
    @staticmethod
    def is_session_error(error_msg: str) -> tuple[bool, str]:
        """
        Check if error is a session-related error
        
        Returns:
            (is_session_error, error_type)
        """
        error_msg = error_msg.lower()
        
        # Session conflict errors
        if any(phrase in error_msg for phrase in [
            "auth_key_unregistered",
            "auth_key_duplicated",
            "401",
            "406",
            "authorization key",
            "session_revoked",
            "session expired"
        ]):
            return True, "conflict"
        
        # Session invalidation errors
        if any(phrase in error_msg for phrase in [
            "user_deactivated",
            "failed to get valid user info",
            "duplicated",
            "session_password_needed",
            "unauthorized",
            "invalid session"
        ]):
            return True, "invalidation"
        
        return False, ""
