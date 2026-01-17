# -*- coding: utf-8 -*-
"""Callback router for handling different callback types"""
import logging
from typing import Callable, Dict

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
            "accept_spam_warning": self.handle_spam_master_callback,
            "decline_spam_warning": self.handle_spam_master_callback,
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
        """Handle contacts callbacks"""
        try:
            # Contacts callbacks are handled by contact_handler
            # Just acknowledge them here
            await event.answer("✅ Processing...")
        except Exception as e:
            logger.error(f"Contacts callback error: {e}")
            await event.answer("❌ Error processing request")

    async def handle_spam_master_callback(self, event, user_id: int, data: str):
        """Handle spam master callbacks"""
        try:
            # Spam master callbacks are handled by advanced_spam_handler
            # Just acknowledge them here
            await event.answer("✅ Processing...")
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
                from bson import ObjectId

                await self.menu.account_manager.db_manager.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$unset": {"otp_destroyer_disable_auth": ""}},
                )
                await event.answer("✅ Password removed")
                await self.menu.send_otp_account_management(
                    user_id, account_id, event.message_id
                )
            elif action == "status":
                from bson import ObjectId

                account = await self.menu.account_manager.db_manager.accounts.find_one(
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
            elif action == "stats":
                await self.menu._show_messaging_statistics(user_id, event.message_id)
            elif action == "history":
                await self.menu._show_message_history(user_id, event.message_id)
            elif action == "settings":
                await self.menu._show_messaging_settings(user_id, event.message_id)
            else:
                await event.answer("❌ Unknown messaging action")
        except Exception as e:
            logger.error(f"Messaging callback error: {e}")
            await event.answer("❌ Error processing messaging request")

    async def handle_auto_reply_callback(self, event, user_id: int, data: str):
        """Handle auto-reply callbacks"""
        try:
            parts = data.split(":")
            action = parts[1] if len(parts) > 1 else "main"

            if action == "main":
                if hasattr(self.menu, "messaging_operations"):
                    await self.menu.messaging_operations.send_autoreply_menu(
                        user_id, event.message_id
                    )
                else:
                    await event.answer("❌ Auto-reply not available")
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

            parts = data.split(":")
            action = parts[1] if len(parts) > 1 else "main"
            account_phone = parts[2] if len(parts) > 2 else None

            if action == "select" and account_phone:
                text = f"📢 **Channel Management**\n\nAccount: {account_phone}\n\nSelect action:"
                buttons = [
                    [
                        Button.inline(
                            "🔗 Join Channel", f"channel:join:{account_phone}"
                        ),
                        Button.inline(
                            "🚪 Leave Channel", f"channel:leave:{account_phone}"
                        ),
                    ],
                    [
                        Button.inline(
                            "🆕 Create Channel", f"channel:create:{account_phone}"
                        ),
                        Button.inline(
                            "🗑️ Delete Channel", f"channel:delete:{account_phone}"
                        ),
                    ],
                    [
                        Button.inline(
                            "📋 List Channels", f"channel:list:{account_phone}"
                        )
                    ],
                    [Button.inline("🔙 Back to Accounts", "menu:channels")],
                ]
                await self.menu.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )
            elif action == "stats":
                text = "📊 **Channel Statistics**\n\nGlobal channel metrics:\n\n• Total channels joined\n• Active subscriptions\n• Recent activity\n• Engagement metrics\n\nFeature coming soon!"
                buttons = [[Button.inline("🔙 Back to Channels", "menu:channels")]]
                await self.menu.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )
            elif action == "search":
                text = "🔍 **Channel Discovery**\n\nChannel search feature coming soon!"
                buttons = [[Button.inline("🔙 Back to Channels", "menu:channels")]]
                await self.menu.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
                )
            elif action == "join" and account_phone:
                if self.menu.account_manager:
                    self.menu.account_manager.pending_actions[user_id] = {
                        "action": "channel_join",
                        "account_phone": account_phone,
                    }
                    await event.answer("🔗 Reply with channel link")
                    await self.menu.bot.send_message(
                        user_id,
                        f"🔗 **Join Channel - {account_phone}**\n\nReply with the channel link or username:\n\nExamples:\n• @channelname\n• https://t.me/channelname\n• t.me/joinchat/xxxxx",
                    )
            elif action == "leave" and account_phone:
                if self.menu.account_manager:
                    self.menu.account_manager.pending_actions[user_id] = {
                        "action": "channel_leave",
                        "account_phone": account_phone,
                    }
                    await event.answer("🚪 Reply with channel")
                    await self.menu.bot.send_message(
                        user_id,
                        f"🚪 **Leave Channel - {account_phone}**\n\nReply with the channel username or link to leave:\n\nExamples:\n• @channelname\n• https://t.me/channelname",
                    )
            elif action == "create" and account_phone:
                if self.menu.account_manager:
                    self.menu.account_manager.pending_actions[user_id] = {
                        "action": "channel_create",
                        "account_phone": account_phone,
                    }
                    await event.answer("🆕 Reply with channel name")
                    await self.menu.bot.send_message(
                        user_id,
                        f"🆕 **Create Channel - {account_phone}**\n\nReply with the channel name:\n\nExample: My Awesome Channel",
                    )
            elif action == "delete" and account_phone:
                if self.menu.account_manager:
                    self.menu.account_manager.pending_actions[user_id] = {
                        "action": "channel_delete",
                        "account_phone": account_phone,
                    }
                    await event.answer("🗑️ Reply with channel")
                    await self.menu.bot.send_message(
                        user_id,
                        f"🗑️ **Delete Channel - {account_phone}**\n\n⚠️ Reply with the channel username to delete:\n\nExample: @channelname\n\n🚨 This action cannot be undone!",
                    )
            elif action == "list" and account_phone:
                await event.answer("📋 Loading channels...")
                # Try to get actual channel list
                try:
                    client = None
                    for uid, clients in self.menu.account_manager.user_clients.items():
                        for name, c in clients.items():
                            if name == account_phone or (
                                hasattr(c, "get_me") and c.is_connected()
                            ):
                                me = await c.get_me()
                                if me.phone == account_phone:
                                    client = c
                                    break
                    if client:
                        pass

                        dialogs = await client.get_dialogs(limit=100)
                        channels = [d for d in dialogs if d.is_channel]
                        text = f"📋 **Channels - {account_phone}**\n\n📊 Total channels: {
                            len(channels)}\n\n"
                        for ch in channels[:10]:
                            text += f"• {ch.name}\n"
                        if len(channels) > 10:
                            text += f"\n... and {len(channels) - 10} more"
                    else:
                        text = f"📋 **Channels - {account_phone}**\n\n⚠️ Account not loaded. Use /channel_list for full details."
                except Exception:
                    text = f"📋 **Channels - {account_phone}**\n\n⚠️ Could not fetch channels. Use /channel_list command."
                buttons = [
                    [Button.inline("🔙 Back", f"channel:select:{account_phone}")]
                ]
                await self.menu.bot.edit_message(
                    user_id, event.message_id, text, buttons=buttons
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
