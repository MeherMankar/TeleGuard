# -*- coding: utf-8 -*-
"""Callback router for handling different callback types"""
import logging
from typing import Callable, Dict
from bson import ObjectId

from ...core.mongo_database import mongodb
from .callback_handlers import CallbackHandlers

logger = logging.getLogger(__name__)


class CallbackRouter:
    """Routes callbacks to appropriate handlers"""

    def __init__(self, menu_system):
        self.menu = menu_system
        self.handlers = CallbackHandlers(menu_system)

        # Callback routing map
        self.routes: Dict[str, Callable] = {
            "account": self.handlers.handle_account_callback,
            "remove": self.handlers.handle_remove_callback,
            "otp": self.handlers.handle_otp_callback,
            "otp_setting": self.handle_otp_setting_callback,
            "otp_pwd": self.handle_otp_pwd_callback,
            "online": self.handlers.handle_online_callback,
            "simulate": self.handlers.handle_simulate_callback,
            "profile": self.handlers.handle_profile_callback,
            "sessions": self.handlers.handle_session_callback,
            "session": self.handlers.handle_session_callback,
            "2fa": self.handlers.handle_2fa_callback,
            "menu": self.handle_menu_callback,
            "create": self.handle_create_callback,
            "import": self.handle_import_callback,
            "export": self.handle_export_callback,
            "toggle_session": self.handle_toggle_session_callback,
            "toggle_all_sessions": self.handle_toggle_all_sessions_callback,
            "create_selected_sessions": self.handle_create_selected_sessions_callback,
            "session_type": self.handle_session_type_callback,
            "cleanup": self.handle_cleanup_callback,
            "session_login": self.handle_session_login_callback,
            "login_session_file": self.handle_session_login_callback,
            "login_session_string": self.handle_session_login_callback,
            "export_sessions": self.handle_session_login_callback,
            "create_sess": self.handle_session_login_callback,
            "create_sess_fmt": self.handle_session_login_callback,
            "contacts": self.handle_contacts_callback,
            "spam_master": self.handle_spam_master_callback,
            "manual_otp": self.handle_manual_otp_callback,
            "resend_otp": self.handle_resend_otp_callback,
            "cancel_session": self.handle_cancel_session_callback,
            "msg": self.handle_messaging_callback,
            "auto_reply": self.handle_auto_reply_callback,
            "dm_reply": self.handle_dm_reply_callback,
            "template": self.handle_template_callback,
            "bulk": self.handle_bulk_callback,
            "bulk_list_account": self.handle_bulk_list_account_callback,
            "bulk_contacts_account": self.handle_bulk_contacts_account_callback,
            "channel": self.handle_channel_callback,
            "help": self.handle_help_callback,
            "support": self.handle_support_callback,
            "dev": self.handle_dev_callback,
            "appeal_account_id": self.handle_appeal_callback,
            "advanced_spam": self.handle_spam_master_callback,
            "contact": self.handle_contacts_callback,
            "sync": self.handle_contacts_callback,
            "group": self.handle_contacts_callback,
            "tag": self.handle_contacts_callback,
            "export_acc": self.handle_contacts_callback,
            "device": self.handle_device_callback,
            "back": self.handle_back_callback,
            "toggle_otp": self.handlers.handle_otp_callback,
            "manage": self.handle_manage_callback,
            "export_session": self.handle_export_session_callback,
            "export_fresh": self.handle_export_fresh_callback,
            "export_string": self.handle_export_string_callback,
            "export_file": self.handle_export_file_callback,
            "export_contacts": self.handle_export_contacts_callback,
            "session_info": self.handle_session_login_callback,
            "session_operations": self.handle_session_login_callback,
            "session_op": self.handle_session_login_callback,
            "session_delete": self.handle_session_login_callback,
            "session_export_string": self.handle_session_login_callback,
            "autoreply": self.handle_auto_reply_callback,
            "channels": self.handle_channel_callback,
            "import_sessions": self.handle_session_login_callback,
        }

    async def route_callback(self, event, user_id: int, data: str) -> bool:
        """Route callback to appropriate handler"""
        try:
            # Parse callback data
            parts = data.split(":")
            if not parts:
                logger.warning(f"Invalid callback data: {data}")
                return False

            callback_type = parts[0]

            # Find and execute handler
            handler = self.routes.get(callback_type)
            if handler:
                await handler(event, user_id, data)
                return True
            else:
                logger.warning(
                    f"No handler found for callback type: '{callback_type}' in data: '{data}'"
                )
                # Catch-all: acknowledge callback to prevent error message
                try:
                    await event.answer("✅ Processing...")
                except BaseException:
                    pass
                return True

        except Exception as e:
            # Handle specific Telegram errors
            error_msg = str(e).lower()
            if (
                "content of the message was not modified" in error_msg
                or "editmessagerequest" in error_msg
            ):
                # Message content is the same, just answer the callback
                try:
                    await event.answer("✅ Updated")
                except BaseException:
                    pass
                return True
            logger.error(f"Error routing callback {data}: {e}")
            await event.answer("❌ Error processing request")
            return False

    def register_handler(self, callback_type: str, handler: Callable):
        """Register a new callback handler"""
        self.routes[callback_type] = handler
        logger.info(f"Registered handler for callback type: {callback_type}")

    def get_registered_types(self) -> list:
        """Get list of registered callback types"""
        return list(self.routes.keys())

    async def handle_menu_callback(self, event, user_id: int, data: str):
        """Handle menu navigation callbacks"""
        try:
            parts = data.split(":")
            if len(parts) < 2:
                await event.answer("❌ Invalid menu callback")
                return

            menu_type = parts[1]

            # Route to appropriate menu handler
            if menu_type == "accounts":
                await self.menu.handlers.handle_account_settings(event)
            elif menu_type == "otp":
                await self.menu.handlers.handle_otp_manager(event)
            elif menu_type == "messaging":
                await self.menu.handlers.handle_messaging(event)
            elif menu_type == "channels":
                await self.menu.handlers.handle_channels(event)
            elif menu_type == "contacts":
                await self.menu._handle_contacts(event)
            elif menu_type == "cleanup":
                await self.menu.handlers.handle_cleanup(event)
            elif menu_type == "import":
                await self.handle_session_import_callback(event, user_id, "import_sessions")
            elif menu_type == "main":
                # Send main menu instead of calling non-existent handle_start
                await self.menu.send_main_menu(user_id)
                await event.answer("🏠 Main menu")
            else:
                await event.answer(f"❌ Unknown menu: {menu_type}")

        except Exception as e:
            logger.error(f"Menu callback error: {e}")
            await event.answer("❌ Error processing menu request")

    async def handle_create_callback(self, event, user_id: int, data: str):
        """Handle create session callbacks"""
        await event.answer("✅ Creating session...")

    async def handle_import_callback(self, event, user_id: int, data: str):
        """Handle import session callbacks"""
        await event.answer("✅ Importing session...")

    async def handle_export_callback(self, event, user_id: int, data: str):
        """Handle export session callbacks"""
        await event.answer("✅ Exporting session...")

    async def handle_toggle_session_callback(self, event, user_id: int, data: str):
        """Handle toggle session selection callbacks"""
        try:
            parts = data.split(":")
            if len(parts) < 2:
                await event.answer("❌ Invalid selection")
                return

            account_name = ":".join(parts[1:])  # Handle account names with colons

            bot_manager = getattr(self.menu, "account_manager", None)
            if bot_manager and hasattr(bot_manager, "session_export_handler"):
                await bot_manager.session_export_handler._toggle_account_selection(
                    event, user_id, account_name
                )
            else:
                await event.answer("❌ Session export not available")

        except Exception as e:
            logger.error(f"Toggle session callback error: {e}")
            await event.answer("❌ Error toggling selection")

    async def handle_create_selected_sessions_callback(
        self, event, user_id: int, data: str
    ):
        """Handle create selected sessions callback"""
        try:
            bot_manager = getattr(self.menu, "account_manager", None)
            if bot_manager and hasattr(bot_manager, "session_export_handler"):
                await bot_manager.session_export_handler._create_selected_sessions(
                    event, user_id
                )
            else:
                await event.answer("❌ Session export not available")

        except Exception as e:
            logger.error(f"Create selected sessions callback error: {e}")
            await event.answer("❌ Error creating sessions")

    async def handle_toggle_all_sessions_callback(self, event, user_id: int, data: str):
        """Handle toggle all sessions callback"""
        try:
            bot_manager = getattr(self.menu, "account_manager", None)
            if bot_manager and hasattr(bot_manager, "session_export_handler"):
                await bot_manager.session_export_handler._toggle_all_sessions(
                    event, user_id
                )
            else:
                await event.answer("❌ Session export not available")
        except Exception as e:
            logger.error(f"Toggle all sessions callback error: {e}")
            await event.answer("❌ Error toggling all")

    async def handle_session_type_callback(self, event, user_id: int, data: str):
        """Handle session type selection callback"""
        try:
            parts = data.split(":")
            if len(parts) < 2:
                await event.answer("❌ Invalid session type")
                return

            session_type = parts[1]
            bot_manager = getattr(self.menu, "account_manager", None)
            if not bot_manager:
                logger.error("account_manager not found on menu")
                await event.answer("❌ Session export not available")
                return
            if not hasattr(bot_manager, "session_export_handler"):
                logger.error("session_export_handler not found on account_manager")
                await event.answer("❌ Session export not available")
                return
            await bot_manager.session_export_handler._show_account_selection(
                event, user_id, session_type
            )
        except Exception as e:
            logger.error(f"Session type callback error: {e}", exc_info=True)
            await event.answer("❌ Error selecting type")

    async def handle_cleanup_callback(self, event, user_id: int, data: str):
        """Handle cleanup callbacks"""
        try:
            parts = data.split(":")
            if len(parts) < 2:
                await event.answer("❌ Invalid cleanup callback")
                return

            action = parts[1]

            if action == "menu":
                await self.menu.handlers.handle_cleanup(event)

            elif action == "select" and len(parts) >= 3:
                account_id = parts[2]
                if hasattr(self.menu, "cleanup_operations"):
                    await self.menu.cleanup_operations.send_cleanup_selection(
                        user_id, event.message_id, account_id
                    )
                else:
                    await event.answer("❌ Cleanup not available")

            elif action == "bulk_all":
                if hasattr(self.menu, "cleanup_operations"):
                    await self.menu.cleanup_operations.send_bulk_cleanup_selection(
                        user_id, event.message_id
                    )
                else:
                    await event.answer("❌ Cleanup not available")

            elif action == "options" and len(parts) >= 4:
                # cleanup:options:{account_id}:{cleanup_types}
                account_id = parts[2]
                cleanup_types = ":".join(parts[3:])
                try:
                    await self.menu._send_cleanup_confirmation(
                        user_id, event.message_id, account_id, cleanup_types
                    )
                except Exception as e:
                    if "not modified" in str(e).lower():
                        await event.answer("✅ Already confirmed")
                    else:
                        logger.error(f"Cleanup options error: {e}")
                        await event.answer("❌ Error processing cleanup options")

            elif action == "confirm" and len(parts) >= 4:
                # cleanup:confirm:{account_id}:{cleanup_types}
                account_id = parts[2]
                cleanup_types = ":".join(parts[3:])
                await self.menu._execute_cleanup(event, user_id, account_id, cleanup_types)

            elif action == "appeal" and len(parts) >= 3:
                account_id = parts[2]
                await self.menu._handle_spam_appeal(event, user_id, account_id)

            elif action == "spam_appeal_select":
                await self.menu._handle_spam_appeal_select(event, user_id)

            else:
                await event.answer("❌ Unknown cleanup action")

        except Exception as e:
            logger.error(f"Cleanup callback error: {e}")
            await event.answer("❌ Error processing cleanup request")

    async def handle_session_login_callback(self, event, user_id: int, data: str):
        """Handle session login and creation callbacks"""
        try:
            # These callbacks are handled by session_login_handler
            # Just acknowledge them here
            await event.answer("✅ Processing...")

        except Exception as e:
            logger.error(f"Session login callback error: {e}")
            await event.answer("❌ Error processing request")

    async def handle_contacts_callback(self, event, user_id: int, data: str):
        """Handle contacts sub-callbacks (contact:, contacts:, sync:, group:, tag:, export_acc:)"""
        try:
            ch = getattr(self.menu.account_manager, "contact_handler", None)
            if ch is None:
                await event.answer("❌ Contact handler not available")
                return

            parts = data.split(":")
            prefix = parts[0]

            # contacts: prefix — main menu actions
            if prefix == "contacts":
                action = parts[1] if len(parts) > 1 else "main"
                if action == "list":
                    await ch._show_contacts_list(event, user_id)
                elif action == "add":
                    await ch._start_add_contact(event, user_id)
                elif action == "search":
                    await ch._start_search(event, user_id)
                elif action == "groups":
                    await ch._show_groups(event, user_id)
                elif action == "tags":
                    await ch._show_tags(event, user_id)
                elif action == "export":
                    await ch._export_contacts(event, user_id)
                elif action == "import":
                    await ch._start_import(event, user_id)
                elif action == "sync":
                    await ch._show_sync_menu(event, user_id)
                elif action == "main":
                    await ch._show_main_menu(event, user_id)
                else:
                    await event.answer("✅ Processing...")

            # contact: prefix — per-contact actions
            elif prefix == "contact":
                action = parts[1] if len(parts) > 1 else ""
                try:
                    contact_id = int(parts[2]) if len(parts) > 2 else 0
                except ValueError:
                    contact_id = 0
                dispatch = {
                    "view": ch._view_contact,
                    "edit": ch._edit_contact_menu,
                    "delete": ch._delete_contact,
                    "delete_confirm": ch._confirm_delete_contact,
                    "blacklist": ch._toggle_blacklist,
                    "whitelist": ch._toggle_whitelist,
                    "add_notes": ch._start_add_notes,
                    "add_tags": ch._start_add_tags,
                }
                handler = dispatch.get(action)
                if handler:
                    await handler(event, user_id, contact_id)
                else:
                    await event.answer("✅ Processing...")

            elif prefix == "sync":
                sync_type = parts[1] if len(parts) > 1 else "from_telegram"
                await ch._handle_sync(event, user_id, sync_type)

            elif prefix == "group":
                action = parts[1] if len(parts) > 1 else ""
                if action == "create":
                    await ch._start_create_group(event, user_id)
                elif action == "view":
                    group_name = ":".join(parts[2:]) if len(parts) > 2 else ""
                    await ch._view_group(event, user_id, group_name)
                else:
                    await event.answer("✅ Processing...")

            elif prefix == "tag":
                action = parts[1] if len(parts) > 1 else ""
                if action == "view":
                    tag = ":".join(parts[2:]) if len(parts) > 2 else ""
                    await ch._view_tag_contacts(event, user_id, tag)
                else:
                    await event.answer("✅ Processing...")

            elif prefix == "export_acc":
                try:
                    account_idx = int(parts[1]) if len(parts) > 1 else 0
                except ValueError:
                    account_idx = 0
                await ch._process_export(event, user_id, account_idx)

            else:
                await event.answer("✅ Processing...")

        except Exception as e:
            logger.error(f"Contacts callback error: {e}")
            await event.answer("❌ Error processing request")

    async def handle_spam_master_callback(self, event, user_id: int, data: str):
        """Handle spam master callbacks"""
        try:
            # Redirect to advanced spam handler menu
            if hasattr(self.menu.account_manager, "advanced_spam_handler"):
                await self.menu.account_manager.advanced_spam_handler._handle_spam_master_menu(
                    event
                )
            else:
                await event.answer("❌ SpamMaster not available", alert=True)
        except Exception as e:
            logger.error(f"Spam master callback error: {e}")
            await event.answer("❌ Error processing request")

    async def handle_manual_otp_callback(self, event, user_id: int, data: str):
        """Handle manual OTP entry callback"""
        try:
            parts = data.split(":")
            account_name = ":".join(parts[1:]) if len(parts) > 1 else "Unknown"

            await event.edit(
                f"📱 **Manual OTP Entry - {account_name}**\n\n"
                f"Please send the OTP code you received.\n"
                f"Format: Just the numbers (e.g., 12345)"
            )
        except Exception as e:
            logger.error(f"Manual OTP callback error: {e}")
            await event.answer("❌ Error")

    async def handle_resend_otp_callback(self, event, user_id: int, data: str):
        """Handle resend OTP callback"""
        try:
            await event.answer("🔄 Resending OTP...")
            await event.edit("🔄 **Resending OTP...**\n\nPlease wait...")
            # The actual resend logic would be in session_export_handler
        except Exception as e:
            logger.error(f"Resend OTP callback error: {e}")
            await event.answer("❌ Error")

    async def handle_cancel_session_callback(self, event, user_id: int, data: str):
        """Handle cancel session callback"""
        try:
            await event.edit("❌ **Session Creation Cancelled**")
            # Clean up any pending session data
            bot_manager = getattr(self.menu, "account_manager", None)
            if bot_manager and hasattr(bot_manager, "pending_fresh_sessions"):
                bot_manager.pending_fresh_sessions.pop(user_id, None)
        except Exception as e:
            logger.error(f"Cancel session callback error: {e}")
            await event.answer("❌ Error")

    async def handle_otp_setting_callback(self, event, user_id: int, data: str):
        """Handle OTP setting callbacks (destroyer, forward, temp)"""
        parts = data.split(":")
        setting_type = parts[1] if len(parts) > 1 else "destroyer"

        try:
            from telethon import Button

            from ...core.mongo_database import mongodb
            from ...utils.network_helpers import format_display_name

            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                await event.answer("❌ No accounts found")
                return

            if setting_type == "destroyer":
                text = "🛡️ **OTP Destroyer Settings**\n\nSelect account to toggle OTP Destroyer:"
                buttons = []
                for account in accounts:
                    status = "✅" if account.get("is_active", False) else "🔴"
                    destroyer_status = (
                        "🛡️" if account.get("otp_destroyer_enabled", False) else "❌"
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
                text = "📤 **OTP Forward Settings**\n\nSelect account to toggle OTP Forward:"
                buttons = []
                for account in accounts:
                    status = "✅" if account.get("is_active", False) else "🔴"
                    forward_status = (
                        "📤" if account.get("otp_forward_enabled", False) else "❌"
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
                    status = "✅" if account.get("is_active", False) else "🔴"
                    destroyer_status = (
                        "🛡️" if account.get("otp_destroyer_enabled", False) else "❌"
                    )
                    display_name = format_display_name(account)
                    button_text = f"{status}{destroyer_status} {display_name}"
                    buttons.append(
                        [Button.inline(button_text, f"otp:temp:{account['_id']}")]
                    )
            else:
                text = "🛡️ **OTP Settings**\n\nSelect account:"
                buttons = []
                for account in accounts:
                    status = "✅" if account.get("is_active", False) else "🔴"
                    display_name = format_display_name(account)
                    button_text = f"{status} {display_name}"
                    buttons.append(
                        [Button.inline(button_text, f"otp:manage:{account['_id']}")]
                    )

            buttons.append([Button.inline("🔙 Back to OTP Manager", "menu:otp")])
            await self.menu.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )

        except Exception as e:
            logger.error(f"OTP setting callback error: {e}")
            await event.answer("❌ Error processing OTP setting")

    async def handle_otp_pwd_callback(self, event, user_id: int, data: str):
        """Handle OTP password callbacks"""
        try:
            parts = data.split(":")
            action = parts[1] if len(parts) > 1 else "status"
            account_id = parts[2] if len(parts) > 2 else "0"

            if action == "set":
                if self.menu.account_manager:
                    self.menu.account_manager.pending_actions[user_id] = {
                        "action": "set_otp_disable_password",
                        "account_id": account_id,
                    }
                    await event.answer("🔒 Reply with password")
                    await self.menu.bot.send_message(
                        user_id,
                        "🔒 **Set Disable Password**\n\nReply with a password that will be required to disable OTP Destroyer.\n\n⚠️ Minimum 6 characters required.",
                    )
            elif action == "change":
                if self.menu.account_manager:
                    self.menu.account_manager.pending_actions[user_id] = {
                        "action": "change_otp_disable_password",
                        "account_id": account_id,
                    }
                    await event.answer("🔒 Reply with new password")
                    await self.menu.bot.send_message(
                        user_id,
                        "🔒 **Change Disable Password**\n\nReply with the new password.",
                    )
            elif action == "remove":
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$unset": {"otp_destroyer_disable_auth": ""}},
                )
                await event.answer("✅ Password removed")
                await self.menu.send_otp_account_management(
                    user_id, account_id, event.message_id
                )
            elif action == "status":
                account = await mongodb.db.accounts.find_one(
                    {"_id": ObjectId(account_id)}
                )
                has_pwd = (
                    "✅ Set"
                    if account and account.get("otp_destroyer_disable_auth")
                    else "❌ Not Set"
                )
                await event.answer(f"Password Status: {has_pwd}")
        except Exception as e:
            logger.error(f"OTP password callback error: {e}")
            await event.answer("❌ Error processing password request")

    async def handle_messaging_callback(self, event, user_id: int, data: str):
        """Handle messaging callbacks"""
        try:
            parts = data.split(":")
            action = parts[1] if len(parts) > 1 else "main"

            if action == "send":
                if hasattr(self.menu, "messaging_operations"):
                    await self.menu.messaging_operations.send_message_menu(
                        user_id, event.message_id
                    )
                else:
                    await event.answer("❌ Messaging not available")
            elif action == "compose":
                account_id = parts[2] if len(parts) > 2 else None
                if account_id and self.menu.account_manager:
                    self.menu.account_manager.pending_actions[user_id] = {
                        "action": "compose_message_target",
                        "account_id": account_id,
                    }
                    await event.answer("📝 Reply with target")
                    await self.menu.bot.send_message(
                        user_id,
                        "📝 **Compose Message**\n\nReply with the target (username, phone, or chat ID):\n\nExamples:\n• @username\n• +1234567890\n• -1001234567890 (for groups/channels)",
                    )
                else:
                    await event.answer("❌ Invalid account")
            elif action == "bulk":
                if hasattr(self.menu, "messaging_operations"):
                    await self.menu.messaging_operations.send_bulk_sender_menu(
                        user_id, event.message_id
                    )
                else:
                    await event.answer("❌ Bulk messaging not available")
            elif action == "templates":
                await self.handle_template_callback(event, user_id, "template:main")
            elif action in ("stats", "analytics"):
                await self.menu._show_messaging_statistics(user_id, event.message_id)
            elif action == "history":
                await self.menu._show_message_history(user_id, event.message_id)
            elif action == "settings":
                await self.menu._show_messaging_settings(user_id, event.message_id)
            elif action == "autoreply":
                await self.handle_auto_reply_callback(event, user_id, "auto_reply:main")
            elif action == "dm":
                await self.handle_dm_reply_callback(event, user_id, "dm_reply:main")
            else:
                await event.answer("❌ Unknown messaging action")
        except Exception as e:
            logger.error(f"Messaging callback error: {e}")
            await event.answer("❌ Error processing messaging request")

    async def handle_auto_reply_callback(self, event, user_id: int, data: str):
        """Handle auto-reply callbacks"""
        try:
            from telethon import Button
            parts = data.split(":")
            action = parts[1] if len(parts) > 1 else "main"

            if action == "main":
                if hasattr(self.menu, "messaging_operations"):
                    await self.menu.messaging_operations.send_autoreply_menu(
                        user_id, event.message_id
                    )
                else:
                    await event.answer("❌ Auto-reply not available")

            elif action == "toggle":
                # Show per-account toggle list
                accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
                if not accounts:
                    await event.answer("❌ No accounts found")
                    return
                text = "🤖 **Auto-Reply — Toggle Per Account**\n\nTap an account to toggle:"
                buttons = []
                for acc in accounts:
                    enabled = acc.get("auto_reply_enabled", False)
                    status = "✅" if enabled else "❌"
                    from ...utils.network_helpers import format_display_name
                    name = format_display_name(acc)
                    buttons.append([Button.inline(
                        f"{status} {name}",
                        f"auto_reply:toggle_acc:{acc['_id']}"
                    )])
                buttons.append([Button.inline("🔙 Back", "auto_reply:main")])
                await self.menu.bot.edit_message(user_id, event.message_id, text, buttons=buttons)

            elif action == "toggle_acc":
                account_id = parts[2] if len(parts) > 2 else None
                if not account_id:
                    await event.answer("❌ Invalid account")
                    return
                from bson import ObjectId
                acc = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
                if not acc:
                    await event.answer("❌ Account not found")
                    return
                new_val = not acc.get("auto_reply_enabled", False)
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {"auto_reply_enabled": new_val}}
                )
                # Register/unregister handler if auto_reply_handler available
                am = self.menu.account_manager
                if hasattr(am, "auto_reply_handler"):
                    try:
                        am.auto_reply_handler.setup_auto_reply_handlers()
                    except Exception:
                        pass
                status = "enabled" if new_val else "disabled"
                await event.answer(f"{'✅' if new_val else '❌'} Auto-reply {status}!")
                # Refresh toggle list
                await self.handle_auto_reply_callback(event, user_id, "auto_reply:toggle")

            elif action == "keyword_settings":
                settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
                enabled = settings.get("keyword_replies_enabled", False)
                keywords = settings.get("keywords", [])
                kw_list = "\n".join(f"• `{k['trigger']}` → {k['response'][:40]}" for k in keywords[:10]) or "No keywords set."
                text = (
                    f"🔑 **Keyword Auto-Reply**\n\n"
                    f"Status: {'🟢 Enabled' if enabled else '🔴 Disabled'}\n\n"
                    f"**Keywords ({len(keywords)}):**\n{kw_list}\n\n"
                    "Use /autoreply_add to add keywords via command."
                )
                toggle_label = "🔴 Disable" if enabled else "🟢 Enable"
                buttons = [
                    [Button.inline(toggle_label, "auto_reply:toggle_keyword")],
                    [Button.inline("🔙 Back", "auto_reply:main")],
                ]
                await self.menu.bot.edit_message(user_id, event.message_id, text, buttons=buttons)

            elif action == "toggle_keyword":
                settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
                new_val = not settings.get("keyword_replies_enabled", False)
                await mongodb.db.auto_reply_settings.update_one(
                    {"user_id": user_id},
                    {"$set": {"keyword_replies_enabled": new_val}},
                    upsert=True
                )
                await event.answer(f"{'🟢 Keyword replies enabled' if new_val else '🔴 Keyword replies disabled'}")
                await self.handle_auto_reply_callback(event, user_id, "auto_reply:keyword_settings")

            elif action == "time_settings":
                settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
                enabled = settings.get("time_based_replies_enabled", False)
                start_h = settings.get("active_start_hour", 9)
                end_h = settings.get("active_end_hour", 22)
                text = (
                    f"⏰ **Time-Based Auto-Reply**\n\n"
                    f"Status: {'🟢 Enabled' if enabled else '🔴 Disabled'}\n"
                    f"Active Hours: {start_h:02d}:00 – {end_h:02d}:00\n\n"
                    "Auto-reply only fires during the configured hours.\n"
                    "Use /autoreply_hours to change the schedule."
                )
                toggle_label = "🔴 Disable" if enabled else "🟢 Enable"
                buttons = [
                    [Button.inline(toggle_label, "auto_reply:toggle_time")],
                    [Button.inline("🔙 Back", "auto_reply:main")],
                ]
                await self.menu.bot.edit_message(user_id, event.message_id, text, buttons=buttons)

            elif action == "toggle_time":
                settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
                new_val = not settings.get("time_based_replies_enabled", False)
                await mongodb.db.auto_reply_settings.update_one(
                    {"user_id": user_id},
                    {"$set": {"time_based_replies_enabled": new_val}},
                    upsert=True
                )
                await event.answer(f"{'🟢 Time-based replies enabled' if new_val else '🔴 Time-based replies disabled'}")
                await self.handle_auto_reply_callback(event, user_id, "auto_reply:time_settings")

            elif action == "analytics":
                # Reuse the messaging stats view
                await self.menu._show_messaging_statistics(user_id, event.message_id)

            elif action == "reset":
                text = (
                    "⚠️ **Reset Auto-Reply Settings**\n\n"
                    "This will disable auto-reply on all accounts and clear all keyword rules.\n\n"
                    "Are you sure?"
                )
                buttons = [
                    [Button.inline("✅ Yes, Reset All", "auto_reply:confirm_reset")],
                    [Button.inline("❌ Cancel", "auto_reply:main")],
                ]
                await self.menu.bot.edit_message(user_id, event.message_id, text, buttons=buttons)

            elif action == "confirm_reset":
                await mongodb.db.accounts.update_many(
                    {"user_id": user_id},
                    {"$set": {"auto_reply_enabled": False}}
                )
                await mongodb.db.auto_reply_settings.delete_one({"user_id": user_id})
                await event.answer("✅ Auto-reply settings reset!")
                await self.handle_auto_reply_callback(event, user_id, "auto_reply:main")

            else:
                await event.answer("✅ Processing...")
        except Exception as e:
            logger.error(f"Auto-reply callback error: {e}")
            await event.answer("❌ Error processing auto-reply")

    async def handle_dm_reply_callback(self, event, user_id: int, data: str):
        """Handle DM reply callbacks"""
        try:
            from telethon import Button

            from ...core.mongo_database import mongodb

            parts = data.split(":")
            action = parts[1] if len(parts) > 1 else "main"

            if action == "main":
                accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                    None
                )
                if not accounts:
                    text = "📨 **Unified DM Manager**\n\n❌ No accounts found. Add accounts first."
                    buttons = [[Button.inline("🔙 Back", "menu:messaging")]]
                else:
                    user = await mongodb.db.users.find_one({"telegram_id": user_id})
                    dm_group = user.get("dm_reply_group_id") if user else None
                    status = "✅ Active" if dm_group else "❌ Not Setup"
                    text = f"📨 **Unified DM Manager**\n\n📊 Manage all your DMs in one place\n\n📝 **Features:**\n• Centralized inbox for all accounts\n• Forum-based organization\n• Quick reply system\n• Message filtering\n\n📱 Accounts: {
                        len(accounts)}\n🔧 Status: {status}"
                    buttons = [
                        [Button.inline("⚙️ Setup DM Manager", "dm_reply:setup")],
                        [Button.inline("📊 View Status", "dm_reply:status")],
                    ]
                    if dm_group:
                        buttons.append([Button.inline("🗑️ Remove DM Manager", "dm_reply:remove")])
                    buttons.append([Button.inline("🔙 Back", "menu:messaging")])
                await self.menu.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )
            elif action == "setup":
                user = await mongodb.db.users.find_one({"telegram_id": user_id})
                dm_group = user.get("dm_reply_group_id") if user else None
                if dm_group:
                    text = f"⚙️ **DM Manager Setup**\n\n✅ Already configured!\n\n📱 Admin Group ID: `{dm_group}`\n\nTo change, use /dm_reply command."
                else:
                    text = "⚙️ **DM Manager Setup**\n\n📋 **Steps:**\n1. Create a new group\n2. Enable Topics in group settings\n3. Add this bot to the group\n4. Use /dm_reply command to link the group\n\n💡 All DMs will be forwarded to topics in that group."
                buttons = [[Button.inline("🔙 Back", "dm_reply:main")]]
                await self.menu.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )
            elif action == "status":
                user = await mongodb.db.users.find_one({"telegram_id": user_id})
                dm_group = user.get("dm_reply_group_id") if user else None
                accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                    None
                )
                topic_count = (
                    await mongodb.db.dm_topics.count_documents({"group_id": dm_group})
                    if dm_group
                    else 0
                )
                if dm_group:
                    text = f"📊 **DM Manager Status**\n\n✅ **Active**\n\n📱 Accounts: {
                        len(accounts)}\n💬 Active Topics: {topic_count}\n🔗 Admin Group: `{dm_group}`\n\n✨ All DMs are being forwarded to your admin group."
                else:
                    text = f"📊 **DM Manager Status**\n\n❌ **Not Setup**\n\n📱 Accounts: {
                        len(accounts)}\n\n⚠️ DM forwarding is not active. Use Setup to configure."
                buttons = [[Button.inline("🔙 Back", "dm_reply:main")]]
                await self.menu.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )
            elif action == "remove":
                user = await mongodb.db.users.find_one({"telegram_id": user_id})
                dm_group = user.get("dm_reply_group_id") if user else None
                if dm_group:
                    # Remove DM group from user
                    await mongodb.db.users.update_one(
                        {"telegram_id": user_id},
                        {"$unset": {"dm_reply_group_id": ""}}
                    )
                    # Remove DM group from all accounts
                    await mongodb.db.accounts.update_many(
                        {"user_id": user_id},
                        {"$unset": {"dm_reply_group_id": ""}}
                    )
                    # Delete all topic mappings for this group
                    await mongodb.db.topic_mappings.delete_many(
                        {"admin_group_id": dm_group}
                    )
                    text = "✅ **DM Manager Removed**\n\n🗑️ Successfully removed DM Manager configuration\n\n📝 **What was removed:**\n• Admin group link\n• All topic mappings\n• Account DM forwarding settings\n\n💡 You can set it up again anytime using Setup button."
                    await event.answer("✅ DM Manager removed")
                else:
                    text = "❌ **Not Configured**\n\nDM Manager is not currently set up.\n\nUse Setup to configure it."
                    await event.answer("❌ Not configured")
                buttons = [[Button.inline("🔙 Back", "dm_reply:main")]]
                await self.menu.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )
            else:
                await event.answer("✅ Processing...")
        except Exception as e:
            logger.error(f"DM reply callback error: {e}")
            await event.answer("❌ Error processing DM reply")

    async def handle_template_callback(self, event, user_id: int, data: str):
        """Handle template callbacks"""
        try:
            from telethon import Button

            from ...core.mongo_database import mongodb

            parts = data.split(":")
            action = parts[1] if len(parts) > 1 else "main"

            if action == "main":
                templates = await mongodb.db.message_templates.find(
                    {"user_id": user_id}
                ).to_list(None)
                text = f"📝 **Message Templates**\n\n✨ Saved templates: {
                    len(templates)}\n\n🔹 **Features:**\n• Dynamic variables ({{name}}, {{username}})\n• Rich media support\n• Template categories\n• Quick reply buttons"
                buttons = [
                    [Button.inline("🆕 Create Template", "template:create")],
                    [Button.inline("📚 View Templates", "template:list")],
                    [Button.inline("🔙 Back", "menu:messaging")],
                ]
                await self.menu.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )
            elif action == "create":
                if self.menu.account_manager:
                    self.menu.account_manager.pending_actions[user_id] = {
                        "action": "template_create_name"
                    }
                text = "🆕 **Create Template**\n\n📝 Reply with template name:\n\nExample: Welcome Message"
                buttons = [[Button.inline("🔙 Back", "template:main")]]
                await self.menu.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )
                await event.answer("📝 Reply with name")
            elif action == "list":
                templates = await mongodb.db.message_templates.find(
                    {"user_id": user_id}
                ).to_list(None)
                if not templates:
                    text = "📚 **Your Templates**\n\n❌ No templates found.\n\nCreate your first template!"
                    buttons = [
                        [Button.inline("🆕 Create Template", "template:create")],
                        [Button.inline("🔙 Back", "template:main")],
                    ]
                else:
                    text = f"📚 **Your Templates** ({len(templates)})\n\n"
                    buttons = []
                    for tmpl in templates[:10]:
                        name = tmpl.get("name", "Unnamed")
                        buttons.append(
                            [
                                Button.inline(
                                    f"📄 {name}", f"template:view:{tmpl['_id']}"
                                )
                            ]
                        )
                    buttons.append([Button.inline("🔙 Back", "template:main")])
                await self.menu.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )
                await event.answer("📚 Templates loaded")
        except Exception as e:
            logger.error(f"Template callback error: {e}")
            await event.answer("❌ Error processing template")

    async def handle_bulk_callback(self, event, user_id: int, data: str):
        """Handle bulk messaging callbacks"""
        try:
            parts = data.split(":")
            action = parts[1] if len(parts) > 1 else "main"

            if hasattr(self.menu, "messaging_operations"):
                if action == "send_list":
                    await self.menu.messaging_operations.start_bulk_list_flow(
                        user_id, event
                    )
                elif action == "send_contacts":
                    await self.menu.messaging_operations.start_bulk_contacts_flow(
                        user_id, event
                    )
                elif action == "send_all":
                    await self.menu.messaging_operations.start_bulk_all_flow(
                        user_id, event
                    )
                elif action == "jobs":
                    await self.menu.messaging_operations.show_bulk_jobs(
                        user_id, event.message_id
                    )
                elif action == "help":
                    await self.menu.messaging_operations.show_bulk_help(
                        user_id, event.message_id
                    )
                else:
                    await event.answer("❌ Unknown bulk action")
            else:
                await event.answer("❌ Bulk messaging not available")
        except Exception as e:
            logger.error(f"Bulk callback error: {e}")
            await event.answer("❌ Error processing bulk request")

    async def handle_bulk_list_account_callback(self, event, user_id: int, data: str):
        """Handle bulk list account selection"""
        try:
            parts = data.split(":")
            account_id = parts[1] if len(parts) > 1 else None
            if account_id and self.menu.account_manager:
                self.menu.account_manager.pending_actions[user_id] = {
                    "action": "bulk_list_targets",
                    "account_id": account_id,
                }
                await event.answer("📝 Reply with targets")
                await self.menu.bot.send_message(
                    user_id,
                    "📝 **Bulk Send to List**\n\nStep 2: Reply with target usernames/IDs (comma-separated):\n\nExamples:\n• @user1,@user2,@user3\n• +1234567890,@username,123456789",
                )
            else:
                await event.answer("❌ Invalid account")
        except Exception as e:
            logger.error(f"Bulk list account callback error: {e}")
            await event.answer("❌ Error")

    async def handle_bulk_contacts_account_callback(
        self, event, user_id: int, data: str
    ):
        """Handle bulk contacts account selection"""
        try:
            parts = data.split(":")
            account_id = parts[1] if len(parts) > 1 else None
            if account_id and self.menu.account_manager:
                self.menu.account_manager.pending_actions[user_id] = {
                    "action": "bulk_contacts_message",
                    "account_id": account_id,
                }
                await event.answer("📝 Reply with message")
                await self.menu.bot.send_message(
                    user_id,
                    "📝 **Bulk Send to Contacts**\n\nStep 2: Reply with the message to send to all contacts.",
                )
            else:
                await event.answer("❌ Invalid account")
        except Exception as e:
            logger.error(f"Bulk contacts account callback error: {e}")
            await event.answer("❌ Error")

    async def handle_channel_callback(self, event, user_id: int, data: str):
        """Handle channel management callbacks"""
        try:
            from telethon import Button
            from ...utils.network_helpers import format_display_name

            parts = data.split(":")
            action = parts[1] if len(parts) > 1 else "main"
            account_phone = parts[2] if len(parts) > 2 else None

            if action == "select" and account_phone:
                # Show per-account channel operations menu
                text = (
                    f"📢 **Channel Management**\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📱 Account: `{account_phone}`\n\n"
                    "Choose an operation:"
                )
                buttons = [
                    [
                        Button.inline("🔗 Join Channel", f"channel:join:{account_phone}"),
                        Button.inline("🚪 Leave Channel", f"channel:leave:{account_phone}"),
                    ],
                    [
                        Button.inline("🆕 Create Channel", f"channel:create:{account_phone}"),
                        Button.inline("🗑️ Delete Channel", f"channel:delete:{account_phone}"),
                    ],
                    [Button.inline("📋 List Channels", f"channel:list:{account_phone}")],
                    [Button.inline("🔙 Back", "menu:channels")],
                ]
                await self.menu.bot.edit_message(user_id, event.message_id, text, buttons=buttons)

            elif action == "stats":
                # Aggregate channel stats across all accounts
                accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
                total_accounts = len(accounts)
                active = sum(1 for a in accounts if a.get("is_active"))
                text = (
                    "📊 **Channel Statistics**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📱 Accounts: {active}/{total_accounts} active\n\n"
                    "💡 Select an account from the Channel Hub to view its channel list."
                )
                buttons = [[Button.inline("🔙 Back", "menu:channels")]]
                await self.menu.bot.edit_message(user_id, event.message_id, text, buttons=buttons)

            elif action == "search":
                text = (
                    "🔍 **Channel Discovery**\n\n"
                    "To search for channels, use the Join Channel option and enter:\n"
                    "• A channel username: `@channelname`\n"
                    "• A t.me link: `https://t.me/channelname`\n"
                    "• An invite link: `https://t.me/+xxxxx`"
                )
                buttons = [[Button.inline("🔙 Back", "menu:channels")]]
                await self.menu.bot.edit_message(user_id, event.message_id, text, buttons=buttons)

            elif action == "join" and account_phone:
                if self.menu.account_manager:
                    self.menu.account_manager.pending_actions[user_id] = {
                        "action": "channel_join_target",
                        "account_phone": account_phone,
                    }
                await event.answer("🔗 Reply with channel link")
                try:
                    await self.menu.bot.edit_message(
                        user_id, event.message_id,
                        f"🔗 **Join Channel**\n\n📱 Account: `{account_phone}`\n\n"
                        "Reply with the channel link or username:\n\n"
                        "• `@channelname`\n"
                        "• `https://t.me/channelname`\n"
                        "• `https://t.me/+invitehash`",
                        buttons=[[Button.inline("❌ Cancel", f"channel:select:{account_phone}")]]
                    )
                except Exception:
                    pass

            elif action == "leave" and account_phone:
                if self.menu.account_manager:
                    self.menu.account_manager.pending_actions[user_id] = {
                        "action": "channel_leave_target",
                        "account_phone": account_phone,
                    }
                await event.answer("🚪 Reply with channel")
                try:
                    await self.menu.bot.edit_message(
                        user_id, event.message_id,
                        f"🚪 **Leave Channel**\n\n📱 Account: `{account_phone}`\n\n"
                        "Reply with the channel username or link:\n\n"
                        "• `@channelname`\n"
                        "• `https://t.me/channelname`\n"
                        "• A number (1, 2, 3…) from your channel list",
                        buttons=[[Button.inline("❌ Cancel", f"channel:select:{account_phone}")]]
                    )
                except Exception:
                    pass

            elif action == "create" and account_phone:
                if self.menu.account_manager:
                    self.menu.account_manager.pending_actions[user_id] = {
                        "action": "channel_create_type",
                        "account_phone": account_phone,
                    }
                await event.answer("🆕 Reply with type")
                try:
                    await self.menu.bot.edit_message(
                        user_id, event.message_id,
                        f"🆕 **Create Channel/Group**\n\n📱 Account: `{account_phone}`\n\n"
                        "Reply with the type:\n• `channel` — broadcast channel\n• `group` — supergroup",
                        buttons=[[Button.inline("❌ Cancel", f"channel:select:{account_phone}")]]
                    )
                except Exception:
                    pass

            elif action == "delete" and account_phone:
                if self.menu.account_manager:
                    self.menu.account_manager.pending_actions[user_id] = {
                        "action": "channel_delete_target",
                        "account_phone": account_phone,
                    }
                await event.answer("🗑️ Reply with channel")
                try:
                    await self.menu.bot.edit_message(
                        user_id, event.message_id,
                        f"🗑️ **Delete Channel**\n\n📱 Account: `{account_phone}`\n\n"
                        "⚠️ Reply with the channel username to delete:\n\n"
                        "• `@channelname`\n"
                        "• A number from your channel list\n\n"
                        "🚨 **This action is permanent and cannot be undone!**",
                        buttons=[[Button.inline("❌ Cancel", f"channel:select:{account_phone}")]]
                    )
                except Exception:
                    pass

            elif action == "list" and account_phone:
                await event.answer("📋 Loading channels…")
                try:
                    am = self.menu.account_manager
                    channel_manager = getattr(am, "channel_manager", None)
                    if channel_manager:
                        success, channels = await channel_manager.get_user_channels(user_id, account_phone)
                    else:
                        # Fallback: get client directly
                        client = None
                        for name, c in am.user_clients.get(user_id, {}).items():
                            if c and c.is_connected():
                                try:
                                    me = await c.get_me()
                                    if me and (me.phone == account_phone.lstrip("+") or
                                               f"+{me.phone}" == account_phone or
                                               name == account_phone):
                                        client = c
                                        break
                                except Exception:
                                    pass
                        if client:
                            dialogs = await client.get_dialogs(limit=200)
                            channels = [
                                {
                                    "title": d.entity.title,
                                    "username": getattr(d.entity, "username", None),
                                    "type": "channel" if getattr(d.entity, "broadcast", False) else "group",
                                    "id": d.entity.id,
                                }
                                for d in dialogs
                                if hasattr(d.entity, "broadcast") or hasattr(d.entity, "megagroup")
                            ]
                            success = True
                        else:
                            success, channels = False, []

                    if success and channels:
                        text = (
                            f"📋 **Channels & Groups — `{account_phone}`**\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"📊 Total: {len(channels)}\n\n"
                        )
                        ch_lines = []
                        for i, ch in enumerate(channels[:30], 1):
                            t = "📢" if ch.get("type") == "channel" else "👥"
                            uname = f" @{ch['username']}" if ch.get("username") else ""
                            ch_lines.append(f"{i}. {t} **{ch['title']}**{uname}")
                        text += "\n".join(ch_lines)
                        if len(channels) > 30:
                            text += f"\n\n_…and {len(channels) - 30} more_"
                    elif success:
                        text = f"📋 **Channels — `{account_phone}`**\n\n💭 No channels or groups found."
                    else:
                        text = f"📋 **Channels — `{account_phone}`**\n\n❌ Could not load channels. Make sure the account is connected."

                    buttons = [
                        [Button.inline("🔄 Refresh", f"channel:list:{account_phone}")],
                        [Button.inline("🔙 Back", f"channel:select:{account_phone}")],
                    ]
                    await self.menu.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                except Exception as list_err:
                    logger.error(f"Channel list error: {list_err}")
                    await self.menu.bot.edit_message(
                        user_id, event.message_id,
                        f"❌ Error loading channel list: {list_err}",
                        buttons=[[Button.inline("🔙 Back", f"channel:select:{account_phone}")]]
                    )

            else:
                await event.answer("❌ Unknown channel action")
        except Exception as e:
            logger.error(f"Channel callback error: {e}")
            await event.answer("❌ Error processing channel request")

    async def handle_help_callback(self, event, user_id: int, data: str):
        """Handle help callbacks"""
        try:
            from telethon import Button

            if hasattr(self.menu, "help_callbacks"):
                await self.menu.help_callbacks.handle_callback(event, user_id, data)
            else:
                text = "❓ **Help & Support**\n\n📚 **Quick Links:**\n• /start - Main menu\n• /help - Full help guide\n• /accs - Manage accounts\n• /otp - OTP protection\n\n💬 Need more help? Contact support!"
                buttons = [
                    [Button.inline("📖 Full Guide", "help:guide")],
                    [Button.inline("💬 Contact Support", "support:main")],
                    [Button.inline("🔙 Back", "menu:main")],
                ]
                await self.menu.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )
                await event.answer("❓ Help")
        except Exception as e:
            logger.error(f"Help callback error: {e}")
            await event.answer("❌ Error")

    async def handle_support_callback(self, event, user_id: int, data: str):
        """Handle support callbacks"""
        try:
            from telethon import Button

            if hasattr(self.menu, "help_callbacks"):
                await self.menu.help_callbacks.handle_support_callback(
                    event, user_id, data
                )
            else:
                text = "💬 **Support & Contact**\n\n📧 **Get Help:**\n• Telegram: @ContactXYZrobot\n• Response time: 12-24 hours\n\n🐛 **Report Issues:**\n• Bug reports welcome\n• Feature requests accepted\n\n⚡ **Priority Support:**\n• Critical issues: 1-2 hours\n• General queries: 24-48 hours"
                buttons = [[Button.inline("🔙 Back", "help:main")]]
                await self.menu.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )
                await event.answer("💬 Support")
        except Exception as e:
            logger.error(f"Support callback error: {e}")
            await event.answer("❌ Error")

    async def handle_dev_callback(self, event, user_id: int, data: str):
        """Handle developer callbacks"""
        try:
            from telethon import Button

            if hasattr(self.menu, "help_callbacks"):
                await self.menu.help_callbacks.handle_developer_callback(
                    event, user_id, data
                )
            else:
                text = "👨‍💻 **Developer Info**\n\n**Created by:**\n• @Meher_Mankar - Lead Developer\n• @Gutkesh - Core Developer\n\n**Tech Stack:**\n• Python 3.9+\n• Telethon\n• MongoDB\n\n**Version:** 2.0.0\n**License:** MIT"
                buttons = [[Button.inline("🔙 Back", "help:main")]]
                await self.menu.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )
                await event.answer("👨‍💻 Developer info")
        except Exception as e:
            logger.error(f"Dev callback error: {e}")
            await event.answer("❌ Error")

    async def handle_appeal_callback(self, event, user_id: int, data: str):
        """Handle spam appeal callbacks"""
        try:
            parts = data.split(":")
            account_id = parts[1] if len(parts) > 1 else None
            if account_id:
                await event.answer("📝 Starting spam appeal...")
                # Delegate to spam appeal handler if available
                if hasattr(self.menu.account_manager, "spam_appeal_handler"):
                    await self.menu.account_manager.spam_appeal_handler.start_appeal(
                        user_id, account_id
                    )
                else:
                    await self.menu.bot.send_message(
                        user_id,
                        "📝 **Spam Appeal**\n\nManual steps:\n1. Go to @spambot\n2. Send /start\n3. Follow the appeal process",
                    )
            else:
                await event.answer("❌ Invalid account")
        except Exception as e:
            logger.error(f"Appeal callback error: {e}")
            await event.answer("❌ Error")

    async def handle_device_callback(self, event, user_id: int, data: str):
        """Handle device management callbacks"""
        try:
            from telethon import Button

            from ...core.mongo_database import mongodb

            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                None
            )
            text = f"📱 **Device Management**\n\n🔧 Manage device info for accounts\n\n📊 Accounts: {
                len(accounts)}\n\n⚙️ Features:\n• Custom device models\n• System version spoofing\n• App version control"
            buttons = [
                [Button.inline("📱 Select Account", "device:select")],
                [Button.inline("🔙 Back", "menu:accounts")],
            ]
            await self.menu.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
            await event.answer("📱 Device management")
        except Exception as e:
            logger.error(f"Device callback error: {e}")
            await event.answer("❌ Error")

    async def handle_back_callback(self, event, user_id: int, data: str):
        """Handle back button callbacks"""
        try:
            parts = data.split(":")
            destination = parts[1] if len(parts) > 1 else "main"
            if destination == "accounts":
                await self.menu.handlers.handle_account_settings(event)
            else:
                await self.menu.send_main_menu(user_id)
                await event.answer("🏠 Main menu")
        except Exception as e:
            logger.error(f"Back callback error: {e}")
            await event.answer("❌ Error")

    async def handle_manage_callback(self, event, user_id: int, data: str):
        """Handle manage callbacks"""
        try:
            parts = data.split(":")
            account_phone = parts[1] if len(parts) > 1 else None
            if account_phone:
                await self.handle_channel_callback(
                    event, user_id, f"channel:select:{account_phone}"
                )
            else:
                await event.answer("❌ Invalid account")
        except Exception as e:
            logger.error(f"Manage callback error: {e}")
            await event.answer("❌ Error")

    async def handle_export_session_callback(self, event, user_id: int, data: str):
        """Handle export session callbacks"""
        try:
            await event.answer("✅ Use session export feature")
        except Exception as e:
            logger.error(f"Export session callback error: {e}")
            await event.answer("❌ Error")

    async def handle_export_fresh_callback(self, event, user_id: int, data: str):
        """Handle export fresh session callbacks"""
        try:
            parts = data.split(":")
            account_name = parts[1] if len(parts) > 1 else None
            if account_name and hasattr(self.menu, "_handle_export_fresh_session"):
                await self.menu._handle_export_fresh_session(
                    event, user_id, account_name
                )
            else:
                await event.answer("✅ Processing...")
        except Exception as e:
            logger.error(f"Export fresh callback error: {e}")
            await event.answer("❌ Error")

    async def handle_export_string_callback(self, event, user_id: int, data: str):
        """Handle export string callbacks"""
        try:
            await event.answer("✅ Use session export feature")
        except Exception as e:
            logger.error(f"Export string callback error: {e}")
            await event.answer("❌ Error")

    async def handle_export_file_callback(self, event, user_id: int, data: str):
        """Handle export file callbacks"""
        try:
            await event.answer("✅ Use session export feature")
        except Exception as e:
            logger.error(f"Export file callback error: {e}")
            await event.answer("❌ Error")

    async def handle_export_contacts_callback(self, event, user_id: int, data: str):
        """Handle export contacts callbacks"""
        try:
            from telethon import Button

            from ...core.mongo_database import mongodb

            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                None
            )
            if not accounts:
                text = "👥 **Export Contacts**\n\n❌ No accounts found."
                buttons = [[Button.inline("🔙 Back", "menu:contacts")]]
            else:
                text = f"👥 **Export Contacts**\n\n📊 Select account to export contacts:\n\n📱 Available accounts: {
                    len(accounts)}"
                buttons = []
                for acc in accounts:
                    status = "✅" if acc.get("is_active") else "❌"
                    buttons.append(
                        [
                            Button.inline(
                                f"{status} {acc['name']}", f"export_acc:{acc['_id']}"
                            )
                        ]
                    )
                buttons.append([Button.inline("🔙 Back", "menu:contacts")])
            await self.menu.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
            await event.answer("👥 Export contacts")
        except Exception as e:
            logger.error(f"Export contacts callback error: {e}")
            await event.answer("❌ Error")
