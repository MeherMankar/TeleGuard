"""
Session Destroyer Handler
UI handlers for the Session Destroyer feature.
"""

import logging
from typing import Optional
from telethon import Button, events

from ..sync.session_destroyer_db import SessionDestroyerDB
from ..services.protection_storage import ProtectionStorage
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class SessionDestroyerHandler:
    """Handles UI and callbacks for Session Destroyer"""

    def __init__(self, menu_system):
        self.menu = menu_system
        self.bot = menu_system.bot

    async def show_submenu(self, user_id: int, message_id: Optional[int] = None):
        """Show the Session Destroyer submenu"""
        try:
            settings = await ProtectionStorage.get_settings(user_id)
            accounts_count = await mongodb.db.accounts.count_documents(
                {"user_id": user_id, "is_active": True}
            )
            
            is_enabled = settings.get("session_destroyer_enabled", False)
            status_text = "🟢 Enabled" if is_enabled else "🔴 Disabled"
            destroyed_count = settings.get("stats", {}).get("sessions_destroyed", 0)
            
            text = (
                "🔥 **Session Destroyer**\n\n"
                f"**Status:** {status_text}\n"
                f"**Protected Accounts:** {accounts_count if is_enabled else 0}\n"
                f"**Sessions Terminated:** {destroyed_count}\n\n"
                "**Description:**\n"
                "Automatically destroys newly logged-in Telegram sessions while keeping your existing trusted sessions safe.\n\n"
                "💡 *Any session created AFTER enabling this protection will be terminated instantly.*"
            )
            
            buttons = [
                [
                    Button.inline("🟢 Enable", "sd:enable") if not is_enabled else Button.inline("🔴 Disable", "sd:disable")
                ],
                [
                    Button.inline("📋 View Logs", "sd:logs"),
                    Button.inline("🔙 Back", "menu:protection") # Protection Manager menu
                ]
            ]
            
            if message_id:
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            else:
                await self.bot.send_message(user_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing Session Destroyer submenu: {e}")

    async def handle_callback(self, event, user_id: int, data: str):
        """Handle sd: callbacks"""
        try:
            if data == "sd:enable":
                await self._enable_protection(event, user_id)
            elif data == "sd:disable":
                await self._disable_protection(event, user_id)
            elif data == "sd:logs":
                await self._show_logs(event, user_id)
            elif data == "sd:main":
                await self.show_submenu(user_id, event.message_id)
        except Exception as e:
            logger.error(f"Error in Session Destroyer callback: {e}")
            await event.answer("⚠️ Error processing request")

    async def _enable_protection(self, event, user_id: int):
        """Enable protection and sync trusted sessions"""
        protection_manager = getattr(
            self.menu.account_manager, "protection_manager", None
        )
        if not protection_manager:
            await event.answer("❌ Protection service unavailable", alert=True)
            return
        await protection_manager.toggle_session_destroyer(user_id, True)
        await event.answer("✅ Session Destroyer Enabled", alert=True)
        await self.show_submenu(user_id, event.message_id)

    async def _disable_protection(self, event, user_id: int):
        """Disable protection"""
        protection_manager = getattr(
            self.menu.account_manager, "protection_manager", None
        )
        if not protection_manager:
            await event.answer("❌ Protection service unavailable", alert=True)
            return
        await protection_manager.toggle_session_destroyer(user_id, False)
        await event.answer("🔴 Session Destroyer Disabled", alert=True)
        await self.show_submenu(user_id, event.message_id)

    async def _show_logs(self, event, user_id: int):
        """Show recent destruction logs"""
        logs = await SessionDestroyerDB.get_logs(user_id)
        if not logs:
            await event.answer("📋 No logs found.", alert=True)
            return
            
        text = "📋 **Security Audit Log**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for log in logs:
            status = "✅ Terminated" if log.get("success") else "❌ Failed"
            timestamp = log.get("timestamp")
            ts = (
                timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if hasattr(timestamp, "strftime")
                else "Unknown time"
            )
            text += (
                f"📅 {ts}\n"
                f"🖥 {log.get('device', 'Unknown')} ({log.get('platform', 'Unknown')})\n"
                f"🌍 {log.get('country', 'Unknown')} | IP: {log.get('ip', 'Unknown')}\n"
                f"🛡 Status: {status}\n\n"
            )
            
        buttons = [[Button.inline("🔙 Back", "sd:main")]]
        await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
