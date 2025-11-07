"""Account Invalidation Handler for TeleGuard
Automatically removes invalidated accounts and notifies users
"""
import asyncio
import logging
from typing import Optional
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class AccountInvalidationHandler:
    """Handles automatic removal of invalidated accounts with user notifications"""
    
    def __init__(self, bot_manager) -> None:
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot if bot_manager else None
    
    async def handle_account_invalidation(
        self, user_id: int, account_name: str, phone: str, error_message: str
    ) -> None:
        """Handle account invalidation with removal and user notification."""
        try:
            success = await self._remove_invalidated_account(user_id, account_name, phone)
            if success:
                await self._send_invalidation_notification(user_id, account_name, phone, error_message)
        except Exception as e:
            logger.error(f"Error handling account invalidation: {e}")
    
    async def _remove_invalidated_account(
        self, user_id: int, account_name: str, phone: str
    ) -> bool:
        """Remove invalidated account from database and active clients."""
        try:
            account = await self._find_account(user_id, account_name, phone)
            if not account:
                return False
                
            await self._cleanup_session_monitor(user_id, account_name)
            await self._disconnect_active_clients(user_id, account_name, phone, account)
            await self._cleanup_2fa_password(user_id, account)
            await self._remove_from_database(account)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove account: {e}")
            return False
    
    async def _find_account(self, user_id: int, account_name: str, phone: str) -> Optional[dict]:
        """Find account in database by user_id and name/phone."""
        return await mongodb.db.accounts.find_one({
            "user_id": user_id,
            "$or": [{"name": account_name}, {"phone": phone}]
        })
    
    async def _cleanup_session_monitor(self, user_id: int, account_name: str) -> None:
        """Remove account from session monitoring."""
        if hasattr(self.bot_manager, 'session_monitor') and self.bot_manager.session_monitor:
            self.bot_manager.session_monitor.remove_client_from_monitor(user_id, account_name)
    
    async def _disconnect_active_clients(
        self, user_id: int, account_name: str, phone: str, account: dict
    ) -> None:
        """Disconnect and remove active Telegram clients."""
        if user_id not in self.bot_manager.user_clients:
            return
            
        client_keys = [account_name, phone, account.get('display_name')]
        for key, client in list(self.bot_manager.user_clients[user_id].items()):
            if key in client_keys:
                await self._safe_disconnect_client(client)
                self.bot_manager.user_clients[user_id].pop(key, None)
    
    async def _safe_disconnect_client(self, client) -> None:
        """Safely disconnect a Telegram client."""
        try:
            if client and client.is_connected():
                await asyncio.wait_for(client.disconnect(), timeout=5)
        except Exception:
            pass
    
    async def _cleanup_2fa_password(self, user_id: int, account: dict) -> None:
        """Remove stored 2FA password for security."""
        try:
            from ..core.database_manager import db_manager
            await db_manager.remove_2fa_password(user_id, str(account['_id']))
        except Exception:
            pass
    
    async def _remove_from_database(self, account: dict) -> None:
        """Remove account from MongoDB."""
        await mongodb.db.accounts.delete_one({"_id": account["_id"]})
    
    async def _send_invalidation_notification(
        self, user_id: int, account_name: str, phone: str, error_message: str
    ) -> None:
        """Send notification to user about account removal."""
        if not self.bot:
            return
            
        try:
            message = self._build_notification_message(account_name, phone, error_message)
            await self._send_with_rate_limit(user_id, message)
            
        except Exception as e:
            await self._handle_notification_error(e)
    
    def _build_notification_message(self, account_name: str, phone: str, error_message: str) -> str:
        """Build sanitized notification message."""
        import html
        
        reason = self._extract_telegram_reason(error_message)
        safe_name = html.escape(str(account_name)[:50])
        safe_phone = html.escape(str(phone)[:20])
        safe_reason = html.escape(str(reason)[:200])
        
        return (
            f"🔔🔴 **Account status information!**\n\n"
            f"Your account **[{safe_name}]** has automatically been removed from your collection, "
            f"because Telegram said:\n\n"
            f"**Telegram says:** {safe_reason}\n\n"
            f"**Phone number:** {safe_phone}\n\n"
            f"❓ **Have you got any questions?** Contact support -> @meher_mankar"
        )
    
    async def _send_with_rate_limit(self, user_id: int, message: str) -> None:
        """Send message with rate limiting protection."""
        await asyncio.sleep(0.5)
        await self.bot.send_message(user_id, message, parse_mode='markdown')
    
    async def _handle_notification_error(self, error: Exception) -> None:
        """Handle notification sending errors."""
        if "flood" in str(error).lower():
            await asyncio.sleep(5)
        logger.error(f"Failed to send notification: {error}")
    
    def _extract_telegram_reason(self, error_message: str) -> str:
        """Extract and format Telegram's error reason"""
        error_lower = error_message.lower()
        
        # Common error patterns and their user-friendly messages
        if "auth_key_unregistered" in error_lower:
            return "[401 AUTH_KEY_UNREGISTERED] - The key is not registered in the system. Delete your session file and login again (caused by \"updates.GetState\")"
        elif "auth_key_duplicated" in error_lower:
            return "[406 AUTH_KEY_DUPLICATED] - The authorization key (session) was used under two different IP addresses simultaneously"
        elif "session_revoked" in error_lower:
            return "[401 SESSION_REVOKED] - The authorization has been invalidated, because of the user logging out"
        elif "user_deactivated" in error_lower:
            return "[401 USER_DEACTIVATED] - The user has been deleted/deactivated"
        elif "authorization key" in error_lower and "ip addresses" in error_lower:
            return "[406 AUTH_KEY_DUPLICATED] - The authorization key was used from different IP addresses simultaneously"
        elif "failed to get valid user info" in error_lower:
            return "[401 AUTH_KEY_UNREGISTERED] - Session is no longer valid. The key is not registered in the system"
        else:
            # Return the original error if we can't parse it
            return f"[UNKNOWN ERROR] - {error_message}"

_account_invalidation_handler: Optional[AccountInvalidationHandler] = None

def init_account_invalidation_handler(bot_manager) -> AccountInvalidationHandler:
    """Initialize the global account invalidation handler."""
    global _account_invalidation_handler
    _account_invalidation_handler = AccountInvalidationHandler(bot_manager)
    return _account_invalidation_handler

async def handle_account_error(
    user_id: int, account_name: str, phone: str, error_message: str
) -> None:
    """Handle account errors using the global handler."""
    if _account_invalidation_handler:
        await _account_invalidation_handler.handle_account_invalidation(
            user_id, account_name, phone, error_message
        )
