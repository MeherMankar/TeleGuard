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
            # Mask the hash — keep first 4 and last 4 chars
            hash_str = str(auth.hash)
            masked_hash = (
                hash_str[:4] + "••••" + hash_str[-4:]
                if len(hash_str) > 8
                else "••••••••"
            )

            # Format timestamps — show "—" when unavailable
            def _fmt_time(dt):
                if dt is None:
                    return "—"
                try:
                    return dt.strftime("%Y-%m-%d %H:%M UTC")
                except Exception:
                    return "—"

            login_time  = _fmt_time(getattr(auth, "date",        None))
            last_active = _fmt_time(getattr(auth, "date_active", None))

            # Build location string: "City, Country" or just whichever is present
            country = (getattr(auth, "country", None) or "").strip()
            region  = (getattr(auth, "region",  None) or "").strip()
            location_parts = [p for p in [region, country] if p]
            location = ", ".join(location_parts) if location_parts else "Unknown"

            # IP
            ip = (getattr(auth, "ip", None) or "").strip() or "Unknown"

            # Official app badge
            official = getattr(auth, "official_app", False)
            official_badge = "✅ Yes" if official else "⚠️ No (Third-party)"

            # System info — collapse empty parts
            platform       = (getattr(auth, "platform",       None) or "").strip()
            system_version = (getattr(auth, "system_version", None) or "").strip()
            system_line = platform
            if system_version:
                system_line = f"{platform} {system_version}".strip()

            app_name    = (getattr(auth, "app_name",    None) or "").strip()
            app_version = (getattr(auth, "app_version", None) or "").strip()
            app_line = f"{app_name} {app_version}".strip() or "Unknown"

            message = (
                "🚨 **Unauthorized Session Destroyed**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "📱 **Device Info**\n"
                f"  💻 Device: {auth.device_model or 'Unknown'}\n"
                f"  🖥 OS: {system_line or 'Unknown'}\n"
                f"  📲 App: {app_line}\n"
                f"  🏷 Official App: {official_badge}\n\n"
                "🌐 **Network**\n"
                f"  🔌 IP: `{ip}`\n"
                f"  📍 Location: {location}\n\n"
                "🕰 **Timeline**\n"
                f"  📥 Logged In: {login_time}\n"
                f"  🕒 Last Active: {last_active}\n\n"
                "🔐 **Session**\n"
                f"  🆔 Hash: `{masked_hash}`\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🛡 **Terminated successfully.**"
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
