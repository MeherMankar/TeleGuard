"""Minimal menu system - delegates to modules
Developed by: @Meher_Mankar, @Gutkesh
GitHub: https://github.com/mehermankar/teleguard
"""
import logging
from typing import List, Optional
from telethon import Button
from ..core.mongo_database import mongodb
from .secure_2fa_handlers import Secure2FAHandlers
from .missing_handlers import register_missing_handlers
from ..utils.network_helpers import format_display_name, format_phone_number
from .menu_callbacks import AccountCallbacks, OTPCallbacks, MessagingCallbacks, CleanupCallbacks, HelpCallbacks
from .menu_modules import MenuBuilders, MenuHandlers, CallbackRouter, AccountOperations, CallbackHandlers, UtilityHelpers, CleanupOperations, ProfileOperations, MessagingOperations, EventSetup

logger = logging.getLogger(__name__)

class MenuSystem:
    def __init__(self, bot_instance, account_manager=None):
        self.bot = bot_instance
        self.account_manager = account_manager
        self.secure_2fa_handlers = Secure2FAHandlers(bot_instance, account_manager)
        self.missing_handlers = None
        self._menu_text_handler = None
        self._callback_handler = None
        # Initialize all modules
        self.builders = MenuBuilders(self)
        self.handlers = MenuHandlers(self)
        self.router = CallbackRouter(self)
        self.account_ops = AccountOperations(self)
        self.callback_handlers = CallbackHandlers(self)
        self.cleanup_ops = CleanupOperations(self)
        self.profile_ops = ProfileOperations(self)
        self.messaging_ops = MessagingOperations(self)
        self.event_setup = EventSetup(self)
        self.account_callbacks = AccountCallbacks(bot_instance, account_manager, self)
        self.otp_callbacks = OTPCallbacks(bot_instance, account_manager, self)
        self.messaging_callbacks = MessagingCallbacks(bot_instance, account_manager, self)
        self.cleanup_callbacks = CleanupCallbacks(bot_instance, account_manager, self)
        self.help_callbacks = HelpCallbacks(bot_instance, account_manager, self)
    
    # Utility delegations
    def _parse_callback(self, callback_data): return UtilityHelpers.parse_callback(callback_data)
    def format_display_name(self, account): return UtilityHelpers.format_display_name(account)
    def get_main_menu_keyboard(self, user_id): return self.builders.get_main_menu_keyboard(user_id)
    def get_account_menu_buttons(self, account_id, account=None): return self.builders.get_account_menu_buttons(account_id, account)
    def get_otp_account_buttons(self, account_id, account): return self.builders.get_otp_account_buttons(account_id, account)
    
    # Account operations delegations
    async def send_account_management(self, user_id, account_id, edit_message_id=None): await self.account_ops.send_account_management(user_id, account_id, edit_message_id)
    async def send_otp_account_management(self, user_id, account_id, edit_message_id=None): await self.account_ops.send_otp_account_management(user_id, account_id, edit_message_id)
    async def send_audit_log(self, user_id, account_id): await self.account_ops.send_audit_log(user_id, account_id)
    
    # Callback handler delegations
    async def _handle_otp_callback(self, event, user_id, data): await self.callback_handlers.handle_otp_callback(event, user_id, data)
    async def _handle_online_callback(self, event, user_id, data): await self.callback_handlers.handle_online_callback(event, user_id, data)
    async def _handle_simulate_callback(self, event, user_id, data): await self.callback_handlers.handle_simulate_callback(event, user_id, data)
    
    # Cleanup operations delegations
    async def _send_cleanup_selection(self, user_id, message_id, account_id): await self.cleanup_ops.send_cleanup_selection(user_id, message_id, account_id)
    async def _execute_cleanup(self, event, user_id, account_id, cleanup_types): await self.cleanup_ops.execute_cleanup(event, user_id, account_id, cleanup_types)
    
    # Profile operations delegations
    async def _send_profile_management(self, user_id, account_id, message_id): await self.profile_ops.send_profile_management(user_id, account_id, message_id)
    
    # Messaging operations delegations
    async def _send_message_menu(self, user_id, message_id): await self.messaging_ops.send_message_menu(user_id, message_id)
    async def _send_autoreply_menu(self, user_id, message_id): await self.messaging_ops.send_autoreply_menu(user_id, message_id)
    async def _send_templates_menu(self, user_id, message_id): await self.messaging_ops.send_templates_menu(user_id, message_id)
    async def _send_bulk_sender_menu(self, user_id, message_id): await self.messaging_ops.send_bulk_sender_menu(user_id, message_id)
    
    async def send_main_menu(self, user_id):
        await self._cleanup_old_messages(user_id)
        keyboard = self.get_main_menu_keyboard(user_id)
        text = "🤖 **TeleGuard Account Manager**\n\n🛡️ Professional Telegram security & automation\n\nUse the menu buttons below to get started:"
        message = await self.bot.send_message(user_id, text, buttons=keyboard)
        await mongodb.db.users.update_one({"telegram_id": user_id}, {"$set": {"main_menu_message_id": message.id}}, upsert=True)
        return message.id
    
    async def _cleanup_old_messages(self, user_id):
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if user and user.get("main_menu_message_id"):
                try:
                    await self.bot.delete_messages(user_id, user["main_menu_message_id"])
                except:
                    pass
        except Exception as e:
            logger.debug(f"Cleanup old messages error: {e}")
    
    async def send_accounts_list(self, user_id, edit_message_id=None):
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        if not accounts:
            text = "📱 **Account Management**\n\nNo accounts found. Add your first account to get started.\n\nUse /add command or enable Developer Mode to add accounts."
        else:
            text = f"📱 **Account Management**\n\nYou have {len(accounts)} account(s):\n\n"
            for i, account in enumerate(accounts, 1):
                status = "✅" if account.get("is_active", False) else "❌"
                destroyer_status = "✅" if account.get("otp_destroyer_enabled", False) else "❌"
                display_name = format_display_name(account)
                phone = format_phone_number(account.get('phone', 'Unknown'))
                text += f"{i}. {status}{destroyer_status} {display_name} ({phone})\n"
            text += "\nUse /accs to list accounts or /add to add more."
        await self.bot.send_message(user_id, text)
    
    def register_handlers(self): self.setup_menu_handlers()
    
    def setup_menu_handlers(self):
        register_missing_handlers(self)
        if self._menu_text_handler:
            self.bot.remove_event_handler(self._menu_text_handler)
        if self._callback_handler:
            self.bot.remove_event_handler(self._callback_handler)
        self.event_setup.setup_text_handlers()
        self.event_setup.setup_callback_handler()
    
    # Placeholder methods that delegate or need minimal implementation
    async def _handle_account_settings(self, event): await self.handlers.handle_account_settings(event)
    async def _handle_otp_manager(self, event): await self.handlers.handle_otp_manager(event)
    async def _handle_messaging(self, event): await self.handlers.handle_messaging(event)
    async def _handle_channels(self, event): await self.handlers.handle_channels(event)
    async def _handle_cleanup(self, event): await self.handlers.handle_cleanup(event)
    async def _handle_help(self, event): await self.handlers.handle_help(event)
    async def _handle_support(self, event): await self.handlers.handle_support(event)
    async def _handle_developer(self, event): await self.handlers.handle_developer(event)
    
    # Stub methods - implement as needed or delegate to existing handlers
    async def _handle_dm_reply(self, event): pass
    async def _handle_contacts(self, event): pass
    async def _handle_spam_master(self, event): pass
    async def _handle_2fa_callback(self, event, user_id, data): pass
    async def _handle_profile_callback(self, event, user_id, data): pass
    async def _handle_sessions_callback(self, event, user_id, data): pass
    async def _handle_audit_callback(self, event, user_id, data): pass
    async def _handle_channel_callback(self, event, user_id, data): pass
    async def _handle_cleanup_callback(self, event, user_id, data): pass
    async def _handle_messaging_callback(self, event, user_id, data): pass
    async def _handle_help_callback(self, event, user_id, data): pass
    async def _handle_support_callback(self, event, user_id, data): pass
    async def _handle_developer_callback(self, event, user_id, data): pass
    async def _handle_otp_setting_callback(self, event, user_id, data): pass
    async def _handle_add_account(self, event, user_id): pass
    async def _handle_remove_account(self, event, user_id): pass
    async def _send_channel_actions_menu(self, user_id, account_phone, message_id): pass
    async def _show_channel_statistics(self, user_id, message_id): pass
    async def _handle_bulk_otp_enable(self, user_id, message_id): pass
    async def _handle_bulk_otp_disable(self, user_id, message_id): pass
    async def _show_otp_statistics(self, user_id, message_id): pass
    async def _show_global_audit_log(self, user_id, message_id): pass
    async def _show_messaging_statistics(self, user_id, message_id): pass
    async def _show_message_history(self, user_id, message_id): pass
    async def _show_messaging_settings(self, user_id, message_id): pass
