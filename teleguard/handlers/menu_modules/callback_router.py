"""Callback routing logic"""
import logging

logger = logging.getLogger(__name__)

class CallbackRouter:
    def __init__(self, menu_system):
        self.menu = menu_system
    
    async def route_callback(self, event, user_id, data):
        """Route callback to appropriate handler"""
        if data.startswith("account:"):
            await self._route_account(event, user_id, data)
        elif data.startswith("otp:") or data.startswith("otp_setting:"):
            await self._route_otp(event, user_id, data)
        elif data.startswith("2fa:"):
            await self.menu._handle_2fa_callback(event, user_id, data)
        elif data.startswith("profile:"):
            await self.menu._handle_profile_callback(event, user_id, data)
        elif data.startswith("sessions:"):
            await self.menu._handle_sessions_callback(event, user_id, data)
        elif data.startswith("online:"):
            await self.menu._handle_online_callback(event, user_id, data)
        elif data.startswith("msg:"):
            await self._route_messaging(event, user_id, data)
        elif data.startswith("simulate:"):
            await self.menu._handle_simulate_callback(event, user_id, data)
        elif data.startswith("channel:"):
            await self._route_channel(event, user_id, data)
        elif data.startswith("cleanup:"):
            await self.menu._handle_cleanup_callback(event, user_id, data)
        elif data.startswith("remove:"):
            await self.menu.callback_handlers.handle_remove_callback(event, user_id, data)
        elif data.startswith("contacts:") or data.startswith("sync:"):
            await self._route_contacts(event, user_id, data)
        elif data.startswith("menu:"):
            await self._route_menu(event, user_id, data)
        elif data.startswith("help:") or data.startswith("support:") or data.startswith("dev:"):
            await self._route_system(event, user_id, data)
        elif data in ["session_login", "import_sessions", "export_sessions", "validate_session"] or data.startswith(("export_session:", "export_string:", "export_file:", "export_fresh:", "export_all_sessions")):
            await self._route_session(event, user_id, data)
        else:
            await event.answer("Action processed", alert=False)
    
    async def _route_account(self, event, user_id, data):
        await self.menu.callback_handlers.handle_account_callback(event, user_id, data)
    
    async def _route_otp(self, event, user_id, data):
        if data.startswith("otp_setting:"):
            await self.menu._handle_otp_setting_callback(event, user_id, data)
        elif data.startswith("otp:manage:"):
            account_id = data.split(":")[2]
            await self.menu.send_otp_account_management(user_id, account_id, event.message_id)
        elif data == "otp:enable_all":
            await self.menu._handle_bulk_otp_enable(user_id, event.message_id)
            await event.answer("🛡️ Bulk enable completed")
        elif data == "otp:disable_all":
            await self.menu._handle_bulk_otp_disable(user_id, event.message_id)
            await event.answer("🔴 Bulk disable completed")
        elif data == "otp:stats":
            await self.menu._show_otp_statistics(user_id, event.message_id)
            await event.answer("📊 OTP statistics")
        else:
            await self.menu._handle_otp_callback(event, user_id, data)
    
    async def _route_messaging(self, event, user_id, data):
        parts = data.split(":")
        action = parts[1]
        if action == "send":
            await self.menu._send_message_menu(user_id, event.message_id)
        elif action == "autoreply":
            await self.menu._send_autoreply_menu(user_id, event.message_id)
        elif action == "templates":
            await self.menu._send_templates_menu(user_id, event.message_id)
        elif action == "stats":
            await self.menu._show_messaging_statistics(user_id, event.message_id)
            await event.answer("📊 Messaging stats loaded")
        elif action == "history":
            await self.menu._show_message_history(user_id, event.message_id)
            await event.answer("📋 Message history loaded")
        elif action == "settings":
            await self.menu._show_messaging_settings(user_id, event.message_id)
            await event.answer("⚙️ Messaging settings loaded")
        elif action == "bulk":
            await self.menu._send_bulk_sender_menu(user_id, event.message_id)
        else:
            await self.menu._handle_messaging_callback(event, user_id, data)
    
    async def _route_channel(self, event, user_id, data):
        parts = data.split(":")
        action = parts[1]
        if action == "select" and len(parts) > 2:
            account_phone = parts[2]
            await self.menu._send_channel_actions_menu(user_id, account_phone, event.message_id)
        elif action == "stats":
            await self.menu._show_channel_statistics(user_id, event.message_id)
            await event.answer("📊 Statistics loaded")
        elif action == "search":
            from telethon import Button
            text = "🔍 **Search Channels**\n\nChannel search functionality:\n\n• Search by name or username\n• Filter by type (channel/group)\n• Browse popular channels\n• Find recommended channels\n\nFeature coming soon!"
            buttons = [[Button.inline("🔙 Back to Channels", "menu:channels")]]
            await self.menu.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            await event.answer("🔍 Search feature")
        else:
            await self.menu._handle_channel_callback(event, user_id, data)
    
    async def _route_contacts(self, event, user_id, data):
        if data.startswith("contacts:"):
            await self.menu._handle_contacts_callback(event, user_id, data)
        elif data.startswith("sync:"):
            await self.menu._handle_sync_callback(event, user_id, data)
    
    async def _route_menu(self, event, user_id, data):
        if data == "menu:accounts":
            await self.menu.handlers.handle_account_settings(type("Event", (), {"sender_id": user_id})())
        elif data == "menu:otp":
            await self.menu.handlers.handle_otp_manager(type("Event", (), {"sender_id": user_id})())
        elif data == "menu:messaging":
            await self.menu.handlers.handle_messaging(type("Event", (), {"sender_id": user_id})())
        elif data == "menu:channels":
            await self.menu.handlers.handle_channels(type("Event", (), {"sender_id": user_id})())
        elif data == "menu:cleanup":
            await self.menu.handlers.handle_cleanup(type("Event", (), {"sender_id": user_id})())
        elif data == "menu:help":
            await self.menu.handlers.handle_help(type("Event", (), {"sender_id": user_id})())
        elif data == "menu:support":
            await self.menu.handlers.handle_support(type("Event", (), {"sender_id": user_id})())
        elif data == "menu:developer":
            await self.menu.handlers.handle_developer(type("Event", (), {"sender_id": user_id})())
        elif data == "menu:main":
            await self.menu.send_main_menu(user_id)
    
    async def _route_system(self, event, user_id, data):
        if data.startswith("help:"):
            await self.menu._handle_help_callback(event, user_id, data)
        elif data.startswith("support:"):
            await self.menu._handle_support_callback(event, user_id, data)
        elif data.startswith("dev:"):
            await self.menu._handle_developer_callback(event, user_id, data)
    
    async def _route_session(self, event, user_id, data):
        if data == "session_login":
            await self._handle_session_login(event, user_id)
        elif data == "import_sessions":
            await self._handle_import_sessions(event, user_id)
        elif data == "export_sessions":
            await self._handle_export_sessions(event, user_id)
        elif data == "validate_session":
            await self._handle_validate_session(event, user_id)
        elif data == "export_all_sessions":
            await self._handle_export_all_sessions(event, user_id)
        elif data.startswith("export_session:"):
            account_name = data.split(":")[1]
            await self._handle_export_session_select(event, user_id, account_name)
        elif data.startswith("export_string:"):
            account_name = data.split(":")[1]
            await self._handle_export_string_session(event, user_id, account_name)
        elif data.startswith("export_file:"):
            account_name = data.split(":")[1]
            await self._handle_export_file_session(event, user_id, account_name)
        elif data.startswith("export_fresh:"):
            account_name = data.split(":")[1]
            await self._handle_export_fresh_session(event, user_id, account_name)
    
    async def _handle_session_login(self, event, user_id):
        """Handle session login"""
        try:
            if hasattr(self.menu.account_manager, 'session_login_handler'):
                await self.menu.account_manager.session_login_handler._start_session_creation(event, user_id)
            else:
                await event.answer("❌ Session login not available")
        except Exception as e:
            logger.error(f"Session login error: {e}")
            await event.answer("❌ Error starting session login")
    
    async def _handle_import_sessions(self, event, user_id):
        """Handle session import"""
        try:
            from telethon import Button
            text = "📥 **Import Sessions**\n\nSession import functionality:\n\n• Import .session files\n• Import session strings\n• Bulk session import\n• Session validation\n\nFeature coming soon!"
            buttons = [[Button.inline("🔙 Back to Accounts", "menu:accounts")]]
            await self.menu.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            await event.answer("📥 Import feature")
        except Exception as e:
            logger.error(f"Import sessions error: {e}")
    
    async def _handle_export_sessions(self, event, user_id):
        """Handle session export menu"""
        try:
            from telethon import Button
            from ...core.mongo_database import mongodb
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            if not accounts:
                text = "✨ **Fresh Sessions**\n\n❌ No accounts found. Add accounts first to create fresh sessions."
                buttons = [[Button.inline("🔙 Back to Accounts", "menu:accounts")]]
            else:
                text = "✨ **Fresh Sessions**\n\nSelect account to create fresh session for:"
                buttons = []
                for account in accounts:
                    status = "🟢" if account.get("is_active", False) else "🔴"
                    display_name = self.menu.format_display_name(account)
                    buttons.append([Button.inline(f"{status} {display_name}", f"export_session:{account['name']}")])
                buttons.append([Button.inline("🔙 Back to Accounts", "menu:accounts")])
            await self.menu.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Export sessions error: {e}")
    
    async def _handle_validate_session(self, event, user_id):
        """Handle session validation"""
        try:
            if self.menu.account_manager:
                self.menu.account_manager.pending_actions[user_id] = {"action": "validate_session_string"}
                text = "🔍 **Session String Validator**\n\nReply with a session string to validate and see DC information (DC1, DC2, DC3, DC4, or DC5):"
                await self.menu.bot.send_message(user_id, text)
                await event.answer("🔍 Send session string to validate")
        except Exception as e:
            logger.error(f"Validate session error: {e}")
    
    async def _handle_export_session_select(self, event, user_id, account_name):
        """Handle export session selection"""
        try:
            from ...core.mongo_database import mongodb
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            if not account:
                await event.answer("❌ Account not found")
                return
            display_name = self.menu.format_display_name(account)
            text = f"✨ **Fresh Session: {display_name}**\n\nThis will create a completely new session:"
            from telethon import Button
            buttons = [
                [Button.inline("✨ Create Fresh Session", f"export_fresh:{account_name}")],
                [Button.inline("🔙 Back to Export", "export_sessions")]
            ]
            await self.menu.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Export session select error: {e}")
    
    async def _handle_export_fresh_session(self, event, user_id, account_name):
        """Handle fresh session creation"""
        try:
            if hasattr(self.menu.account_manager, 'session_export_handler'):
                await self.menu.account_manager.session_export_handler._create_fresh_session(event, user_id, account_name, 'both')
            else:
                await event.answer("❌ Session export not available")
        except Exception as e:
            logger.error(f"Export fresh session error: {e}")
            await event.answer("❌ Error creating fresh session")
    
    async def _handle_export_all_sessions(self, event, user_id):
        """Handle export all sessions"""
        try:
            if hasattr(self.menu.account_manager, 'session_export_handler'):
                await self.menu.account_manager.session_export_handler._export_all_sessions(event, user_id)
            else:
                await event.answer("❌ Session export not available")
        except Exception as e:
            logger.error(f"Export all sessions error: {e}")
            await event.answer("❌ Error exporting sessions")
    
    async def _handle_export_string_session(self, event, user_id, account_name):
        """Handle export string session"""
        try:
            if hasattr(self.menu.account_manager, 'session_export_handler'):
                await self.menu.account_manager.session_export_handler._create_fresh_session(event, user_id, account_name, 'string')
            else:
                await event.answer("❌ Session export not available")
        except Exception as e:
            logger.error(f"Export string session error: {e}")
            await event.answer("❌ Error creating string session")
    
    async def _handle_export_file_session(self, event, user_id, account_name):
        """Handle export file session"""
        try:
            if hasattr(self.menu.account_manager, 'session_export_handler'):
                await self.menu.account_manager.session_export_handler._create_fresh_session(event, user_id, account_name, 'file')
            else:
                await event.answer("❌ Session export not available")
        except Exception as e:
            logger.error(f"Export file session error: {e}")
            await event.answer("❌ Error creating session file")
