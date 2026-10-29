# -*- coding: utf-8 -*-
"""Inline menu system for account management
Developed by:
- @Meher_Mankar
- @Gutkesh
GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""
import logging
from typing import List, Optional

from telethon import Button, events

from ..core.config import ADMIN_IDS
from ..core.mongo_database import mongodb
from ..utils.network_helpers import format_display_name, format_phone_number
from .menu_callbacks import (
    AccountCallbacks,
    HelpCallbacks,
    MessagingCallbacks,
    OTPCallbacks,
)
from .menu_modules import (
    AccountOperations,
    CallbackHandlers,
    CallbackRouter,
    MenuBuilders,
    MenuHandlers,
    UtilityHelpers,
)
from .secure_2fa_handlers import Secure2FAHandlers

logger = logging.getLogger(__name__)

_OWNED_CALLBACK_PREFIXES = frozenset(
    {
        "session_login",
        "export_sessions",
        "create_sess",
        "login_session_file",
        "login_bulk_import",
        "login_tdata_import",
        "session_info",
        "session_operations",
        "session_op",
        "session_delete",
        "session_export_string",
        "session_analytics",
        "session_automation",
        "session_bulk_ops",
        "resend_code",
        "restart_auth",
        "import_sessions",
        "import_string",
        "import_file",
        "import_zip",
        "import_tdata",
        "import_formats",
        "proxy",
        "auto_reply",
        "template",
        "contact_scrape",
        "dm_",
        "advanced_spam",
        "spam_filters",
        "spam_master",
        "accept_spam_warning",
        "decline_spam_warning",
        "forward_bomb",
        "mass_invite",
        "multi_raid",
        "raid_coord",
        "stealth_raid",
        "message_flood",
        "username_check",
        "group_leave",
        "group_list",
        "group_manager",
        "send_all_groups",
        "cs_acc",
        "cs_all",
        "cs_all_groups",
        "fb_acc",
        "fb_all",
        "fb_spec",
        "mf_acc",
        "mf_all",
        "mf_spec",
        "mi_acc",
        "mi_all",
        "mi_spec",
        "sag_acc",
        "uc_acc",
        "bulk_import",
        "sim_stats",
        "analytics_account",
        "security_dashboard",
        "security_activity",
        "security_report",
        "messaging_stats",
        "transfer_toggle",
        "transfer_select_all",
        "transfer_done",
        "transfer_cancel",
        "coowner_cancel",
        "otp_pwd",
        "device",
        "help_main",
        "appeal_account_id",
        "appeal_cancel",
        "captcha_",
        "schedule_msg",
        "schedule_list",
        "schedule_cancel",
        "schedule_new",
        "schedule_account",
        "export_contacts",
    }
)


def _is_owned_callback(data: str) -> bool:
    callback_prefix = data.split(":", 1)[0]
    return (
        callback_prefix in _OWNED_CALLBACK_PREFIXES
        or data == "contacts:export"
        or (
            data.startswith(("dm_", "captcha_"))
            and not data.startswith("dm_reply:")
        )
    )


class MenuSystem:
    """Handles inline keyboard menus and callback queries"""

    def __init__(self, bot_instance, account_manager=None):
        self.bot = bot_instance
        self.account_manager = account_manager
        self.secure_2fa_handlers = Secure2FAHandlers(bot_instance, account_manager)
        self._menu_text_handler = None
        self._callback_handler = None
        # Initialize modular components
        self.builders = MenuBuilders(self)
        self.handlers = MenuHandlers(self)
        self.router = CallbackRouter(self)
        self.account_ops = AccountOperations(self)
        self.callback_handlers = CallbackHandlers(self)
        from .menu_modules import (
            CleanupOperations,
            MessagingOperations,
            ProfileOperations,
        )

        self.cleanup_operations = CleanupOperations(self)
        self.profile_operations = ProfileOperations(self)
        self.messaging_operations = MessagingOperations(self)
        # Initialize modular callbacks
        self.account_callbacks = AccountCallbacks(bot_instance, account_manager, self)
        self.otp_callbacks = OTPCallbacks(bot_instance, account_manager, self)
        self.messaging_callbacks = MessagingCallbacks(
            bot_instance, account_manager, self
        )
        self.help_callbacks = HelpCallbacks(bot_instance, account_manager, self)

        # Initialize proxy handler
        from ..handlers.proxy_handler import ProxyHandler

        self.proxy_handler = ProxyHandler(account_manager)
        self.proxy_handler.register_handlers()

    def _parse_callback(self, callback_data: str):
        """Parse callback data - handles both JSON and colon-delimited formats"""
        return UtilityHelpers.parse_callback(callback_data)

    def format_display_name(self, account):
        """Format display name from account object or DB record"""
        return UtilityHelpers.format_display_name(account)

    def get_main_menu_keyboard(self, user_id: int) -> List[List[Button]]:
        """Get enhanced persistent reply keyboard menu"""
        try:
            return self.builders.get_main_menu_keyboard(user_id)
        except (AttributeError, KeyError, ValueError) as e:
            logger.error(f"Error getting main menu keyboard: {e}")
            # Fallback to basic menu
            from ..core.config import ADMIN_IDS

            buttons = [
                [
                    Button.text("📱 Account Settings", resize=True),
                    Button.text("🛡️ Protection Manager", resize=True),
                ],
                [
                    Button.text("💬 Messaging", resize=True),
                    Button.text("📢 Channels", resize=True),
                ],
                [
                    Button.text("👥 Contacts", resize=True),
                    Button.text("🎯 SpamMaster", resize=True),
                ],
                [
                    Button.text("🧹 Cleanup", resize=True),
                    Button.text("🌐 Proxy Manager", resize=True),
                ],
                [
                    Button.text("❓ Help", resize=True),
                    Button.text("🆘 Support", resize=True),
                ],
            ]
            if user_id in ADMIN_IDS:
                buttons.append([Button.text("🔧 Developer Panel", resize=True)])
            return buttons

    async def send_main_menu(self, user_id: int) -> int:
        """Send persistent reply keyboard menu"""
        try:
            # Delete previous menu messages to avoid collision
            await self._cleanup_old_messages(user_id)

            keyboard = self.get_main_menu_keyboard(user_id)
            text = (
                "🛡️ **TeleGuard Account Manager**\n\n"
                "⚡ Professional Telegram security & automation\n\n"
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
        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.error(f"Failed to send main menu: {e}", exc_info=True)
            # Send basic message as fallback
            try:
                await self.bot.send_message(
                    user_id,
                    "🛡️ **TeleGuard Account Manager**\n\nWelcome back! Use /start to reload the menu.",
                )
            except (ValueError, KeyError):
                pass
            return 0

    def get_account_menu_buttons(
        self, account_id: str, account=None
    ) -> List[List[Button]]:
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
                    try:
                        await self.bot.edit_message(user_id, user["main_menu_message_id"], "")
                    except Exception:
                        await self.bot.delete_messages(user_id, user["main_menu_message_id"])
                except Exception:
                    pass  # Message might be service message or already deleted
        except Exception as e:
            logger.debug(f"Cleanup old messages error: {e}")

    async def send_accounts_list(
        self, user_id: int, edit_message_id: Optional[int] = None
    ):
        """Send detailed accounts list with comprehensive information"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = "📱 **Account Management**\n\n❌ No accounts found. Add your first account to get started.\n\n💡 Use /add command or enable Developer Mode to add accounts."
            else:
                text = f"📱 **Detailed Account Inventory**\n━━━━━━━━━━━━━━━━━━━━\n👤 Total Accounts: {len(accounts)}\n\n"
                
                for i, account in enumerate(accounts, 1):
                    status_emoji = "🟢" if account.get("is_active", False) else "🔴"
                    destroyer = "🛡️" if account.get("otp_destroyer_enabled", False) else "⚪"
                    forward = "📤" if account.get("otp_forward_enabled", False) else "⚪"
                    
                    display_name = format_display_name(account)
                    phone = format_phone_number(account.get("phone", "Unknown"))
                    
                    dc_id = account.get("dc_id", "?")
                    session_type = account.get("added_via", "phone")
                    
                    text += (
                        f"{i}. **{display_name}** (`{phone}`)\n"
                        f"   ├ Status: {status_emoji} | DC: {dc_id} | Type: {session_type}\n"
                        f"   └ Security: Destroyer: {destroyer} | Forward: {forward}\n\n"
                    )
                
                text += "━━━━━━━━━━━━━━━━━━━━\n💡 **Legend:**\n🟢 Online | 🔴 Offline | 🛡️ Destroyer Active | 📤 Forward Active"
            
            from telethon import Button
            buttons = [[Button.inline("🔙 Back to Accounts", "menu:accounts")]]
            
            if edit_message_id:
                await self.bot.edit_message(user_id, edit_message_id, text, buttons=buttons)
            else:
                await self.bot.send_message(user_id, text, buttons=buttons)
        except (ConnectionError, ValueError, KeyError) as e:
            logger.error(f"Failed to send accounts list: {e}")
            await self.bot.send_message(user_id, "❌ Error generating detailed list")

    async def send_account_management(
        self, user_id: int, account_id: str, edit_message_id: Optional[int] = None
    ):
        """Send account management menu"""
        await self.account_ops.send_account_management(
            user_id, account_id, edit_message_id
        )

    async def send_otp_account_management(
        self, user_id: int, account_id: str, edit_message_id: Optional[int] = None
    ):
        """Send OTP account management menu"""
        await self.account_ops.send_otp_account_management(
            user_id, account_id, edit_message_id
        )

    def register_handlers(self):
        """Register menu handlers - called during bot initialization"""
        self.setup_menu_handlers()

    def setup_menu_handlers(self):
        """Set up menu text handlers - DIRECT FIX for non-working buttons"""

        # All known menu button texts — receiving any of these cancels pending actions
        _MENU_BUTTON_TEXTS = frozenset([
            "📱 Account Settings", "Account Settings",
            "🛡️ Protection Manager", "Protection Manager",
            "💬 Messaging", "Messaging",
            "📢 Channels", "Channels",
            "👥 Contacts", "Contacts",
            "🎭 SpamMaster", "SpamMaster", "🎯 SpamMaster",
            "🧹 Cleanup", "Cleanup",
            "❓ Help", "Help",
            "🆘 Support", "Support",
            "⚙️ Developer Panel", "🔧 Developer Panel", "🔧 Developer",
            "Developer Panel", "Developer",
            "🌐 Proxy Manager", "Proxy Manager", "Proxy",
        ])

        # DIRECT TEXT HANDLER - Simple and reliable
        @self.bot.on(
            events.NewMessage(incoming=True, func=lambda e: e.is_private and e.text and not e.text.startswith("/"))
        )
        async def direct_menu_handler(event):
            text = event.text.strip()
            user_id = event.sender_id

            # If user taps a menu button while a pending action is active, cancel it
            # so the menu button text doesn't get routed to the pending action handler
            if text in _MENU_BUTTON_TEXTS:
                if self.account_manager:
                    self.account_manager.pending_actions.pop(user_id, None)
                
                # Safe logging without Unicode emojis - ONLY for actual menu buttons
                safe_text = text.encode("ascii", errors="replace").decode("ascii")
                logger.info(f"Menu button clicked: '{safe_text}' from user {user_id}")
            else:
                # Not a menu button, ignore
                return

            try:
                if text in ["📱 Account Settings", "Account Settings"]:
                    await self.handlers.handle_account_settings(event)
                elif text in ["🛡️ Protection Manager", "Protection Manager"]:
                    await self.handlers.handle_otp_manager(event)
                elif text in ["💬 Messaging", "Messaging"]:
                    await self.handlers.handle_messaging(event)
                elif text in ["📢 Channels", "Channels"]:
                    await self.handlers.handle_channels(event)
                elif text in ["👥 Contacts", "Contacts"]:
                    await self._handle_contacts(event)
                elif text in ["🎭 SpamMaster", "SpamMaster", "🎯 SpamMaster"]:
                    await self._handle_spam_master(event)
                elif text in ["🧹 Cleanup", "Cleanup"]:
                    await self.handlers.handle_cleanup(event)
                elif text in ["❓ Help", "Help"]:
                    await self.handlers.handle_help(event)
                elif text in ["🆘 Support", "Support"]:
                    await self.handlers.handle_support(event)
                elif text in [
                    "⚙️ Developer Panel",
                    "🔧 Developer Panel",
                    "🔧 Developer",
                    "Developer Panel",
                    "Developer",
                ]:
                    if user_id in ADMIN_IDS:
                        await self.handlers.handle_developer(event)
                    else:
                        await event.reply("🚫 Access denied")
                elif text in ["🌐 Proxy Manager", "Proxy Manager", "Proxy"]:
                    await self._handle_proxy_menu(event)
            except AttributeError as e:
                logger.error(
                    f"Handler method not found for '{text}': {e}", exc_info=True
                )
                await event.reply("⚠️ Feature temporarily unavailable")
            except Exception as e:
                logger.error(f"Menu handler error for '{text}': {e}", exc_info=True)
                await event.reply("⚠️ Error processing menu action")

        # DIRECT CALLBACK HANDLER
        @self.bot.on(events.CallbackQuery())
        async def direct_callback_handler(event):
            try:
                user_id = event.sender_id
                data = event.data.decode("utf-8")

                # Dedicated handlers own these callbacks. Contact actions are
                # routed here, except contact export handled by its own handler.
                if _is_owned_callback(data):
                    return

                logger.info(f"Callback: {data} from user {user_id}")

                # Handle session export callbacks (managed here, not by pattern handlers)
                if data.startswith("session_type:"):
                    await self.router.handle_session_type_callback(event, user_id, data)
                    return
                elif data.startswith("toggle_session:"):
                    await self.router.handle_toggle_session_callback(event, user_id, data)
                    return
                elif data == "toggle_all_sessions":
                    await self.router.handle_toggle_all_sessions_callback(event, user_id, data)
                    return
                elif data == "create_selected_sessions":
                    await self.router.handle_create_selected_sessions_callback(event, user_id, data)
                    return

                await self.router.route_callback(event, user_id, data)
            except Exception as e:
                logger.error(f"Callback error: {e}", exc_info=True)
                await event.answer("⚠️ Service temporarily unavailable", alert=True)

        logger.info("✅ Menu handlers registered successfully (DIRECT METHOD)")
        self._menu_text_handler = direct_menu_handler
        self._callback_handler = direct_callback_handler

    async def _handle_account_settings(self, event):
        """Handle Account Settings menu"""
        await self.handlers.handle_account_settings(event)

    async def _handle_messaging(self, event):
        """Handle Messaging menu"""
        await self.handlers.handle_messaging(event)

    async def _handle_channels(self, event):
        """Handle Channels menu"""
        await self.handlers.handle_channels(event)

    async def _handle_contacts(self, event):
        """Handle Contacts menu — works for both text and callback events"""
        user_id = event.sender_id
        try:
            # contact_handler lives on bot_manager (account_manager here)
            ch = getattr(self.account_manager, "contact_handler", None)
            if ch is None:
                await event.reply("👥 Use /contacts to manage contacts.")
                return

            await ch._show_main_menu(
                event, user_id, reply=not isinstance(event, events.CallbackQuery.Event)
            )

        except Exception as e:
            logger.error(f"Failed to handle contacts menu: {e}", exc_info=True)
            await event.reply("❌ Error loading contacts menu")

    async def _handle_spam_master(self, event):
        """Handle SpamMaster menu - redirect to advanced spam handler"""
        try:
            # Redirect to advanced spam handler
            if hasattr(self.account_manager, "advanced_spam_handler"):
                await self.account_manager.advanced_spam_handler._handle_spam_master_menu(
                    event
                )
            else:
                await event.reply("❌ SpamMaster not available")
        except Exception as e:
            logger.error(f"Failed to handle SpamMaster menu: {e}")
            await event.reply("❌ Error loading SpamMaster menu")

    async def _handle_proxy_menu(self, event):
        """Handle Proxy Manager menu"""
        try:
            user_id = event.sender_id
            if self.proxy_handler:
                await self.proxy_handler._show_proxy_menu(event, user_id)
            else:
                await event.reply("❌ Proxy Manager not available")
        except Exception as e:
            logger.error(f"Failed to handle Proxy menu: {e}")
            await event.reply("❌ Error loading Proxy menu")

    async def _handle_export_sessions_menu(self, event, user_id):
        """Handle export sessions menu"""
        try:
            if hasattr(self.account_manager, "session_export_handler"):
                await self.account_manager.session_export_handler._show_export_menu(event)
            else:
                await event.answer("❌ Session export unavailable", alert=True)
        except Exception as e:
            logger.error(f"Export sessions menu error: {e}")
            await event.answer("❌ Error loading export menu", alert=True)

    async def _execute_cleanup(
        self, event, user_id: int, account_id: str, cleanup_types: str
    ):
        """Execute account cleanup - delegated to CleanupOperations"""
        try:
            from .menu_modules.cleanup_operations import CleanupOperations

            ops = CleanupOperations(self)
            await ops.execute_cleanup(event, user_id, account_id, cleanup_types)
        except Exception as e:
            logger.error(f"Cleanup execution error: {e}")
            await event.answer("❌ Error executing cleanup")

    async def _send_cleanup_confirmation(
        self, user_id: int, message_id: int, account_id: str, cleanup_types: str
    ):
        """Send cleanup confirmation with selected options."""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                if message_id:
                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        "\u274c Account not found",
                        buttons=[[Button.inline("\ud83d\udd19 Back", "cleanup:menu")]],
                    )
                else:
                    await self.bot.send_message(user_id, "\u274c Account not found")
                return

            display_name = format_display_name(account)

            from ..core.cleanup_types import parse_cleanup_types

            cleanup_list, _ = parse_cleanup_types(cleanup_types)

            # Create display text for selected options
            selected_options = []
            if "personal" in cleanup_list:
                selected_options.append("\u274c 💬 Personal chats")
            if "bots" in cleanup_list:
                selected_options.append("✅ 🔵 Bot chats")
            if "telegram" in cleanup_list:
                selected_options.append("✅ 🔵 Telegram official chats")
            if "spambot" in cleanup_list:
                selected_options.append("✅ 🔵 Spambot chats")
            if "my_messages" in cleanup_list:
                selected_options.append("✅ 🗑️ Your messages from groups")
            if "channels" in cleanup_list:
                selected_options.append("✅ 🔵 Exit from channels")
            if "groups" in cleanup_list:
                selected_options.append("✅ 🔵 Exit from groups")
            if "owned_groups" in cleanup_list:
                selected_options.append("✅ 🔵? Delete owned groups")
            if "owned_channels" in cleanup_list:
                selected_options.append("✅ 🔵 Delete owned channels")

            if not selected_options:
                error_msg = "❌ No valid cleanup options selected. Please try again with valid options: personal, bots, telegram, spambot, my_messages, channels, groups, owned_groups, owned_channels, all"
                if message_id:
                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        error_msg,
                        buttons=[[Button.inline("\ud83d\udd19 Back", "cleanup:menu")]],
                    )
                else:
                    await self.bot.send_message(user_id, error_msg)
                return

            text = (
                f"\ud83d\udd19 **Final Cleanup Confirmation**\n\n"
                f"\ud83d\udd19 Account: {display_name}\n\n"
                f"**Selected cleanup actions:**\n"
                + "\n".join(selected_options)
                + "\n\n"
                "\ud83d\udd19 **FINAL WARNING**: This action cannot be undone!\n"
                "All selected chats and data will be permanently deleted.\n\n"
                "Are you absolutely sure you want to proceed?"
            )

            buttons = [
                [
                    Button.inline(
                        "\ud83d\udd19 YES, Start Cleanup",
                        f"cleanup:confirm:{account_id}:{cleanup_types}",
                    )
                ],
                [Button.inline("\u274c Cancel", "cleanup:menu")],
            ]

            if message_id:
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            else:
                await self.bot.send_message(user_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Error in cleanup confirmation: {e}")
            error_msg = "❌ Error loading cleanup confirmation"
            if message_id:
                try:
                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        error_msg,
                        buttons=[[Button.inline("\ud83d\udd19 Back", "cleanup:menu")]],
                    )
                except BaseException:
                    await self.bot.send_message(user_id, error_msg)
            else:
                await self.bot.send_message(user_id, error_msg)

    async def _handle_spam_appeal_select(self, event, user_id: int):
        """Handle spam appeal account selection"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = "📝 **Spam Appeal**\n\n❌ No accounts found."
                buttons = [[Button.inline("\ud83d\udd19 Back", "cleanup:menu")]]
                await self.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )
                return

            text = "📝 **Spam Appeal**\n\n" "Select account to submit spam appeal:"
            buttons = []
            for account in accounts:
                status = "✅" if account.get("is_active", False) else "🔴"
                display_name = format_display_name(account)
                button_text = f"{status} {display_name}"
                buttons.append(
                    [Button.inline(button_text, f"appeal_account_id:{account['_id']}")]
                )

            buttons.append([Button.inline("\ud83d\udd19 Back", "cleanup:menu")])
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )

        except Exception as e:
            logger.error(f"Error in spam appeal select: {e}")
            await event.answer("\u274c Error loading spam appeal")

    async def _handle_spam_appeal(self, event, user_id: int, account_id: str):
        """Handle spam appeal for account before cleanup"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                await event.answer("\u274c Account not found")
                return

            display_name = format_display_name(account)

            # Check if spam appeal handler is available
            if hasattr(self.account_manager, "spam_appeal_handler"):
                text = (
                    f"\ud83d\udd19 **Spam Appeal - {display_name}**\n\n"
                    f"\ud83d\udd19 **Smart Appeal System**\n\n"
                    f"Before cleaning your account, you can try appealing any spam restrictions.\n\n"
                    f"**Features:**\n"
                    f"• AI-powered message selection\n"
                    f"• Automatic @spambot interaction\n"
                    f"• Manual captcha verification\n"
                    f"• Smart detection of restriction types\n\n"
                    f"Would you like to start the appeal process?"
                )

                buttons = [
                    [
                        Button.inline(
                            "\ud83d\udd19 Start Appeal",
                            f"appeal_account_id:{account_id}",
                        )
                    ],
                    [
                        Button.inline(
                            "\ud83d\udd19 Skip to Cleanup",
                            f"cleanup:select:{account_id}",
                        )
                    ],
                    [Button.inline("\ud83d\udd19 Back to Menu", "cleanup:menu")],
                ]

                await self.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )
            else:
                text = (
                    f"\ud83d\udd19 **Manual Spam Appeal - {display_name}**\n\n"
                    f"Spam appeal system is not available.\n\n"
                    f"**Manual steps:**\n"
                    f"1. Go to @spambot\n"
                    f"2. Send /start\n"
                    f"3. Follow the appeal process\n"
                    f"4. Complete any captcha verification\n\n"
                    f"After appealing, you can return to cleanup if needed."
                )

                buttons = [
                    [
                        Button.inline(
                            "\ud83d\udd19 Continue to Cleanup",
                            f"cleanup:select:{account_id}",
                        )
                    ],
                    [Button.inline("\ud83d\udd19 Back to Menu", "cleanup:menu")],
                ]

                await self.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )

        except Exception as e:
            logger.error(f"Error in spam appeal: {e}")
            await event.answer("\u274c Error loading spam appeal")

    async def _handle_help(self, event):
        """Handle Help menu - delegated to modular handler"""
        await self.handlers.handle_help(event)

    async def _handle_support(self, event):
        """Handle Support menu - delegated to modular handler"""
        await self.handlers.handle_support(event)

    async def _handle_developer(self, event):
        """Handle Developer menu - delegated to the admin-guarded handler."""
        await self.handlers.handle_developer(event)

    async def _handle_help_callback(self, event, user_id: int, data: str):
        """Handle help-related callbacks"""
        await self.help_callbacks.handle_callback(event, user_id, data)

    async def _handle_support_callback(self, event, user_id: int, data: str):
        """Handle support-related callbacks"""
        await self.help_callbacks.handle_support_callback(event, user_id, data)

    async def _handle_developer_callback(self, event, user_id: int, data: str):
        """Handle developer-related callbacks"""
        await self.help_callbacks.handle_developer_callback(event, user_id, data)

    async def _handle_dm_reply(self, event):
        """Handle DM Reply menu"""
        await event.answer("DM Reply - use main menu")

    async def _handle_otp_callback(self, event, user_id: int, data: str):
        """Handle OTP-related callbacks with proper error handling"""
        try:
            await self.callback_handlers.handle_otp_callback(event, user_id, data)
        except Exception as e:
            logger.error(f"OTP callback error: {e}")
            await event.answer("❌ Error processing OTP request")

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
                    {
                        "$set": {
                            "otp_destroyer_enabled": True,
                            "otp_forward_enabled": False,  # Disable forward when destroyer is enabled
                        }
                    },
                )
                await event.answer("✅ OTP Destroyer enabled! Forward disabled.")
                # Go back to OTP Destroyer account selection instead of individual
                # account menu
                await self._handle_otp_setting_callback(
                    event, user_id, "otp_setting:destroyer"
                )
            except Exception:
                await event.answer("⚠️ Error enabling OTP Destroyer")
        elif action == "disable":
            try:
                from bson import ObjectId

                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id), "user_id": user_id},
                    {"$set": {"otp_destroyer_enabled": False}},
                )
                await event.answer("🔴 OTP Destroyer disabled!")
                # Go back to OTP Destroyer account selection instead of individual
                # account menu
                await self._handle_otp_setting_callback(
                    event, user_id, "otp_setting:destroyer"
                )
            except Exception:
                await event.answer("⚠️ Error disabling OTP Destroyer")
        elif action == "forward_enable":
            try:
                from bson import ObjectId

                account = await mongodb.db.accounts.find_one(
                    {"_id": ObjectId(account_id), "user_id": user_id}
                )
                if account and account.get("otp_destroyer_enabled", False):
                    await event.answer(
                        "\u274c Cannot enable forward while OTP Destroyer is active"
                    )
                    return
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id), "user_id": user_id},
                    {"$set": {"otp_forward_enabled": True}},
                )
                await event.answer("✅ OTP Forward enabled!")
                # Go back to OTP Forward account selection instead of individual account
                # menu
                await self._handle_otp_setting_callback(
                    event, user_id, "otp_setting:forward"
                )
            except Exception:
                await event.answer("⚠️ Error enabling OTP Forward")
        elif action == "forward_disable":
            try:
                from bson import ObjectId

                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id), "user_id": user_id},
                    {"$set": {"otp_forward_enabled": False}},
                )
                await event.answer("🔴 OTP Forward disabled!")
                # Go back to OTP Forward account selection instead of individual account
                # menu
                await self._handle_otp_setting_callback(
                    event, user_id, "otp_setting:forward"
                )
            except Exception:
                await event.answer("⚠️ Error disabling OTP Forward")
        elif action == "temp":
            try:
                from bson import ObjectId

                account = await mongodb.db.accounts.find_one(
                    {"_id": ObjectId(account_id), "user_id": user_id}
                )
                if not account:
                    await event.answer("\u274c Account not found")
                    return

                # Check if temp OTP is already active
                import time

                if account.get("otp_temp_passthrough", False):
                    expiry = account.get("temp_passthrough_expiry", 0)
                    if time.time() < expiry:
                        # Stop temp OTP - restore original states
                        original_destroyer_state = account.get(
                            "original_destroyer_state", True
                        )
                        original_forward_state = account.get(
                            "original_forward_state", False
                        )
                        await mongodb.db.accounts.update_one(
                            {"_id": ObjectId(account_id)},
                            {
                                "$set": {
                                    "otp_destroyer_enabled": original_destroyer_state,
                                    "otp_forward_enabled": original_forward_state,
                                },
                                "$unset": {
                                    "otp_temp_passthrough": "",
                                    "temp_passthrough_expiry": "",
                                    "original_destroyer_state": "",
                                    "original_forward_state": "",
                                },
                            },
                        )
                        await mongodb.add_audit_entry(
                            account_id,
                            {
                                "action": "temp_passthrough_stopped",
                                "timestamp": int(time.time()),
                            },
                        )
                        await event.answer(
                            "✅ Temp OTP stopped! Original settings restored."
                        )
                        await self._handle_otp_setting_callback(
                            event, user_id, "otp_setting:temp"
                        )
                        return

                # Start temp OTP - enable forward, disable destroyer for 5 minutes
                expiry_time = time.time() + 300  # 5 minutes
                original_destroyer_state = account.get("otp_destroyer_enabled", False)
                original_forward_state = account.get("otp_forward_enabled", False)
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {
                        "$set": {
                            "otp_temp_passthrough": True,
                            "temp_passthrough_expiry": expiry_time,
                            "otp_destroyer_enabled": False,  # Disable destroyer
                            "otp_forward_enabled": True,  # Enable forward
                            "original_destroyer_state": original_destroyer_state,
                            "original_forward_state": original_forward_state,
                        }
                    },
                )
                await mongodb.add_audit_entry(
                    account_id,
                    {
                        "action": "temp_passthrough_enabled",
                        "duration": "5_minutes",
                        "timestamp": int(time.time()),
                    },
                )
                await event.answer(
                    "⏰ Temp OTP enabled! Forward ON, Destroyer OFF for 5 minutes."
                )
                await self._handle_otp_setting_callback(
                    event, user_id, "otp_setting:temp"
                )
                # Schedule cleanup after 5 minutes
                import asyncio

                async def simple_cleanup():
                    await asyncio.sleep(300)  # 5 minutes
                    try:
                        from bson import ObjectId

                        await mongodb.db.accounts.update_one(
                            {"_id": ObjectId(account_id)},
                            {
                                "$unset": {
                                    "otp_temp_passthrough": "",
                                    "temp_passthrough_expiry": "",
                                    "original_destroyer_state": "",
                                    "original_forward_state": "",
                                }
                            },
                        )
                    except Exception as e:
                        logger.error(f"Temp OTP cleanup error: {e}")

                asyncio.create_task(simple_cleanup())
            except Exception as e:
                logger.error(f"Error handling temp OTP: {e}")
                await event.answer("⚠️ Error handling temp OTP")

        elif action == "setpass":
            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {
                    "action": "set_otp_disable_password",
                    "account_id": account_id,
                }
                text = (
                    "🔒 **Set Disable Password**\n\n"
                    "Reply with a password that will be required to disable OTP Destroyer.\n\n"
                    "🔒 This adds an extra security layer - choose a strong password!\n"
                    "⚠️ Minimum 6 characters required."
                )
                await event.answer("🔒 Reply with password")
                await self.bot.send_message(user_id, text)
            else:
                await event.answer("\u274c Service unavailable")

    async def _handle_otp_setting_callback(self, event, user_id: int, data: str):
        """Handle OTP setting callbacks from main OTP menu"""
        parts = data.split(":")
        setting_type = parts[1] if len(parts) > 1 else "destroyer"

        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = "🛡️ **OTP Settings**\n\n❌ No accounts found."
                buttons = [
                    [Button.inline("\ud83d\udd19 Back to OTP Manager", "menu:otp")]
                ]
                await self.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )
                return

            if setting_type == "destroyer":
                text = "🛡️ **OTP Destroyer Settings**\n\nSelect account to enable/disable OTP Destroyer:"
            elif setting_type == "forward":
                text = "📧 **OTP Forward Settings**\n\nSelect account to enable/disable OTP Forward:"
            elif setting_type == "temp":
                text = "⏰ **Temp OTP Settings**\n\nSelect account to enable 5-minute passthrough:"
            else:
                text = "🛡️ **OTP Settings**\n\nSelect account:"

            buttons = []
            for account in accounts:
                status = "\ud83d\udd19" if account.get("is_active", False) else "🔴"

                if setting_type == "destroyer":
                    feature_status = (
                        "🛡️" if account.get("otp_destroyer_enabled", False) else "❌"
                    )
                elif setting_type == "forward":
                    feature_status = (
                        "📧" if account.get("otp_forward_enabled", False) else "❌"
                    )
                else:
                    feature_status = "❌"

                display_name = format_display_name(account)
                button_text = f"{status}{feature_status} {display_name}"
                buttons.append(
                    [Button.inline(button_text, f"otp:manage:{account['_id']}")]
                )

            buttons.append(
                [Button.inline("\ud83d\udd19 Back to OTP Manager", "menu:otp")]
            )
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )

        except Exception as e:
            logger.error(f"Error in OTP setting callback: {e}")
            await event.answer("❌ Error loading OTP settings")

    async def _send_help_menu(self, user_id: int, message_id: int):
        """Send help menu"""
        text = (
            "❓ **Help & Information**\n\n"
            "\ud83d\udd19? **OTP Destroyer**: Automatically invalidates login codes to prevent unauthorized access\n\n"
            "\ud83d\udd19 **Account Management**: Add, remove, and configure your Telegram accounts\n\n"
            "🔐 **Security**: All data is encrypted and stored securely\n\n"
            "\ud83d\udd19 **Developer Mode**: Access advanced features and text commands"
        )
        await self.bot.send_message(user_id, text)

    async def _toggle_developer_mode(self, user_id: int, message_id: int):
        """Toggle developer mode"""
        if user_id not in ADMIN_IDS:
            await self.bot.send_message(
                user_id, "❌ You don't have access to Developer tools."
            )
            return

        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if user:
                current_mode = user.get("developer_mode", False)
                new_mode = not current_mode
                await mongodb.db.users.update_one(
                    {"telegram_id": user_id}, {"$set": {"developer_mode": new_mode}}
                )
                status = "enabled" if new_mode else "disabled"
                text = f"🔧 **Developer Mode**\n\nDeveloper mode {status}.\n\n"
                if new_mode:
                    text += "You now have access to text commands:\n/add, /remove, /accs, /toggle_protection, etc."
                else:
                    text += "Text commands are now hidden. Use the menu system."
                buttons = [[Button.inline("\ud83d\udd19 Back to Main", "menu:main")]]
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except (ValueError, KeyError, ConnectionError) as e:
            logger.error(f"Failed to toggle developer mode: {e}")

    async def send_otp_menu(self, user_id: int, edit_message_id: Optional[int] = None):
        """Send OTP Manager menu with proper buttons"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )

            if not accounts:
                text = (
                    "🛡️ **OTP Manager**\n\n"
                    "❌ No accounts found. Add accounts first to manage OTP settings.\n\n"
                    "🔐 **Available Features:**\n"
                    "• 🛡️ **OTP Destroyer** - Blocks unauthorized logins\n"
                    "• 📤 **OTP Forward** - Forwards codes to you\n"
                    "• ⏰ **Temp OTP** - 5-minute security bypass"
                )
                buttons = [
                    [Button.inline("➕ Add Account", "account:add")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                # Count enabled features
                destroyer_count = sum(
                    1 for acc in accounts if acc.get("otp_destroyer_enabled", False)
                )
                forward_count = sum(
                    1 for acc in accounts if acc.get("otp_forward_enabled", False)
                )
                active_count = sum(1 for acc in accounts if acc.get("is_active", False))

                text = (
                    "🛡️ **OTP Manager**\n\n"
                    f"📊 **Account Status:**\n"
                    f"• Total Accounts: {len(accounts)}\n"
                    f"• Active Accounts: {active_count}\n"
                    f"• 🛡️ Destroyer Enabled: {destroyer_count}\n"
                    f"• 📤 Forward Enabled: {forward_count}\n\n"
                    "🔐 **Security Features:**\n"
                    "• 🛡️ **Destroyer** - Blocks unauthorized logins\n"
                    "• 📤 **Forward** - Forwards OTP codes to you\n"
                    "• ⏰ **Temp OTP** - 5-minute security bypass\n\n"
                    "Select an option below:"
                )
                buttons = [
                    [Button.inline("🛡️ OTP Destroyer", "otp_setting:destroyer")],
                    [Button.inline("📤 OTP Forward", "otp_setting:forward")],
                    [Button.inline("⏰ Temp OTP", "otp_setting:temp")],
                    [Button.inline("📊 OTP Statistics", "otp:stats")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]

            if edit_message_id:
                await self.bot.edit_message(
                    user_id, edit_message_id, text, buttons=buttons
                )
            else:
                await self.bot.send_message(user_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to send OTP menu: {e}")
            # Fallback message
            fallback_text = (
                "🛡️ **OTP Manager**\n\n❌ Error loading OTP menu. Please try again."
            )
            fallback_buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            try:
                if edit_message_id:
                    await self.bot.edit_message(
                        user_id,
                        edit_message_id,
                        fallback_text,
                        buttons=fallback_buttons,
                    )
                else:
                    await self.bot.send_message(
                        user_id, fallback_text, buttons=fallback_buttons
                    )
            except BaseException:
                pass

    async def _send_sessions_menu(self, user_id: int, message_id: int):
        """Send sessions management menu"""
        text = (
            "🔐 **Session Management**\n\n"
            "Manage your account sessions and security.\n\n"
            "Features coming soon:"
            "• Export session strings\n"
            "• Import sessions\n"
            "• Session health check"
        )
        buttons = [[Button.inline("\ud83d\udd19 Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _send_2fa_menu(self, user_id: int, message_id: int):
        """Send 2FA settings menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = "🔑 **2FA Settings**\n\nNo accounts found. Add accounts first."
                buttons = [[Button.inline("\ud83d\udd19 Back to Main", "menu:main")]]
            else:
                text = "🔑 **2FA Settings**\n\nSelect an account to manage 2FA:"
                buttons = []
                for account in accounts:
                    has_2fa = "✅" if account.get("twofa_password") else "❌"
                    button_text = f"{has_2fa} {account['name']}"
                    buttons.append(
                        [Button.inline(button_text, f"2fa:status:{account['_id']}")]
                    )
                buttons.append(
                    [Button.inline("\ud83d\udd19 Back to Main", "menu:main")]
                )
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except (ValueError, KeyError, ConnectionError) as e:
            logger.error(f"Failed to send 2FA menu: {e}")

    async def _send_online_menu(self, user_id: int, message_id: int):
        """Send online maker menu"""
        text = (
            "\ud83d\udd19 **Online Maker**\n\n"
            "Keep your accounts online automatically.\n\n"
            "Features coming soon:"
            "• Auto-online intervals\n"
            "• Custom status messages\n"
            "• Schedule management"
        )
        buttons = [[Button.inline("\ud83d\udd19 Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _send_security_menu(self, user_id: int, account_id: str, message_id: int):
        """Send security settings menu"""
        text = (
            "🔒 **Security Settings**\n\n"
            "Advanced security options for OTP destroyer.\n\n"
            "Features coming soon:"
            "• Disable password protection\n"
            "• Audit log retention\n"
            "• Alert preferences"
        )
        buttons = [[Button.inline("\ud83d\udd19 Back", f"account:manage:{account_id}")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _send_profile_menu(self, user_id: int, message_id: int):
        """Send profile management menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = "\ud83d\udd19 **Profile Manager**\n\nNo accounts found. Add accounts first."
                buttons = [[Button.inline("\ud83d\udd19 Back to Main", "menu:main")]]
            else:
                text = "\ud83d\udd19 **Profile Manager**\n\nSelect an account to manage profile:"
                buttons = []
                for account in accounts:
                    status = "\u2705" if account.get("is_active", False) else "\u274c"
                    username_display = (
                        f"@{account.get('username', '')}"
                        if account.get("username")
                        else "No username"
                    )
                    button_text = f"{status} {account['name']} ({username_display})"
                    buttons.append(
                        [Button.inline(button_text, f"profile:manage:{account['_id']}")]
                    )
                buttons.append(
                    [Button.inline("\ud83d\udd19 Back to Main", "menu:main")]
                )
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to send profile menu: {e}")

    async def _send_groups_menu(self, user_id: int, message_id: int):
        """Send groups and channels menu"""
        text = (
            "\ud83d\udd19 **Groups & Channels**\n\n"
            "Manage groups and channels for your accounts.\n\n"
            "Features coming soon:"
            "• Create channels/groups\n"
            "• Manage members and admins\n"
            "• Post and schedule content\n"
            "• Invite link management"
        )
        buttons = [[Button.inline("\ud83d\udd19 Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _send_messaging_menu(self, user_id: int, message_id: int):
        """Render the canonical messaging menu."""
        await self.handlers.show_messaging_menu(user_id, message_id)

    async def _send_automation_menu(self, user_id: int, message_id: int):
        """Send automation menu"""
        text = (
            "\u274c **Automation**\n\n"
            "Automate account actions and workflows.\n\n"
            "Available features:"
            "• Online maker (keep accounts online)\n"
            "• Auto-reply rules\n"
            "• Scheduled posts\n"
            "• Auto-join/leave groups"
        )
        buttons = [[Button.inline("\ud83d\udd19 Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _send_analytics_menu(self, user_id: int, message_id: int):
        """Send analytics menu"""
        text = (
            "\ud83d\udd19 **Analytics**\n\n"
            "View account statistics and activity.\n\n"
            "Features coming soon:"
            "• Account health monitoring\n"
            "• Session activity logs\n"
            "• OTP destroyer statistics\n"
            "• Automation performance"
        )
        buttons = [[Button.inline("\ud83d\udd19 Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _send_support_menu(self, user_id: int, message_id: int):
        """Send support menu"""
        text = (
            "\ud83d\udd19 **Support & Contact**\n\n"
            "Need help? Contact our support team:\n\n"
            "👨💻 **Developers:**\n"
            "• @Meher_Mankar\n"
            "• @Gutkesh\n\n"
            "\ud83d\udd19 **Support:** https://t.me/ContactXYZrobot\n"
            "🐛 **Bug Reports:** Create an issue on GitHub\n\n"
            "⏰ **Response Time:** Usually within 24 hours\n\n"
            "💬 **Tips:**\n"
            "• Include error messages when reporting bugs\n"
            "• Describe steps to reproduce issues\n"
            "• Check /help for common solutions first"
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
                await event.answer("\u274c Service unavailable", alert=True)
                return

            # Get twofa_commands handler
            twofa_handler = None
            if hasattr(self.account_manager, "twofa_commands"):
                twofa_handler = self.account_manager.twofa_commands
            elif hasattr(self, "twofa_commands"):
                twofa_handler = self.twofa_commands

            if action in ["set", "change", "remove"]:
                if not twofa_handler:
                    await event.answer(
                        "\u274c 2FA management not available", alert=True
                    )
                    return
                await twofa_handler.handle_2fa_callback(event, user_id, data)
            elif action == "status":
                # Show 2FA status using secure handlers
                if self.secure_2fa_handlers:
                    await self.secure_2fa_handlers.show_2fa_status(
                        user_id, account_id, event.message_id
                    )
                else:
                    await event.answer(
                        "\u274c 2FA management not available", alert=True
                    )
        except Exception as e:
            logger.error(f"2FA callback error: {e}")
            await event.answer("❌ Error processing 2FA request", alert=True)

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
                    if hasattr(self.account_manager, "online_maker"):
                        account_identifier = account.get("phone") or account.get(
                            "name", "unknown"
                        )
                        if new_status:
                            await self.account_manager.online_maker.start_online_maker(
                                user_id, account_identifier
                            )
                        else:
                            await self.account_manager.online_maker.stop_online_maker(
                                user_id, account_identifier
                            )
                    status = "started" if new_status else "stopped"
                    status_emoji = "✅" if new_status else "❌"
                    await event.answer(f"{status_emoji} Online maker {status}!")
                    await self.send_account_management(
                        user_id, account_id, event.message_id
                    )
            except Exception:
                await event.answer("❌ Error toggling online maker")

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
            "🔐 **Active Sessions**\n\n"
            "Loading session information...\n\n"
            "This will show all active login sessions for the account."
        )
        buttons = [[Button.inline("\ud83d\udd19 Back", f"account:manage:{account_id}")]]
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
                text = f"\ud83d\udd19 **Online Maker {
                    status.title()}**\n\nAccount: {
                    account['name']}\nStatus: {status}\nInterval: {interval}s"
                buttons = [
                    [Button.inline("\ud83d\udd19 Back", f"account:manage:{account_id}")]
                ]
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except (ValueError, KeyError, ConnectionError) as e:
            logger.error(f"Failed to toggle online maker: {e}")

    async def _send_automation_management(
        self, user_id: int, account_id: str, message_id: int
    ):
        """Send automation management for account"""
        text = (
            "\u274c **Automation Management**\n\n"
            "Configure automation rules and jobs.\n\n"
            "Available options:"
            "• Online maker\n"
            "• Auto-reply rules\n"
            "• Scheduled actions"
        )
        buttons = [
            [Button.inline("\ud83d\udd19 Online Maker", f"online:toggle:{account_id}")],
            [Button.inline("\ud83d\udd19 Back", f"account:manage:{account_id}")],
        ]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _handle_profile_name_change(self, user_id: int, account_id: str, event):
        """Handle profile name change - delegated to ProfileOperations"""
        from .menu_modules import ProfileOperations

        ops = ProfileOperations(self)
        await ops.handle_profile_name_change(user_id, account_id, event)

    async def _handle_profile_name_change_legacy(
        self, user_id: int, account_id: str, event
    ):
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
                except (ValueError, ConnectionError) as e:
                    await name_event.reply(f"Failed to update name: {e}")
            else:
                await name_event.reply("Account client not found")
            self.bot.remove_event_handler(handle_name_input)

    async def _handle_profile_username_change(
        self, user_id: int, account_id: str, event
    ):
        """Handle username change - delegated to ProfileOperations"""
        from .menu_modules import ProfileOperations

        ops = ProfileOperations(self)
        await ops.handle_profile_username_change(user_id, account_id, event)

    async def _handle_profile_username_change_legacy(
        self, user_id: int, account_id: str, event
    ):
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
                except (ValueError, ConnectionError) as e:
                    await username_event.reply(f"Failed to update username: {e}")
            else:
                await username_event.reply(
                    f"Account client not found. Account: {
                        account['name']}, User: {user_id}"
                )
            self.bot.remove_event_handler(handle_username_input)

    async def _handle_profile_bio_change(self, user_id: int, account_id: str, event):
        """Handle bio change - delegated to ProfileOperations"""
        from .menu_modules import ProfileOperations

        ops = ProfileOperations(self)
        await ops.handle_profile_bio_change(user_id, account_id, event)

    async def _handle_profile_bio_change_legacy(
        self, user_id: int, account_id: str, event
    ):
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
                except (ValueError, ConnectionError) as e:
                    await bio_event.reply(f"Failed to update bio: {e}")
            else:
                await bio_event.reply(
                    f"Account client not found. Account: {
                        account['name']}, User: {user_id}"
                )
            self.bot.remove_event_handler(handle_bio_input)

    async def _handle_profile_photo_change(self, user_id: int, account_id: str, event):
        """Handle photo change - delegated to ProfileOperations"""
        from .menu_modules import ProfileOperations

        ops = ProfileOperations(self)
        await ops.handle_profile_photo_change(user_id, account_id, event)

    async def _handle_profile_photo_change_legacy(
        self, user_id: int, account_id: str, event
    ):
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

                    if (
                        photo_path
                        and os.path.exists(photo_path)
                        and os.path.isfile(photo_path)
                    ):
                        os.remove(photo_path)
                    await photo_event.reply("Profile photo updated successfully")
                except (ValueError, ConnectionError, OSError) as e:
                    await photo_event.reply(f"Failed to update photo: {e}")
            else:
                await photo_event.reply(
                    f"Account client not found. Account: {
                        account['name']}, User: {user_id}"
                )
            self.bot.remove_event_handler(handle_photo_input)

    async def _handle_add_account(self, event, user_id: int):
        """Handle add account request"""
        try:
            from ..core.config import MAX_ACCOUNTS

            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if not user:
                await event.answer("🚀 Please start the bot first")
                return
            account_count = await mongodb.db.accounts.count_documents(
                {"user_id": user_id}
            )
            if account_count >= MAX_ACCOUNTS:
                await event.answer(f"⚠️ Maximum account limit ({MAX_ACCOUNTS}) reached")
                return
            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {
                    "action": "add_account"
                }
                text = (
                    "➕ **Add New Account**\n\n"
                    "Reply with the phone number for the new account.\n\n"
                    "📞 Format: +1234567890 (include country code)\n"
                    "💡 Tip: Enter OTP codes as 1-2-3-4-5 (with hyphens)"
                )
                await event.answer("➕ Reply with phone number")
                await self.bot.send_message(user_id, text)
            else:
                await event.answer("❌ Service unavailable")
        except (ValueError, KeyError, ConnectionError) as e:
            logger.error(f"Failed to handle add account: {e}")
            await event.answer("❌ Error processing request")

    async def _handle_remove_account(self, event, user_id: int):
        """Handle remove account request"""
        try:
            # Prompt user to select account to remove
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                await self.bot.send_message(user_id, "❌ No accounts to remove.")
                return
            text = "🗑️ **Remove Account**\n\nSelect an account to remove:"
            buttons = []
            for account in accounts:
                buttons.append(
                    [
                        Button.inline(
                            f"🗑️ {account['name']} ({account['phone']})",
                            f"remove:confirm:{account['_id']}",
                        )
                    ]
                )
            buttons.append([Button.inline("🔙 Back to Accounts", "menu:accounts")])
            await self.bot.send_message(user_id, text, buttons=buttons)
        except (ValueError, KeyError, ConnectionError) as e:
            logger.error(f"Failed to handle remove account: {e}")
            await event.reply("⚠️ Error processing remove account request")

    async def _execute_remove_account(self, event, user_id: int, account_id: str):
        """Execute account removal"""
        try:
            if self.account_manager:
                try:
                    from ..core.database_manager import db_manager

                    await db_manager.remove_2fa_password(user_id, account_id)
                except Exception:
                    pass
                success, message = await self.account_manager.remove_account_by_id(
                    user_id, account_id
                )
                message = (
                    "Account removed successfully"
                    if success
                    else "Failed to remove account"
                )
                if success:
                    await event.answer("✅ Account removed successfully!")
                    await self.bot.edit_message(
                        user_id,
                        event.message_id,
                        "✅ **Account Removed**\n\nThe account has been successfully removed from TeleGuard.\n\n🔐 Session terminated from Telegram\n🔐 Stored 2FA password also removed for security",
                        buttons=[
                            [Button.inline("🔙 Back to Accounts", "menu:accounts")]
                        ],
                    )
                else:
                    await event.answer(f"❌ Failed to remove account: {message}")
                    await self.bot.edit_message(
                        user_id,
                        event.message_id,
                        f"❌ **Removal Failed**\n\n{message}",
                        buttons=[
                            [Button.inline("🔙 Back to Accounts", "menu:accounts")]
                        ],
                    )
            else:
                await event.answer("❌ Service unavailable")
        except (ValueError, KeyError, ConnectionError) as e:
            logger.error(f"Failed to execute remove account: {e}")
            await event.reply("⚠️ Error executing account removal")

    async def _handle_messaging_callback(self, event, user_id: int, data: str):
        """Delegate messaging callbacks to the canonical router."""
        await self.router.handle_messaging_callback(event, user_id, data)

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
                "\ud83d\udd19 **Compose Message**\n\n"
                "Reply with the target (username, phone, or chat ID):\n\n"
                "Examples:\n"
                "• @username\n"
                "• +1234567890\n"
                "• -1001234567890 (for groups/channels)"
            )
            await event.answer("\ud83d\udd19 Reply with target")
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
            if hasattr(self.account_manager, "template_handler"):
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
                await self.bot.send_message(user_id, "\u274c Account not found")
                return
            auto_enabled = account.get("auto_reply_enabled", False)
            auto_message = account.get("auto_reply_message", "Not set")
            text = (
                f"🔄 **Auto Reply: {account['name']}**\n\n"
                f"Status: {'?? Enabled' if auto_enabled else '🔴 Disabled'}\n"
                f"Message: {auto_message[:50]}{'...' if len(auto_message) > 50 else ''}\n\n"
                f"Configure auto-reply settings:"
            )
            toggle_text = "🔴 Disable" if auto_enabled else "\ud83d\udd19 Enable"
            buttons = [
                [
                    Button.inline(
                        f"{toggle_text} Auto Reply", f"autoreply:toggle:{account_id}"
                    )
                ],
                [
                    Button.inline(
                        "\ud83d\udd19 Set Message", f"autoreply:set:{account_id}"
                    )
                ],
                [Button.inline("\ud83d\udd19 Back", "msg:autoreply")],
            ]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except (ValueError, KeyError, ConnectionError) as e:
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
                    {"$set": {"auto_reply_enabled": new_status}},
                )
                await event.answer(
                    f"🔄 Auto-reply {'enabled' if new_status else 'disabled'}"
                )
                await self._send_autoreply_management(
                    user_id, account_id, event.message_id
                )
        except (ValueError, KeyError, ConnectionError) as e:
            logger.error(f"Toggle autoreply error: {e}")
            await event.answer("❌ Error toggling auto-reply")

    async def _set_autoreply_message(self, user_id: int, account_id: str, event):
        """Set auto-reply message"""
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "set_autoreply_message",
                "account_id": account_id,
            }
            text = (
                "\ud83d\udd19 **Set Auto-Reply Message**\n\n"
                "Reply with the message to send automatically:\n\n"
                "This message will be sent to anyone who messages this account."
            )
            await event.answer("\ud83d\udd19 Reply with message")
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

    async def _start_bulk_contacts_flow(self, user_id: int, event):
        """Start bulk contacts flow - delegated to MessagingOperations"""
        from .menu_modules import MessagingOperations

        ops = MessagingOperations(self)
        await ops.start_bulk_contacts_flow(user_id, event)

    async def _start_bulk_all_flow(self, user_id: int, event):
        """Start bulk all flow - delegated to MessagingOperations"""
        from .menu_modules import MessagingOperations

        ops = MessagingOperations(self)
        await ops.start_bulk_all_flow(user_id, event)

    async def _show_bulk_jobs(self, user_id: int, message_id: int):
        """Show bulk jobs - delegated to MessagingOperations"""
        from .menu_modules import MessagingOperations

        ops = MessagingOperations(self)
        await ops.show_bulk_jobs(user_id, message_id)

    async def _show_bulk_help(self, user_id: int, message_id: int):
        """Show bulk help - delegated to MessagingOperations"""
        from .menu_modules import MessagingOperations

        ops = MessagingOperations(self)
        await ops.show_bulk_help(user_id, message_id)

    async def _handle_simulate_callback(self, event, user_id: int, data: str):
        await self.callback_handlers.handle_simulate_callback(event, user_id, data)

    async def _handle_manage_callback(self, event, user_id: int, data: str):
        """Handle channel management account selection"""
        account_phone = data.split(":")[1]
        await self._send_channel_actions_menu(user_id, account_phone, event.message_id)

    async def _send_channel_actions_menu(
        self, user_id: int, account_phone: str, message_id: int
    ):
        """Send channel actions menu for selected account"""
        text = (
            f"\ud83d\udd19 **Managing: {account_phone}**\n\nWhat would you like to do?"
        )
        buttons = [
            [
                Button.inline("🔗 Join Channel", f"channel:join:{account_phone}"),
                Button.inline(
                    "\ud83d\udd19 Leave Channel", f"channel:leave:{account_phone}"
                ),
            ],
            [
                Button.inline(
                    "\ud83d\udd19 Create Channel", f"channel:create:{account_phone}"
                ),
                Button.inline(
                    "\ud83d\udd19? Delete Channel", f"channel:delete:{account_phone}"
                ),
            ],
            [
                Button.inline(
                    "\ud83d\udd19 List Channels", f"channel:list:{account_phone}"
                )
            ],
            [Button.inline("\ud83d\udd19 Back to Accounts", "back:accounts")],
        ]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _handle_channels_pagination(self, event, user_id: int, data: str):
        """Handle channels pagination callbacks"""
        parts = data.split(":")
        parts[1]  # prev or next
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
            text = f"\ud83d\udd19 **Channels for {account_phone}** (Page {
                page + 1}/{total_pages})\n\n"
            for i, ch in enumerate(page_channels, start_idx + 1):
                emoji = "\ud83d\udd19" if ch["type"] == "channel" else "\ud83d\udd19"
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
                        "⬅️ Previous", f"channels:prev:{account_phone}:{page - 1}"
                    )
                )
            if page < total_pages - 1:
                nav_buttons.append(
                    Button.inline(
                        "➡️ Next",
                        f"channels:next:{account_phone}:{
                            page + 1}")
                )
            buttons = []
            if nav_buttons:
                buttons.append(nav_buttons)
            buttons.append(
                [Button.inline("\ud83d\udd19 Back", f"manage:{account_phone}")]
            )
            await event.answer(f"Page {page + 1}")
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )

    def _get_uptime(self) -> str:
        """Get bot uptime"""
        try:
            import time

            if hasattr(self.account_manager, "start_time"):
                uptime_seconds = time.time() - self.account_manager.start_time
                hours = int(uptime_seconds // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                return f"{hours}h {minutes}m"
            return "Unknown"
        except BaseException:
            return "Unknown"

    async def _handle_export_sessions(self, event, user_id: int):
        """Handle export sessions menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = "✨ **Fresh Sessions**\n\n? No accounts found. Add accounts first to create fresh sessions."
                buttons = [
                    [Button.inline("\ud83d\udd19 Back to Accounts", "menu:accounts")]
                ]
            else:
                text = "✨ **Fresh Sessions**\n\nSelect account to create fresh session for:"
                buttons = []
                for account in accounts:
                    status = "\u2705" if account.get("is_active", False) else "\u274c"
                    display_name = self.format_display_name(account)
                    buttons.append(
                        [
                            Button.inline(
                                f"{status} {display_name}",
                                f"export_session:{account['name']}",
                            )
                        ]
                    )
                buttons.append(
                    [Button.inline("\ud83d\udd19 Back to Accounts", "menu:accounts")]
                )
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        except (ValueError, KeyError, ConnectionError) as e:
            logger.error(f"Failed to handle export sessions: {e}")
            await event.answer("\u274c Error loading export sessions")

    async def _handle_export_session_select(
        self, event, user_id: int, account_name: str
    ):
        """Handle export session selection"""
        try:
            # Find account by name
            account = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "name": account_name}
            )
            if not account:
                await event.answer("\u274c Account not found")
                return

            display_name = self.format_display_name(account)
            text = f"✨ **Fresh Session: {display_name}**\n\nThis will create a completely new session:"
            buttons = [
                [
                    Button.inline(
                        "✨ Create Fresh Session", f"export_fresh:{account_name}"
                    )
                ],
                [Button.inline("\ud83d\udd19 Back to Export", "export_sessions")],
            ]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        except (ValueError, KeyError, ConnectionError) as e:
            logger.error(f"Failed to handle export session select: {e}")
            await event.answer("\u274c Error processing export selection")

    async def _handle_export_session_file(self, event, user_id: int, account_name: str):
        """Handle export session file"""
        try:
            # Find account by name
            account = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "name": account_name}
            )
            if not account:
                await event.answer("\u274c Account not found")
                return

            if not account.get("is_active", False):
                await event.answer("\u274c Account is not connected")
                return

            # Use account manager to export session file
            if hasattr(self.account_manager, "export_session_file"):
                success, message = await self.account_manager.export_session_file(
                    user_id, account["phone"]
                )
                if success:
                    await event.answer("\u274c Session file exported successfully")
                else:
                    await event.answer(f"\u274c Export failed: {message}")
            else:
                await event.answer("\u274c Export functionality not available")
        except (ValueError, KeyError, ConnectionError) as e:
            logger.error(f"Failed to export session file: {e}")
            await event.answer("❌ Error exporting session file")

    async def _handle_export_fresh_session(
        self, event, user_id: int, account_name: str
    ):
        """Handle export session string with DC information"""
        try:
            # Find account by name
            account = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "name": account_name}
            )
            if not account:
                await event.answer("\u274c Account not found")
                return

            if not account.get("is_active", False):
                await event.answer("\u274c Account is not connected")
                return

            # Get client from account manager
            if (
                user_id in self.account_manager.user_clients
                and account_name in self.account_manager.user_clients[user_id]
            ):
                client = self.account_manager.user_clients[user_id][account_name]
                if client and client.is_connected():
                    try:
                        # Get session string
                        session_string = client.session.save()

                        # Get DC information - this is what you want: DC1, DC2, DC3,
                        # DC4, or DC5
                        dc_id = client.session.dc_id
                        if dc_id and 1 <= dc_id <= 5:
                            dc_display = f"DC{dc_id}"
                        else:
                            dc_display = "Unknown DC"

                        # Get account info
                        display_name = self.format_display_name(account)
                        phone = account.get("phone", "Unknown")

                        # Format message with prominent DC information
                        message = (
                            f"\ud83d\udd19 **Session Export - {dc_display}**\n\n"
                            f"\ud83d\udd19 **Account:** {display_name}\n"
                            f"\ud83d\udd19 **Phone:** {phone}\n"
                            f"\ud83d\udd19 **Data Center:** {dc_display}\n\n"
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
                            f"\ud83d\udd19 **Keep this {dc_display} session secure!**"
                        )

                        from telethon import Button

                        buttons = [
                            [
                                Button.inline(
                                    "\ud83d\udd19 Back to Export", "export_sessions"
                                )
                            ]
                        ]
                        await event.answer()
                        await self.bot.edit_message(
                            user_id, event.message_id, message, buttons=buttons
                        )

                    except (ValueError, AttributeError, ConnectionError) as e:
                        logger.error(f"Error getting session data: {e}")
                        await event.answer("❌ Error extracting session data")
                else:
                    await event.answer("❌ Account client not connected")
            else:
                await event.answer("❌ Account client not found")

        except (ValueError, KeyError, ConnectionError) as e:
            logger.error(f"Failed to export session string: {e}")
            await event.answer("❌ Error exporting session string")

    async def _handle_export_contacts(self, event, user_id: int, account_name: str):
        """Handle export contacts"""
        try:
            # Find account by name
            account = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "name": account_name}
            )
            if not account:
                await event.answer("\u274c Account not found")
                return

            if not account.get("is_active", False):
                await event.answer("\u274c Account is not connected")
                return

            # Use contact export handler
            try:
                from ..handlers.contact_export_handler import ContactExportHandler

                export_handler = ContactExportHandler(self.account_manager)
                success, message = await export_handler.export_contacts_to_csv(
                    user_id, account["name"]
                )
                if success:
                    await event.answer("✅ Contacts exported successfully")
                else:
                    await event.answer(f"\u274c Export failed: {message}")
            except ImportError:
                await event.answer("❌ Contact export handler not available")
        except (ValueError, KeyError, ConnectionError) as e:
            logger.error(f"Failed to export contacts: {e}")
            await event.answer("❌ Error exporting contacts")

    def validate_session_string(self, session_string: str) -> dict:
        """Validate session string and extract DC information (DC1, DC2, DC3, DC4, or DC5)"""
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession

            from ..core.config import config

            # Test the provided session string
            test_session = StringSession(session_string)
            TelegramClient(
                test_session, config.telegram.api_id, config.telegram.api_hash
            )

            # Extract DC information - show DC1, DC2, DC3, DC4, or DC5
            dc_id = test_session.dc_id if hasattr(test_session, "dc_id") else None
            if dc_id and 1 <= dc_id <= 5:
                dc_name = f"DC{dc_id}"
            else:
                dc_name = "Unknown DC"

            return {
                "valid": True,
                "dc_id": dc_id,
                "dc_name": dc_name,
                "length": len(session_string),
                "format": "Telethon StringSession",
            }
        except (ValueError, AttributeError, ImportError) as e:
            return {
                "valid": False,
                "error": str(e),
                "length": len(session_string) if session_string else 0,
                "format": "Invalid",
            }

    async def _handle_bulk_otp_enable(self, user_id: int, message_id: int):
        """Enable OTP Destroyer for all user accounts"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = "\ud83d\udd19? **Enable All OTP Destroyers**\n\n? No accounts found."
                buttons = [
                    [Button.inline("\ud83d\udd19 Back to OTP Manager", "menu:otp")]
                ]
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                return

            # Enable OTP Destroyer for all accounts
            enabled_count = 0
            for account in accounts:
                try:
                    from bson import ObjectId

                    await mongodb.db.accounts.update_one(
                        {"_id": ObjectId(account["_id"])},
                        {
                            "$set": {
                                "otp_destroyer_enabled": True,
                                "otp_forward_enabled": False,
                            }
                        },
                    )
                    enabled_count += 1
                except Exception as e:
                    logger.error(
                        f"Error enabling OTP for account {account['name']}: {e}"
                    )

            text = (
                f"\ud83d\udd19? **Bulk Enable Complete**\n\n"
                f"\u274c Enabled OTP Destroyer for {enabled_count}/{
                    len(accounts)} accounts\n\n"
                f"🔴 Forward disabled for all accounts (security best practice)\n\n"
                f"\ud83d\udd19? All your accounts are now protected!"
            )

            buttons = [
                [Button.inline("\ud83d\udd19 View Statistics", "otp:stats")],
                [Button.inline("\ud83d\udd19 Back to OTP Manager", "menu:otp")],
            ]

            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

        except (ValueError, KeyError, ConnectionError) as e:
            logger.error(f"Error in bulk OTP enable: {e}")
            text = f"\u274c Error enabling OTP Destroyers: {str(e)}"
            buttons = [[Button.inline("\ud83d\udd19 Back to OTP Manager", "menu:otp")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _handle_bulk_otp_disable(self, user_id: int, message_id: int):
        """Disable OTP Destroyer for all user accounts"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = "🔴 **Disable All OTP Destroyers**\n\n? No accounts found."
                buttons = [
                    [Button.inline("\ud83d\udd19 Back to OTP Manager", "menu:otp")]
                ]
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                return

            # Disable OTP Destroyer for all accounts
            disabled_count = 0
            for account in accounts:
                try:
                    from bson import ObjectId

                    await mongodb.db.accounts.update_one(
                        {"_id": ObjectId(account["_id"])},
                        {"$set": {"otp_destroyer_enabled": False}},
                    )
                    disabled_count += 1
                except Exception as e:
                    logger.error(
                        f"Error disabling OTP for account {account['name']}: {e}"
                    )

            text = (
                f"🔴 **Bulk Disable Complete**\n\n"
                f"\u274c Disabled OTP Destroyer for {disabled_count}/{
                    len(accounts)} accounts\n\n"
                f"\ud83d\udd19 **WARNING:** All your accounts are now vulnerable to unauthorized login attempts!\n\n"
                f"\ud83d\udd19? Consider re-enabling protection when needed."
            )

            buttons = [
                [Button.inline("\ud83d\udd19? Enable All Again", "otp:enable_all")],
                [Button.inline("\ud83d\udd19 Back to OTP Manager", "menu:otp")],
            ]

            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

        except (ValueError, KeyError, ConnectionError) as e:
            logger.error(f"Error in bulk OTP disable: {e}")
            text = f"\u274c Error disabling OTP Destroyers: {str(e)}"
            buttons = [[Button.inline("\ud83d\udd19 Back to OTP Manager", "menu:otp")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _handle_otp_setting_callback(self, event, user_id: int, data: str):
        """Handle OTP setting callbacks - direct enable/disable without old menu"""
        parts = data.split(":")
        setting_type = parts[1]  # destroyer, forward, or temp

        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                await event.answer("\u274c No accounts found")
                return

            if setting_type == "destroyer":
                text = "\ud83d\udd19? **OTP Destroyer Settings**\n\nSelect account to toggle OTP Destroyer:"
                buttons = []
                for account in accounts:
                    status = "\ud83d\udd19" if account.get("is_active", False) else "🔴"
                    destroyer_status = (
                        "\ud83d\udd19?"
                        if account.get("otp_destroyer_enabled", False)
                        else "\u2705"
                    )
                    display_name = format_display_name(account)
                    action = (
                        "disable"
                        if account.get("otp_destroyer_enabled", False)
                        else "enable"
                    )
                    button_text = f"{status}{destroyer_status} {display_name}"
                    buttons.append(
                        [Button.inline(button_text, f"otp:{action}:{account['_id']}")]
                    )

            elif setting_type == "forward":
                text = "\ud83d\udd19 **OTP Forward Settings**\n\nSelect account to toggle OTP Forward:"
                buttons = []
                for account in accounts:
                    status = "\ud83d\udd19" if account.get("is_active", False) else "🔴"
                    forward_status = (
                        "\ud83d\udd19"
                        if account.get("otp_forward_enabled", False)
                        else "\u2705"
                    )
                    display_name = format_display_name(account)
                    action = (
                        "forward_disable"
                        if account.get("otp_forward_enabled", False)
                        else "forward_enable"
                    )
                    button_text = f"{status}{forward_status} {display_name}"
                    buttons.append(
                        [Button.inline(button_text, f"otp:{action}:{account['_id']}")]
                    )

            elif setting_type == "temp":
                text = "⏰ **Temp OTP Settings**\n\nSelect account to enable 5-minute temp OTP:"
                buttons = []
                for account in accounts:
                    status = "\ud83d\udd19" if account.get("is_active", False) else "🔴"
                    destroyer_status = (
                        "\ud83d\udd19?"
                        if account.get("otp_destroyer_enabled", False)
                        else "\u2705"
                    )
                    display_name = format_display_name(account)
                    button_text = f"{status}{destroyer_status} {display_name}"
                    buttons.append(
                        [Button.inline(button_text, f"otp:temp:{account['_id']}")]
                    )

            buttons.append(
                [Button.inline("\ud83d\udd19 Back to OTP Manager", "menu:otp")]
            )
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )

        except Exception as e:
            logger.error(f"Error in OTP setting callback: {e}")
            await event.answer("❌ Error processing OTP setting")

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
                await event.answer("\u274c Account not found")
                return

            display_name = format_display_name(account)

            if toggle_type == "destroyer":
                current_status = account.get("otp_destroyer_enabled", False)
                new_status = not current_status

                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {
                        "$set": {
                            "otp_destroyer_enabled": new_status,
                            "otp_forward_enabled": (
                                False
                                if new_status
                                else account.get("otp_forward_enabled", False)
                            ),
                        }
                    },
                )

                if new_status:
                    await event.answer(
                        f"\ud83d\udd19? OTP Destroyer enabled for {display_name}!"
                    )
                else:
                    await event.answer(f"🔴 OTP Destroyer disabled for {display_name}!")

            elif toggle_type == "forward":
                # Check if destroyer is enabled first
                if account.get("otp_destroyer_enabled", False):
                    await event.answer(
                        "\u274c Cannot enable forward while OTP Destroyer is active"
                    )
                    return

                current_status = account.get("otp_forward_enabled", False)
                new_status = not current_status

                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {"otp_forward_enabled": new_status}},
                )

                if new_status:
                    await event.answer(
                        f"\ud83d\udd19 OTP Forward enabled for {display_name}!"
                    )
                else:
                    await event.answer(f"🔴 OTP Forward disabled for {display_name}!")

            elif toggle_type == "temp":
                if not account.get("otp_destroyer_enabled", False):
                    await event.answer(
                        "⚠️ Temp OTP only works when OTP Destroyer is enabled"
                    )
                    return

                # Enable 5-minute temp passthrough
                import time

                expiry_time = time.time() + 300  # 5 minutes

                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {
                        "$set": {
                            "otp_temp_passthrough": True,
                            "temp_passthrough_expiry": expiry_time,
                            "otp_destroyer_enabled": False,  # Temporarily disable
                            "otp_forward_enabled": True,  # Temporarily enable
                        }
                    },
                )

                await event.answer(f"⏰ 5-minute temp OTP enabled for {display_name}!")

                # Schedule cleanup
                try:
                    import asyncio

                    from ..handlers.temp_otp_cleanup import cleanup_temp_otp

                    asyncio.create_task(
                        cleanup_temp_otp(user_id, account_id, expiry_time)
                    )
                except ImportError:
                    logger.warning("temp_otp_cleanup module not found")

            # Refresh the current menu to show updated status
            await self._handle_otp_setting_callback(
                event, user_id, f"otp_setting:{toggle_type}"
            )

        except Exception as e:
            logger.error(f"Error in OTP toggle callback: {e}")
            await event.answer("❌ Error toggling OTP setting")


    async def _show_messaging_statistics(self, user_id: int, message_id: int):
        """Show messaging analytics dashboard"""
        try:
            from telethon import Button

            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            total_accounts = len(accounts)
            active_accounts = sum(1 for a in accounts if a.get("is_active"))
            auto_reply_on = sum(1 for a in accounts if a.get("auto_reply_enabled"))

            from ..services.messaging_stats import MessagingStats

            stats = await MessagingStats().get_user_stats(user_id)
            total_sent = stats["total_messages"]
            auto_replies = stats["total_auto_replies"]
            bulk_sent = stats["total_bulk_messages"]
            dm_topics = await mongodb.db.dm_topics.count_documents({"user_id": user_id})

            text = (
                "📊 **Messaging Analytics**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📱 **Accounts:** {active_accounts}/{total_accounts} active\n"
                f"🤖 **Auto-Reply:** {auto_reply_on} accounts enabled\n\n"
                "📤 **Message Activity (last 7 days):**\n"
                f"• Total Sent: {total_sent:,}\n"
                f"• Auto-Replies: {auto_replies:,}\n"
                f"• Bulk Messages: {bulk_sent:,}\n"
                f"• DM Topics: {dm_topics}\n\n"
                "💡 Messages are tracked as you use the bot."
            )
            buttons = [
                [Button.inline("🔄 Refresh", "msg:stats")],
                [Button.inline("🔙 Back to Messaging", "menu:messaging")],
            ]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing messaging statistics: {e}")
            from telethon import Button
            await self.bot.edit_message(
                user_id, message_id,
                "❌ Error loading analytics",
                buttons=[[Button.inline("🔙 Back", "menu:messaging")]]
            )

    async def _show_message_history(self, user_id: int, message_id: int):
        """Show recent message history from DB"""
        try:
            import time
            from telethon import Button

            # Fetch last 15 sent messages from DB
            from ..services.messaging_stats import MessagingStats

            records = await MessagingStats().get_recent_messages(user_id, limit=15)

            if not records:
                text = (
                    "📋 **Message History**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "💭 No message history found yet.\n\n"
                    "History is recorded when you send messages through:\n"
                    "• Smart Messaging\n"
                    "• Bulk Campaigns\n"
                    "• Auto-Reply responses"
                )
            else:
                text = (
                    f"📋 **Message History** (last {len(records)})\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                )
                for rec in records:
                    ts = time.strftime("%m-%d %H:%M", time.localtime(rec.get("timestamp", 0)))
                    target = rec.get("target", "Unknown")
                    msg_type = rec.get("type", "msg")
                    type_emoji = {
                        "auto_reply": "🤖",
                        "bulk": "📨",
                        "manual": "📤",
                        "scheduled": "⏰",
                    }.get(msg_type, "📤")
                    account_id = str(rec.get("account_id", "?"))
                    text += (
                        f"{type_emoji} `{ts}` → **{target}** via "
                        f"account `{account_id[:8]}`\n"
                    )

            buttons = [
                [Button.inline("🔄 Refresh", "msg:history")],
                [Button.inline("🔙 Back to Messaging", "menu:messaging")],
            ]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing message history: {e}")
            from telethon import Button
            await self.bot.edit_message(
                user_id, message_id,
                "❌ Error loading message history",
                buttons=[[Button.inline("🔙 Back", "menu:messaging")]]
            )
