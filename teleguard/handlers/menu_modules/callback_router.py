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
        elif data.startswith("contacts:") or data.startswith("sync:"):
            await self._route_contacts(event, user_id, data)
        elif data.startswith("menu:"):
            await self._route_menu(event, user_id, data)
        elif data.startswith("help:") or data.startswith("support:") or data.startswith("dev:"):
            await self._route_system(event, user_id, data)
        elif data in ["session_login", "import_sessions", "export_sessions", "validate_session"]:
            await self._route_session(event, user_id, data)
        else:
            await event.answer("Action processed", alert=False)
    
    async def _route_account(self, event, user_id, data):
        if data == "account:add":
            await self.menu._handle_add_account(event, user_id)
        elif data.startswith("account:manage:"):
            account_id = data.split(":")[2]
            await self.menu.send_account_management(user_id, account_id, event.message_id)
        elif data == "account:list":
            await self.menu._handle_account_settings(type("Event", (), {"sender_id": user_id, "reply": lambda x, buttons=None: self.menu.bot.send_message(user_id, x, buttons=buttons)})())
        elif data == "account:remove":
            await self.menu._handle_remove_account(event, user_id)
        elif data == "account:refresh":
            await self.menu._handle_account_settings(type("Event", (), {"sender_id": user_id, "reply": lambda x, buttons=None: self.menu.bot.edit_message(user_id, event.message_id, x, buttons=buttons)})())
    
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
            text = "🔍 **Search Channels**\n\nChannel search functionality:\n\n• Search by name or username\n• Filter by type (channel/group)\n• Browse popular channels\n• Find recommended channels\n\nFeature coming soon!"
            buttons = [[self.menu.bot.Button.inline("🔙 Back to Channels", "menu:channels")]]
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
            await self.menu.missing_handlers.handle_session_login(event, user_id)
        elif data == "import_sessions":
            await self.menu.missing_handlers.handle_import_sessions(event, user_id)
        elif data == "export_sessions":
            session_handler = None
            if hasattr(self.menu.account_manager, 'bot_manager') and hasattr(self.menu.account_manager.bot_manager, 'session_login_handler'):
                session_handler = self.menu.account_manager.bot_manager.session_login_handler
            elif hasattr(self.menu.account_manager, 'session_login_handler'):
                session_handler = self.menu.account_manager.session_login_handler
            if session_handler:
                await session_handler._start_session_creation(event, user_id)
            else:
                await event.answer("❌ Session creation not available")
        elif data == "validate_session":
            if self.menu.account_manager:
                self.menu.account_manager.pending_actions[user_id] = {"action": "validate_session_string"}
                text = "🔍 **Session String Validator**\n\nReply with a session string to validate and see DC information (DC1, DC2, DC3, DC4, or DC5):"
                await self.menu.bot.send_message(user_id, text)
                await event.answer("🔍 Send session string to validate")
