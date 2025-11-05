"""Inline menu system for account management
Developed by:
- @Meher_Mankar
- @Gutkesh
GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""
import json
import logging
from typing import List, Optional
from telethon import Button, events
from ..core.config import ADMIN_IDS
from ..core.mongo_database import mongodb
from .secure_2fa_handlers import Secure2FAHandlers
from .missing_handlers import MissingHandlers, register_missing_handlers
from ..utils.network_helpers import format_display_name, format_phone_number
from .menu_callbacks import (
    AccountCallbacks, OTPCallbacks, MessagingCallbacks,
    CleanupCallbacks, HelpCallbacks
)
from .menu_modules import MenuBuilders, MenuHandlers, CallbackRouter, AccountOperations, CallbackHandlers, UtilityHelpers
logger = logging.getLogger(__name__)
class MenuSystem:
    """Handles inline keyboard menus and callback queries"""
    def __init__(self, bot_instance, account_manager=None):
        self.bot = bot_instance
        self.account_manager = account_manager
        self.secure_2fa_handlers = Secure2FAHandlers(bot_instance, account_manager)
        self.missing_handlers = None
        self._menu_text_handler = None
        self._callback_handler = None
        # Initialize modular components
        self.builders = MenuBuilders(self)
        self.handlers = MenuHandlers(self)
        self.router = CallbackRouter(self)
        self.account_ops = AccountOperations(self)
        self.callback_handlers = CallbackHandlers(self)
        # Initialize modular callbacks
        self.account_callbacks = AccountCallbacks(bot_instance, account_manager, self)
        self.otp_callbacks = OTPCallbacks(bot_instance, account_manager, self)
        self.messaging_callbacks = MessagingCallbacks(bot_instance, account_manager, self)
        self.cleanup_callbacks = CleanupCallbacks(bot_instance, account_manager, self)
        self.help_callbacks = HelpCallbacks(bot_instance, account_manager, self)
    def _parse_callback(self, callback_data: str):
        """Parse callback data - handles both JSON and colon-delimited formats"""
        return UtilityHelpers.parse_callback(callback_data)
    def format_display_name(self, account):
        """Format display name from account object or DB record"""
        return UtilityHelpers.format_display_name(account)
    def get_main_menu_keyboard(self, user_id: int) -> List[List[Button]]:
        """Get enhanced persistent reply keyboard menu"""
        return self.builders.get_main_menu_keyboard(user_id)
    
    async def send_main_menu(self, user_id: int) -> int:
        """Send persistent reply keyboard menu"""
        try:
            # Delete previous menu messages to avoid collision
            await self._cleanup_old_messages(user_id)
            
            keyboard = self.get_main_menu_keyboard(user_id)
            text = (
                "ðŸ¤– **TeleGuard Account Manager**\n\n"
                "ðŸ›¡ï¸ Professional Telegram security & automation\n\n"
                "Use the menu buttons below to get started:"
            )
            message = await self.bot.send_message(user_id, text, buttons=keyboard)
            # Store menu message ID in MongoDB
            await mongodb.db.users.update_one(
                {"telegram_id": user_id},
                {"$set": {"main_menu_message_id": message.id}},
                upsert=True,
            )
            return message.id
        except Exception as e:
            logger.error(f"Failed to send main menu: {e}")
            return 0
    def get_account_menu_buttons(self, account_id: str, account=None) -> List[List[Button]]:
        """Get account-specific menu buttons"""
        return self.builders.get_account_menu_buttons(account_id, account)
    def get_otp_account_buttons(self, account_id: str, account) -> List[List[Button]]:
        """Get OTP account management buttons"""
        return self.builders.get_otp_account_buttons(account_id, account)
    async def _cleanup_old_messages(self, user_id: int):
        """Delete old menu messages to prevent collision"""
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if user and user.get("main_menu_message_id"):
                try:
                    await self.bot.delete_messages(user_id, user["main_menu_message_id"])
                except:
                    pass  # Message might already be deleted
        except Exception as e:
            logger.debug(f"Cleanup old messages error: {e}")
    async def send_accounts_list(
        self, user_id: int, edit_message_id: Optional[int] = None
    ):
        """Send accounts list with management options"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = "ðŸ“± **Account Management**\n\nNo accounts found. Add your first account to get started.\n\nUse /add command or enable Developer Mode to add accounts."
            else:
                text = f"ðŸ“± **Account Management**\n\nYou have {len(accounts)} account(s):\n\n"
                for i, account in enumerate(accounts, 1):
                    status = "âœ…" if account.get("is_active", False) else "âŒ"
                    destroyer_status = (
                        "âœ…" if account.get("otp_destroyer_enabled", False) else "âŒ"
                    )
                    display_name = format_display_name(account)
                    phone = format_phone_number(account.get('phone', 'Unknown'))
                    text += f"{i}. {status}{destroyer_status} {display_name} ({phone})\n"
                text += "\nUse /accs to list accounts or /add to add more."
            await self.bot.send_message(user_id, text)
        except Exception as e:
            logger.error(f"Failed to send accounts list: {e}")
    async def send_account_management(self, user_id: int, account_id: str, edit_message_id: Optional[int] = None):
        """Send account management menu"""
        await self.account_ops.send_account_management(user_id, account_id, edit_message_id)
    async def send_otp_account_management(self, user_id: int, account_id: str, edit_message_id: Optional[int] = None):
        """Send OTP account management menu"""
        await self.account_ops.send_otp_account_management(user_id, account_id, edit_message_id)
    async def send_audit_log(self, user_id: int, account_id: str):
        """Send audit log for account"""
        await self.account_ops.send_audit_log(user_id, account_id)
    def register_handlers(self):
        """Register menu handlers - called during bot initialization"""
        self.setup_menu_handlers()
    
    def setup_menu_handlers(self):
        """Set up menu text handlers and legacy callback handler - delegated to handler_setup module"""
        from teleguard_modular.handlers.handler_setup import (
            setup_menu_text_handler,
            setup_cleanup_selection_handler,
            setup_callback_handler
        )
        
        # Register missing handlers
        register_missing_handlers(self)
        
        # Clear existing handlers to prevent duplicates
        if self._menu_text_handler:
            self.bot.remove_event_handler(self._menu_text_handler)
        if self._callback_handler:
            self.bot.remove_event_handler(self._callback_handler)
        
        # Setup handlers using extracted module
        import asyncio
        loop = asyncio.get_event_loop()
        self._menu_text_handler = loop.run_until_complete(setup_menu_text_handler(self.bot, self))
        loop.run_until_complete(setup_cleanup_selection_handler(self.bot, self))
        self._callback_handler = loop.run_until_complete(setup_callback_handler(self.bot, self))
    
    async def _handle_account_settings(self, event):
        """Handle Account Settings menu - delegated to modular handler"""
        from teleguard_modular.menu_delegation import handle_account_settings
        await handle_account_settings(self.bot, event.sender_id, event)
    async def _handle_otp_manager(self, event):
        """Handle OTP Manager menu - delegated to modular handler"""
        from teleguard_modular.menu_delegation import handle_otp_manager
        await handle_otp_manager(self.bot, event.sender_id, event)
    async def _handle_messaging(self, event):
        """Handle Messaging menu - delegated to modular handler"""
        from teleguard_modular.menu_delegation import handle_messaging_menu
        await handle_messaging_menu(self.bot, event.sender_id, event)
    async def _handle_channels(self, event):
        """Handle Channels menu - delegated to modular handler"""
        from teleguard_modular.menu_delegation import handle_channels_menu
        await handle_channels_menu(self.bot, event.sender_id, event)
    async def _handle_contacts(self, event):
        """Handle Contacts menu - delegated to modular handler"""
        from teleguard_modular.menu_delegation import handle_contacts_menu
        await handle_contacts_menu(self.bot, event.sender_id, event, self.account_manager)
    
    async def _handle_spam_master(self, event):
        """Handle SpamMaster menu - redirect to advanced spam handler"""
        user_id = event.sender_id
        try:
            # Redirect to advanced spam handler
            if hasattr(self.account_manager, 'advanced_spam_handler'):
                await self.account_manager.advanced_spam_handler._handle_spam_master_menu(event)
            else:
                await event.reply("âŒ SpamMaster not available")
        except Exception as e:
            logger.error(f"Failed to handle SpamMaster menu: {e}")
            await event.reply("âŒ Error loading SpamMaster menu")
    
    async def _handle_cleanup(self, event):
        """Handle Cleanup menu"""
        user_id = event.sender_id
        try:
            # Delete previous messages to avoid collision
            await self._cleanup_old_messages(user_id)
            
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = (
                    "ðŸ§¹ **Professional Account Cleanup**\n"
                    "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\n"
                    "ðŸš¨ **No accounts available!**\n\n"
                    "You need active accounts to use cleanup features.\n\n"
                    "ðŸŽ¯ **Cleanup Capabilities:**\n"
                    "â€¢ ðŸ’¬ **Smart Chat Cleanup** - Personal, bot, official chats\n"
                    "â€¢ ðŸš« **Spam Removal** - Spambot and unwanted chats\n"
                    "â€¢ ðŸšª **Mass Exit** - Leave channels and groups\n"
                    "â€¢ ðŸ—‘ï¸ **Ownership Cleanup** - Delete owned channels/groups\n"
                    "â€¢ ðŸ“ž **Spam Appeals** - Automated appeal system\n\n"
                    "âš ï¸ **Important:** All cleanup actions are irreversible!\n\n"
                    "Add accounts to access cleanup tools:"
                )
                buttons = [
                    [Button.inline("ðŸš€ Add First Account", "account:add")],
                    [Button.inline("â“ Cleanup Guide", "help:features")],
                    [Button.inline("ðŸ”™ Back to Main Menu", "menu:main")],
                ]
            else:
                active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
                
                text = (
                    "ðŸ§¹ **Professional Account Cleanup**\n"
                    "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\n"
                    f"ðŸ“Š **System Status:**\n"
                    f"â€¢ ðŸ“± Active Accounts: {active_accounts}/{len(accounts)}\n"
                    f"â€¢ ðŸŸ¢ Cleanup Tools: Ready\n\n"
                    "âš ï¸ **CRITICAL WARNING:**\n"
                    "All cleanup actions are **PERMANENT** and **IRREVERSIBLE**!\n\n"
                    "ðŸŽ¯ **Available Cleanup Options:**\n"
                    "â€¢ ðŸ’¬ Personal chats â€¢ ðŸ¤– Bot conversations\n"
                    "â€¢ ðŸ“¢ Telegram official â€¢ ðŸš« Spambot chats\n"
                    "â€¢ ðŸšª Exit channels â€¢ ðŸ‘¥ Exit groups\n"
                    "â€¢ ðŸ—‘ï¸ Delete owned groups â€¢ ðŸ“º Delete owned channels\n\n"
                    "ðŸŽ›ï¸ **Select Account to Clean:**"
                )
                
                buttons = []
                for account in accounts:
                    status = "ðŸŸ¢" if account.get("is_active", False) else "ðŸ”´"
                    display_name = format_display_name(account)
                    button_text = f"{status} {display_name}"
                    buttons.append([Button.inline(button_text, f"cleanup:select:{account['_id']}")])
                
                buttons.append([Button.inline("ðŸ”™ Back to Main Menu", "menu:main")])
            if hasattr(event, 'message_id'):
                await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            else:
                await self.bot.send_message(user_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to handle cleanup: {e}")
            await event.reply("âŒ Error loading cleanup menu")
    
    async def _handle_cleanup_callback(self, event, user_id: int, data: str):
        """Handle account cleanup callbacks"""
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else "menu"
        
        if action == "menu":
            # Redirect to main cleanup handler
            await self._handle_cleanup(type("Event", (), {"sender_id": user_id, "reply": lambda x, buttons=None: self.bot.edit_message(user_id, event.message_id, x, buttons=buttons)})())
        elif action == "select":
            account_id = parts[2] if len(parts) > 2 else None
            if account_id:
                await self._send_cleanup_selection(user_id, event.message_id, account_id)
        elif action == "options":
            account_id = parts[2] if len(parts) > 2 else None
            cleanup_types = parts[3] if len(parts) > 3 else None
            if account_id and cleanup_types:
                try:
                    await self._send_cleanup_confirmation(user_id, event.message_id, account_id, cleanup_types)
                except Exception as e:
                    if "Content of the message was not modified" in str(e):
                        # Message content is the same, just answer the callback
                        await event.answer("âœ… Cleanup options confirmed")
                    else:
                        logger.error(f"Cleanup options error: {e}")
                        await event.answer("âŒ Error processing cleanup options")
        elif action == "confirm":
            account_id = parts[2] if len(parts) > 2 else None
            cleanup_types = parts[3] if len(parts) > 3 else None
            if account_id and cleanup_types:
                await self._execute_cleanup(event, user_id, account_id, cleanup_types)
        elif action == "appeal":
            account_id = parts[2] if len(parts) > 2 else None
            if account_id:
                await self._handle_spam_appeal(event, user_id, account_id)
        elif action == "spam_appeal_select":
            await self._handle_spam_appeal_select(event, user_id)
    

    
    async def _send_cleanup_selection(self, user_id: int, message_id: int, account_id: str):
        """Send cleanup type selection - delegated to CleanupOperations"""
        from .menu_modules import CleanupOperations
        ops = CleanupOperations(self)
        await ops.send_cleanup_selection(user_id, message_id, account_id)
    
    async def _send_cleanup_confirmation(self, user_id: int, message_id: int, account_id: str, cleanup_types: str):
        """Send cleanup confirmation with selected options"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                await self.bot.edit_message(user_id, message_id, "âŒ Account not found", buttons=[[Button.inline("ðŸ”™ Back", "cleanup:menu")]])
                return
            
            display_name = format_display_name(account)
            
            # Parse cleanup types
            cleanup_list = [t.strip().lower() for t in cleanup_types.split(',')]
            if 'all' in cleanup_list:
                cleanup_list = ['personal', 'bots', 'telegram', 'spambot', 'channels', 'groups', 'owned_groups', 'owned_channels']
            
            # Create display text for selected options
            selected_options = []
            if 'personal' in cleanup_list:
                selected_options.append("âœ… ðŸ’¬ Personal chats")
            if 'bots' in cleanup_list:
                selected_options.append("âœ… ðŸ¤– Bot chats")
            if 'telegram' in cleanup_list:
                selected_options.append("âœ… ðŸ“¢ Telegram official chats")
            if 'spambot' in cleanup_list:
                selected_options.append("âœ… ðŸš« Spambot chats")
            if 'channels' in cleanup_list:
                selected_options.append("âœ… ðŸšª Exit from channels")
            if 'groups' in cleanup_list:
                selected_options.append("âœ… ðŸ‘¥ Exit from groups")
            if 'owned_groups' in cleanup_list:
                selected_options.append("âœ… ðŸ—‘ï¸ Delete owned groups")
            if 'owned_channels' in cleanup_list:
                selected_options.append("âœ… ðŸ“º Delete owned channels")
            
            if not selected_options:
                await self.bot.send_message(user_id, "âŒ No valid cleanup options selected. Please try again.")
                return
            
            text = (
                f"ðŸ§¹ **Final Cleanup Confirmation**\n\n"
                f"ðŸ“± Account: {display_name}\n\n"
                f"**Selected cleanup actions:**\n"
                + "\n".join(selected_options) + "\n\n"
                f"âš ï¸ **FINAL WARNING**: This action cannot be undone!\n"
                f"All selected chats and data will be permanently deleted.\n\n"
                f"Are you absolutely sure you want to proceed?"
            )
            
            buttons = [
                [Button.inline("ðŸš€ YES, Start Cleanup", f"cleanup:confirm:{account_id}:{cleanup_types}")],
                [Button.inline("âŒ Cancel", "cleanup:menu")]
            ]
            
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in cleanup confirmation: {e}")
            await self.bot.edit_message(user_id, message_id, "âŒ Error loading cleanup confirmation", buttons=[[Button.inline("ðŸ”™ Back", "cleanup:menu")]])
    
    async def _execute_cleanup(self, event, user_id: int, account_id: str, cleanup_types: str):
        """Execute account cleanup - delegated to CleanupOperations"""
        from .menu_modules import CleanupOperations
        ops = CleanupOperations(self)
        await ops.execute_cleanup(event, user_id, account_id, cleanup_types)
    
    async def _handle_cleanup_selection_callback(self, event, user_id: int, data: str):
        """Handle cleanup selection text input"""
        try:
            # Check if this is a text message (not callback)
            if hasattr(event, 'text'):
                # This is a text message response
                if not hasattr(self.account_manager, 'pending_actions') or user_id not in self.account_manager.pending_actions:
                    await event.reply("âŒ No pending cleanup action found.")
                    return
                
                action_data = self.account_manager.pending_actions[user_id]
                if action_data.get('action') != 'cleanup_selection':
                    await event.reply("âŒ Invalid action state.")
                    return
                
                account_id = action_data.get('account_id')
                cleanup_types = event.text.strip().lower()
                
                # Clear pending action
                del self.account_manager.pending_actions[user_id]
                
                # Send confirmation as new message to avoid edit conflicts
                await self._send_cleanup_confirmation_new(user_id, account_id, cleanup_types)
            else:
                # This is a callback query - handle differently
                parts = data.split(":")
                if len(parts) >= 3:
                    account_id = parts[2]
                    cleanup_types = parts[3] if len(parts) > 3 else "all"
                    await self._send_cleanup_confirmation_new(user_id, account_id, cleanup_types)
            
        except Exception as e:
            logger.error(f"Error in cleanup selection callback: {e}")
            await event.reply("âŒ Error processing cleanup selection.")
    
    async def _send_cleanup_confirmation_new(self, user_id: int, account_id: str, cleanup_types: str):
        """Send cleanup confirmation as new message to avoid edit conflicts"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                await self.bot.send_message(user_id, "âŒ Account not found")
                return
            
            display_name = format_display_name(account)
            
            # Parse cleanup types
            cleanup_list = [t.strip().lower() for t in cleanup_types.split(',')]
            if 'all' in cleanup_list:
                cleanup_list = ['personal', 'bots', 'telegram', 'spambot', 'channels', 'groups', 'owned_groups', 'owned_channels']
            
            # Create display text for selected options
            selected_options = []
            if 'personal' in cleanup_list:
                selected_options.append("âœ… ðŸ’¬ Personal chats")
            if 'bots' in cleanup_list:
                selected_options.append("âœ… ðŸ¤– Bot chats")
            if 'telegram' in cleanup_list:
                selected_options.append("âœ… ðŸ“¢ Telegram official chats")
            if 'spambot' in cleanup_list:
                selected_options.append("âœ… ðŸš« Spambot chats")
            if 'channels' in cleanup_list:
                selected_options.append("âœ… ðŸšª Exit from channels")
            if 'groups' in cleanup_list:
                selected_options.append("âœ… ðŸ‘¥ Exit from groups")
            if 'owned_groups' in cleanup_list:
                selected_options.append("âœ… ðŸ—‘ï¸ Delete owned groups")
            if 'owned_channels' in cleanup_list:
                selected_options.append("âœ… ðŸ“º Delete owned channels")
            
            if not selected_options:
                await self.bot.send_message(user_id, "âŒ No valid cleanup options selected. Please try again with valid options: personal, bots, telegram, spambot, channels, groups, owned_groups, owned_channels, all")
                return
            
            text = (
                f"ðŸ§¹ **Final Cleanup Confirmation**\n\n"
                f"ðŸ“± Account: {display_name}\n\n"
                f"**Selected cleanup actions:**\n"
                + "\n".join(selected_options) + "\n\n"
                f"âš ï¸ **FINAL WARNING**: This action cannot be undone!\n"
                f"All selected chats and data will be permanently deleted.\n\n"
                f"Are you absolutely sure you want to proceed?"
            )
            
            buttons = [
                [Button.inline("ðŸš€ YES, Start Cleanup", f"cleanup:confirm:{account_id}:{cleanup_types}")],
                [Button.inline("âŒ Cancel", "cleanup:menu")]
            ]
            
            await self.bot.send_message(user_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in cleanup confirmation: {e}")
            await self.bot.send_message(user_id, "âŒ Error loading cleanup confirmation")
    
    async def _send_cleanup_confirmation(self, user_id: int, message_id: int, account_id: str, cleanup_types: str):
        """Send cleanup confirmation with selected options (legacy method for edit)"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                if message_id:
                    await self.bot.edit_message(user_id, message_id, "âŒ Account not found", buttons=[[Button.inline("ðŸ”™ Back", "cleanup:menu")]])
                else:
                    await self.bot.send_message(user_id, "âŒ Account not found")
                return
            
            display_name = format_display_name(account)
            
            # Parse cleanup types
            cleanup_list = [t.strip().lower() for t in cleanup_types.split(',')]
            if 'all' in cleanup_list:
                cleanup_list = ['personal', 'bots', 'telegram', 'spambot', 'channels', 'groups', 'owned_groups', 'owned_channels']
            
            # Create display text for selected options
            selected_options = []
            if 'personal' in cleanup_list:
                selected_options.append("âœ… ðŸ’¬ Personal chats")
            if 'bots' in cleanup_list:
                selected_options.append("âœ… ðŸ¤– Bot chats")
            if 'telegram' in cleanup_list:
                selected_options.append("âœ… ðŸ“¢ Telegram official chats")
            if 'spambot' in cleanup_list:
                selected_options.append("âœ… ðŸš« Spambot chats")
            if 'channels' in cleanup_list:
                selected_options.append("âœ… ðŸšª Exit from channels")
            if 'groups' in cleanup_list:
                selected_options.append("âœ… ðŸ‘¥ Exit from groups")
            if 'owned_groups' in cleanup_list:
                selected_options.append("âœ… ðŸ—‘ï¸ Delete owned groups")
            if 'owned_channels' in cleanup_list:
                selected_options.append("âœ… ðŸ“º Delete owned channels")
            
            if not selected_options:
                error_msg = "âŒ No valid cleanup options selected. Please try again with valid options: personal, bots, telegram, spambot, channels, groups, owned_groups, owned_channels, all"
                if message_id:
                    await self.bot.edit_message(user_id, message_id, error_msg, buttons=[[Button.inline("ðŸ”™ Back", "cleanup:menu")]])
                else:
                    await self.bot.send_message(user_id, error_msg)
                return
            
            text = (
                f"ðŸ§¹ **Final Cleanup Confirmation**\n\n"
                f"ðŸ“± Account: {display_name}\n\n"
                f"**Selected cleanup actions:**\n"
                + "\n".join(selected_options) + "\n\n"
                f"âš ï¸ **FINAL WARNING**: This action cannot be undone!\n"
                f"All selected chats and data will be permanently deleted.\n\n"
                f"Are you absolutely sure you want to proceed?"
            )
            
            buttons = [
                [Button.inline("ðŸš€ YES, Start Cleanup", f"cleanup:confirm:{account_id}:{cleanup_types}")],
                [Button.inline("âŒ Cancel", "cleanup:menu")]
            ]
            
            if message_id:
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            else:
                await self.bot.send_message(user_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in cleanup confirmation: {e}")
            error_msg = "âŒ Error loading cleanup confirmation"
            if message_id:
                try:
                    await self.bot.edit_message(user_id, message_id, error_msg, buttons=[[Button.inline("ðŸ”™ Back", "cleanup:menu")]])
                except:
                    await self.bot.send_message(user_id, error_msg)
            else:
                await self.bot.send_message(user_id, error_msg)
    
    async def _handle_spam_appeal_select(self, event, user_id: int):
        """Handle spam appeal account selection"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = "ðŸ“ž **Spam Appeal**\n\nâŒ No accounts found."
                buttons = [[Button.inline("ðŸ”™ Back", "cleanup:menu")]]
                await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                return
            
            text = (
                "ðŸ“ž **Spam Appeal**\n\n"
                "Select account to submit spam appeal:"
            )
            buttons = []
            for account in accounts:
                status = "ðŸŸ¢" if account.get("is_active", False) else "ðŸ”´"
                display_name = format_display_name(account)
                button_text = f"{status} {display_name}"
                buttons.append([Button.inline(button_text, f"appeal_account_id:{account['_id']}")])
            
            buttons.append([Button.inline("ðŸ”™ Back", "cleanup:menu")])
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in spam appeal select: {e}")
            await event.answer("âŒ Error loading spam appeal")
    
    async def _handle_spam_appeal(self, event, user_id: int, account_id: str):
        """Handle spam appeal for account before cleanup"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                await event.answer("âŒ Account not found")
                return
            
            display_name = format_display_name(account)
            
            # Check if spam appeal handler is available
            if hasattr(self.account_manager, 'spam_appeal_handler'):
                text = (
                    f"ðŸ“ž **Spam Appeal - {display_name}**\n\n"
                    f"ðŸ¤– **Smart Appeal System**\n\n"
                    f"Before cleaning your account, you can try appealing any spam restrictions.\n\n"
                    f"**Features:**\n"
                    f"â€¢ AI-powered message selection\n"
                    f"â€¢ Automatic @spambot interaction\n"
                    f"â€¢ Manual captcha verification\n"
                    f"â€¢ Smart detection of restriction types\n\n"
                    f"Would you like to start the appeal process?"
                )
                
                buttons = [
                    [Button.inline("ðŸš€ Start Appeal", f"appeal_account_id:{account_id}")],
                    [Button.inline("ðŸ§¹ Skip to Cleanup", f"cleanup:select:{account_id}")],
                    [Button.inline("ðŸ”™ Back to Menu", "cleanup:menu")]
                ]
                
                await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            else:
                text = (
                    f"ðŸ“ž **Manual Spam Appeal - {display_name}**\n\n"
                    f"Spam appeal system is not available.\n\n"
                    f"**Manual steps:**\n"
                    f"1. Go to @spambot\n"
                    f"2. Send /start\n"
                    f"3. Follow the appeal process\n"
                    f"4. Complete any captcha verification\n\n"
                    f"After appealing, you can return to cleanup if needed."
                )
                
                buttons = [
                    [Button.inline("ðŸ§¹ Continue to Cleanup", f"cleanup:select:{account_id}")],
                    [Button.inline("ðŸ”™ Back to Menu", "cleanup:menu")]
                ]
                
                await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in spam appeal: {e}")
            await event.answer("âŒ Error loading spam appeal")
    async def _handle_help(self, event):
        """Handle Help menu - delegated to modular handler"""
        from teleguard_modular.menu_delegation import handle_help_menu
        await handle_help_menu(self.bot, event.sender_id, event)
    async def _handle_support(self, event):
        """Handle Support menu - delegated to modular handler"""
        from teleguard_modular.menu_delegation import handle_support_menu
        await handle_support_menu(self.bot, event.sender_id, event)
    async def _get_account_age_info(self, user_id: int, account_name: str, account_data: dict = None) -> str:
        """Get account age information using ID-based estimation"""
        try:
            from ..utils.account_age_estimator import AccountAgeEstimator
            from datetime import timezone, datetime
            
            # Skip invalid cached data
            cached_age = account_data.get('age_days') if account_data else None
            if cached_age and cached_age > 0:
                years = cached_age // 365
                months = (cached_age % 365) // 30
                days = (cached_age % 365) % 30
                return f"Age: {years}y {months}m {days}d ({cached_age} days)"
            
            # Get Telegram user ID
            telegram_user_id = account_data.get('telegram_user_id') if account_data else None
            if not telegram_user_id:
                telegram_user_id = await self._get_telegram_user_id(user_id, account_name)
            
            if telegram_user_id:
                telegram_user_id = int(telegram_user_id)
                creation_date, method = await AccountAgeEstimator.estimate_creation_date(telegram_user_id)
                
                if creation_date:
                    now = datetime.now(timezone.utc)
                    if creation_date.tzinfo is None:
                        creation_date = creation_date.replace(tzinfo=timezone.utc)
                    age_days = max(0, (now - creation_date).days)
                    
                    await self._update_account_age_cache(user_id, account_name, creation_date, age_days, telegram_user_id)
                    
                    years = age_days // 365
                    months = (age_days % 365) // 30
                    days = (age_days % 365) % 30
                    return f"Age: {years}y {months}m {days}d ({age_days} days)"
            
            return "Age: Unknown"
        except Exception as e:
            logger.error(f"Error getting account age for {account_name}: {e}")
            return "Age: Unknown"
    
    async def _get_telegram_user_id(self, user_id: int, account_name: str) -> Optional[int]:
        """Get Telegram user ID from connected client"""
        try:
            if hasattr(self.account_manager, 'user_clients') and user_id in self.account_manager.user_clients:
                user_clients = self.account_manager.user_clients[user_id]
                
                # Try all possible client keys
                for key in [account_name] + list(user_clients.keys()):
                    client = user_clients.get(key)
                    if client:
                        try:
                            if not client.is_connected():
                                await client.connect()
                            me = await client.get_me()
                            if me:
                                return me.id
                        except:
                            continue
            return None
        except Exception:
            return None
    
    async def _update_account_age_cache(self, user_id: int, account_name: str, creation_date, age_days: int, telegram_user_id: int):
        """Update account age cache in database"""
        try:
            from datetime import datetime, timezone
            
            update_data = {
                'creation_date': creation_date,
                'age_days': age_days,
                'telegram_user_id': telegram_user_id,
                'last_age_update': datetime.now(timezone.utc)
            }
            
            await mongodb.db.accounts.update_one(
                {'user_id': user_id, 'name': account_name},
                {'$set': update_data}
            )
        except Exception as e:
            logger.debug(f"Error updating age cache for {account_name}: {e}")
    
    async def _update_single_account_age(self, user_id: int, account: dict):
        """Update age for a single account"""
        try:
            from ..utils.account_age_estimator import AccountAgeEstimator
            from datetime import datetime, timezone
            
            account_name = account.get('name')
            phone = account.get('phone')
            
            if not account_name:
                return
            
            # Try to get client
            client = None
            if hasattr(self.account_manager, 'user_clients') and user_id in self.account_manager.user_clients:
                user_clients = self.account_manager.user_clients[user_id]
                client = user_clients.get(account_name) or user_clients.get(phone)
            
            if client and hasattr(client, 'is_connected') and client.is_connected():
                me = await client.get_me()
                telegram_user_id = int(me.id)
                
                creation_date, method = await AccountAgeEstimator.estimate_creation_date(telegram_user_id)
                
                if creation_date:
                    now = datetime.now(timezone.utc)
                    if creation_date.tzinfo is None:
                        creation_date = creation_date.replace(tzinfo=timezone.utc)
                    age_days = max(0, (now - creation_date).days)
                    
                    await mongodb.db.accounts.update_one(
                        {'_id': account['_id']},
                        {'$set': {
                            'creation_date': creation_date,
                            'age_days': age_days,
                            'telegram_user_id': telegram_user_id,
                            'last_age_update': datetime.now(timezone.utc)
                        }}
                    )
        except Exception as e:
            logger.debug(f"Error updating age for {account.get('name')}: {e}")
    



    async def _handle_developer(self, event):
        """Handle Developer menu - delegated to modular handler"""
        from teleguard_modular.menu_delegation import handle_developer_menu
        await handle_developer_menu(self.bot, event.sender_id, event)
    async def _handle_dm_reply(self, event):
        """Handle DM Reply menu - delegated to modular handler"""
        from teleguard_modular.menu_delegation import handle_dm_reply_menu
        await handle_dm_reply_menu(self.bot, event.sender_id, event, self.account_manager)
    async def _handle_otp_callback(self, event, user_id: int, data: str):
        await self.callback_handlers.handle_otp_callback(event, user_id, data)
    
    async def _handle_otp_callback_legacy(self, event, user_id: int, data: str):
        """Handle OTP-related callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"
        if action == "manage":
            await self.send_otp_account_management(
                user_id, account_id, event.message_id
            )
        elif action == "enable":
            try:
                from bson import ObjectId
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id), "user_id": user_id},
                    {"$set": {
                        "otp_destroyer_enabled": True,
                        "otp_forward_enabled": False  # Disable forward when destroyer is enabled
                    }},
                )
                await event.answer("ðŸ›¡ï¸ OTP Destroyer enabled! Forward disabled.")
                # Go back to OTP Destroyer account selection instead of individual account menu
                await self._handle_otp_setting_callback(event, user_id, "otp_setting:destroyer")
            except Exception as e:
                await event.answer("âŒ Error enabling OTP Destroyer")
        elif action == "disable":
            try:
                from bson import ObjectId
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id), "user_id": user_id},
                    {"$set": {"otp_destroyer_enabled": False}},
                )
                await event.answer("ðŸ”´ OTP Destroyer disabled!")
                # Go back to OTP Destroyer account selection instead of individual account menu
                await self._handle_otp_setting_callback(event, user_id, "otp_setting:destroyer")
            except Exception as e:
                await event.answer("âŒ Error disabling OTP Destroyer")
        elif action == "forward_enable":
            try:
                from bson import ObjectId
                account = await mongodb.db.accounts.find_one(
                    {"_id": ObjectId(account_id), "user_id": user_id}
                )
                if account and account.get("otp_destroyer_enabled", False):
                    await event.answer("âŒ Cannot enable forward while OTP Destroyer is active")
                    return
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id), "user_id": user_id},
                    {"$set": {"otp_forward_enabled": True}},
                )
                await event.answer("ðŸ“¤ OTP Forward enabled!")
                # Go back to OTP Forward account selection instead of individual account menu
                await self._handle_otp_setting_callback(event, user_id, "otp_setting:forward")
            except Exception as e:
                await event.answer("âŒ Error enabling OTP Forward")
        elif action == "forward_disable":
            try:
                from bson import ObjectId
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id), "user_id": user_id},
                    {"$set": {"otp_forward_enabled": False}},
                )
                await event.answer("ðŸ”´ OTP Forward disabled!")
                # Go back to OTP Forward account selection instead of individual account menu
                await self._handle_otp_setting_callback(event, user_id, "otp_setting:forward")
            except Exception as e:
                await event.answer("âŒ Error disabling OTP Forward")
        elif action == "temp":
            try:
                from bson import ObjectId
                account = await mongodb.db.accounts.find_one(
                    {"_id": ObjectId(account_id), "user_id": user_id}
                )
                if not account:
                    await event.answer("âŒ Account not found")
                    return
                
                # Check if temp OTP is already active
                import time
                if account.get("otp_temp_passthrough", False):
                    expiry = account.get("temp_passthrough_expiry", 0)
                    if time.time() < expiry:
                        # Stop temp OTP - restore original states
                        original_destroyer_state = account.get("original_destroyer_state", True)
                        original_forward_state = account.get("original_forward_state", False)
                        await mongodb.db.accounts.update_one(
                            {"_id": ObjectId(account_id)},
                            {
                                "$set": {
                                    "otp_destroyer_enabled": original_destroyer_state,
                                    "otp_forward_enabled": original_forward_state
                                },
                                "$unset": {
                                    "otp_temp_passthrough": "",
                                    "temp_passthrough_expiry": "",
                                    "original_destroyer_state": "",
                                    "original_forward_state": ""
                                }
                            }
                        )
                        await mongodb.add_audit_entry(account_id, {
                            "action": "temp_passthrough_stopped",
                            "timestamp": int(time.time())
                        })
                        await event.answer("âŒ Temp OTP stopped! Original settings restored.")
                        await self._handle_otp_setting_callback(event, user_id, "otp_setting:temp")
                        return
                
                # Start temp OTP - enable forward, disable destroyer for 5 minutes
                expiry_time = time.time() + 300  # 5 minutes
                original_destroyer_state = account.get("otp_destroyer_enabled", False)
                original_forward_state = account.get("otp_forward_enabled", False)
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {
                        "otp_temp_passthrough": True,
                        "temp_passthrough_expiry": expiry_time,
                        "otp_destroyer_enabled": False,  # Disable destroyer
                        "otp_forward_enabled": True,     # Enable forward
                        "original_destroyer_state": original_destroyer_state,
                        "original_forward_state": original_forward_state
                    }}
                )
                await mongodb.add_audit_entry(account_id, {
                    "action": "temp_passthrough_enabled",
                    "duration": "5_minutes",
                    "timestamp": int(time.time())
                })
                await event.answer("â° Temp OTP enabled! Forward ON, Destroyer OFF for 5 minutes.")
                await self._handle_otp_setting_callback(event, user_id, "otp_setting:temp")
                # Schedule cleanup after 5 minutes
                import asyncio
                async def simple_cleanup():
                    await asyncio.sleep(300)  # 5 minutes
                    try:
                        from bson import ObjectId
                        await mongodb.db.accounts.update_one(
                            {"_id": ObjectId(account_id)},
                            {"$unset": {
                                "otp_temp_passthrough": "",
                                "temp_passthrough_expiry": "",
                                "original_destroyer_state": "",
                                "original_forward_state": ""
                            }}
                        )
                    except Exception as e:
                        logger.error(f"Temp OTP cleanup error: {e}")
                asyncio.create_task(simple_cleanup())
            except Exception as e:
                logger.error(f"Error handling temp OTP: {e}")
                await event.answer("âŒ Error handling temp OTP")
        elif action == "audit":
            await self.send_audit_log(user_id, account_id)
        elif action == "setpass":
            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {
                    "action": "set_otp_disable_password",
                    "account_id": account_id,
                }
                text = (
                    "ðŸ”’ **Set Disable Password**\n\n"
                    "Reply with a password that will be required to disable OTP Destroyer.\n\n"
                    "âš ï¸ This adds an extra security layer - choose a strong password!\n"
                    "ðŸ“ Minimum 6 characters required."
                )
                await event.answer("ðŸ”’ Reply with password")
                await self.bot.send_message(user_id, text)
            else:
                await event.answer("âŒ Service unavailable")
    
    async def _handle_otp_setting_callback(self, event, user_id: int, data: str):
        """Handle OTP setting callbacks from main OTP menu"""
        parts = data.split(":")
        setting_type = parts[1] if len(parts) > 1 else "destroyer"
        
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = "ðŸ›¡ï¸ **OTP Settings**\n\nâŒ No accounts found."
                buttons = [[Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]]
                await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                return
            
            if setting_type == "destroyer":
                text = "ðŸ›¡ï¸ **OTP Destroyer Settings**\n\nSelect account to enable/disable OTP Destroyer:"
            elif setting_type == "forward":
                text = "ðŸ“¤ **OTP Forward Settings**\n\nSelect account to enable/disable OTP Forward:"
            elif setting_type == "temp":
                text = "â° **Temp OTP Settings**\n\nSelect account to enable 5-minute passthrough:"
            else:
                text = "ðŸ›¡ï¸ **OTP Settings**\n\nSelect account:"
            
            buttons = []
            for account in accounts:
                status = "ðŸŸ¢" if account.get("is_active", False) else "ðŸ”´"
                
                if setting_type == "destroyer":
                    feature_status = "ðŸ›¡ï¸" if account.get("otp_destroyer_enabled", False) else "âšª"
                elif setting_type == "forward":
                    feature_status = "ðŸ“¤" if account.get("otp_forward_enabled", False) else "âšª"
                else:
                    feature_status = "âšª"
                
                display_name = format_display_name(account)
                button_text = f"{status}{feature_status} {display_name}"
                buttons.append([Button.inline(button_text, f"otp:manage:{account['_id']}")])
            
            buttons.append([Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")])
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in OTP setting callback: {e}")
            await event.answer("âŒ Error loading OTP settings")
    
    async def _send_help_menu(self, user_id: int, message_id: int):
        """Send help menu"""
        text = (
            "â“ **Help & Information**\n\n"
            "ðŸ›¡ï¸ **OTP Destroyer**: Automatically invalidates login codes to prevent unauthorized access\n\n"
            "ðŸ“± **Account Management**: Add, remove, and configure your Telegram accounts\n\n"
            "ðŸ” **Security**: All data is encrypted and stored securely\n\n"
            "âš™ï¸ **Developer Mode**: Access advanced features and text commands"
        )
        await self.bot.send_message(user_id, text)
    async def _toggle_developer_mode(self, user_id: int, message_id: int):
        """Toggle developer mode"""
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if user:
                current_mode = user.get("developer_mode", False)
                new_mode = not current_mode
                await mongodb.db.users.update_one(
                    {"telegram_id": user_id}, {"$set": {"developer_mode": new_mode}}
                )
                status = "enabled" if new_mode else "disabled"
                text = f"âš™ï¸ **Developer Mode**\n\nDeveloper mode {status}.\n\n"
                if new_mode:
                    text += "You now have access to text commands:\n/add, /remove, /accs, /toggle_protection, etc."
                else:
                    text += "Text commands are now hidden. Use the menu system."
                buttons = [[Button.inline("ðŸ”™ Back to Main", "menu:main")]]
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to toggle developer mode: {e}")
    async def send_otp_menu(self, user_id: int, edit_message_id: Optional[int] = None):
        """Send OTP Manager menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = "ðŸ›¡ï¸ **OTP Manager**\n\nNo accounts found. Add accounts first to manage OTP settings."
            else:
                text = (
                    "ðŸ›¡ï¸ **OTP Manager**\n\n"
                    "OTP security features:\n\n"
                    "â€¢ ðŸ›¡ï¸ Destroyer: Blocks unauthorized logins\n"
                    "â€¢ ðŸ“¤ Forward: Forwards OTP codes to you\n"
                    "â€¢ â° Temp Pass: 5-minute security bypass\n\n"
                    f"You have {len(accounts)} account(s). Use Account Settings to manage OTP protection."
                )
            await self.bot.send_message(user_id, text)
        except Exception as e:
            logger.error(f"Failed to send OTP menu: {e}")
    async def _send_sessions_menu(self, user_id: int, message_id: int):
        """Send sessions management menu"""
        text = (
            "ðŸ” **Session Management**\n\n"
            "Manage your account sessions and security.\n\n"
            "Features coming soon:"
            "â€¢ Export session strings\n"
            "â€¢ Import sessions\n"
            "â€¢ Session health check"
        )
        buttons = [[Button.inline("ðŸ”™ Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    async def _send_2fa_menu(self, user_id: int, message_id: int):
        """Send 2FA settings menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = "ðŸ”‘ **2FA Settings**\n\nNo accounts found. Add accounts first."
                buttons = [[Button.inline("ðŸ”™ Back to Main", "menu:main")]]
            else:
                text = "ðŸ”‘ **2FA Settings**\n\nSelect an account to manage 2FA:"
                buttons = []
                for account in accounts:
                    has_2fa = "ðŸ›¡ï¸" if account.get("twofa_password") else "âŒ"
                    button_text = f"{has_2fa} {account['name']}"
                    buttons.append(
                        [Button.inline(button_text, f"2fa:status:{account['_id']}")]
                    )
                buttons.append([Button.inline("ðŸ”™ Back to Main", "menu:main")])
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to send 2FA menu: {e}")
    async def _send_online_menu(self, user_id: int, message_id: int):
        """Send online maker menu"""
        text = (
            "ðŸŸ¢ **Online Maker**\n\n"
            "Keep your accounts online automatically.\n\n"
            "Features coming soon:"
            "â€¢ Auto-online intervals\n"
            "â€¢ Custom status messages\n"
            "â€¢ Schedule management"
        )
        buttons = [[Button.inline("ðŸ”™ Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    async def _send_security_menu(self, user_id: int, account_id: str, message_id: int):
        """Send security settings menu"""
        text = (
            "ðŸ”’ **Security Settings**\n\n"
            "Advanced security options for OTP destroyer.\n\n"
            "Features coming soon:"
            "â€¢ Disable password protection\n"
            "â€¢ Audit log retention\n"
            "â€¢ Alert preferences"
        )
        buttons = [[Button.inline("ðŸ”™ Back", f"account:manage:{account_id}")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    async def _send_profile_menu(self, user_id: int, message_id: int):
        """Send profile management menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = (
                    "ðŸ‘¤ **Profile Manager**\n\nNo accounts found. Add accounts first."
                )
                buttons = [[Button.inline("ðŸ”™ Back to Main", "menu:main")]]
            else:
                text = "ðŸ‘¤ **Profile Manager**\n\nSelect an account to manage profile:"
                buttons = []
                for account in accounts:
                    status = "âœ…" if account.get("is_active", False) else "âŒ"
                    username_display = (
                        f"@{account.get('username', '')}"
                        if account.get("username")
                        else "No username"
                    )
                    button_text = f"{status} {account['name']} ({username_display})"
                    buttons.append(
                        [Button.inline(button_text, f"profile:manage:{account['_id']}")]
                    )
                buttons.append([Button.inline("ðŸ”™ Back to Main", "menu:main")])
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to send profile menu: {e}")
    async def _send_groups_menu(self, user_id: int, message_id: int):
        """Send groups and channels menu"""
        text = (
            "ðŸ‘¥ **Groups & Channels**\n\n"
            "Manage groups and channels for your accounts.\n\n"
            "Features coming soon:"
            "â€¢ Create channels/groups\n"
            "â€¢ Manage members and admins\n"
            "â€¢ Post and schedule content\n"
            "â€¢ Invite link management"
        )
        buttons = [[Button.inline("ðŸ”™ Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    async def _send_messaging_menu(self, user_id: int, message_id: int):
        """Send messaging menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = "ðŸ’¬ **Messaging**\n\nNo accounts found. Add accounts first to use messaging features."
                buttons = [[Button.inline("ðŸ”™ Back to Main", "menu:main")]]
            else:
                text = "ðŸ’¬ **Messaging**\n\nSelect messaging action:"
                buttons = [
                    [Button.inline("ðŸ“¤ Send Message", "msg:send")],
                    [Button.inline("ðŸ”„ Auto Reply", "msg:autoreply")],
                    [Button.inline("ðŸ“ Message Templates", "msg:templates")],
                    [Button.inline("ðŸ”™ Back to Main", "menu:main")],
                ]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to send messaging menu: {e}")
    async def _send_automation_menu(self, user_id: int, message_id: int):
        """Send automation menu"""
        text = (
            "âš¡ **Automation**\n\n"
            "Automate account actions and workflows.\n\n"
            "Available features:"
            "â€¢ Online maker (keep accounts online)\n"
            "â€¢ Auto-reply rules\n"
            "â€¢ Scheduled posts\n"
            "â€¢ Auto-join/leave groups"
        )
        buttons = [[Button.inline("ðŸ”™ Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    async def _send_analytics_menu(self, user_id: int, message_id: int):
        """Send analytics menu"""
        text = (
            "ðŸ“Š **Analytics**\n\n"
            "View account statistics and activity.\n\n"
            "Features coming soon:"
            "â€¢ Account health monitoring\n"
            "â€¢ Session activity logs\n"
            "â€¢ OTP destroyer statistics\n"
            "â€¢ Automation performance"
        )
        buttons = [[Button.inline("ðŸ”™ Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    async def _send_support_menu(self, user_id: int, message_id: int):
        """Send support menu"""
        text = (
            "ðŸ†˜ **Support & Contact**\n\n"
            "Need help? Contact our support team:\n\n"
            "ðŸ‘¨ðŸ’» **Developers:**\n"
            "â€¢ @Meher_Mankar\n"
            "â€¢ @Gutkesh\n\n"
            "ðŸ“§ **Support:** https://t.me/ContactXYZrobot\n"
            "ðŸ› **Bug Reports:** Create an issue on GitHub\n\n"
            "â° **Response Time:** Usually within 24 hours\n\n"
            "ðŸ’¬ **Tips:**\n"
            "â€¢ Include error messages when reporting bugs\n"
            "â€¢ Describe steps to reproduce issues\n"
            "â€¢ Check /help for common solutions first"
        )
        await self.bot.send_message(user_id, text)
    async def _handle_2fa_callback(self, event, user_id: int, data: str):
        """Handle 2FA-related callbacks"""
        try:
            parts = data.split(":")
            action = parts[1]
            account_id = parts[2] if len(parts) > 2 else "0"
            
            # Check if account manager and handlers are available
            if not self.account_manager:
                await event.answer("âŒ Service unavailable", alert=True)
                return
            
            # Get twofa_commands handler
            twofa_handler = None
            if hasattr(self.account_manager, 'twofa_commands'):
                twofa_handler = self.account_manager.twofa_commands
            elif hasattr(self, 'twofa_commands'):
                twofa_handler = self.twofa_commands
            
            if action in ["set", "change", "remove"]:
                if not twofa_handler:
                    await event.answer("âŒ 2FA management not available", alert=True)
                    return
                await twofa_handler.handle_2fa_callback(event, user_id, data)
            elif action == "status":
                # Show 2FA status using secure handlers
                if self.secure_2fa_handlers:
                    await self.secure_2fa_handlers.show_2fa_status(
                        user_id, account_id, event.message_id
                    )
                else:
                    await event.answer("âŒ 2FA management not available", alert=True)
        except Exception as e:
            logger.error(f"2FA callback error: {e}")
            await event.answer("âŒ Error processing 2FA request", alert=True)
    async def _handle_profile_callback(self, event, user_id: int, data: str):
        """Handle profile-related callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"
        if action == "manage":
            await self._send_profile_management(user_id, account_id, event.message_id)
        elif action == "name":
            await self._handle_profile_name_change(user_id, account_id, event)
        elif action == "username":
            await self._handle_profile_username_change(user_id, account_id, event)
        elif action == "bio":
            await self._handle_profile_bio_change(user_id, account_id, event)
        elif action == "photo":
            await self._handle_profile_photo_change(user_id, account_id, event)
    async def _handle_sessions_callback(self, event, user_id: int, data: str):
        """Handle sessions-related callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"
        if action == "list":
            from ..handlers.sessions_handler import handle_sessions_list
            await handle_sessions_list(
                self.bot, self.account_manager, user_id, account_id, event.message_id
            )
        elif action == "terminate_all":
            from ..handlers.sessions_handler import handle_terminate_all
            await handle_terminate_all(
                self.bot, self.account_manager, user_id, account_id, event.message_id
            )
    async def _handle_online_callback(self, event, user_id: int, data: str):
        await self.callback_handlers.handle_online_callback(event, user_id, data)
    
    async def _handle_online_callback_legacy(self, event, user_id: int, data: str):
        """Handle online maker callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"
        if action == "toggle":
            try:
                from bson import ObjectId
                account = await mongodb.db.accounts.find_one(
                    {"_id": ObjectId(account_id), "user_id": user_id}
                )
                if account:
                    new_status = not account.get("online_maker_enabled", False)
                    await mongodb.db.accounts.update_one(
                        {"_id": ObjectId(account_id)},
                        {"$set": {"online_maker_enabled": new_status}},
                    )
                    if hasattr(self.account_manager, 'online_maker'):
                        account_identifier = account.get("phone") or account.get("name", "unknown")
                        if new_status:
                            await self.account_manager.online_maker.start_online_maker(user_id, account_identifier)
                        else:
                            await self.account_manager.online_maker.stop_online_maker(user_id, account_identifier)
                    status = "started" if new_status else "stopped"
                    status_emoji = "âœ…" if new_status else "âŒ"
                    await event.answer(f"{status_emoji} Online maker {status}!")
                    await self.send_account_management(
                        user_id, account_id, event.message_id
                    )
            except Exception as e:
                await event.answer("âŒ Error toggling online maker")
    async def _handle_automation_callback(self, event, user_id: int, data: str):
        """Handle automation callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"
        if action == "manage":
            await self._send_automation_management(
                user_id, account_id, event.message_id
            )
    async def _send_profile_management(
        self, user_id: int, account_id: str, message_id: int
    ):
        """Send profile management options - delegated to ProfileOperations"""
        from .menu_modules import ProfileOperations
        ops = ProfileOperations(self)
        await ops.send_profile_management(user_id, account_id, message_id)
    async def _get_current_profile_info(self, user_id: int, account_name: str) -> dict:
        """Fetch current profile information - delegated to ProfileOperations"""
        from .menu_modules import ProfileOperations
        ops = ProfileOperations(self)
        return await ops._get_current_profile_info(user_id, account_name)
    async def _send_sessions_list(self, user_id: int, account_id: str, message_id: int):
        """Send active sessions list"""
        text = (
            f"ðŸ” **Active Sessions**\n\n"
            f"Loading session information...\n\n"
            f"This will show all active login sessions for the account."
        )
        buttons = [[Button.inline("ðŸ”™ Back", f"account:manage:{account_id}")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    async def _toggle_online_maker(
        self, user_id: int, account_id: str, message_id: int
    ):
        """Toggle online maker for account"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if account:
                current_status = account.get("online_maker_enabled", False)
                new_status = not current_status
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {"online_maker_enabled": new_status}},
                )
                status = "enabled" if new_status else "disabled"
                interval = account.get("online_maker_interval", 300)
                text = f"ðŸŸ¢ **Online Maker {status.title()}**\n\nAccount: {account['name']}\nStatus: {status}\nInterval: {interval}s"
                buttons = [[Button.inline("ðŸ”™ Back", f"account:manage:{account_id}")]]
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to toggle online maker: {e}")
    async def _send_automation_management(
        self, user_id: int, account_id: str, message_id: int
    ):
        """Send automation management for account"""
        text = (
            f"âš¡ **Automation Management**\n\n"
            f"Configure automation rules and jobs.\n\n"
            f"Available options:"
            f"â€¢ Online maker\n"
            f"â€¢ Auto-reply rules\n"
            f"â€¢ Scheduled actions"
        )
        buttons = [
            [Button.inline("ðŸŸ¢ Online Maker", f"online:toggle:{account_id}")],
            [Button.inline("ðŸ”™ Back", f"account:manage:{account_id}")],
        ]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    async def _handle_profile_name_change(self, user_id: int, account_id: str, event):
        """Handle profile name change - delegated to ProfileOperations"""
        from .menu_modules import ProfileOperations
        ops = ProfileOperations(self)
        await ops.handle_profile_name_change(user_id, account_id, event)
    
    async def _handle_profile_name_change_legacy(self, user_id: int, account_id: str, event):
        """Legacy profile name change handler"""
        from bson import ObjectId
        account = await mongodb.db.accounts.find_one(
            {"_id": ObjectId(account_id), "user_id": user_id}
        )
        if not account:
            await event.answer("Account not found")
            return
        await event.answer("Enter new name")
        await self.bot.send_message(
            user_id, "Reply with your new name (Example: John Doe):"
        )
        @self.bot.on(events.NewMessage(from_users=user_id))
        async def handle_name_input(name_event):
            if name_event.raw_text.startswith("/"):
                return
            names = name_event.raw_text.split(" ", 1)
            first_name = names[0]
            last_name = names[1] if len(names) > 1 else ""
            client = None
            if hasattr(self.account_manager, "user_clients"):
                client = self.account_manager.user_clients.get(user_id, {}).get(
                    account["name"]
                )
            if client:
                try:
                    from telethon import functions
                    await client(
                        functions.account.UpdateProfileRequest(
                            first_name=first_name, last_name=last_name
                        )
                    )
                    await name_event.reply(
                        f"Profile name updated to: {first_name} {last_name}"
                    )
                except Exception as e:
                    await name_event.reply(f"Failed to update name: {e}")
            else:
                await name_event.reply("Account client not found")
            self.bot.remove_event_handler(handle_name_input)
    async def _handle_profile_username_change(self, user_id: int, account_id: str, event):
        """Handle username change - delegated to ProfileOperations"""
        from .menu_modules import ProfileOperations
        ops = ProfileOperations(self)
        await ops.handle_profile_username_change(user_id, account_id, event)
    
    async def _handle_profile_username_change_legacy(self, user_id: int, account_id: str, event):
        """Legacy username change handler"""
        from bson import ObjectId
        account = await mongodb.db.accounts.find_one(
            {"_id": ObjectId(account_id), "user_id": user_id}
        )
        if not account:
            await event.answer("Account not found")
            return
        await event.answer("Enter username")
        await self.bot.send_message(
            user_id, "Reply with your new username (without @):"
        )
        @self.bot.on(events.NewMessage(from_users=user_id))
        async def handle_username_input(username_event):
            if username_event.raw_text.startswith("/"):
                return
            username = username_event.raw_text.replace("@", "").strip()
            client = None
            if hasattr(self.account_manager, "user_clients"):
                client = self.account_manager.user_clients.get(user_id, {}).get(
                    account["name"]
                )
            if client:
                try:
                    from telethon import functions
                    await client(
                        functions.account.UpdateUsernameRequest(username=username)
                    )
                    await username_event.reply(f"Username updated to: @{username}")
                except Exception as e:
                    await username_event.reply(f"Failed to update username: {e}")
            else:
                await username_event.reply(
                    f"Account client not found. Account: {account['name']}, User: {user_id}"
                )
            self.bot.remove_event_handler(handle_username_input)
    async def _handle_profile_bio_change(self, user_id: int, account_id: str, event):
        """Handle bio change - delegated to ProfileOperations"""
        from .menu_modules import ProfileOperations
        ops = ProfileOperations(self)
        await ops.handle_profile_bio_change(user_id, account_id, event)
    
    async def _handle_profile_bio_change_legacy(self, user_id: int, account_id: str, event):
        """Legacy bio change handler"""
        from bson import ObjectId
        account = await mongodb.db.accounts.find_one(
            {"_id": ObjectId(account_id), "user_id": user_id}
        )
        if not account:
            await event.answer("Account not found")
            return
        await event.answer("Enter bio")
        await self.bot.send_message(
            user_id, "Reply with your new bio (max 70 characters):"
        )
        @self.bot.on(events.NewMessage(from_users=user_id))
        async def handle_bio_input(bio_event):
            if bio_event.raw_text.startswith("/"):
                return
            bio_text = bio_event.raw_text.strip()
            client = None
            if hasattr(self.account_manager, "user_clients"):
                client = self.account_manager.user_clients.get(user_id, {}).get(
                    account["name"]
                )
            if client:
                try:
                    from telethon import functions
                    await client(functions.account.UpdateProfileRequest(about=bio_text))
                    await bio_event.reply("Bio updated successfully")
                except Exception as e:
                    await bio_event.reply(f"Failed to update bio: {e}")
            else:
                await bio_event.reply(
                    f"Account client not found. Account: {account['name']}, User: {user_id}"
                )
            self.bot.remove_event_handler(handle_bio_input)
    async def _handle_profile_photo_change(self, user_id: int, account_id: str, event):
        """Handle photo change - delegated to ProfileOperations"""
        from .menu_modules import ProfileOperations
        ops = ProfileOperations(self)
        await ops.handle_profile_photo_change(user_id, account_id, event)
    
    async def _handle_profile_photo_change_legacy(self, user_id: int, account_id: str, event):
        """Legacy photo change handler"""
        from bson import ObjectId
        account = await mongodb.db.accounts.find_one(
            {"_id": ObjectId(account_id), "user_id": user_id}
        )
        if not account:
            await event.answer("Account not found")
            return
        await event.answer("Send photo")
        await self.bot.send_message(
            user_id, "Send a photo to set as your profile picture:"
        )
        @self.bot.on(events.NewMessage(from_users=user_id, func=lambda e: e.photo))
        async def handle_photo_input(photo_event):
            client = None
            if hasattr(self.account_manager, "user_clients"):
                client = self.account_manager.user_clients.get(user_id, {}).get(
                    account["name"]
                )
            if client:
                try:
                    photo_path = await photo_event.download_media()
                    from telethon import functions
                    uploaded_file = await client.upload_file(photo_path)
                    await client(
                        functions.photos.UploadProfilePhotoRequest(file=uploaded_file)
                    )
                    import os
                    if os.path.exists(photo_path):
                        os.remove(photo_path)
                    await photo_event.reply("Profile photo updated successfully")
                except Exception as e:
                    await photo_event.reply(f"Failed to update photo: {e}")
            else:
                await photo_event.reply(
                    f"Account client not found. Account: {account['name']}, User: {user_id}"
                )
            self.bot.remove_event_handler(handle_photo_input)
    async def _handle_add_account(self, event, user_id: int):
        """Handle add account request"""
        try:
            from ..core.config import MAX_ACCOUNTS
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if not user:
                await event.answer("âŒ Please start the bot first")
                return
            account_count = await mongodb.db.accounts.count_documents(
                {"user_id": user_id}
            )
            if account_count >= MAX_ACCOUNTS:
                await event.answer(f"âŒ Maximum account limit ({MAX_ACCOUNTS}) reached")
                return
            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {
                    "action": "add_account"
                }
                text = (
                    "âž• **Add New Account**\n\n"
                    "Reply with the phone number for the new account.\n\n"
                    "ðŸ“± Format: +1234567890 (include country code)\n"
                    "ðŸ’¡ Tip: Enter OTP codes as 1-2-3-4-5 (with hyphens)"
                )
                await event.answer("âž• Reply with phone number")
                await self.bot.send_message(user_id, text)
            else:
                await event.answer("âŒ Service unavailable")
        except Exception as e:
            logger.error(f"Failed to handle add account: {e}")
            await event.answer("âŒ Error processing request")
    async def _handle_remove_account(self, event, user_id: int):
        """Handle remove account request"""
        try:
            # Prompt user to select account to remove
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                await self.bot.send_message(user_id, "âŒ No accounts to remove.")
                return
            text = "ðŸ—‘ï¸ **Remove Account**\n\nSelect an account to remove:"
            buttons = []
            for account in accounts:
                buttons.append(
                    [
                        Button.inline(
                            f"ðŸ—‘ï¸ {account['name']} ({account['phone']})",
                            f"remove:confirm:{account['_id']}",
                        )
                    ]
                )
            buttons.append([Button.inline("ðŸ”™ Back to Accounts", "menu:accounts")])
            await self.bot.send_message(user_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to handle remove account: {e}")
            await event.reply("âŒ Error processing remove account request")
    async def _execute_remove_account(self, event, user_id: int, account_id: str):
        """Execute account removal"""
        try:
            if self.account_manager:
                try:
                    from ..core.database_manager import db_manager
                    await db_manager.remove_2fa_password(user_id, account_id)
                except Exception:
                    pass
                success, message = await self.account_manager.remove_account_by_id(user_id, account_id)
                message = "Account removed successfully" if success else "Failed to remove account"
                if success:
                    await event.answer("âœ… Account removed successfully!")
                    await self.bot.edit_message(
                        user_id,
                        event.message_id,
                        "âœ… **Account Removed**\n\nThe account has been successfully removed from TeleGuard.\n\nðŸ” Session terminated from Telegram\nðŸ” Stored 2FA password also removed for security",
                        buttons=[[Button.inline("ðŸ”™ Back to Accounts", "menu:accounts")]],
                    )
                else:
                    await event.answer(f"âŒ Failed to remove account: {message}")
                    await self.bot.edit_message(
                        user_id,
                        event.message_id,
                        f"âŒ **Removal Failed**\n\n{message}",
                        buttons=[[Button.inline("ðŸ”™ Back to Accounts", "menu:accounts")]],
                    )
            else:
                await event.answer("âŒ Service unavailable")
        except Exception as e:
            logger.error(f"Failed to execute remove account: {e}")
            await event.reply("âŒ Error executing account removal")
    async def _handle_messaging_callback(self, event, user_id: int, data: str):
        """Handle messaging-related callbacks"""
        parts = data.split(":")
        action = parts[1]
        if action == "send":
            await self._send_message_menu(user_id, event.message_id)
        elif action == "autoreply":
            await self._send_autoreply_menu(user_id, event.message_id)
        elif action == "templates":
            await self._send_templates_menu(user_id, event.message_id)
        elif action == "compose":
            account_id = parts[2]  # Keep as string for MongoDB ObjectId
            await self._handle_compose_message(user_id, account_id, event)
    async def _send_message_menu(self, user_id: int, message_id: int):
        """Send message composition menu - delegated to MessagingOperations"""
        from .menu_modules import MessagingOperations
        ops = MessagingOperations(self)
        await ops.send_message_menu(user_id, message_id)
    async def _send_autoreply_menu(self, user_id: int, message_id: int):
        """Send auto-reply management menu - delegated to MessagingOperations"""
        from .menu_modules import MessagingOperations
        ops = MessagingOperations(self)
        await ops.send_autoreply_menu(user_id, message_id)
    async def _send_templates_menu(self, user_id: int, message_id: int):
        """Send message templates menu - delegated to MessagingOperations"""
        from .menu_modules import MessagingOperations
        ops = MessagingOperations(self)
        await ops.send_templates_menu(user_id, message_id)
    async def _handle_compose_message(self, user_id: int, account_id: str, event):
        """Handle message composition request"""
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "compose_message_target",
                "account_id": account_id,
            }
            text = (
                "ðŸ“¤ **Compose Message**\n\n"
                "Reply with the target (username, phone, or chat ID):\n\n"
                "Examples:\n"
                "â€¢ @username\n"
                "â€¢ +1234567890\n"
                "â€¢ -1001234567890 (for groups/channels)"
            )
            await event.answer("ðŸ“¤ Reply with target")
            await self.bot.send_message(user_id, text)
    async def _handle_autoreply_callback(self, event, user_id: int, data: str):
        """Handle auto-reply callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"
        if action == "manage":
            await self._send_autoreply_management(user_id, account_id, event.message_id)
        elif action == "toggle":
            await self._toggle_autoreply(user_id, account_id, event)
        elif action == "set":
            await self._set_autoreply_message(user_id, account_id, event)
    async def _handle_template_callback(self, event, user_id: int, data: str):
        """Handle template callbacks - redirect to new template system"""
        parts = data.split(":")
        action = parts[1]
        if action == "main":
            # Redirect to new advanced template system
            if hasattr(self.account_manager, 'template_handler'):
                await self.account_manager.template_handler.show_main_menu(event)
            else:
                await event.answer("Template system not available")
        else:
            # All other template actions handled by new system
            await event.answer("Use /templates command for advanced template features")
    async def _send_autoreply_management(
        self, user_id: int, account_id: str, message_id: int
    ):
        """Send auto-reply management for specific account"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                await self.bot.send_message(user_id, "âŒ Account not found")
                return
            auto_enabled = account.get("auto_reply_enabled", False)
            auto_message = account.get("auto_reply_message", "Not set")
            text = (
                f"ðŸ”„ **Auto Reply: {account['name']}**\n\n"
                f"Status: {'ðŸŸ¢ Enabled' if auto_enabled else 'ðŸ”´ Disabled'}\n"
                f"Message: {auto_message[:50]}{'...' if len(auto_message) > 50 else ''}\n\n"
                f"Configure auto-reply settings:"
            )
            toggle_text = "ðŸ”´ Disable" if auto_enabled else "ðŸŸ¢ Enable"
            buttons = [
                [
                    Button.inline(
                        f"{toggle_text} Auto Reply", f"autoreply:toggle:{account_id}"
                    )
                ],
                [Button.inline("ðŸ“ Set Message", f"autoreply:set:{account_id}")],
                [Button.inline("ðŸ”™ Back", "msg:autoreply")],
            ]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to send auto-reply management: {e}")
    async def _toggle_autoreply(self, user_id: int, account_id: str, event):
        """Toggle auto-reply for account"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if account:
                new_status = not account.get("auto_reply_enabled", False)
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {"auto_reply_enabled": new_status}}
                )
                await event.answer(f"ðŸ”„ Auto-reply {'enabled' if new_status else 'disabled'}")
                await self._send_autoreply_management(user_id, account_id, event.message_id)
        except Exception as e:
            logger.error(f"Toggle autoreply error: {e}")
            await event.answer("âŒ Error toggling auto-reply")
    async def _set_autoreply_message(self, user_id: int, account_id: str, event):
        """Set auto-reply message"""
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "set_autoreply_message",
                "account_id": account_id,
            }
            text = (
                "ðŸ“ **Set Auto-Reply Message**\n\n"
                "Reply with the message to send automatically:\n\n"
                "This message will be sent to anyone who messages this account."
            )
            await event.answer("ðŸ“ Reply with message")
            await self.bot.send_message(user_id, text)
    async def _send_bulk_sender_menu(self, user_id: int, message_id: int):
        """Send bulk sender management menu - delegated to MessagingOperations"""
        from .menu_modules import MessagingOperations
        ops = MessagingOperations(self)
        await ops.send_bulk_sender_menu(user_id, message_id)
    async def _handle_bulk_callback(self, event, user_id: int, data: str):
        """Handle bulk sender callbacks"""
        parts = data.split(":")
        action = parts[1]
        if action == "send_list":
            await self._start_bulk_list_flow(user_id, event)
        elif action == "send_contacts":
            await self._start_bulk_contacts_flow(user_id, event)
        elif action == "send_all":
            await self._start_bulk_all_flow(user_id, event)
        elif action == "jobs":
            await self._show_bulk_jobs(user_id, event.message_id)
        elif action == "help":
            await self._show_bulk_help(user_id, event.message_id)
    async def _start_bulk_list_flow(self, user_id: int, event):
        """Start bulk list flow - delegated to MessagingOperations"""
        from .menu_modules import MessagingOperations
        ops = MessagingOperations(self)
        await ops.start_bulk_list_flow(user_id, event)
    
    async def _start_bulk_list_flow_legacy(self, user_id: int, event):
        """Legacy bulk list flow"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                await event.answer("âŒ No accounts found")
                return
            text = (
                "ðŸ“‹ **Bulk Send to List**\n\n"
                "Step 1: Select account to send from:\n\n"
            )
            buttons = []
            for account in accounts:
                status = "âœ…" if account.get("is_active", False) else "âŒ"
                button_text = f"{status} {account['name']}"
                buttons.append([Button.inline(button_text, f"bulk_list_account:{account['_id']}")])
            buttons.append([Button.inline("ðŸ”™ Back to Bulk Sender", "msg:bulk")])
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            await event.answer("ðŸ“‹ Select account")
        except Exception as e:
            logger.error(f"Failed to start bulk list flow: {e}")
    async def _start_bulk_contacts_flow(self, user_id: int, event):
        """Start bulk contacts flow - delegated to MessagingOperations"""
        from .menu_modules import MessagingOperations
        ops = MessagingOperations(self)
        await ops.start_bulk_contacts_flow(user_id, event)
    
    async def _start_bulk_contacts_flow_legacy(self, user_id: int, event):
        """Legacy bulk contacts flow"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                await event.answer("âŒ No accounts found")
                return
            text = (
                "ðŸ‘¥ **Bulk Send to Contacts**\n\n"
                "Step 1: Select account to send from:\n\n"
                "This will send to ALL contacts of the selected account."
            )
            buttons = []
            for account in accounts:
                status = "âœ…" if account.get("is_active", False) else "âŒ"
                button_text = f"{status} {account['name']}"
                buttons.append([Button.inline(button_text, f"bulk_contacts_account:{account['_id']}")])
            buttons.append([Button.inline("ðŸ”™ Back to Bulk Sender", "msg:bulk")])
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            await event.answer("ðŸ‘¥ Select account")
        except Exception as e:
            logger.error(f"Failed to start bulk contacts flow: {e}")
    async def _start_bulk_all_flow(self, user_id: int, event):
        """Start bulk all flow - delegated to MessagingOperations"""
        from .menu_modules import MessagingOperations
        ops = MessagingOperations(self)
        await ops.start_bulk_all_flow(user_id, event)
    
    async def _start_bulk_all_flow_legacy(self, user_id: int, event):
        """Legacy bulk all flow"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                await event.answer("âŒ No accounts found")
                return
            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {
                    "action": "bulk_all_targets"
                }
            text = (
                f"ðŸŒ **Bulk Send from All Accounts**\n\n"
                f"This will send from ALL {len(accounts)} accounts.\n\n"
                "Step 1: Reply with target usernames/IDs (comma-separated):\n\n"
                "**Examples:**\n"
                "â€¢ @username1,@username2,@username3\n"
                "â€¢ +1234567890,@username,123456789\n\n"
                "Reply with the targets:"
            )
            await self.bot.edit_message(user_id, event.message_id, text)
            await event.answer("ðŸŒ Reply with targets")
        except Exception as e:
            logger.error(f"Failed to start bulk all flow: {e}")
    async def _show_bulk_jobs(self, user_id: int, message_id: int):
        """Show bulk jobs - delegated to MessagingOperations"""
        from .menu_modules import MessagingOperations
        ops = MessagingOperations(self)
        await ops.show_bulk_jobs(user_id, message_id)
    
    async def _show_bulk_jobs_legacy(self, user_id: int, message_id: int):
        """Legacy bulk jobs display"""
        try:
            if not hasattr(self.account_manager, 'bulk_sender'):
                text = "âŒ Bulk sender not available"
                buttons = [[Button.inline("ðŸ”™ Back to Bulk Sender", "msg:bulk")]]
            else:
                user_jobs = [job for job in self.account_manager.bulk_sender.active_jobs.values() if job['user_id'] == user_id]
                if not user_jobs:
                    text = "ðŸ“Š **Active Bulk Jobs**\n\nðŸ’­ No active jobs found."
                    buttons = [[Button.inline("ðŸ”™ Back to Bulk Sender", "msg:bulk")]]
                else:
                    text = f"ðŸ“Š **Active Bulk Jobs** ({len(user_jobs)})\n\n"
                    buttons = []
                    for job in user_jobs:
                        progress = f"{job['sent']}/{job['total']}"
                        status_emoji = "âœ…" if job['status'] == 'running' else "âŒ"
                        account_info = f" [{job['account_name']}]" if job.get('multi_account') else ""
                        text += f"{status_emoji} **Job {job['id'][:8]}**{account_info}\n"
                        text += f"   Progress: {progress} ({job['status']})\n"
                        if job['failed'] > 0:
                            text += f"   Failed: {job['failed']}\n"
                        text += "\n"
                        if job['status'] == 'running':
                            buttons.append([Button.inline(f"â¹ï¸ Stop {job['id'][:8]}", f"bulk:stop:{job['id']}")])
                    buttons.append([Button.inline("ðŸ”„ Refresh", "bulk:jobs")])
                    buttons.append([Button.inline("ðŸ”™ Back to Bulk Sender", "msg:bulk")])
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to show bulk jobs: {e}")
    async def _show_bulk_help(self, user_id: int, message_id: int):
        """Show bulk help - delegated to MessagingOperations"""
        from .menu_modules import MessagingOperations
        ops = MessagingOperations(self)
        await ops.show_bulk_help(user_id, message_id)
    
    async def _show_bulk_help_legacy(self, user_id: int, message_id: int):
        """Legacy bulk help display"""
        text = (
            "â“ **Bulk Sender Help**\n\n"
            "**Available Commands:**\n"
            "â€¢ `/bulk_send` - Show bulk sender help\n"
            "â€¢ `/bulk_send_list account_name` - Send to specific users\n"
            "â€¢ `/bulk_send_contacts account_name` - Send to all contacts\n"
            "â€¢ `/bulk_send_all` - Send from ALL accounts\n"
            "â€¢ `/bulk_jobs` - View active jobs\n"
            "â€¢ `/bulk_stop <job_id>` - Stop a job\n\n"
            "**Format for list sending:**\n"
            "`/bulk_send_list account_name\n"
            "username1,username2,user_id3\n"
            "Your message here`\n\n"
            "**Button Format:**\n"
            "Add buttons using: `[Button Text](url)` or `[Button Text](callback_data)`\n"
            "Example: `Check this out [Visit Site](https://example.com) [More Info](info_callback)`\n\n"
            "**Tips:**\n"
            "â€¢ Use the menu buttons for easier setup\n"
            "â€¢ Commands provide more advanced options\n"
            "â€¢ Jobs run in background with progress updates"
        )
        buttons = [[Button.inline("ðŸ”™ Back to Bulk Sender", "msg:bulk")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    async def _handle_simulate_callback(self, event, user_id: int, data: str):
        await self.callback_handlers.handle_simulate_callback(event, user_id, data)
    
    async def _handle_simulate_callback_legacy(self, event, user_id: int, data: str):
        """Handle Activity Simulator callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"
        if action == "toggle":
            await self._toggle_simulation(user_id, account_id, event)
        elif action == "status":
            await self._show_simulation_status(user_id, account_id, event.message_id)
        elif action == "log":
            await self._show_activity_log(user_id, account_id, event.message_id)
        elif action == "stats":
            await self._show_simulation_stats(user_id, account_id, event.message_id)
    async def _toggle_simulation(self, user_id: int, account_id: str, event):
        """Toggle Activity Simulator for account"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if account:
                new_status = not account.get("simulation_enabled", False)
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {"simulation_enabled": new_status}}
                )
                if hasattr(self.account_manager, "activity_simulator"):
                    if new_status:
                        await self.account_manager.activity_simulator._start_account_simulation(
                            user_id, account_id, account["name"]
                        )
                    else:
                        task_key = f"{user_id}_{account_id}"
                        if task_key in self.account_manager.activity_simulator.simulation_tasks:
                            self.account_manager.activity_simulator.simulation_tasks[task_key].cancel()
                            del self.account_manager.activity_simulator.simulation_tasks[task_key]
                status = "enabled" if new_status else "disabled"
                status_emoji = "ðŸŽ­" if new_status else "ðŸ”´"
                await event.answer(f"{status_emoji} Activity simulation {status}!")
                await self.send_account_management(
                    user_id, account_id, event.message_id
                )
            else:
                await event.answer("âŒ Account not found")
        except Exception as e:
            logger.error(f"Toggle simulation error: {e}")
            await event.answer("âŒ Error toggling simulation")
    async def _show_simulation_status(
        self, user_id: int, account_id: str, message_id: int
    ):
        """Show Activity Simulator status"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if account:
                status = (
                    "âœ… Active"
                    if account.get("simulation_enabled", False)
                    else "âŒ Inactive"
                )
                text = (
                    f"ðŸŽ­ **Activity Simulator: {account['name']}**\n\n"
                    f"Status: {status}\n\n"
                    f"The simulator performs human-like activities:\n"
                    f"â€¢ Views random channels/groups\n"
                    f"â€¢ Reacts to posts with emojis\n"
                    f"â€¢ Votes in polls occasionally\n"
                    f"â€¢ Browses user profiles\n"
                    f"â€¢ Rarely joins/leaves channels\n\n"
                    f"Sessions every 30-90 minutes with 2-5 actions each."
                )
                toggle_text = (
                    "ðŸ”´ Disable"
                    if account.get("simulation_enabled", False)
                    else "ðŸŸ¢ Enable"
                )
                buttons = [
                    [
                        Button.inline(
                            f"{toggle_text} Simulation", f"simulate:toggle:{account_id}"
                        )
                    ],
                    [
                        Button.inline(
                            "ðŸ“‹ Activity Log (4h)", f"simulate:log:{account_id}"
                        )
                    ],
                    [Button.inline("ðŸ”™ Back", f"account:manage:{account_id}")],
                ]
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            else:
                await self.bot.send_message(user_id, "âŒ Account not found")
        except Exception as e:
            logger.error(f"Show simulation status error: {e}")
    async def _show_activity_log(self, user_id: int, account_id: str, message_id: int):
        """Show activity log for account"""
        from ..handlers.activity_log_handler import show_activity_log
        await show_activity_log(self.bot, user_id, account_id, message_id)
    async def _show_simulation_stats(self, user_id: int, account_id: str, message_id: int):
        """Show simulation statistics for account"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if account:
                stats_text = "Loading statistics..."
                if hasattr(self.account_manager, 'activity_simulator'):
                    task_key = f"{user_id}_{account_id}"
                    if task_key in self.account_manager.activity_simulator.simulation_tasks:
                        stats = self.account_manager.activity_simulator.stats.get(task_key, {})
                        total_actions = stats.get('total_actions', 0)
                        last_session = stats.get('last_session', 'Never')
                        avg_actions = stats.get('avg_actions_per_session', 0)
                        stats_text = (
                            f"**Statistics:**\n"
                            f"â€¢ Total Actions: {total_actions}\n"
                            f"â€¢ Last Session: {last_session}\n"
                            f"â€¢ Avg Actions/Session: {avg_actions:.1f}\n"
                            f"â€¢ Status: {'Active' if account.get('simulation_enabled') else 'Inactive'}"
                        )
                    else:
                        stats_text = "No active simulation session found."
                text = (
                    f"ðŸ“Š **Simulation Stats: {account['name']}**\n\n"
                    f"{stats_text}\n\n"
                    f"**Activity Types:**\n"
                    f"â€¢ Channel/Group browsing\n"
                    f"â€¢ Emoji reactions\n"
                    f"â€¢ Poll voting\n"
                    f"â€¢ Profile viewing\n"
                    f"â€¢ Occasional joins/leaves"
                )
                buttons = [
                    [Button.inline("ðŸ”„ Refresh", f"simulate:stats:{account_id}")],
                    [Button.inline("ðŸ”™ Back", f"account:manage:{account_id}")]
                ]
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            else:
                await self.bot.send_message(user_id, "âŒ Account not found")
        except Exception as e:
            logger.error(f"Show simulation stats error: {e}")
            text = "âŒ Error loading simulation statistics"
            buttons = [[Button.inline("ðŸ”™ Back", f"account:manage:{account_id}")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    async def _handle_audit_callback(self, event, user_id: int, data: str):
        """Handle audit-related callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"
        hours = int(parts[3]) if len(parts) > 3 else 24
        if hasattr(self.account_manager, "activity_simulator"):
            from ..handlers.audit_handler import AuditHandler
            audit_handler = AuditHandler(self.account_manager)
            if action == "refresh":
                await audit_handler.show_comprehensive_audit_log(
                    self.bot, user_id, account_id, event.message_id, hours
                )
            elif action == "summary":
                await audit_handler.show_activity_summary(
                    self.bot, user_id, account_id, event.message_id
                )
            elif action == "stats":
                await audit_handler.show_activity_stats(
                    self.bot, user_id, account_id, event.message_id
                )
        else:
            await event.answer("âŒ Audit system unavailable")
    async def _handle_manage_callback(self, event, user_id: int, data: str):
        """Handle channel management account selection"""
        account_phone = data.split(":")[1]
        await self._send_channel_actions_menu(user_id, account_phone, event.message_id)
    async def _send_channel_actions_menu(
        self, user_id: int, account_phone: str, message_id: int
    ):
        """Send channel actions menu for selected account"""
        text = f"ðŸ“± **Managing: {account_phone}**\n\nWhat would you like to do?"
        buttons = [
            [
                Button.inline("ðŸ”— Join Channel", f"channel:join:{account_phone}"),
                Button.inline("ðŸš« Leave Channel", f"channel:leave:{account_phone}"),
            ],
            [
                Button.inline("ðŸ†• Create Channel", f"channel:create:{account_phone}"),
                Button.inline("ðŸ—‘ï¸ Delete Channel", f"channel:delete:{account_phone}"),
            ],
            [Button.inline("ðŸ“‹ List Channels", f"channel:list:{account_phone}")],
            [Button.inline("ðŸ”™ Back to Accounts", "back:accounts")],
        ]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    async def _handle_channels_pagination(self, event, user_id: int, data: str):
        """Handle channels pagination callbacks"""
        parts = data.split(":")
        action = parts[1]  # prev or next
        account_phone = parts[2]
        page = int(parts[3])
        (
            success,
            channels,
        ) = await self.account_manager.command_handlers.channel_manager.get_user_channels(
            user_id, account_phone
        )
        if success and channels:
            per_page = 10
            total_pages = (len(channels) + per_page - 1) // per_page
            start_idx = page * per_page
            end_idx = min(start_idx + per_page, len(channels))
            page_channels = channels[start_idx:end_idx]
            text = f"ðŸ“‹ **Channels for {account_phone}** (Page {page + 1}/{total_pages})\n\n"
            for i, ch in enumerate(page_channels, start_idx + 1):
                emoji = "ðŸ“¢" if ch["type"] == "channel" else "ðŸ‘¥"
                type_text = "Channel" if ch["type"] == "channel" else "Group"
                username = f"@{ch['username']}" if ch["username"] else f"ID: {ch['id']}"
                text += (
                    f"{i}. {emoji} **{ch['title']}** ({type_text})\n   {username}\n\n"
                )
            # Navigation buttons
            nav_buttons = []
            if page > 0:
                nav_buttons.append(
                    Button.inline(
                        "â¬…ï¸ Previous", f"channels:prev:{account_phone}:{page-1}"
                    )
                )
            if page < total_pages - 1:
                nav_buttons.append(
                    Button.inline("âž¡ï¸ Next", f"channels:next:{account_phone}:{page+1}")
                )
            buttons = []
            if nav_buttons:
                buttons.append(nav_buttons)
            buttons.append([Button.inline("ðŸ”™ Back", f"manage:{account_phone}")])
            await event.answer(f"Page {page + 1}")
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
    def _get_uptime(self) -> str:
        """Get bot uptime"""
        try:
            import time
            if hasattr(self.account_manager, 'start_time'):
                uptime_seconds = time.time() - self.account_manager.start_time
                hours = int(uptime_seconds // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                return f"{hours}h {minutes}m"
            return "Unknown"
        except:
            return "Unknown"
    async def _handle_export_sessions(self, event, user_id: int):
        """Handle export sessions menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = "âœ¨ **Fresh Sessions**\n\nâŒ No accounts found. Add accounts first to create fresh sessions."
                buttons = [[Button.inline("ðŸ”™ Back to Accounts", "menu:accounts")]]
            else:
                text = "âœ¨ **Fresh Sessions**\n\nSelect account to create fresh session for:"
                buttons = []
                for account in accounts:
                    status = "âœ…" if account.get("is_active", False) else "âŒ"
                    display_name = self.format_display_name(account)
                    buttons.append([Button.inline(f"{status} {display_name}", f"export_session:{account['name']}")])
                buttons.append([Button.inline("ðŸ”™ Back to Accounts", "menu:accounts")])
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to handle export sessions: {e}")
            await event.answer("âŒ Error loading export sessions")
    
    async def _handle_export_session_select(self, event, user_id: int, account_name: str):
        """Handle export session selection"""
        try:
            # Find account by name
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            if not account:
                await event.answer("âŒ Account not found")
                return
            
            display_name = self.format_display_name(account)
            text = f"âœ¨ **Fresh Session: {display_name}**\n\nThis will create a completely new session:"
            buttons = [
                [Button.inline("âœ¨ Create Fresh Session", f"export_fresh:{account_name}")],
                [Button.inline("ðŸ”™ Back to Export", "export_sessions")]
            ]
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to handle export session select: {e}")
            await event.answer("âŒ Error processing export selection")
    
    async def _handle_export_session_file(self, event, user_id: int, account_name: str):
        """Handle export session file"""
        try:
            # Find account by name
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            if not account:
                await event.answer("âŒ Account not found")
                return
            
            if not account.get("is_active", False):
                await event.answer("âŒ Account is not connected")
                return
            
            # Use account manager to export session file
            if hasattr(self.account_manager, 'export_session_file'):
                success, message = await self.account_manager.export_session_file(user_id, account['phone'])
                if success:
                    await event.answer("âœ… Session file exported successfully")
                else:
                    await event.answer(f"âŒ Export failed: {message}")
            else:
                await event.answer("âŒ Export functionality not available")
        except Exception as e:
            logger.error(f"Failed to export session file: {e}")
            await event.answer("âŒ Error exporting session file")
    
    async def _handle_export_fresh_session(self, event, user_id: int, account_name: str):
        """Handle export session string with DC information"""
        try:
            # Find account by name
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            if not account:
                await event.answer("âŒ Account not found")
                return
            
            if not account.get("is_active", False):
                await event.answer("âŒ Account is not connected")
                return
            
            # Get client from account manager
            if (user_id in self.account_manager.user_clients and 
                account_name in self.account_manager.user_clients[user_id]):
                client = self.account_manager.user_clients[user_id][account_name]
                if client and client.is_connected():
                    try:
                        # Get session string
                        session_string = client.session.save()
                        
                        # Get DC information - this is what you want: DC1, DC2, DC3, DC4, or DC5
                        dc_id = client.session.dc_id
                        if dc_id and 1 <= dc_id <= 5:
                            dc_display = f"DC{dc_id}"
                        else:
                            dc_display = "Unknown DC"
                        
                        # Get account info
                        display_name = self.format_display_name(account)
                        phone = account.get('phone', 'Unknown')
                        
                        # Format message with prominent DC information
                        message = (
                            f"ðŸ“ **Session Export - {dc_display}**\n\n"
                            f"ðŸ“± **Account:** {display_name}\n"
                            f"ðŸ“ž **Phone:** {phone}\n"
                            f"ðŸŒ **Data Center:** {dc_display}\n\n"
                            f"**Session String:**\n"
                            f"```\n{session_string}\n```\n\n"
                            f"**Usage Example:**\n"
                            f"```python\n"
                            f"from telethon import TelegramClient\n"
                            f"from telethon.sessions import StringSession\n\n"
                            f"# {dc_display} Session\n"
                            f"client = TelegramClient(\n"
                            f"    StringSession('{session_string}'),\n"
                            f"    api_id, api_hash\n"
                            f")\n"
                            f"await client.start()\n"
                            f"```\n\n"
                            f"âš ï¸ **Keep this {dc_display} session secure!**"
                        )
                        
                        from telethon import Button
                        buttons = [[Button.inline("ðŸ”™ Back to Export", "export_sessions")]]
                        await event.answer()
                        await self.bot.edit_message(user_id, event.message_id, message, buttons=buttons)
                        
                    except Exception as e:
                        logger.error(f"Error getting session data: {e}")
                        await event.answer("âŒ Error extracting session data")
                else:
                    await event.answer("âŒ Account client not connected")
            else:
                await event.answer("âŒ Account client not found")
                
        except Exception as e:
            logger.error(f"Failed to export session string: {e}")
            await event.answer("âŒ Error exporting session string")
    
    async def _handle_export_contacts(self, event, user_id: int, account_name: str):
        """Handle export contacts"""
        try:
            # Find account by name
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            if not account:
                await event.answer("âŒ Account not found")
                return
            
            if not account.get("is_active", False):
                await event.answer("âŒ Account is not connected")
                return
            
            # Use contact export handler
            try:
                from ..handlers.contact_export_handler import ContactExportHandler
                export_handler = ContactExportHandler(self.account_manager)
                success, message = await export_handler.export_contacts_to_csv(user_id, account['phone'])
                if success:
                    await event.answer("âœ… Contacts exported successfully")
                else:
                    await event.answer(f"âŒ Export failed: {message}")
            except ImportError:
                await event.answer("âŒ Contact export handler not available")
        except Exception as e:
            logger.error(f"Failed to export contacts: {e}")
            await event.answer("âŒ Error exporting contacts")
    
    async def _show_otp_statistics(self, user_id: int, message_id: int):
        """Show OTP statistics using the OTP metrics service"""
        try:
            from ..services.otp_metrics import OTPMetrics
            from datetime import datetime, timedelta
            
            otp_metrics = OTPMetrics()
            
            # Get date range for last 30 days
            end_date = datetime.utcnow().strftime("%Y-%m-%d")
            start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
            
            # Get global statistics
            global_stats = await otp_metrics.get_global_stats(start_date, end_date)
            
            # Get user's accounts for account-specific stats
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            
            # Get top blocked accounts (global)
            top_blocked = await otp_metrics.get_top_blocked_accounts(limit=5)
            
            # Get activity sparkline for last 7 days
            sparkline_start = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
            sparkline = await otp_metrics.get_activity_sparkline(sparkline_start, end_date)
            
            # Build statistics text
            text = (
                "ðŸ“Š **OTP Statistics (Last 30 Days)**\n\n"
                f"ðŸ•° **Global Summary:**\n"
                f"â€¢ Total Blocks: {global_stats.get('total_blocked', 0):,}\n"
                f"â€¢ Total Allows: {global_stats.get('total_allowed', 0):,}\n"
                f"â€¢ Protected Accounts: {len(global_stats.get('accounts', []))}\n"
                f"â€¢ Success Rate: {global_stats.get('block_rate', 0):.1f}%\n\n"
            )
            
            # Add user account stats if available
            if accounts:
                user_total_blocks = 0
                user_total_allows = 0
                for account in accounts:
                    account_id = str(account['_id'])
                    account_stats = await otp_metrics.get_account_stats(account_id, start_date, end_date)
                    user_total_blocks += account_stats.get('total_blocked', 0)
                    user_total_allows += account_stats.get('total_allowed', 0)
                
                text += (
                    f"ðŸ“± **Your Accounts:**\n"
                    f"â€¢ Your Blocks: {user_total_blocks:,}\n"
                    f"â€¢ Your Allows: {user_total_allows:,}\n"
                    f"â€¢ Managed Accounts: {len(accounts)}\n\n"
                )
            
            # Add top blocked accounts
            if top_blocked:
                text += "ðŸ† **Top Protected Accounts:**\n"
                for i, account_data in enumerate(top_blocked, 1):
                    account_id = account_data['_id']
                    blocks = account_data['total_blocked']
                    text += f"{i}. Account {account_id[:8]}... - {blocks:,} blocks\n"
                text += "\n"
            
            # Add activity sparkline
            if sparkline:
                text += f"ðŸ“ˆ **Activity (Last 7 Days):**\n{sparkline}\n\n"
            
            text += (
                "ðŸ“ **Legend:**\n"
                "â€¢ Blocks: Unauthorized login attempts stopped\n"
                "â€¢ Allows: Legitimate OTP codes forwarded\n"
                "â€¢ Success Rate: Percentage of malicious attempts blocked"
            )
            
            buttons = [
                [Button.inline("ðŸ”„ Refresh Stats", "otp:stats")],
                [Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]
            ]
            
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error showing OTP statistics: {e}")
            text = (
                "ðŸ“Š **OTP Statistics**\n\n"
                "âŒ Error loading statistics. Please try again.\n\n"
                f"Error: {str(e)}"
            )
            buttons = [[Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    def validate_session_string(self, session_string: str) -> dict:
        """Validate session string and extract DC information (DC1, DC2, DC3, DC4, or DC5)"""
        try:
            from telethon.sessions import StringSession
            from telethon import TelegramClient
            from ..core.config import config
            
            # Test the provided session string
            test_session = StringSession(session_string)
            temp_client = TelegramClient(test_session, config.telegram.api_id, config.telegram.api_hash)
            
            # Extract DC information - show DC1, DC2, DC3, DC4, or DC5
            dc_id = test_session.dc_id if hasattr(test_session, 'dc_id') else None
            if dc_id and 1 <= dc_id <= 5:
                dc_name = f"DC{dc_id}"
            else:
                dc_name = "Unknown DC"
            
            return {
                "valid": True,
                "dc_id": dc_id,
                "dc_name": dc_name,
                "length": len(session_string),
                "format": "Telethon StringSession"
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
                "length": len(session_string) if session_string else 0,
                "format": "Invalid"
            }
    
    async def _handle_bulk_otp_enable(self, user_id: int, message_id: int):
        """Enable OTP Destroyer for all user accounts"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = "ðŸ›¡ï¸ **Enable All OTP Destroyers**\n\nâŒ No accounts found."
                buttons = [[Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]]
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                return
            
            # Enable OTP Destroyer for all accounts
            enabled_count = 0
            for account in accounts:
                try:
                    from bson import ObjectId
                    await mongodb.db.accounts.update_one(
                        {"_id": ObjectId(account['_id'])},
                        {"$set": {
                            "otp_destroyer_enabled": True,
                            "otp_forward_enabled": False
                        }}
                    )
                    enabled_count += 1
                except Exception as e:
                    logger.error(f"Error enabling OTP for account {account['name']}: {e}")
            
            text = (
                f"ðŸ›¡ï¸ **Bulk Enable Complete**\n\n"
                f"âœ… Enabled OTP Destroyer for {enabled_count}/{len(accounts)} accounts\n\n"
                f"ðŸ”´ Forward disabled for all accounts (security best practice)\n\n"
                f"ðŸ›¡ï¸ All your accounts are now protected!"
            )
            
            buttons = [
                [Button.inline("ðŸ“Š View Statistics", "otp:stats")],
                [Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]
            ]
            
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in bulk OTP enable: {e}")
            text = f"âŒ Error enabling OTP Destroyers: {str(e)}"
            buttons = [[Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _handle_bulk_otp_disable(self, user_id: int, message_id: int):
        """Disable OTP Destroyer for all user accounts"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = "ðŸ”´ **Disable All OTP Destroyers**\n\nâŒ No accounts found."
                buttons = [[Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]]
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                return
            
            # Disable OTP Destroyer for all accounts
            disabled_count = 0
            for account in accounts:
                try:
                    from bson import ObjectId
                    await mongodb.db.accounts.update_one(
                        {"_id": ObjectId(account['_id'])},
                        {"$set": {"otp_destroyer_enabled": False}}
                    )
                    disabled_count += 1
                except Exception as e:
                    logger.error(f"Error disabling OTP for account {account['name']}: {e}")
            
            text = (
                f"ðŸ”´ **Bulk Disable Complete**\n\n"
                f"âŒ Disabled OTP Destroyer for {disabled_count}/{len(accounts)} accounts\n\n"
                f"âš ï¸ **WARNING:** All your accounts are now vulnerable to unauthorized login attempts!\n\n"
                f"ðŸ›¡ï¸ Consider re-enabling protection when needed."
            )
            
            buttons = [
                [Button.inline("ðŸ›¡ï¸ Enable All Again", "otp:enable_all")],
                [Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]
            ]
            
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in bulk OTP disable: {e}")
            text = f"âŒ Error disabling OTP Destroyers: {str(e)}"
            buttons = [[Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _show_global_audit_log(self, user_id: int, message_id: int):
        """Show global audit log for all user accounts"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = "ðŸ“‹ **Global OTP Audit Log**\n\nâŒ No accounts found."
                buttons = [[Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]]
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                return
            
            # Collect audit entries from all accounts
            all_entries = []
            for account in accounts:
                audit_log = account.get("audit_log", [])
                for entry in audit_log:
                    entry_copy = entry.copy()
                    entry_copy["account_name"] = account.get("name", "Unknown")
                    entry_copy["account_phone"] = account.get("phone", "Unknown")
                    all_entries.append(entry_copy)
            
            # Sort by timestamp (newest first)
            all_entries.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            
            if not all_entries:
                text = "ðŸ“‹ **Global OTP Audit Log**\n\nðŸ’­ No audit entries found across all accounts."
            else:
                text = f"ðŸ“‹ **Global OTP Audit Log**\n\nShowing last {min(15, len(all_entries))} entries across all accounts:\n\n"
                
                # Show last 15 entries
                for entry in all_entries[:15]:
                    timestamp = entry.get("timestamp", 0)
                    action = entry.get("action", "unknown")
                    account_name = entry.get("account_name", "Unknown")
                    
                    import time
                    time_str = time.strftime("%m-%d %H:%M", time.localtime(timestamp))
                    
                    # Map actions to user-friendly messages
                    action_messages = {
                        "otp_destroyed": f"ðŸ›¡ï¸ Blocked login code {entry.get('code', 'Unknown')}",
                        "otp_forwarded": f"ðŸ“¤ Forwarded login code {entry.get('code', 'Unknown')}",
                        "destroyer_enabled": "ðŸ›¡ï¸ OTP Destroyer enabled",
                        "destroyer_disabled": "ðŸ”´ OTP Destroyer disabled",
                        "forwarding_enabled": "ðŸ“¤ OTP Forwarding enabled",
                        "forwarding_disabled": "ðŸ”´ OTP Forwarding disabled",
                        "temp_passthrough_enabled": "â° 5-minute passthrough activated",
                        "temp_passthrough_expired": "â° 5-minute passthrough expired",
                    }
                    
                    message = action_messages.get(action, f"Unknown: {action}")
                    text += f"{time_str} | {account_name[:12]}: {message}\n"
                
                if len(all_entries) > 15:
                    text += f"\n... and {len(all_entries) - 15} more entries"
            
            buttons = [
                [Button.inline("ðŸ”„ Refresh Log", "otp:audit_all")],
                [Button.inline("ðŸ“Š View Statistics", "otp:stats")],
                [Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]
            ]
            
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error showing global audit log: {e}")
            text = f"âŒ Error loading global audit log: {str(e)}"
            buttons = [[Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    async def _handle_otp_setting_callback(self, event, user_id: int, data: str):
        """Handle OTP setting callbacks - direct enable/disable without old menu"""
        parts = data.split(":")
        setting_type = parts[1]  # destroyer, forward, or temp
        
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                await event.answer("âŒ No accounts found")
                return
            
            if setting_type == "destroyer":
                text = "ðŸ›¡ï¸ **OTP Destroyer Settings**\n\nSelect account to toggle OTP Destroyer:"
                buttons = []
                for account in accounts:
                    status = "ðŸŸ¢" if account.get("is_active", False) else "ðŸ”´"
                    destroyer_status = "ðŸ›¡ï¸" if account.get("otp_destroyer_enabled", False) else "âšª"
                    display_name = format_display_name(account)
                    action = "disable" if account.get("otp_destroyer_enabled", False) else "enable"
                    button_text = f"{status}{destroyer_status} {display_name}"
                    buttons.append([Button.inline(button_text, f"otp:{action}:{account['_id']}")])
                    
            elif setting_type == "forward":
                text = "ðŸ“¤ **OTP Forward Settings**\n\nSelect account to toggle OTP Forward:"
                buttons = []
                for account in accounts:
                    status = "ðŸŸ¢" if account.get("is_active", False) else "ðŸ”´"
                    forward_status = "ðŸ“¤" if account.get("otp_forward_enabled", False) else "âšª"
                    display_name = format_display_name(account)
                    action = "forward_disable" if account.get("otp_forward_enabled", False) else "forward_enable"
                    button_text = f"{status}{forward_status} {display_name}"
                    buttons.append([Button.inline(button_text, f"otp:{action}:{account['_id']}")])
                    
            elif setting_type == "temp":
                text = "â° **Temp OTP Settings**\n\nSelect account to enable 5-minute temp OTP:"
                buttons = []
                for account in accounts:
                    status = "ðŸŸ¢" if account.get("is_active", False) else "ðŸ”´"
                    destroyer_status = "ðŸ›¡ï¸" if account.get("otp_destroyer_enabled", False) else "âšª"
                    display_name = format_display_name(account)
                    button_text = f"{status}{destroyer_status} {display_name}"
                    buttons.append([Button.inline(button_text, f"otp:temp:{account['_id']}")])
            
            buttons.append([Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")])
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in OTP setting callback: {e}")
            await event.answer("âŒ Error processing OTP setting")

    async def _show_global_audit_log(self, user_id: int, message_id: int):
        """Show global audit log for all user accounts"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = "ðŸ“‹ **Global Audit Log**\n\nâŒ No accounts found."
                buttons = [[Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]]
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                return
            
            all_entries = []
            for account in accounts:
                audit_log = account.get("audit_log", [])
                for entry in audit_log[-5:]:
                    entry["account_name"] = account["name"]
                    all_entries.append(entry)
            
            all_entries.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            
            if not all_entries:
                text = "ðŸ“‹ **Global Audit Log**\n\nðŸ’­ No audit entries found."
            else:
                text = f"ðŸ“‹ **Global Audit Log** (Last {len(all_entries)} entries)\n\n"
                
                for entry in all_entries[:15]:
                    timestamp = entry.get("timestamp", 0)
                    action = entry.get("action", "unknown")
                    account_name = entry.get("account_name", "Unknown")
                    
                    import time
                    time_str = time.strftime("%m-%d %H:%M", time.localtime(timestamp))
                    
                    if action in ["otp_destroyed", "invalidate_codes"]:
                        emoji = "ðŸ›¡ï¸"
                        msg = f"Blocked login code {entry.get('code', 'Unknown')}"
                    elif action == "otp_forwarded":
                        emoji = "ðŸ“¤"
                        msg = f"Forwarded login code {entry.get('code', 'Unknown')}"
                    elif action in ["destroyer_enabled", "enable_otp_destroyer"]:
                        emoji = "ðŸŸ¢"
                        msg = "OTP Destroyer enabled"
                    elif action in ["destroyer_disabled", "disable_otp_destroyer"]:
                        emoji = "ðŸ”´"
                        msg = "OTP Destroyer disabled"
                    else:
                        emoji = "â„¹ï¸"
                        msg = f"Action: {action}"
                    
                    text += f"{emoji} {time_str} [{account_name}]: {msg}\n"
            
            buttons = [
                [Button.inline("ðŸ”„ Refresh", "otp:audit_all")],
                [Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]
            ]
            
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error showing global audit log: {e}")
            text = "âŒ Error loading global audit log"
            buttons = [[Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    async def _handle_otp_toggle_callback(self, event, user_id: int, data: str):
        """Handle direct OTP toggle callbacks without showing old menu"""
        parts = data.split(":")
        toggle_type = parts[1]  # destroyer, forward, or temp
        account_id = parts[2]
        
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                await event.answer("âŒ Account not found")
                return
            
            display_name = format_display_name(account)
            
            if toggle_type == "destroyer":
                current_status = account.get("otp_destroyer_enabled", False)
                new_status = not current_status
                
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {
                        "otp_destroyer_enabled": new_status,
                        "otp_forward_enabled": False if new_status else account.get("otp_forward_enabled", False)
                    }}
                )
                
                if new_status:
                    await event.answer(f"ðŸ›¡ï¸ OTP Destroyer enabled for {display_name}!")
                else:
                    await event.answer(f"ðŸ”´ OTP Destroyer disabled for {display_name}!")
                    
            elif toggle_type == "forward":
                # Check if destroyer is enabled first
                if account.get("otp_destroyer_enabled", False):
                    await event.answer("âŒ Cannot enable forward while OTP Destroyer is active")
                    return
                    
                current_status = account.get("otp_forward_enabled", False)
                new_status = not current_status
                
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {"otp_forward_enabled": new_status}}
                )
                
                if new_status:
                    await event.answer(f"ðŸ“¤ OTP Forward enabled for {display_name}!")
                else:
                    await event.answer(f"ðŸ”´ OTP Forward disabled for {display_name}!")
                    
            elif toggle_type == "temp":
                if not account.get("otp_destroyer_enabled", False):
                    await event.answer("âš ï¸ Temp OTP only works when OTP Destroyer is enabled")
                    return
                    
                # Enable 5-minute temp passthrough
                import time
                expiry_time = time.time() + 300  # 5 minutes
                
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {
                        "otp_temp_passthrough": True,
                        "temp_passthrough_expiry": expiry_time,
                        "otp_destroyer_enabled": False,  # Temporarily disable
                        "otp_forward_enabled": True,    # Temporarily enable
                    }}
                )
                
                await event.answer(f"â° 5-minute temp OTP enabled for {display_name}!")
                
                # Schedule cleanup
                try:
                    from ..handlers.temp_otp_cleanup import cleanup_temp_otp
                    import asyncio
                    asyncio.create_task(cleanup_temp_otp(user_id, account_id, expiry_time))
                except ImportError:
                    logger.warning("temp_otp_cleanup module not found")
            
            # Refresh the current menu to show updated status
            await self._handle_otp_setting_callback(event, user_id, f"otp_setting:{toggle_type}")
            
        except Exception as e:
            logger.error(f"Error in OTP toggle callback: {e}")
            await event.answer("âŒ Error toggling OTP setting")



    async def _show_messaging_statistics(self, user_id: int, message_id: int):
        """Show messaging statistics"""
        try:
            from telethon import Button
            if hasattr(self.account_manager, 'unified_messaging'):
                stats = await self.account_manager.unified_messaging.get_messaging_statistics(user_id)
                
                text = (
                    "ðŸ“Š **Messaging Analytics**\n\n"
                    f"ðŸ“¤ **Total Messages:** {stats.get('total_messages_sent', 0)}\n"
                    f"ðŸ¤– **Auto-Replies:** {stats.get('auto_replies_sent', 0)}\n"
                    f"ðŸ“± **Active Accounts:** {stats.get('active_accounts', 0)}\n"
                    f"ðŸ“¨ **DM Topics:** {stats.get('dm_topics_created', 0)}\n\n"
                    "ðŸ’¡ **Tip:** Enable auto-reply for better engagement"
                )
            else:
                text = "ðŸ“Š **Messaging Analytics**\n\nâŒ Analytics is unavailable for messages"
            
            buttons = [[Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing messaging statistics: {e}")
            from telethon import Button
            text = "âŒ Analytics is unavailable for messages"
            buttons = [[Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _show_message_history(self, user_id: int, message_id: int):
        """Show message history"""
        try:
            from telethon import Button
            from ..services.messaging_stats import MessagingStats
            stats_service = MessagingStats()
            
            recent_messages = await stats_service.get_recent_messages(user_id, limit=10)
            
            if not recent_messages:
                text = "ðŸ“‹ **Message History**\n\nðŸ’­ No recent messages found."
            else:
                text = "ðŸ“‹ **Message History** (Last 10)\n\n"
                for msg in recent_messages:
                    import time
                    timestamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(msg.get('timestamp', 0)))
                    target = msg.get('target', 'Unknown')
                    msg_type = msg.get('type', 'message')
                    emoji = "ðŸ¤–" if msg_type == "auto_reply" else "ðŸ“¤"
                    text += f"{emoji} {timestamp} â†’ {target}\n"
            
            buttons = [[Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing message history: {e}")
            from telethon import Button
            text = "âŒ Message history is unavailable"
            buttons = [[Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _show_messaging_settings(self, user_id: int, message_id: int):
        """Show messaging system settings"""
        try:
            from telethon import Button
            settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
            
            keyword_enabled = settings.get('keyword_replies_enabled', False)
            time_based_enabled = settings.get('time_based_replies_enabled', False)
            
            text = (
                "âš™ï¸ **Messaging System Settings**\n\n"
                f"ðŸ”‘ **Keyword Replies:** {'âœ… Enabled' if keyword_enabled else 'âŒ Disabled'}\n"
                f"â° **Time-Based Replies:** {'âœ… Enabled' if time_based_enabled else 'âŒ Disabled'}\n\n"
                "**Configure:**\n"
                "â€¢ Auto-reply rules\n"
                "â€¢ Message templates\n"
                "â€¢ DM forwarding\n"
                "â€¢ Notification preferences\n\n"
                "Use the buttons below to manage settings."
            )
            
            buttons = [
                [Button.inline("ðŸ¤– Auto-Reply Settings", "auto_reply:main")],
                [Button.inline("ðŸ“ Template Settings", "template:main")],
                [Button.inline("ðŸ“¨ DM Reply Settings", "dm_reply:main")],
                [Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]
            ]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing messaging settings: {e}")
            from telethon import Button
            text = "âŒ System settings is unavailable"
            buttons = [[Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)



    async def _show_messaging_statistics(self, user_id: int, message_id: int):
        """Show messaging statistics"""
        try:
            from telethon import Button
            if hasattr(self.account_manager, 'unified_messaging'):
                stats = await self.account_manager.unified_messaging.get_messaging_statistics(user_id)
                
                text = (
                    "ðŸ“Š **Messaging Analytics**\n\n"
                    f"ðŸ“¤ **Total Messages:** {stats.get('total_messages_sent', 0)}\n"
                    f"ðŸ¤– **Auto-Replies:** {stats.get('auto_replies_sent', 0)}\n"
                    f"ðŸ“± **Active Accounts:** {stats.get('active_accounts', 0)}\n"
                    f"ðŸ“¨ **DM Topics:** {stats.get('dm_topics_created', 0)}\n\n"
                    "ðŸ’¡ **Tip:** Enable auto-reply for better engagement"
                )
            else:
                text = "ðŸ“Š **Messaging Analytics**\n\nâŒ Analytics is unavailable for messages"
            
            buttons = [[Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing messaging statistics: {e}")
            from telethon import Button
            text = "âŒ Analytics is unavailable for messages"
            buttons = [[Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _show_message_history(self, user_id: int, message_id: int):
        """Show message history"""
        try:
            from telethon import Button
            from ..services.messaging_stats import MessagingStats
            stats_service = MessagingStats()
            
            recent_messages = await stats_service.get_recent_messages(user_id, limit=10)
            
            if not recent_messages:
                text = "ðŸ“‹ **Message History**\n\nðŸ’­ No recent messages found."
            else:
                text = "ðŸ“‹ **Message History** (Last 10)\n\n"
                for msg in recent_messages:
                    import time
                    timestamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(msg.get('timestamp', 0)))
                    target = msg.get('target', 'Unknown')
                    msg_type = msg.get('type', 'message')
                    emoji = "ðŸ¤–" if msg_type == "auto_reply" else "ðŸ“¤"
                    text += f"{emoji} {timestamp} â†’ {target}\n"
            
            buttons = [[Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing message history: {e}")
            from telethon import Button
            text = "âŒ Message history is unavailable"
            buttons = [[Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _show_messaging_settings(self, user_id: int, message_id: int):
        """Show messaging system settings"""
        try:
            from telethon import Button
            settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
            
            keyword_enabled = settings.get('keyword_replies_enabled', False)
            time_based_enabled = settings.get('time_based_replies_enabled', False)
            
            text = (
                "âš™ï¸ **Messaging System Settings**\n\n"
                f"ðŸ”‘ **Keyword Replies:** {'âœ… Enabled' if keyword_enabled else 'âŒ Disabled'}\n"
                f"â° **Time-Based Replies:** {'âœ… Enabled' if time_based_enabled else 'âŒ Disabled'}\n\n"
                "**Configure:**\n"
                "â€¢ Auto-reply rules\n"
                "â€¢ Message templates\n"
                "â€¢ DM forwarding\n"
                "â€¢ Notification preferences\n\n"
                "Use the buttons below to manage settings."
            )
            
            buttons = [
                [Button.inline("ðŸ¤– Auto-Reply Settings", "auto_reply:main")],
                [Button.inline("ðŸ“ Template Settings", "template:main")],
                [Button.inline("ðŸ“¨ DM Reply Settings", "dm_reply:main")],
                [Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]
            ]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing messaging settings: {e}")
            from telethon import Button
            text = "âŒ System settings is unavailable"
            buttons = [[Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _show_messaging_statistics(self, user_id: int, message_id: int):
        """Show messaging statistics"""
        try:
            if hasattr(self.account_manager, 'unified_messaging'):
                stats = await self.account_manager.unified_messaging.get_messaging_statistics(user_id)
                text = (
                    "ðŸ“Š **Messaging Analytics**\n\n"
                    f"ðŸ“¤ Total Messages Sent: {stats.get('total_messages_sent', 0)}\n"
                    f"ðŸ¤– Auto-Replies Sent: {stats.get('auto_replies_sent', 0)}\n"
                    f"ðŸ“± Active Accounts: {stats.get('active_accounts', 0)}\n"
                    f"ðŸ“¨ DM Topics Created: {stats.get('dm_topics_created', 0)}\n\n"
                    "Use messaging features to see more detailed statistics."
                )
            else:
                text = "ðŸ“Š **Messaging Analytics**\n\nâŒ Statistics service unavailable."
            buttons = [[Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing messaging statistics: {e}")
            text = "âŒ Error loading statistics"
            buttons = [[Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _show_message_history(self, user_id: int, message_id: int):
        """Show message history"""
        try:
            text = (
                "ðŸ“‹ **Message History**\n\n"
                "View your recent messaging activity:\n\n"
                "â€¢ Sent messages\n"
                "â€¢ Received messages\n"
                "â€¢ Auto-reply interactions\n"
                "â€¢ Bulk campaign results\n\n"
                "ðŸ’¡ **Coming Soon:** Full message history tracking with filters and search."
            )
            buttons = [[Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing message history: {e}")
    
    async def _show_messaging_settings(self, user_id: int, message_id: int):
        """Show messaging system settings"""
        try:
            text = (
                "âš™ï¸ **Messaging System Settings**\n\n"
                "Configure your messaging preferences:\n\n"
                "ðŸ“¤ **Message Delivery:**\n"
                "â€¢ Delivery confirmation\n"
                "â€¢ Read receipts\n"
                "â€¢ Typing indicators\n\n"
                "ðŸ¤– **Auto-Reply:**\n"
                "â€¢ Global enable/disable\n"
                "â€¢ Response delay settings\n"
                "â€¢ Keyword management\n\n"
                "ðŸ“¨ **DM Management:**\n"
                "â€¢ Topic auto-creation\n"
                "â€¢ Notification preferences\n"
                "â€¢ Archive settings\n\n"
                "ðŸ’¡ **Coming Soon:** Advanced configuration options."
            )
            buttons = [[Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing messaging settings: {e}")

    async def _show_bulk_otp_enable(self, user_id: int, message_id: int):
        """Enable OTP Destroyer for all accounts"""
        try:
            accounts = await mongodb.db.accounts.find({" user_id": user_id}).to_list(length=None)
            enabled_count = 0
            for account in accounts:
                if not account.get("otp_destroyer_enabled", False):
                    await mongodb.db.accounts.update_one(
                        {"_id": account["_id"]},
                        {"$set": {"otp_destroyer_enabled": True, "otp_forward_enabled": False}}
                    )
                    enabled_count += 1
            text = f"âœ… **Bulk Enable Complete**\n\nðŸ›¡ï¸ Enabled OTP Destroyer on {enabled_count} accounts"
            buttons = [[Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Bulk OTP enable error: {e}")

    async def _handle_bulk_otp_disable(self, user_id: int, message_id: int):
        """Disable OTP Destroyer for all accounts"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            disabled_count = 0
            for account in accounts:
                if account.get("otp_destroyer_enabled", False):
                    await mongodb.db.accounts.update_one(
                        {"_id": account["_id"]},
                        {"$set": {"otp_destroyer_enabled": False}}
                    )
                    disabled_count += 1
            text = f"ðŸ”´ **Bulk Disable Complete**\n\nâŒ Disabled OTP Destroyer on {disabled_count} accounts"
            buttons = [[Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Bulk OTP disable error: {e}")

    async def _show_otp_statistics(self, user_id: int, message_id: int):
        """Show OTP statistics"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            total = len(accounts)
            destroyer_enabled = sum(1 for acc in accounts if acc.get("otp_destroyer_enabled", False))
            forward_enabled = sum(1 for acc in accounts if acc.get("otp_forward_enabled", False))
            text = (
                "ðŸ“Š **OTP Statistics**\n\n"
                f"ðŸ“± Total Accounts: {total}\n"
                f"ðŸ›¡ï¸ Destroyer Enabled: {destroyer_enabled}\n"
                f"ðŸ“¤ Forward Enabled: {forward_enabled}\n"
                f"âšª Unprotected: {total - destroyer_enabled - forward_enabled}\n\n"
                f"Security Score: {int((destroyer_enabled/max(total,1))*100)}%"
            )
            buttons = [
                [Button.inline("ðŸ”„ Refresh Stats", "otp:stats")],
                [Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]
            ]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"OTP stats error: {e}")

    async def _show_global_audit_log(self, user_id: int, message_id: int):
        """Show global audit log for all accounts"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            text = "ðŸ“‹ **Global Audit Log**\n\n"
            for account in accounts[:5]:
                audit_log = account.get("audit_log", [])[-3:]
                display_name = format_display_name(account)
                text += f"**{display_name}**\n"
                if audit_log:
                    for entry in audit_log:
                        action = entry.get("action", "unknown")
                        text += f"  â€¢ {action}\n"
                else:
                    text += "  â€¢ No recent activity\n"
                text += "\n"
            buttons = [
                [Button.inline("ðŸ”„ Refresh", "otp:audit_all")],
                [Button.inline("ðŸ”™ Back to OTP Manager", "menu:otp")]
            ]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Global audit log error: {e}")

    async def _show_messaging_statistics(self, user_id: int, message_id: int):
        """Show messaging statistics"""
        try:
            if hasattr(self.account_manager, 'unified_messaging'):
                stats = await self.account_manager.unified_messaging.get_messaging_statistics(user_id)
                text = (
                    "ðŸ“Š **Messaging Analytics**\n\n"
                    f"ðŸ“¤ Total Messages Sent: {stats.get('total_messages_sent', 0)}\n"
                    f"ðŸ¤– Auto-Replies Sent: {stats.get('auto_replies_sent', 0)}\n"
                    f"ðŸ“± Active Accounts: {stats.get('active_accounts', 0)}\n"
                    f"ðŸ“¨ DM Topics Created: {stats.get('dm_topics_created', 0)}"
                )
            else:
                text = "ðŸ“Š **Messaging Analytics**\n\nStatistics not available"
            buttons = [[Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Messaging stats error: {e}")

    async def _show_message_history(self, user_id: int, message_id: int):
        """Show message history"""
        text = (
            "ðŸ“‹ **Message History**\n\n"
            "View your recent messaging activity:\n\n"
            "â€¢ Sent messages\n"
            "â€¢ Auto-replies\n"
            "â€¢ DM conversations\n"
            "â€¢ Bulk campaigns\n\n"
            "Feature coming soon!"
        )
        buttons = [[Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _show_messaging_settings(self, user_id: int, message_id: int):
        """Show messaging system settings"""
        text = (
            "âš™ï¸ **Messaging System Settings**\n\n"
            "Configure messaging behavior:\n\n"
            "ðŸ“¤ **Message Delivery:**\n"
            "â€¢ Delivery confirmation\n"
            "â€¢ Read receipts\n"
            "â€¢ Typing indicators\n\n"
            "ðŸ¤– **Auto-Reply:**\n"
            "â€¢ Global enable/disable\n"
            "â€¢ Response delay\n"
            "â€¢ Keyword matching\n\n"
            "ðŸ“¨ **DM Management:**\n"
            "â€¢ Topic creation\n"
            "â€¢ Auto-organization\n"
            "â€¢ Notification settings"
        )
        buttons = [
            [Button.inline("ðŸ¤– Auto-Reply Settings", "auto_reply:main")],
            [Button.inline("ðŸ“ Template Settings", "template:main")],
            [Button.inline("ðŸ“¨ DM Reply Settings", "dm_reply:main")],
            [Button.inline("ðŸ”™ Back to Messaging", "menu:messaging")]
        ]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _show_channel_statistics(self, user_id: int, message_id: int):
        """Show channel statistics"""
        text = (
            "ðŸ“Š **Channel Statistics**\n\n"
            "Global channel metrics:\n\n"
            "â€¢ Total channels joined\n"
            "â€¢ Active subscriptions\n"
            "â€¢ Recent activity\n"
            "â€¢ Engagement metrics\n\n"
            "Feature coming soon!"
        )
        buttons = [[Button.inline("ðŸ”™ Back to Channels", "menu:channels")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _handle_spam_appeal_select(self, event, user_id: int):
        """Handle spam appeal account selection"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                await event.answer("âŒ No accounts found")
                return
            text = "ðŸ“ž **Spam Appeal**\n\nSelect account to submit spam appeal:"
            buttons = []
            for account in accounts:
                status = "âœ…" if account.get("is_active", False) else "âŒ"
                display_name = format_display_name(account)
                buttons.append([Button.inline(f"{status} {display_name}", f"appeal_account_id:{account['_id']}")])
            buttons.append([Button.inline("ðŸ”™ Back to Cleanup", "cleanup:menu")])
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Spam appeal select error: {e}")

    async def _handle_dm_reply_callback(self, event, user_id: int, data: str):
        """Handle DM reply callbacks"""
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else "main"
        
        if action == "enable":
            text = "âœ… **Enable DM Reply**\n\nReply with your forum group ID to enable DM management"
            buttons = [[Button.inline("ðŸ”™ Back to DM Reply", "menu:dm_reply")]]
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        elif action == "disable":
            text = "âŒ **Disable DM Reply**\n\nDM management disabled"
            buttons = [[Button.inline("ðŸ”™ Back to DM Reply", "menu:dm_reply")]]
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        elif action == "change":
            text = "ðŸ”„ **Change Group**\n\nReply with new forum group ID"
            buttons = [[Button.inline("ðŸ”™ Back to DM Reply", "menu:dm_reply")]]
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        elif action == "status":
            text = "ðŸ“Š **DM Reply Status**\n\nStatus information coming soon!"
            buttons = [[Button.inline("ðŸ”™ Back to DM Reply", "menu:dm_reply")]]
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        elif action == "help":
            text = "â“ **DM Reply Setup**\n\nSetup guide coming soon!"
            buttons = [[Button.inline("ðŸ”™ Back to DM Reply", "menu:dm_reply")]]
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)

    async def _handle_channel_callback(self, event, user_id: int, data: str):
        """Handle channel-related callbacks"""
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else "main"
        account_phone = parts[2] if len(parts) > 2 else None
        
        if action == "select" and account_phone:
            await self._send_channel_actions_menu(user_id, account_phone, event.message_id)
        elif action == "stats":
            await self._show_channel_statistics(user_id, event.message_id)
        elif action == "search":
            text = "ðŸ” **Channel Discovery**\n\nChannel search feature coming soon!"
            buttons = [[Button.inline("ðŸ”™ Back to Channels", "menu:channels")]]
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)

    async def _send_channel_actions_menu(self, user_id: int, account_phone: str, message_id: int):
        """Send channel actions menu for specific account"""
        text = f"ðŸ“¢ **Channel Management**\n\nAccount: {account_phone}\n\nSelect action:"
        buttons = [
            [
                Button.inline("ðŸ”— Join Channel", f"channel:join:{account_phone}"),
                Button.inline("ðŸš« Leave Channel", f"channel:leave:{account_phone}"),
            ],
            [
                Button.inline("ðŸ†• Create Channel", f"channel:create:{account_phone}"),
                Button.inline("ðŸ—‘ï¸ Delete Channel", f"channel:delete:{account_phone}"),
            ],
            [Button.inline("ðŸ“‹ List Channels", f"channel:list:{account_phone}")],
            [Button.inline("ðŸ”™ Back to Accounts", "back:accounts")],
        ]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
