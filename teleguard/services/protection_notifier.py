"""Notifications for Protection Manager - Intruder Alerts"""

import logging
from datetime import datetime, timezone
from telethon import functions
from telethon.tl.types import Authorization

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class ProtectionNotifier:
    """Handle security notifications for the protection system"""

    def __init__(self, bot):
        self.bot = bot

    async def notify_session_destroyed(self, user_id: int, auth: Authorization):
        """Send rich alert when an unauthorized session is destroyed"""
        try:
            # Mask the hash for security
            masked_hash = str(auth.hash)[:4] + "****" + str(auth.hash)[-4:] if len(str(auth.hash)) > 8 else "****"
            
            # Format times
            login_time = auth.date.strftime('%Y-%m-%d %H:%M UTC') if hasattr(auth, 'date') else "Unknown"
            last_active = auth.date_active.strftime('%Y-%m-%d %H:%M UTC') if hasattr(auth, 'date_active') else "Just now"

            message = (
                "🚨 **Unauthorized Session Destroyed**\n\n"
                f"💻 **Device:** {auth.device_model}\n"
                f"🎛 **Platform:** {auth.platform}\n"
                f"🖥 **System:** {auth.system_version}\n\n"
                f"📱 **App:** {auth.app_name} {auth.app_version}\n"
                f"🌐 **IP:** `{auth.ip}`\n\n"
                f"🌍 **Country:** {auth.country}\n"
                f"📍 **Region:** {auth.region}\n\n"
                f"📥 **Login Time:** {login_time}\n"
                f"🕒 **Last Active:** {last_active}\n\n"
                f"🆔 **Session Hash:** `{masked_hash}`\n"
                f"✅ **Official App:** {'Yes' if auth.official_app else 'No'}\n\n"
                "🛡 **Status:** Session terminated successfully."
            )

            await self.bot.send_message(user_id, message)
            logger.info(f"Sent intruder alert to {user_id} for session {auth.hash}")
            
        except Exception as e:
            logger.error(f"Error sending session destruction alert to {user_id}: {e}")

    async def notify_otp_destroyed(self, user_id: int, account_name: str, code: str):
        """Send notification when an OTP is destroyed"""
        try:
            message = (
                "🛡 **OTP Destroyer Active**\n\n"
                f"📱 **Account:** {account_name}\n"
                f"🔑 **Code:** `{code}`\n"
                "✅ **Status:** Invalidated successfully."
            )
            await self.bot.send_message(user_id, message)
        except Exception as e:
            logger.error(f"Error sending OTP destruction alert to {user_id}: {e}")
