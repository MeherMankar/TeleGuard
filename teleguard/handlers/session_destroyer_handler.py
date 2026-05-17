"""
Session Destroyer Handler
UI handlers for the Session Destroyer feature.
"""

import logging
from typing import Optional
from telethon import Button, events

from ..sync.session_destroyer_db import SessionDestroyerDB
from ..services.session_destroyer_service import SessionDestroyerService
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class SessionDestroyerHandler:
    """Handles UI and callbacks for Session Destroyer"""

    def __init__(self, menu_system):
        self.menu = menu_system
        self.bot = menu_system.bot
        self.service = SessionDestroyerService(self.menu.account_manager)

    async def show_submenu(self, user_id: int, message_id: Optional[int] = None):
        """Show the Session Destroyer submenu"""
        try:
            settings = await SessionDestroyerDB.get_settings(user_id)
            stats = await SessionDestroyerDB.get_stats(user_id)
            
            is_enabled = settings.get("enabled", False)
            status_text = "🟢 Enabled" if is_enabled else "🔴 Disabled"
            
            text = (
                "🔥 **Session Destroyer**\n\n"
                f"**Status:** {status_text}\n"
                f"**Protected Accounts:** {stats['protected_accounts']}\n\n"
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
        await event.answer("⏳ Enabling protection and syncing sessions...", alert=False)
        
        # 1. Update settings
        await SessionDestroyerDB.update_settings(user_id, True)
        
        # 2. Sync trusted sessions for all active accounts
        from ..utils.crypto_utils import DataEncryption
        
        accounts_enc = await mongodb.db.accounts.find({"user_id": user_id, "is_active": True}).to_list(length=None)
        synced_count = 0
        for acc_doc in accounts_enc:
            account = DataEncryption.decrypt_account_data(acc_doc)
            client = self.menu.account_manager.get_client(user_id, account)
            
            # Auto-load/start client if not in memory
            if not client:
                try:
                    session_str = account.get("session_string")
                    acc_name = account.get("name")
                    if session_str and acc_name:
                        logger.info(f"Starting disconnected client {acc_name} during trust sync...")
                        await self.menu.account_manager._start_user_client(user_id, acc_name, session_str)
                        client = self.menu.account_manager.get_client(user_id, account)
                except Exception as start_err:
                    logger.error(f"Failed to start client {account.get('name')} during trust sync: {start_err}")
            
            # Auto-connect if loaded but disconnected
            if client and not client.is_connected():
                try:
                    await client.connect()
                except Exception as conn_err:
                    logger.error(f"Failed to connect client {account.get('name')} during trust sync: {conn_err}")
            
            if client and client.is_connected():
                await self.service.sync_trusted_sessions(user_id, str(account["_id"]), client)
                synced_count += 1
        
        await event.answer(f"✅ Session Destroyer Enabled!\nSynced {synced_count} accounts.", alert=True)
        await self.show_submenu(user_id, event.message_id)

    async def _disable_protection(self, event, user_id: int):
        """Disable protection"""
        await SessionDestroyerDB.update_settings(user_id, False)
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
            ts = log["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            text += (
                f"📅 {ts}\n"
                f"🖥 {log['device']} ({log['platform']})\n"
                f"🌍 {log['country']} | IP: {log['ip']}\n"
                f"🛡 Status: {status}\n\n"
            )
            
        buttons = [[Button.inline("🔙 Back", "sd:main")]]
        await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
