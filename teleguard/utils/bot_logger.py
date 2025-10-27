"""Centralized logging to logs bot for all user actions"""
import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class BotLogger:
    """Send all user actions to logs bot"""
    
    _bot = None
    _log_chat_id = None
    
    @classmethod
    def init(cls, bot):
        """Initialize with bot instance"""
        cls._bot = bot
        log_chat_id = os.getenv('LOG_CHAT_ID')
        if log_chat_id:
            cls._log_chat_id = int(log_chat_id)
    
    @classmethod
    async def log(cls, user_id: int, action: str, details: str = "", username: Optional[str] = None):
        """Send log to logs bot"""
        if not cls._bot or not cls._log_chat_id:
            return
        
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            user_info = f"@{username}" if username else f"ID: {user_id}"
            message = f"📋 **User Action Log**\n🕐 {timestamp}\n👤 {user_info}\n⚡ **{action}**"
            if details:
                message += f"\n📝 {details}"
            
            await cls._bot.send_message(cls._log_chat_id, message)
        except Exception as e:
            logger.debug(f"Failed to send log: {e}")
    
    @classmethod
    async def log_account_added(cls, user_id: int, phone: str, username: Optional[str] = None):
        """Log account addition"""
        await cls.log(user_id, "Account Added", f"📱 Phone: {phone}", username)
    
    @classmethod
    async def log_account_removed(cls, user_id: int, phone: str, username: Optional[str] = None):
        """Log account removal"""
        await cls.log(user_id, "Account Removed", f"📱 Phone: {phone}", username)
    
    @classmethod
    async def log_otp_enabled(cls, user_id: int, phone: str, username: Optional[str] = None):
        """Log OTP protection enabled"""
        await cls.log(user_id, "OTP Protection Enabled", f"📱 Phone: {phone}", username)
    
    @classmethod
    async def log_otp_disabled(cls, user_id: int, phone: str, username: Optional[str] = None):
        """Log OTP protection disabled"""
        await cls.log(user_id, "OTP Protection Disabled", f"📱 Phone: {phone}", username)
    
    @classmethod
    async def log_2fa_set(cls, user_id: int, phone: str, username: Optional[str] = None):
        """Log 2FA password set"""
        await cls.log(user_id, "2FA Password Set", f"📱 Phone: {phone}", username)
    
    @classmethod
    async def log_2fa_changed(cls, user_id: int, phone: str, username: Optional[str] = None):
        """Log 2FA password changed"""
        await cls.log(user_id, "2FA Password Changed", f"📱 Phone: {phone}", username)
    
    @classmethod
    async def log_2fa_removed(cls, user_id: int, phone: str, username: Optional[str] = None):
        """Log 2FA password removed"""
        await cls.log(user_id, "2FA Password Removed", f"📱 Phone: {phone}", username)
    
    @classmethod
    async def log_profile_updated(cls, user_id: int, phone: str, field: str, username: Optional[str] = None):
        """Log profile update"""
        await cls.log(user_id, f"Profile Updated: {field}", f"📱 Phone: {phone}", username)
    
    @classmethod
    async def log_session_terminated(cls, user_id: int, phone: str, username: Optional[str] = None):
        """Log session termination"""
        await cls.log(user_id, "Session Terminated", f"📱 Phone: {phone}", username)
    
    @classmethod
    async def log_online_maker_toggled(cls, user_id: int, phone: str, enabled: bool, username: Optional[str] = None):
        """Log online maker toggle"""
        status = "Enabled" if enabled else "Disabled"
        await cls.log(user_id, f"Online Maker {status}", f"📱 Phone: {phone}", username)
    
    @classmethod
    async def log_auto_reply_toggled(cls, user_id: int, phone: str, enabled: bool, username: Optional[str] = None):
        """Log auto-reply toggle"""
        status = "Enabled" if enabled else "Disabled"
        await cls.log(user_id, f"Auto-Reply {status}", f"📱 Phone: {phone}", username)
    
    @classmethod
    async def log_channel_joined(cls, user_id: int, phone: str, channel: str, username: Optional[str] = None):
        """Log channel join"""
        await cls.log(user_id, "Channel Joined", f"📱 Phone: {phone}\n📢 Channel: {channel}", username)
    
    @classmethod
    async def log_channel_left(cls, user_id: int, phone: str, channel: str, username: Optional[str] = None):
        """Log channel leave"""
        await cls.log(user_id, "Channel Left", f"📱 Phone: {phone}\n📢 Channel: {channel}", username)
    
    @classmethod
    async def log_contacts_exported(cls, user_id: int, phone: str, count: int, username: Optional[str] = None):
        """Log contacts export"""
        await cls.log(user_id, "Contacts Exported", f"📱 Phone: {phone}\n📊 Count: {count}", username)
