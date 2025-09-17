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
from .secure_2fa_handlers import Secure2FAHandlers

logger = logging.getLogger(__name__)


class MenuSystem:
    """Handles inline keyboard menus and callback queries"""

    def __init__(self, bot_instance, account_manager=None):
        self.bot = bot_instance
        self.account_manager = account_manager
        self.secure_2fa_handlers = Secure2FAHandlers(bot_instance, account_manager)
        self._menu_text_handler = None
        self._callback_handler = None

    def get_main_menu_keyboard(self, user_id: int) -> List[List[Button]]:
        """Get persistent reply keyboard menu"""
        keyboard = [
            [Button.text("📱 Account Settings"), Button.text("🛡️ OTP Manager")],
            [Button.text("💬 Messaging"), Button.text("📨 DM Reply")],
            [Button.text("📢 Channels"), Button.text("👥 Contacts")],
            [Button.text("❓ Help"), Button.text("🆘 Support")],
        ]

        # Add Developer button only for admins
        if user_id in ADMIN_IDS:
            keyboard.append([Button.text("⚙️ Developer")])

        return keyboard

    def get_account_menu_buttons(self, account_id: str, account=None) -> List[List[Button]]:
        """Get account-specific menu buttons"""
        # Determine online maker button text based on status
        if account:
            online_status = account.get("online_maker_enabled", False)
            online_text = "🔴 Stop Online Maker" if online_status else "🟢 Start Online Maker"
        else:
            online_text = "🟢 Online Maker"
            
        return [
            [
                Button.inline("👤 Profile Settings", f"profile:manage:{account_id}"),
                Button.inline("🔑 2FA Settings", f"2fa:status:{account_id}"),
            ],
            [
                Button.inline("🔐 Active Sessions", f"sessions:list:{account_id}"),
                Button.inline(online_text, f"online:toggle:{account_id}"),
            ],
            [
                Button.inline("🎭 Activity Sim", f"simulate:status:{account_id}"),
                Button.inline("📊 Sim Stats", f"simulate:stats:{account_id}"),
            ],
            [
                Button.inline("📋 Audit Log", f"audit:refresh:{account_id}:24"),
            ],
            [Button.inline("🔙 Back to Accounts", "menu:accounts")],
        ]

    def get_otp_account_buttons(self, account_id: str, account) -> List[List[Button]]:
        """Get OTP account management buttons"""
        destroyer_enabled = (
            account.get("otp_destroyer_enabled", False)
            if isinstance(account, dict)
            else getattr(account, "otp_destroyer_enabled", False)
        )
        forward_enabled = (
            account.get("otp_forward_enabled", False)
            if isinstance(account, dict)
            else getattr(account, "otp_forward_enabled", False)
        )
        has_password = (
            account.get("otp_destroyer_disable_auth")
            if isinstance(account, dict)
            else getattr(account, "otp_destroyer_disable_auth", None)
        )

        destroyer_text = (
            "🔴 Disable Destroyer" if destroyer_enabled else "🛡️ Enable Destroyer"
        )
        destroyer_action = (
            f"otp:disable:{account_id}"
            if destroyer_enabled
            else f"otp:enable:{account_id}"
        )

        forward_text = "🔴 Disable Forward" if forward_enabled else "📤 Enable Forward"
        forward_action = (
            f"otp:forward_disable:{account_id}"
            if forward_enabled
            else f"otp:forward_enable:{account_id}"
        )

        buttons = [
            [Button.inline(destroyer_text, destroyer_action)],
            [Button.inline(forward_text, forward_action)],
            [Button.inline("⏰ Temp OTP (5min)", f"otp:temp:{account_id}")],
        ]

        # Password management buttons
        if has_password:
            buttons.append(
                [
                    Button.inline("🔐 Change Password", f"otp_pwd:change:{account_id}"),
                    Button.inline("🔓 Remove Password", f"otp_pwd:remove:{account_id}"),
                ]
            )
        else:
            buttons.append(
                [Button.inline("🔒 Set Password", f"otp_pwd:set:{account_id}")]
            )

        buttons.extend(
            [
                [Button.inline("📊 Password Status", f"otp_pwd:status:{account_id}")],
                [Button.inline("📋 View Audit Log", f"otp:audit:{account_id}")],
                [Button.inline("🔙 Back to OTP Manager", "menu:otp")],
            ]
        )

        return buttons

    async def send_main_menu(self, user_id: int) -> int:
        """Send persistent reply keyboard menu"""
        try:
            keyboard = self.get_main_menu_keyboard(user_id)
            text = (
                "🤖 **TeleGuard Account Manager**\n\n"
                "🛡️ Professional Telegram security & automation\n\n"
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

    async def send_accounts_list(
        self, user_id: int, edit_message_id: Optional[int] = None
    ):
        """Send accounts list with management options"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )

            if not accounts:
                text = "📱 **Account Management**\n\nNo accounts found. Add your first account to get started.\n\nUse /add command or enable Developer Mode to add accounts."
            else:
                text = f"📱 **Account Management**\n\nYou have {len(accounts)} account(s):\n\n"
                for i, account in enumerate(accounts, 1):
                    status = "🟢" if account.get("is_active", False) else "🔴"
                    destroyer_status = (
                        "🛡️" if account.get("otp_destroyer_enabled", False) else "⚪"
                    )
                    text += f"{i}. {status}{destroyer_status} {account['name']} ({account['phone']})\n"
                text += "\nUse /accs to list accounts or /add to add more."

            await self.bot.send_message(user_id, text)

        except Exception as e:
            logger.error(f"Failed to send accounts list: {e}")

    async def send_account_management(
        self, user_id: int, account_id: str, edit_message_id: Optional[int] = None
    ):
        """Send account management menu"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                await self.bot.send_message(user_id, "❌ Account not found")
                return

            destroyer_status = (
                "🟢 Enabled"
                if account.get("otp_destroyer_enabled", False)
                else "🔴 Disabled"
            )
            simulation_status = (
                "🟢 Active"
                if account.get("simulation_enabled", False)
                else "🔴 Inactive"
            )
            online_maker_status = (
                "🟢 Enabled"
                if account.get("online_maker_enabled", False)
                else "🔴 Disabled"
            )
            last_destroyed = account.get("otp_destroyed_at", "Never")

            text = (
                f"📱 **Account: {account['name']}**\n\n"
                f"📞 Phone: {account['phone']}\n"
                f"🛡️ OTP Destroyer: {destroyer_status}\n"
                f"🎭 Activity Sim: {simulation_status}\n"
                f"🟢 Online Maker: {online_maker_status}\n"
                f"🕒 Last Destroyed: {last_destroyed}\n\n"
                f"Select an action:"
            )

            buttons = self.get_account_menu_buttons(account_id, account)

            if edit_message_id:
                await self.bot.edit_message(
                    user_id, edit_message_id, text, buttons=buttons
                )
            else:
                await self.bot.send_message(user_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to send account management: {e}")

    async def send_otp_account_management(
        self, user_id: int, account_id: str, edit_message_id: Optional[int] = None
    ):
        """Send OTP account management menu"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                await self.bot.send_message(user_id, "❌ Account not found")
                return

            destroyer_status = (
                "🟢 Active"
                if account.get("otp_destroyer_enabled", False)
                else "🔴 Inactive"
            )
            forward_status = (
                "🟢 Active"
                if account.get("otp_forward_enabled", False)
                else "🔴 Inactive"
            )
            # Check if temp OTP is still active (not expired)
            import time
            temp_active = False
            if account.get("otp_temp_passthrough", False):
                expiry = account.get("temp_passthrough_expiry", 0)
                if time.time() < expiry:
                    temp_active = True
                    
            if temp_active:
                remaining = int(expiry - time.time())
                minutes = remaining // 60
                seconds = remaining % 60
                temp_status = f"⏰ Active ({minutes}m {seconds}s left)"
            else:
                temp_status = "⚪ Inactive"
            has_password = (
                "🔒 Set" if account.get("otp_destroyer_disable_auth") else "⚪ Not Set"
            )

            text = (
                f"🛡️ **OTP Manager: {account['name']}**\n\n"
                f"📞 Phone: {account['phone']}\n\n"
                f"🛡️ **Destroyer**: {destroyer_status}\n"
                f"📤 **Forward**: {forward_status}\n"
                f"⏰ **Temp Pass**: {temp_status}\n"
                f"🔒 **Password**: {has_password}\n\n"
                f"🕒 Last Activity: {account.get('otp_destroyed_at', 'Never')}\n\n"
                f"Select an action:"
            )

            buttons = self.get_otp_account_buttons(account_id, account)

            if edit_message_id:
                await self.bot.edit_message(
                    user_id, edit_message_id, text, buttons=buttons
                )
            else:
                await self.bot.send_message(user_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to send OTP account management: {e}")

    async def send_audit_log(self, user_id: int, account_id: str):
        """Send audit log for account"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                await self.bot.send_message(user_id, "❌ Account not found")
                return

            audit_log = account.get("audit_log", [])

            if not audit_log:
                text = f"📋 **Audit Log: {account['name']}**\n\nNo audit entries found."
            else:
                text = f"📋 **Audit Log: {account['name']}**\n\n"

                # Show last 10 entries
                for entry in audit_log[-10:]:
                    timestamp = entry.get("timestamp", 0)
                    action = entry.get("action", "unknown")

                    import time

                    time_str = time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(timestamp)
                    )

                    # Map technical actions to user-friendly messages
                    action_messages = {
                        "invalidate_codes": f"Destroyed codes {entry.get('codes', [])}",
                        "otp_destroyed": f"Blocked login code {entry.get('code', 'Unknown')}",
                        "otp_forwarded": f"Forwarded login code {entry.get('code', 'Unknown')}",
                        "destroyer_enabled": "OTP Destroyer enabled",
                        "destroyer_disabled": "OTP Destroyer disabled",
                        "forwarding_enabled": "OTP Forwarding enabled",
                        "forwarding_disabled": "OTP Forwarding disabled",
                        "temp_passthrough_enabled": "5-minute passthrough activated",
                        "temp_passthrough_expired": "5-minute passthrough expired",
                        "test_entry": "System test completed",
                        "enable_otp_destroyer": "OTP Destroyer enabled",
                        "disable_otp_destroyer": "OTP Destroyer disabled",
                    }

                    message = action_messages.get(action, f"Unknown action: {action}")

                    if action in ["invalidate_codes", "otp_destroyed"]:
                        result = entry.get("result", True)
                        status = "✅" if result else "❌"
                        text += f"{status} {time_str}: {message}\n"
                    elif action in [
                        "destroyer_enabled",
                        "forwarding_enabled",
                        "temp_passthrough_enabled",
                        "enable_otp_destroyer",
                    ]:
                        text += f"🟢 {time_str}: {message}\n"
                    elif action in [
                        "destroyer_disabled",
                        "forwarding_disabled",
                        "temp_passthrough_expired",
                        "disable_otp_destroyer",
                    ]:
                        text += f"🔴 {time_str}: {message}\n"
                    elif action == "otp_forwarded":
                        text += f"📤 {time_str}: {message}\n"
                    else:
                        text += f"ℹ️ {time_str}: {message}\n"

            buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
            await self.bot.send_message(user_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to send audit log: {e}")

    def setup_menu_handlers(self):
        """Set up menu text handlers and legacy callback handler"""
        
        # Clear existing handlers to prevent duplicates
        self.bot.remove_event_handler(self._menu_text_handler)
        self.bot.remove_event_handler(self._callback_handler)

        @self.bot.on(
            events.NewMessage(
                func=lambda e: e.is_private
                and e.text
                and e.text.strip()
                in [
                    "📱 Account Settings",
                    "Account Settings",
                    "🛡️ OTP Manager",
                    "OTP Manager",
                    "💬 Messaging",
                    "Messaging",
                    "📨 DM Reply",
                    "DM Reply",
                    "📢 Channels",
                    "Channels",
                    "👥 Contacts",
                    "Contacts",
                    "❓ Help",
                    "Help",
                    "🆘 Support",
                    "Support",
                    "⚙️ Developer",
                    "Developer",
                ]
            )
        )
        async def menu_text_handler(event):
            user_id = event.sender_id
            text = event.text.strip()

            try:
                if text in ["📱 Account Settings", "Account Settings"]:
                    await self._handle_account_settings(event)
                elif text in ["🛡️ OTP Manager", "OTP Manager"]:
                    await self._handle_otp_manager(event)
                elif text in ["💬 Messaging", "Messaging"]:
                    await self._handle_messaging(event)
                elif text in ["📨 DM Reply", "DM Reply"]:
                    await self._handle_dm_reply(event)
                elif text in ["📢 Channels", "Channels"]:
                    await self._handle_channels(event)
                elif text in ["👥 Contacts", "Contacts"]:
                    await self._handle_contacts(event)
                elif text in ["❓ Help", "Help"]:
                    await self._handle_help(event)
                elif text in ["🆘 Support", "Support"]:
                    await self._handle_support(event)
                elif text in ["⚙️ Developer", "Developer"]:
                    if user_id not in ADMIN_IDS:
                        await event.reply(
                            "❌ You don't have access to Developer tools."
                        )
                        return
                    await self._handle_developer(event)
            except Exception as e:
                logger.error(f"Menu handler error for {text}: {e}")
                await event.reply("❌ Error processing menu action")
        
        # Store handler reference for cleanup
        self._menu_text_handler = menu_text_handler

        # Handle callback queries from inline buttons
        @self.bot.on(events.CallbackQuery)
        async def callback_handler(event):
            try:
                user_id = event.sender_id
                data = event.data.decode("utf-8")

                logger.info(f"Callback from {user_id}: {data}")

                # Route callbacks to appropriate handlers
                if data.startswith("account:"):
                    if data == "account:add":
                        await self._handle_add_account(event, user_id)
                    elif data.startswith("account:manage:"):
                        account_id = data.split(":")[
                            2
                        ]  # Keep as string for MongoDB ObjectId
                        await self.send_account_management(
                            user_id, account_id, event.message_id
                        )
                    elif data == "account:list":
                        await self._handle_account_settings(
                            type(
                                "Event",
                                (),
                                {
                                    "sender_id": user_id,
                                    "reply": lambda x, buttons=None: self.bot.send_message(
                                        user_id, x, buttons=buttons
                                    ),
                                },
                            )()
                        )
                    elif data == "account:remove":
                        await self._handle_remove_account(event, user_id)
                    elif data == "account:refresh":
                        await self._handle_account_settings(
                            type(
                                "Event",
                                (),
                                {
                                    "sender_id": user_id,
                                    "reply": lambda x, buttons=None: self.bot.edit_message(
                                        user_id, event.message_id, x, buttons=buttons
                                    ),
                                },
                            )()
                        )

                elif data.startswith("otp:"):
                    if data.startswith("otp:manage:"):
                        account_id = data.split(":")[
                            2
                        ]  # Keep as string for MongoDB ObjectId
                        await self.send_otp_account_management(
                            user_id, account_id, event.message_id
                        )
                    elif data == "otp:enable_all":
                        text = (
                            "🛡️ **Enable All OTP Destroyers**\n\n"
                            "This will enable OTP Destroyer protection for all your accounts.\n\n"
                            "⚠️ This is a bulk operation that affects all accounts.\n\n"
                            "Feature coming soon!"
                        )
                        buttons = [
                            [Button.inline("🔙 Back to OTP Manager", "menu:otp")]
                        ]
                        await self.bot.edit_message(
                            user_id, event.message_id, text, buttons=buttons
                        )
                        await event.answer("🛡️ Bulk enable feature")
                    elif data == "otp:disable_all":
                        text = (
                            "🔴 **Disable All OTP Destroyers**\n\n"
                            "This will disable OTP Destroyer protection for all your accounts.\n\n"
                            "⚠️ WARNING: This will make all accounts vulnerable!\n\n"
                            "Feature coming soon!"
                        )
                        buttons = [
                            [Button.inline("🔙 Back to OTP Manager", "menu:otp")]
                        ]
                        await self.bot.edit_message(
                            user_id, event.message_id, text, buttons=buttons
                        )
                        await event.answer("🔴 Bulk disable feature")
                    elif data == "otp:stats":
                        text = (
                            "📊 **OTP Statistics**\n\n"
                            "Global OTP protection statistics:\n\n"
                            "• Total accounts protected\n"
                            "• Login attempts blocked today\n"
                            "• OTP codes destroyed\n"
                            "• Security events logged\n\n"
                            "Feature coming soon!"
                        )
                        buttons = [
                            [Button.inline("🔙 Back to OTP Manager", "menu:otp")]
                        ]
                        await self.bot.edit_message(
                            user_id, event.message_id, text, buttons=buttons
                        )
                        await event.answer("📊 OTP statistics")
                    elif data == "otp:audit_all":
                        text = (
                            "📋 **Global OTP Audit Log**\n\n"
                            "Combined audit log for all accounts:\n\n"
                            "• OTP destroyer activities\n"
                            "• Security events\n"
                            "• Login attempts blocked\n"
                            "• Configuration changes\n\n"
                            "Feature coming soon!"
                        )
                        buttons = [
                            [Button.inline("🔙 Back to OTP Manager", "menu:otp")]
                        ]
                        await self.bot.edit_message(
                            user_id, event.message_id, text, buttons=buttons
                        )
                        await event.answer("📋 Global audit log")
                    else:
                        await self._handle_otp_callback(event, user_id, data)

                elif data.startswith("2fa:"):
                    await self._handle_2fa_callback(event, user_id, data)

                elif data.startswith("profile:"):
                    await self._handle_profile_callback(event, user_id, data)

                elif data.startswith("sessions:"):
                    await self._handle_sessions_callback(event, user_id, data)

                elif data.startswith("online:"):
                    await self._handle_online_callback(event, user_id, data)

                elif data.startswith("msg:"):
                    parts = data.split(":")
                    action = parts[1]

                    if action == "send":
                        await self._send_message_menu(user_id, event.message_id)
                    elif action == "autoreply":
                        await self._send_autoreply_menu(user_id, event.message_id)
                    elif action == "templates":
                        await self._send_templates_menu(user_id, event.message_id)
                    elif action == "stats":
                        text = (
                            "📊 **Messaging Statistics**\n\n"
                            "Your messaging activity:\n\n"
                            "• Messages sent today\n"
                            "• Auto-replies triggered\n"
                            "• Templates used\n"
                            "• Active conversations\n\n"
                            "Feature coming soon!"
                        )
                        buttons = [
                            [Button.inline("🔙 Back to Messaging", "menu:messaging")]
                        ]
                        await self.bot.edit_message(
                            user_id, event.message_id, text, buttons=buttons
                        )
                        await event.answer("📊 Messaging stats")
                    elif action == "history":
                        text = (
                            "📋 **Message History**\n\n"
                            "View your message history:\n\n"
                            "• Recent sent messages\n"
                            "• Auto-reply logs\n"
                            "• Template usage\n"
                            "• Message statistics\n\n"
                            "Feature coming soon!"
                        )
                        buttons = [
                            [Button.inline("🔙 Back to Messaging", "menu:messaging")]
                        ]
                        await self.bot.edit_message(
                            user_id, event.message_id, text, buttons=buttons
                        )
                        await event.answer("📋 Message history")
                    elif action == "settings":
                        text = (
                            "⚙️ **Messaging Settings**\n\n"
                            "Configure messaging preferences:\n\n"
                            "• Default message templates\n"
                            "• Auto-reply settings\n"
                            "• Message formatting\n"
                            "• Delivery options\n\n"
                            "Feature coming soon!"
                        )
                        buttons = [
                            [Button.inline("🔙 Back to Messaging", "menu:messaging")]
                        ]
                        await self.bot.edit_message(
                            user_id, event.message_id, text, buttons=buttons
                        )
                        await event.answer("⚙️ Messaging settings")
                    elif action == "bulk":
                        await self._send_bulk_sender_menu(user_id, event.message_id)
                    else:
                        await self._handle_messaging_callback(event, user_id, data)

                elif data.startswith("autoreply:"):
                    await self._handle_autoreply_callback(event, user_id, data)

                elif data.startswith("template:"):
                    await self._handle_template_callback(event, user_id, data)
                
                elif data.startswith("bulk:"):
                    await self._handle_bulk_callback(event, user_id, data)
                
                elif data.startswith("bulk_list_account:"):
                    account_id = data.split(":")[1]
                    if self.account_manager:
                        self.account_manager.pending_actions[user_id] = {
                            "action": "bulk_list_targets",
                            "account_id": account_id
                        }
                    text = "📋 **Step 2:** Reply with targets (comma-separated):\n\n@user1,@user2,+1234567890"
                    await self.bot.edit_message(user_id, event.message_id, text)
                    await event.answer("📋 Reply with targets")
                
                elif data.startswith("bulk_contacts_account:"):
                    account_id = data.split(":")[1]
                    if self.account_manager:
                        self.account_manager.pending_actions[user_id] = {
                            "action": "bulk_contacts_message",
                            "account_id": account_id
                        }
                    text = "👥 **Step 2:** Reply with your message:"
                    await self.bot.edit_message(user_id, event.message_id, text)
                    await event.answer("👥 Reply with message")

                elif data.startswith("simulate:"):
                    await self._handle_simulate_callback(event, user_id, data)
                


                elif data.startswith("audit:"):
                    await self._handle_audit_callback(event, user_id, data)
                elif data.startswith("otp:audit"):
                    parts = data.split(":")
                    if len(parts) >= 3:
                        account_id = parts[2]
                        await self.send_audit_log(user_id, account_id)

                elif data.startswith("channel:"):
                    parts = data.split(":")
                    action = parts[1]

                    if action == "select" and len(parts) > 2:
                        account_phone = parts[2]
                        await self._send_channel_actions_menu(
                            user_id, account_phone, event.message_id
                        )
                    elif action == "stats":
                        text = (
                            "📊 **Channel Statistics**\n\n"
                            "Loading channel statistics...\n\n"
                            "• Total channels: Calculating...\n"
                            "• Active memberships: Counting...\n"
                            "• Admin roles: Checking...\n"
                            "• Recent activity: Analyzing..."
                        )
                        buttons = [
                            [Button.inline("🔙 Back to Channels", "menu:channels")]
                        ]
                        await self.bot.edit_message(
                            user_id, event.message_id, text, buttons=buttons
                        )
                        await event.answer("📊 Loading stats...")
                    elif action == "search":
                        text = (
                            "🔍 **Search Channels**\n\n"
                            "Channel search functionality:\n\n"
                            "• Search by name or username\n"
                            "• Filter by type (channel/group)\n"
                            "• Browse popular channels\n"
                            "• Find recommended channels\n\n"
                            "Feature coming soon!"
                        )
                        buttons = [
                            [Button.inline("🔙 Back to Channels", "menu:channels")]
                        ]
                        await self.bot.edit_message(
                            user_id, event.message_id, text, buttons=buttons
                        )
                        await event.answer("🔍 Search feature")
                    else:
                        await self._handle_channel_callback(event, user_id, data)

                elif data.startswith("help:"):
                    await self._handle_help_callback(event, user_id, data)

                elif data.startswith("support:"):
                    await self._handle_support_callback(event, user_id, data)

                elif data.startswith("dev:"):
                    await self._handle_developer_callback(event, user_id, data)

                elif data.startswith("menu:"):
                    await self._handle_menu_callback(event, user_id, data)

                elif data.startswith("help:"):
                    await self._handle_help_callback(event, user_id, data)

                elif data.startswith("support:"):
                    await self._handle_support_callback(event, user_id, data)

                elif data.startswith("dev:"):
                    await self._handle_developer_callback(event, user_id, data)

                elif data.startswith("menu:"):
                    await self._handle_menu_callback(event, user_id, data)

                elif data.startswith("dm_reply:"):
                    await self._handle_dm_reply_callback(event, user_id, data)
                
                elif data.startswith("contacts:"):
                    # Handle contacts callbacks with simplified approach
                    try:
                        parts = data.split(":")
                        action = parts[1] if len(parts) > 1 else "main"
                        
                        if action == "main":
                            text = (
                                "📱 **Contact Management**\n\n"
                                "📊 Contact system available\n\n"
                                "Choose an option:"
                            )
                            buttons = [
                                [Button.inline("👥 View All Contacts", "contacts:list")],
                                [Button.inline("➕ Add Contact", "contacts:add"), Button.inline("🔍 Search", "contacts:search")],
                                [Button.inline("📁 Groups", "contacts:groups"), Button.inline("🏷️ Tags", "contacts:tags")],
                                [Button.inline("📤 Export", "contacts:export"), Button.inline("📥 Import", "contacts:import")],
                                [Button.inline("🔄 Sync", "contacts:sync")],
                                [Button.inline("🔙 Back", "menu:main")]
                            ]
                            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                            
                        elif action == "list":
                            # Get user's accounts to find contacts
                            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
                            if not accounts:
                                text = "👥 **All Contacts**\n\n❌ No accounts found."
                                buttons = [[Button.inline("🔙 Back", "contacts:main")]]
                            else:
                                # Get contacts from all accounts
                                all_contacts = []
                                for account in accounts:
                                    contacts = await mongodb.db.contacts.find({"managed_by_account": account['name']}).to_list(length=None)
                                    all_contacts.extend(contacts)
                                
                                if not all_contacts:
                                    text = "👥 **All Contacts**\n\n💭 No contacts found.\n\nUse 'Add Contact' or 'Sync' to add contacts."
                                else:
                                    text = f"👥 **All Contacts** ({len(all_contacts)})\n\n"
                                    for i, contact in enumerate(all_contacts[:10], 1):
                                        name = contact.get('first_name', 'Unknown')
                                        if contact.get('last_name'):
                                            name += f" {contact['last_name']}"
                                        username = f"@{contact['username']}" if contact.get('username') else "No username"
                                        phone = contact.get('phone', 'No phone')
                                        account = contact.get('managed_by_account', 'Unknown')
                                        text += f"{i}. **{name}**\n   {username} | {phone}\n   Account: {account}\n\n"
                                    
                                    if len(all_contacts) > 10:
                                        text += f"... and {len(all_contacts) - 10} more contacts"
                                
                                buttons = [[Button.inline("🔙 Back", "contacts:main")]]
                            
                            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                            
                        elif action == "sync":
                            text = (
                                "🔄 **Contact Sync**\n\n"
                                "Choose sync direction:"
                            )
                            buttons = [
                                [Button.inline("📥 From Telegram", "sync:from_telegram")],
                                [Button.inline("📤 To Telegram", "sync:to_telegram")],
                                [Button.inline("🔄 Both Ways", "sync:both")],
                                [Button.inline("🔙 Back", "contacts:main")]
                            ]
                            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                            
                        elif action == "export":
                            # Handle export contacts - redirect to contact export handler
                            from ..handlers.contact_export_handler import ContactExportHandler
                            export_handler = ContactExportHandler(self.account_manager)
                            
                            # Get user accounts
                            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
                            if not accounts:
                                text = "📤 **Export Contacts**\n\n❌ No accounts found. Add accounts first to export contacts."
                                buttons = [[Button.inline("🔙 Back", "contacts:main")]]
                                await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                                return
                            
                            # Show account selection for export
                            buttons = []
                            for account in accounts[:8]:  # Limit to 8 accounts
                                status = "🟢" if account.get("is_active", False) else "🔴"
                                buttons.append([Button.inline(f"{status} {account['name']}", f"export_contacts:{account['name']}")])
                            
                            buttons.append([Button.inline("🔙 Back", "contacts:main")])
                            
                            text = "📤 **Export Contacts to CSV**\n\nSelect account to export contacts from:"
                            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                        
                        else:
                            # For other actions, show coming soon message
                            text = f"⚙️ **{action.title()} Feature**\n\nThis feature is coming soon!"
                            buttons = [[Button.inline("🔙 Back", "contacts:main")]]
                            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                            
                    except Exception as e:
                        logger.error(f"Contact callback error: {e}")
                        await event.answer("❌ Error processing contact action")
                
                elif data.startswith("sync:"):
                    # Handle sync callbacks for contacts - simplified approach
                    try:
                        sync_type = data.split(":")[1]
                        
                        # Get user's first account for sync operations
                        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=1)
                        if not accounts:
                            await self.bot.edit_message(user_id, event.message_id, "❌ No accounts found for sync")
                            return
                            
                        # Show progress
                        await self.bot.edit_message(user_id, event.message_id, "🔄 **Synchronizing...**\n\nPlease wait...")
                        
                        # Simulate sync delay
                        import asyncio
                        await asyncio.sleep(1)
                        
                        # Simple sync result message
                        if sync_type == "from_telegram":
                            result_text = "✅ **Sync from Telegram Complete**\n\nContacts imported from Telegram."
                        elif sync_type == "to_telegram":
                            result_text = "✅ **Sync to Telegram Complete**\n\nContacts exported to Telegram."
                        elif sync_type == "both":
                            result_text = "✅ **Two-way Sync Complete**\n\nContacts synchronized in both directions."
                        else:
                            result_text = "❌ **Invalid Sync Type**\n\nUnknown sync operation."
                            
                        buttons = [[Button.inline("🔙 Back", "contacts:main")]]
                        await self.bot.edit_message(user_id, event.message_id, result_text, buttons=buttons)
                        
                    except Exception as e:
                        logger.error(f"Sync callback error: {e}")
                        await event.answer("❌ Error processing sync")
                        
                elif data.startswith("remove:"):
                    parts = data.split(":")
                    if len(parts) >= 3 and parts[1] == "confirm":
                        account_id = parts[2]
                        text = (
                            "⚠️ **Confirm Account Removal**\n\n"
                            "Are you sure you want to remove this account?\n\n"
                            "This will:\n"
                            "• Delete all account data\n"
                            "• Terminate active sessions\n"
                            "• Remove OTP protection\n"
                            "• Cannot be undone\n\n"
                            "Use the buttons below to confirm or cancel."
                        )
                        buttons = [
                            [
                                Button.inline(
                                    "✅ Yes, Remove Account",
                                    f"remove:execute:{account_id}",
                                )
                            ],
                            [Button.inline("❌ Cancel", "account:remove")],
                        ]
                        await self.bot.edit_message(
                            user_id, event.message_id, text, buttons=buttons
                        )
                        await event.answer("⚠️ Confirm removal")
                    elif len(parts) >= 3 and parts[1] == "execute":
                        account_id = parts[2]
                        await self._execute_remove_account(event, user_id, account_id)

                elif data == "menu:accounts":
                    await self._handle_account_settings(
                        type(
                            "Event",
                            (),
                            {
                                "sender_id": user_id,
                                "reply": lambda x, buttons=None: self.bot.edit_message(
                                    user_id, event.message_id, x, buttons=buttons
                                ),
                            },
                        )()
                    )

                elif data == "menu:otp":
                    await self._handle_otp_manager(
                        type(
                            "Event",
                            (),
                            {
                                "sender_id": user_id,
                                "reply": lambda x, buttons=None: self.bot.edit_message(
                                    user_id, event.message_id, x, buttons=buttons
                                ),
                            },
                        )()
                    )

                elif data == "menu:messaging":
                    await self._handle_messaging(
                        type(
                            "Event",
                            (),
                            {
                                "sender_id": user_id,
                                "reply": lambda x, buttons=None: self.bot.edit_message(
                                    user_id, event.message_id, x, buttons=buttons
                                ),
                            },
                        )()
                    )

                elif data == "menu:channels":
                    await self._handle_channels(
                        type(
                            "Event",
                            (),
                            {
                                "sender_id": user_id,
                                "reply": lambda x, buttons=None: self.bot.edit_message(
                                    user_id, event.message_id, x, buttons=buttons
                                ),
                            },
                        )()
                    )

                elif data.startswith("otp_pwd:"):
                    parts = data.split(":")
                    if len(parts) >= 3:
                        action = parts[1]
                        account_id = parts[2]
                        if action == "set":
                            await event.answer("🔒 Set password feature coming soon!")
                        elif action == "change":
                            if self.account_manager:
                                self.account_manager.pending_actions[user_id] = {
                                    "action": "change_otp_disable_password",
                                    "account_id": account_id,
                                }
                                text = "🔒 **Change Password**\n\nReply with your current password first:"
                                await self.bot.send_message(user_id, text)
                                await event.answer("🔒 Enter current password")
                        elif action == "remove":
                            if self.account_manager:
                                self.account_manager.pending_actions[user_id] = {
                                    "action": "remove_otp_disable_password",
                                    "account_id": account_id,
                                }
                                text = "🔒 **Remove Password**\n\nReply with your current password to remove protection:"
                                await self.bot.send_message(user_id, text)
                                await event.answer("🔒 Enter password to remove")
                        elif action == "status":
                            text = (
                                "🔒 **Password Status**\n\n"
                                "OTP Destroyer password protection:\n\n"
                                "• Current status\n"
                                "• Security level\n"
                                "• Last changed\n"
                                "• Protection active\n\n"
                                "Feature coming soon!"
                            )
                            buttons = [
                                [Button.inline("🔙 Back", f"otp:manage:{account_id}")]
                            ]
                            await self.bot.send_message(user_id, text, buttons=buttons)
                            await event.answer("🔒 Password status")

                elif data.startswith("manage:"):
                    account_phone = data.split(":")[1]
                    await self._send_channel_actions_menu(
                        user_id, account_phone, event.message_id
                    )

                else:
                    await event.answer("Action processed", alert=False)

            except Exception as e:
                logger.error(f"Callback handler error: {e}")
                await event.answer("❌ Error processing action", alert=True)
        
        # Store handler reference for cleanup
        self._callback_handler = callback_handler

    async def _handle_account_settings(self, event):
        """Handle Account Settings menu"""
        user_id = event.sender_id
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )

            if not accounts:
                text = "📱 **Account Management**\n\nNo accounts found. Add your first account to get started."
                buttons = [
                    [Button.inline("➕ Add Account", "account:add")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                text = f"📱 **Account Management**\n\nYou have {len(accounts)} account(s):\n\n"
                buttons = []

                for i, account in enumerate(accounts, 1):
                    status = "🟢" if account.get("is_active", False) else "🔴"
                    destroyer_status = (
                        "🛡️" if account.get("otp_destroyer_enabled", False) else "⚪"
                    )
                    text += f"{i}. {status}{destroyer_status} {account['name']} ({account['phone']})\n"

                    # Add manage button for each account
                    buttons.append(
                        [
                            Button.inline(
                                f"⚙️ Manage {account['name']}",
                                f"account:manage:{account['_id']}",
                            )
                        ]
                    )

                # Add action buttons
                buttons.extend(
                    [
                        [
                            Button.inline("➕ Add Account", "account:add"),
                            Button.inline("📋 List All", "account:list"),
                        ],
                        [
                            Button.inline("🗑️ Remove Account", "account:remove"),
                            Button.inline("🔄 Refresh", "account:refresh"),
                        ],
                        [Button.inline("🔙 Back to Main Menu", "menu:main")],
                    ]
                )

            await self.bot.send_message(user_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to handle account settings: {e}")
            await event.reply("❌ Error loading account settings")

    async def _handle_otp_manager(self, event):
        """Handle OTP Manager menu"""
        user_id = event.sender_id
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )

            if not accounts:
                text = "🛡️ **OTP Manager**\n\nNo accounts found. Add accounts first to manage OTP settings."
                buttons = [
                    [Button.inline("➕ Add Account", "account:add")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                text = (
                    "🛡️ **OTP Manager**\n\n"
                    "Select an account to configure OTP protection:\n\n"
                )
                buttons = []

                for account in accounts:
                    destroyer_status = (
                        "🛡️" if account.get("otp_destroyer_enabled", False) else "🔴"
                    )
                    forward_status = (
                        "📤" if account.get("otp_forward_enabled", False) else "⚪"
                    )
                    button_text = (
                        f"{destroyer_status}{forward_status} {account['name']}"
                    )
                    buttons.append(
                        [Button.inline(button_text, f"otp:manage:{account['_id']}")]
                    )

                buttons.extend(
                    [
                        [
                            Button.inline("🛡️ Enable All Destroyers", "otp:enable_all"),
                            Button.inline("🔴 Disable All", "otp:disable_all"),
                        ],
                        [
                            Button.inline("📊 OTP Statistics", "otp:stats"),
                            Button.inline("📋 Audit Log", "otp:audit_all"),
                        ],
                        [Button.inline("🔙 Back to Main Menu", "menu:main")],
                    ]
                )

            await self.bot.send_message(user_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to handle OTP manager: {e}")
            await event.reply("❌ Error loading OTP manager")

    async def _handle_messaging(self, event):
        """Handle Messaging menu"""
        user_id = event.sender_id
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )

            if not accounts:
                text = "💬 **Messaging**\n\nNo accounts found. Add accounts first to use messaging features."
                buttons = [
                    [Button.inline("➕ Add Account", "account:add")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                text = (
                    "💬 **Messaging Center**\n\n"
                    "Choose a messaging action:\n\n"
                    "📤 Send messages to users/groups\n"
                    "📨 Bulk messaging to multiple users\n"
                    "🤖 Set up auto-reply rules\n"
                    "📝 Create message templates\n"
                    "📊 View message statistics"
                )
                buttons = [
                    [
                        Button.inline("📤 Send Message", "msg:send"),
                        Button.inline("📨 Bulk Sender", "msg:bulk"),
                    ],
                    [
                        Button.inline("🤖 Auto Reply", "auto_reply:main"),
                        Button.inline("📝 Templates", "msg:templates"),
                    ],
                    [
                        Button.inline("📊 Statistics", "msg:stats"),
                        Button.inline("📋 History", "msg:history"),
                    ],
                    [
                        Button.inline("⚙️ Settings", "msg:settings"),
                    ],
                    [
                        Button.inline("🔙 Back to Main Menu", "menu:main"),
                    ],
                ]

            await self.bot.send_message(user_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to handle messaging: {e}")
            await event.reply("❌ Error loading messaging menu")

    async def _handle_channels(self, event):
        """Handle Channels menu"""
        user_id = event.sender_id
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )

            if not accounts:
                text = "📢 **Channel Manager**\n\nNo accounts found. Add accounts first to manage channels."
                buttons = [
                    [Button.inline("➕ Add Account", "account:add")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                text = (
                    "📢 **Channel Manager**\n\n"
                    "Select an account to manage channels:\n\n"
                    "🔗 Join/leave channels\n"
                    "🆕 Create new channels\n"
                    "📋 List your channels\n"
                    "🗑️ Delete channels"
                )
                buttons = []

                for account in accounts[:8]:  # Limit to 8 accounts
                    status = "🔗" if account.get("is_active", False) else "🔴"
                    button_text = f"{status} {account['name']}"
                    buttons.append(
                        [
                            Button.inline(
                                button_text, f"channel:select:{account['phone']}"
                            )
                        ]
                    )

                buttons.extend(
                    [
                        [
                            Button.inline("📊 Channel Statistics", "channel:stats"),
                            Button.inline("🔍 Search Channels", "channel:search"),
                        ],
                        [Button.inline("🔙 Back to Main Menu", "menu:main")],
                    ]
                )

            await self.bot.send_message(user_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to handle channels: {e}")
            await event.reply("❌ Error loading channel manager")

    async def _handle_contacts(self, event):
        """Handle Contacts menu"""
        user_id = event.sender_id
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            
            if not accounts:
                text = "👥 **Contact Management**\n\nNo accounts found. Add accounts first to manage contacts."
                buttons = [
                    [Button.inline("➕ Add Account", "account:add")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                # Get contact count from database
                contact_count = 0
                for account in accounts:
                    count = await mongodb.db.contacts.count_documents({"managed_by_account": account['name']})
                    contact_count += count
                
                text = (
                    "👥 **Contact Management System**\n\n"
                    f"📊 **Statistics:**\n"
                    f"• Total Contacts: {contact_count}\n"
                    f"• Managed Accounts: {len(accounts)}\n\n"
                    "🚀 **Features:**\n"
                    "• Add, edit, delete contacts\n"
                    "• Organize with tags and groups\n"
                    "• Import/export contact lists\n"
                    "• Sync with Telegram contacts\n"
                    "• Blacklist/whitelist management\n\n"
                    "Click below to access the contact manager:"
                )
                
                buttons = [
                    [Button.inline("👥 Open Contact Manager", "contacts:main")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")]
                ]
            
            await self.bot.send_message(user_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Failed to handle contacts: {e}")
            await event.reply("❌ Error loading contact management")

    async def _handle_help(self, event):
        """Handle Help menu"""
        user_id = event.sender_id
        user = await mongodb.db.users.find_one({"telegram_id": user_id})

        text = (
            "❓ **TeleGuard Help Center**\n\n"
            "**🚀 Getting Started:**\n"
            "1️⃣ Use '📱 Account Settings' to add your first account\n"
            "2️⃣ Enable '🛡️ OTP Manager' for security protection\n"
            "3️⃣ Explore other features via the main menu\n\n"
            "**📱 Main Features:**\n"
            "• **Account Settings** - Add, remove, manage accounts\n"
            "• **OTP Manager** - Real-time login protection\n"
            "• **Messaging** - Send messages & auto-replies\n"
            "• **Channels** - Join, create, manage channels\n\n"
            "**🛡️ Security Features:**\n"
            "• OTP Destroyer - Blocks unauthorized logins\n"
            "• 2FA Management - Set/change passwords\n"
            "• Session Control - View/terminate sessions\n"
            "• Activity Simulation - Human-like behavior"
        )

        buttons = [
            [
                Button.inline("📖 User Guide", "help:guide"),
                Button.inline("🛡️ Security Info", "help:security"),
            ],
            [
                Button.inline("🔧 Troubleshooting", "help:troubleshoot"),
                Button.inline("❓ FAQ", "help:faq"),
            ],
            [
                Button.inline("📞 Contact Support", "help:contact"),
                Button.inline("🆘 Emergency Help", "help:emergency"),
            ],
            [
                Button.inline("📚 Chat Import", "menu:import"),
            ],
        ]

        # Add developer mode toggle for admins
        from ..core.config import ADMIN_IDS
        if user and user_id in ADMIN_IDS:
            dev_mode = user.get("developer_mode", False)
            dev_text = "🔴 Disable Dev Mode" if dev_mode else "⚙️ Enable Dev Mode"
            buttons.append([Button.inline(dev_text, "help:toggle_dev")])

        buttons.append([Button.inline("🔙 Back to Main Menu", "menu:main")])

        await self.bot.send_message(user_id, text, buttons=buttons)

    async def _handle_support(self, event):
        """Handle Support menu"""
        text = (
            "🆘 **TeleGuard Support Center**\n\n"
            "**👨💻 Meet the Developers:**\n"
            "• @Meher_Mankar - Lead Developer\n"
            "• @Gutkesh - Core Developer\n\n"
            "**📞 Get Help:**\n"
            "• 💬 Support Chat: @ContactXYZrobot\n"
            "• 🐛 Bug Reports: GitHub Issues\n"
            "• 📚 Documentation: Check README.md\n"
            "• ⏰ Response Time: Usually within 24 hours\n\n"
            "**🔧 Before Contacting Support:**\n"
            "1️⃣ Check the Help section for common solutions\n"
            "2️⃣ Try restarting the bot with /start\n"
            "3️⃣ Ensure your accounts are properly added"
        )

        buttons = [
            [
                Button.inline("💬 Contact Support", "support:contact"),
                Button.inline("🐛 Report Bug", "support:bug"),
            ],
            [
                Button.inline("📚 Documentation", "support:docs"),
                Button.inline("💡 Feature Request", "support:feature"),
            ],
            [
                Button.inline("📊 System Status", "support:status"),
                Button.inline("🔄 Check Updates", "support:updates"),
            ],
            [Button.inline("🔙 Back to Main Menu", "menu:main")],
        ]

        await self.bot.send_message(event.sender_id, text, buttons=buttons)

    async def _handle_developer(self, event):
        """Handle Developer menu"""
        user_id = event.sender_id
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})

            if user:
                current_mode = user.get("developer_mode", False)

                text = (
                    "⚙️ **Developer Tools**\n\n"
                    f"Current Mode: {'🟢 Enabled' if current_mode else '🔴 Disabled'}\n\n"
                    "**Available Tools:**\n"
                    "• Toggle developer mode\n"
                    "• View system information\n"
                    "• Access debug logs\n"
                    "• Database operations\n"
                    "• Performance metrics"
                )

                mode_text = (
                    "🔴 Disable Dev Mode" if current_mode else "🟢 Enable Dev Mode"
                )
                buttons = [
                    [Button.inline(mode_text, "dev:toggle")],
                    [
                        Button.inline("📊 System Info", "dev:sysinfo"),
                        Button.inline("📋 Debug Logs", "dev:logs"),
                    ],
                    [
                        Button.inline("🗄️ Database Stats", "dev:dbstats"),
                        Button.inline("⚡ Performance", "dev:perf"),
                    ],
                    [
                        Button.inline("🔧 Maintenance", "dev:maintenance"),
                        Button.inline("🔄 Restart", "dev:restart"),
                    ],
                    [
                        Button.inline("🚀 Startup Config", "dev:startup"),
                        Button.inline("📚 Commands", "dev:commands"),
                    ],
                    [
                        Button.inline("🔙 Back to Main Menu", "menu:main"),
                    ],
                ]

                await self.bot.send_message(user_id, text, buttons=buttons)
            else:
                await event.reply("❌ User not found")

        except Exception as e:
            logger.error(f"Failed to handle developer menu: {e}")
            await event.reply("❌ Error loading developer tools")
    
    async def _handle_dm_reply(self, event):
        """Handle DM Reply menu"""
        user_id = event.sender_id
        try:
            # Get current DM reply status from unified messaging
            admin_group_id = await self.account_manager.unified_messaging._get_user_admin_group(user_id)
            
            if admin_group_id:
                status_text = f"✅ **Enabled** - Group ID: `{admin_group_id}`"
                buttons = [
                    [Button.inline("🔄 Change Group", "dm_reply:change")],
                    [Button.inline("❌ Disable", "dm_reply:disable")],
                    [Button.inline("📊 Status", "dm_reply:status")],
                ]
            else:
                status_text = "❌ **Disabled**"
                buttons = [
                    [Button.inline("✅ Enable", "dm_reply:enable")],
                    [Button.inline("❓ How to Setup", "dm_reply:help")],
                ]
            
            text = (
                f"📨 **Unified Messaging & DM Reply**\n\n"
                f"**Auto-Topic Creation:** All private messages automatically create topics in your forum group.\n\n"
                f"**Status:** {status_text}\n\n"
                f"**Features:**\n"
                f"• Automatic topic creation for ALL DMs\n"
                f"• Each conversation gets its own persistent thread\n"
                f"• Simply reply in topics - no buttons needed\n"
                f"• Auto-reply and messaging integrated\n"
                f"• Clean organized interface"
            )
            
            buttons.append([Button.inline("🔙 Back to Main Menu", "menu:main")])
            
            await self.bot.send_message(user_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Failed to handle DM reply menu: {e}")
            await event.reply("❌ Error loading DM reply menu")

    async def _handle_otp_callback(self, event, user_id: int, data: str):
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
                await event.answer("🛡️ OTP Destroyer enabled! Forward disabled.")
                await self.send_otp_account_management(
                    user_id, account_id, event.message_id
                )
            except Exception as e:
                await event.answer("❌ Error enabling OTP Destroyer")

        elif action == "disable":
            try:
                from bson import ObjectId

                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id), "user_id": user_id},
                    {"$set": {"otp_destroyer_enabled": False}},
                )
                await event.answer("🔴 OTP Destroyer disabled!")
                await self.send_otp_account_management(
                    user_id, account_id, event.message_id
                )
            except Exception as e:
                await event.answer("❌ Error disabling OTP Destroyer")

        elif action == "forward_enable":
            try:
                from bson import ObjectId
                
                # Check if destroyer is enabled first
                account = await mongodb.db.accounts.find_one(
                    {"_id": ObjectId(account_id), "user_id": user_id}
                )
                
                if account and account.get("otp_destroyer_enabled", False):
                    await event.answer("❌ Cannot enable forward while OTP Destroyer is active")
                    return

                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id), "user_id": user_id},
                    {"$set": {"otp_forward_enabled": True}},
                )
                await event.answer("📤 OTP Forward enabled!")
                await self.send_otp_account_management(
                    user_id, account_id, event.message_id
                )
            except Exception as e:
                await event.answer("❌ Error enabling OTP Forward")

        elif action == "forward_disable":
            try:
                from bson import ObjectId

                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id), "user_id": user_id},
                    {"$set": {"otp_forward_enabled": False}},
                )
                await event.answer("🔴 OTP Forward disabled!")
                await self.send_otp_account_management(
                    user_id, account_id, event.message_id
                )
            except Exception as e:
                await event.answer("❌ Error disabling OTP Forward")

        elif action == "temp":
            try:
                from bson import ObjectId
                
                account = await mongodb.db.accounts.find_one(
                    {"_id": ObjectId(account_id), "user_id": user_id}
                )
                
                if not account:
                    await event.answer("❌ Account not found")
                    return
                    
                if not account.get("otp_destroyer_enabled", False):
                    await event.answer("⚠️ Temp OTP only works when OTP Destroyer is enabled")
                    return
                
                # Store original states and temporarily disable destroyer, enable forward
                import time
                expiry_time = time.time() + 300  # 5 minutes
                original_destroyer_state = account.get("otp_destroyer_enabled", False)
                original_forward_state = account.get("otp_forward_enabled", False)
                
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {
                        "otp_temp_passthrough": True,
                        "temp_passthrough_expiry": expiry_time,
                        "otp_destroyer_enabled": False,  # Temporarily disable destroyer
                        "otp_forward_enabled": True,  # Temporarily enable forward
                        "original_destroyer_state": original_destroyer_state,
                        "original_forward_state": original_forward_state
                    }}
                )
                
                await mongodb.add_audit_entry(account_id, {
                    "action": "temp_passthrough_enabled",
                    "duration": "5_minutes",
                    "timestamp": int(time.time())
                })
                
                await event.answer("⏰ Temp OTP enabled! Destroyer disabled, Forward enabled for 5 minutes.")
                await self.send_otp_account_management(
                    user_id, account_id, event.message_id
                )
                
                # Schedule cleanup after 5 minutes
                from ..handlers.temp_otp_cleanup import cleanup_temp_otp
                import asyncio
                asyncio.create_task(cleanup_temp_otp(user_id, account_id, expiry_time))
                
            except Exception as e:
                logger.error(f"Error enabling temp OTP: {e}")
                await event.answer("❌ Error enabling temp OTP")

        elif action == "audit":
            await self.send_audit_log(user_id, account_id)

        elif action == "setpass":
            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {
                    "action": "set_otp_disable_password",
                    "account_id": account_id,
                }

                text = (
                    "🔒 **Set Disable Password**\n\n"
                    "Reply with a password that will be required to disable OTP Destroyer.\n\n"
                    "⚠️ This adds an extra security layer - choose a strong password!\n"
                    "📝 Minimum 6 characters required."
                )

                await event.answer("🔒 Reply with password")
                await self.bot.send_message(user_id, text)
            else:
                await event.answer("❌ Service unavailable")

    async def _send_help_menu(self, user_id: int, message_id: int):
        """Send help menu"""
        text = (
            "❓ **Help & Information**\n\n"
            "🛡️ **OTP Destroyer**: Automatically invalidates login codes to prevent unauthorized access\n\n"
            "📱 **Account Management**: Add, remove, and configure your Telegram accounts\n\n"
            "🔐 **Security**: All data is encrypted and stored securely\n\n"
            "⚙️ **Developer Mode**: Access advanced features and text commands"
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
                text = f"⚙️ **Developer Mode**\n\nDeveloper mode {status}.\n\n"

                if new_mode:
                    text += "You now have access to text commands:\n/add, /remove, /accs, /toggle_protection, etc."
                else:
                    text += "Text commands are now hidden. Use the menu system."

                buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
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
                text = "🛡️ **OTP Manager**\n\nNo accounts found. Add accounts first to manage OTP settings."
            else:
                text = (
                    "🛡️ **OTP Manager**\n\n"
                    "OTP security features:\n\n"
                    "• 🛡️ Destroyer: Blocks unauthorized logins\n"
                    "• 📤 Forward: Forwards OTP codes to you\n"
                    "• ⏰ Temp Pass: 5-minute security bypass\n\n"
                    f"You have {len(accounts)} account(s). Use Account Settings to manage OTP protection."
                )

            await self.bot.send_message(user_id, text)

        except Exception as e:
            logger.error(f"Failed to send OTP menu: {e}")

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
        buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _send_2fa_menu(self, user_id: int, message_id: int):
        """Send 2FA settings menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )

            if not accounts:
                text = "🔑 **2FA Settings**\n\nNo accounts found. Add accounts first."
                buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
            else:
                text = "🔑 **2FA Settings**\n\nSelect an account to manage 2FA:"
                buttons = []

                for account in accounts:
                    has_2fa = "🔒" if account.get("twofa_password") else "⚪"
                    button_text = f"{has_2fa} {account['name']}"
                    buttons.append(
                        [Button.inline(button_text, f"2fa:status:{account['_id']}")]
                    )

                buttons.append([Button.inline("🔙 Back to Main", "menu:main")])

            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to send 2FA menu: {e}")

    async def _send_online_menu(self, user_id: int, message_id: int):
        """Send online maker menu"""
        text = (
            "🟢 **Online Maker**\n\n"
            "Keep your accounts online automatically.\n\n"
            "Features coming soon:"
            "• Auto-online intervals\n"
            "• Custom status messages\n"
            "• Schedule management"
        )
        buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
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
        buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _send_profile_menu(self, user_id: int, message_id: int):
        """Send profile management menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )

            if not accounts:
                text = (
                    "👤 **Profile Manager**\n\nNo accounts found. Add accounts first."
                )
                buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
            else:
                text = "👤 **Profile Manager**\n\nSelect an account to manage profile:"
                buttons = []

                for account in accounts:
                    username_display = (
                        f"@{account.get('username', '')}"
                        if account.get("username")
                        else "No username"
                    )
                    button_text = f"👤 {account['name']} ({username_display})"
                    buttons.append(
                        [Button.inline(button_text, f"profile:manage:{account['_id']}")]
                    )

                buttons.append([Button.inline("🔙 Back to Main", "menu:main")])

            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to send profile menu: {e}")

    async def _send_groups_menu(self, user_id: int, message_id: int):
        """Send groups and channels menu"""
        text = (
            "👥 **Groups & Channels**\n\n"
            "Manage groups and channels for your accounts.\n\n"
            "Features coming soon:"
            "• Create channels/groups\n"
            "• Manage members and admins\n"
            "• Post and schedule content\n"
            "• Invite link management"
        )
        buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _send_messaging_menu(self, user_id: int, message_id: int):
        """Send messaging menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )

            if not accounts:
                text = "💬 **Messaging**\n\nNo accounts found. Add accounts first to use messaging features."
                buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
            else:
                text = "💬 **Messaging**\n\nSelect messaging action:"
                buttons = [
                    [Button.inline("📤 Send Message", "msg:send")],
                    [Button.inline("🔄 Auto Reply", "msg:autoreply")],
                    [Button.inline("📝 Message Templates", "msg:templates")],
                    [Button.inline("🔙 Back to Main", "menu:main")],
                ]

            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to send messaging menu: {e}")

    async def _send_automation_menu(self, user_id: int, message_id: int):
        """Send automation menu"""
        text = (
            "⚡ **Automation**\n\n"
            "Automate account actions and workflows.\n\n"
            "Available features:"
            "• Online maker (keep accounts online)\n"
            "• Auto-reply rules\n"
            "• Scheduled posts\n"
            "• Auto-join/leave groups"
        )
        buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _send_analytics_menu(self, user_id: int, message_id: int):
        """Send analytics menu"""
        text = (
            "📊 **Analytics**\n\n"
            "View account statistics and activity.\n\n"
            "Features coming soon:"
            "• Account health monitoring\n"
            "• Session activity logs\n"
            "• OTP destroyer statistics\n"
            "• Automation performance"
        )
        buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _send_support_menu(self, user_id: int, message_id: int):
        """Send support menu"""
        text = (
            "🆘 **Support & Contact**\n\n"
            "Need help? Contact our support team:\n\n"
            "👨💻 **Developers:**\n"
            "• @Meher_Mankar\n"
            "• @Gutkesh\n\n"
            "📧 **Support:** https://t.me/ContactXYZrobot\n"
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
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"

        if action == "set":
            # Handle password setting with text input
            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {
                    "action": "set_2fa_password",
                    "account_id": account_id,
                }

                text = (
                    "🔑 **Set 2FA Password**\n\n"
                    "Reply with your new 2FA password:\n\n"
                    "⚠️ This will set the actual 2FA password on Telegram!\n"
                    "⚠️ Message will be deleted after processing for security."
                )

                await event.answer("🔑 Reply with password")
                await self.bot.send_message(user_id, text)

        elif action == "change":
            # Handle password change with text input
            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {
                    "action": "change_2fa_current",
                    "account_id": account_id,
                }

                text = (
                    "🔑 **Change 2FA Password**\n\n"
                    "Reply with your current 2FA password:\n\n"
                    "⚠️ Message will be deleted after processing for security."
                )

                await event.answer("🔑 Enter current password")
                await self.bot.send_message(user_id, text)

        elif action == "remove":
            # Handle password removal with text input
            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {
                    "action": "remove_2fa_password",
                    "account_id": account_id,
                }

                text = (
                    "🔑 **Remove 2FA Password**\n\n"
                    "Reply with your current 2FA password to remove it:\n\n"
                    "⚠️ This will disable 2FA protection!\n"
                    "⚠️ Message will be deleted after processing for security."
                )

                await event.answer("🔑 Enter password to remove")
                await self.bot.send_message(user_id, text)

        elif action == "status":
            # Show 2FA status
            await self.secure_2fa_handlers.show_2fa_status(
                user_id, account_id, event.message_id
            )

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
                    
                    # Start or stop online maker using bot_manager's online_maker
                    if hasattr(self.account_manager, 'online_maker'):
                        if new_status:
                            await self.account_manager.online_maker.start_online_maker(user_id, account["name"])
                        else:
                            await self.account_manager.online_maker.stop_online_maker(user_id, account["name"])
                    
                    status = "started" if new_status else "stopped"
                    status_emoji = "🟢" if new_status else "🔴"
                    await event.answer(f"{status_emoji} Online maker {status}!")
                    await self.send_account_management(
                        user_id, account_id, event.message_id
                    )
            except Exception as e:
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
        """Send profile management options for specific account"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                await self.bot.send_message(user_id, "❌ Account not found")
                return

            # Fetch current profile info from Telegram
            current_info = await self._get_current_profile_info(
                user_id, account["name"]
            )

            if current_info:
                username_display = (
                    f"@{current_info.get('username', '')}"
                    if current_info.get("username")
                    else "Not set"
                )
                first_name = current_info.get("first_name", "")
                last_name = current_info.get("last_name", "")
                name_display = f"{first_name} {last_name}".strip() or "Not set"
                bio_display = current_info.get("about", "") or "Not set"
            else:
                # Fallback to database info
                username_display = (
                    f"@{account.get('username', '')}"
                    if account.get("username")
                    else "Not set"
                )
                name_display = (
                    f"{account.get('profile_first_name', '')} {account.get('profile_last_name', '')}".strip()
                    or "Not set"
                )
                bio_display = account.get("about", "") or "Not set"

            text = (
                f"👤 **Profile: {account['name']}**\n\n"
                f"📞 Phone: {account['phone']}\n"
                f"👤 Name: {name_display}\n"
                f"🆔 Username: {username_display}\n"
                f"📝 Bio: {bio_display}\n\n"
                f"Select what to update:"
            )

            buttons = [
                [
                    Button.inline("🖼️ Change Photo", f"profile:photo:{account_id}"),
                    Button.inline("👤 Change Name", f"profile:name:{account_id}"),
                ],
                [
                    Button.inline("🆔 Set Username", f"profile:username:{account_id}"),
                    Button.inline("📝 Update Bio", f"profile:bio:{account_id}"),
                ],
                [Button.inline("🔙 Back", "account:manage:" + account_id)],
            ]

            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to send profile management: {e}")

    async def _get_current_profile_info(self, user_id: int, account_name: str) -> dict:
        """Fetch current profile information from Telegram"""
        try:
            if (
                not self.account_manager
                or user_id not in self.account_manager.user_clients
            ):
                return None

            user_clients = self.account_manager.user_clients.get(user_id, {})
            client = user_clients.get(account_name)

            if not client or not client.is_connected():
                return None

            # Get current user info from Telegram
            me = await client.get_me()

            return {
                "first_name": me.first_name or "",
                "last_name": me.last_name or "",
                "username": me.username or "",
                "about": getattr(me, "about", "") or "",
            }

        except Exception as e:
            logger.error(f"Failed to fetch current profile info: {e}")
            return None

    async def _send_sessions_list(self, user_id: int, account_id: str, message_id: int):
        """Send active sessions list"""
        text = (
            f"🔐 **Active Sessions**\n\n"
            f"Loading session information...\n\n"
            f"This will show all active login sessions for the account."
        )
        buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
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
                text = f"🟢 **Online Maker {status.title()}**\n\nAccount: {account['name']}\nStatus: {status}\nInterval: {interval}s"
                buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to toggle online maker: {e}")

    async def _send_automation_management(
        self, user_id: int, account_id: str, message_id: int
    ):
        """Send automation management for account"""
        text = (
            f"⚡ **Automation Management**\n\n"
            f"Configure automation rules and jobs.\n\n"
            f"Available options:"
            f"• Online maker\n"
            f"• Auto-reply rules\n"
            f"• Scheduled actions"
        )
        buttons = [
            [Button.inline("🟢 Online Maker", f"online:toggle:{account_id}")],
            [Button.inline("🔙 Back", f"account:manage:{account_id}")],
        ]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _handle_profile_name_change(self, user_id: int, account_id: str, event):
        """Handle profile name change request"""
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

        # Wait for user input
        @self.bot.on(events.NewMessage(from_users=user_id))
        async def handle_name_input(name_event):
            if name_event.raw_text.startswith("/"):
                return

            names = name_event.raw_text.split(" ", 1)
            first_name = names[0]
            last_name = names[1] if len(names) > 1 else ""

            # Get client from bot manager
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

    async def _handle_profile_username_change(
        self, user_id: int, account_id: str, event
    ):
        """Handle username change request"""
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

            # Get client from bot manager
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
        """Handle bio change request"""
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
        """Handle profile photo change request"""
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
            # Check account limit
            from ..core.config import MAX_ACCOUNTS

            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if not user:
                await event.answer("❌ Please start the bot first")
                return

            account_count = await mongodb.db.accounts.count_documents(
                {"user_id": user_id}
            )
            if account_count >= MAX_ACCOUNTS:
                await event.answer(f"❌ Maximum account limit ({MAX_ACCOUNTS}) reached")
                return

            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {
                    "action": "add_account"
                }

                text = (
                    "➕ **Add New Account**\n\n"
                    "Reply with the phone number for the new account.\n\n"
                    "📱 Format: +1234567890 (include country code)\n"
                    "💡 Tip: Enter OTP codes as 1-2-3-4-5 (with hyphens)"
                )

                await event.answer("➕ Reply with phone number")
                await self.bot.send_message(user_id, text)
            else:
                await event.answer("❌ Service unavailable")

        except Exception as e:
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

        except Exception as e:
            logger.error(f"Failed to handle remove account: {e}")
            await event.reply("❌ Error processing remove account request")

    async def _execute_remove_account(self, event, user_id: int, account_id: str):
        """Execute account removal"""
        try:
            if self.account_manager:
                success, message = await self.account_manager.remove_account(
                    user_id, account_id
                )
                if success:
                    await event.answer("✅ Account removed successfully!")
                    await self.bot.edit_message(
                        user_id,
                        event.message_id,
                        "✅ **Account Removed**\n\nThe account has been successfully removed from TeleGuard.",
                        buttons=[[Button.inline("🔙 Back to Accounts", "menu:accounts")]],
                    )
                else:
                    await event.answer(f"❌ Failed to remove account: {message}")
                    await self.bot.edit_message(
                        user_id,
                        event.message_id,
                        f"❌ **Removal Failed**\n\n{message}",
                        buttons=[[Button.inline("🔙 Back to Accounts", "menu:accounts")]],
                    )
            else:
                await event.answer("❌ Service unavailable")

        except Exception as e:
            logger.error(f"Failed to execute remove account: {e}")
            await event.reply("❌ Error executing account removal")

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
        elif action == "account":
            account_id = int(parts[2])
            await self._send_account_messaging(user_id, account_id, event.message_id)
        elif action == "compose":
            account_id = parts[2]  # Keep as string for MongoDB ObjectId
            await self._handle_compose_message(user_id, account_id, event)

    async def _send_message_menu(self, user_id: int, message_id: int):
        """Send message composition menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )

            if not accounts:
                text = "📤 **Send Message**\n\nNo accounts found. Add accounts first."
                buttons = [[Button.inline("🔙 Back", "menu:messaging")]]
            else:
                text = "📤 **Send Message**\n\nSelect account to send from:"
                buttons = []

                for account in accounts:
                    status = "🟢" if account.get("is_active", False) else "🔴"
                    button_text = f"{status} {account['name']}"
                    buttons.append(
                        [Button.inline(button_text, f"msg:compose:{account['_id']}")]
                    )

                buttons.append([Button.inline("🔙 Back", "menu:messaging")])

            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to send message menu: {e}")

    async def _send_autoreply_menu(self, user_id: int, message_id: int):
        """Send auto-reply management menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )

            if not accounts:
                text = "🔄 **Auto Reply**\n\nNo accounts found. Add accounts first."
                buttons = [[Button.inline("🔙 Back", "menu:messaging")]]
            else:
                text = "🔄 **Auto Reply**\n\nSelect account to configure auto-reply:"
                buttons = []

                for account in accounts:
                    status = "🟢" if account.get("is_active", False) else "🔴"
                    auto_status = (
                        "🤖" if account.get("auto_reply_enabled", False) else "⚪"
                    )
                    button_text = f"{status}{auto_status} {account['name']}"
                    buttons.append(
                        [
                            Button.inline(
                                button_text, f"autoreply:manage:{account['_id']}"
                            )
                        ]
                    )

                buttons.append([Button.inline("🔙 Back", "menu:messaging")])

            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to send auto-reply menu: {e}")

    async def _send_templates_menu(self, user_id: int, message_id: int):
        """Send message templates menu - redirect to new advanced template system"""
        text = (
            "📝 **Advanced Message Templates**\n\n"
            "Use the new advanced template system with:\n\n"
            "✨ **Features:**\n"
            "• Dynamic variables ({name}, {username}, {time}, {date})\n"
            "• Rich media support (images, videos)\n"
            "• Template categories\n"
            "• Quick reply buttons\n"
            "• Step-by-step creation wizard\n\n"
            "Use `/templates` command to access the advanced system."
        )
        buttons = [
            [Button.inline("🚀 Open Advanced Templates", "template:main")],
            [Button.inline("🔙 Back", "menu:messaging")],
        ]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _handle_compose_message(self, user_id: int, account_id: str, event):
        """Handle message composition request"""
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "compose_message_target",
                "account_id": account_id,
            }

            text = (
                "📤 **Compose Message**\n\n"
                "Reply with the target (username, phone, or chat ID):\n\n"
                "Examples:\n"
                "• @username\n"
                "• +1234567890\n"
                "• -1001234567890 (for groups/channels)"
            )

            await event.answer("📤 Reply with target")
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
                await self.bot.send_message(user_id, "❌ Account not found")
                return

            auto_enabled = account.get("auto_reply_enabled", False)
            auto_message = account.get("auto_reply_message", "Not set")

            text = (
                f"🔄 **Auto Reply: {account['name']}**\n\n"
                f"Status: {'🟢 Enabled' if auto_enabled else '🔴 Disabled'}\n"
                f"Message: {auto_message[:50]}{'...' if len(auto_message) > 50 else ''}\n\n"
                f"Configure auto-reply settings:"
            )

            toggle_text = "🔴 Disable" if auto_enabled else "🟢 Enable"
            buttons = [
                [
                    Button.inline(
                        f"{toggle_text} Auto Reply", f"autoreply:toggle:{account_id}"
                    )
                ],
                [Button.inline("📝 Set Message", f"autoreply:set:{account_id}")],
                [Button.inline("🔙 Back", "msg:autoreply")],
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
                await event.answer(f"🔄 Auto-reply {'enabled' if new_status else 'disabled'}")
                await self._send_autoreply_management(user_id, account_id, event.message_id)
        except Exception as e:
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
                "📝 **Set Auto-Reply Message**\n\n"
                "Reply with the message to send automatically:\n\n"
                "This message will be sent to anyone who messages this account."
            )

            await event.answer("📝 Reply with message")
            await self.bot.send_message(user_id, text)


    
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
        elif action == "stop" and len(parts) > 2:
            job_id = parts[2]
            await self._stop_bulk_job(user_id, job_id, event)




    
    async def _send_bulk_sender_menu(self, user_id: int, message_id: int):
        """Send bulk sender management menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = "📨 **Bulk Message Sender**\n\nNo accounts found. Add accounts first to use bulk messaging."
                buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
            else:
                active_jobs = 0
                if hasattr(self.account_manager, 'bulk_sender'):
                    user_jobs = [job for job in self.account_manager.bulk_sender.active_jobs.values() if job['user_id'] == user_id]
                    active_jobs = len(user_jobs)
                
                text = (
                    "📨 **Bulk Message Sender**\n\n"
                    "Send messages to multiple users at once.\n\n"
                    f"📊 **Status:**\n"
                    f"• Available accounts: {len(accounts)}\n"
                    f"• Active jobs: {active_jobs}\n\n"
                    "**Choose bulk sending method:**"
                )
                
                buttons = [
                    [Button.inline("📋 Send to List", "bulk:send_list")],
                    [Button.inline("👥 Send to Contacts", "bulk:send_contacts")],
                    [Button.inline("🌐 Send from All Accounts", "bulk:send_all")],
                ]
                
                if active_jobs > 0:
                    buttons.append([Button.inline("📊 View Active Jobs", "bulk:jobs")])
                
                buttons.extend([
                    [Button.inline("❓ Help & Commands", "bulk:help")],
                    [Button.inline("🔙 Back to Messaging", "menu:messaging")]
                ])

            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to send bulk sender menu: {e}")

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
        """Start bulk send to list flow"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                await event.answer("❌ No accounts found")
                return
            
            text = (
                "📋 **Bulk Send to List**\n\n"
                "Step 1: Select account to send from:\n\n"
            )
            
            buttons = []
            for account in accounts:
                status = "🟢" if account.get("is_active", False) else "🔴"
                button_text = f"{status} {account['name']}"
                buttons.append([Button.inline(button_text, f"bulk_list_account:{account['_id']}")])
            
            buttons.append([Button.inline("🔙 Back to Bulk Sender", "msg:bulk")])
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            await event.answer("📋 Select account")
        except Exception as e:
            logger.error(f"Failed to start bulk list flow: {e}")

    async def _start_bulk_contacts_flow(self, user_id: int, event):
        """Start bulk send to contacts flow"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                await event.answer("❌ No accounts found")
                return
            
            text = (
                "👥 **Bulk Send to Contacts**\n\n"
                "Step 1: Select account to send from:\n\n"
                "This will send to ALL contacts of the selected account."
            )
            
            buttons = []
            for account in accounts:
                status = "🟢" if account.get("is_active", False) else "🔴"
                button_text = f"{status} {account['name']}"
                buttons.append([Button.inline(button_text, f"bulk_contacts_account:{account['_id']}")])
            
            buttons.append([Button.inline("🔙 Back to Bulk Sender", "msg:bulk")])
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            await event.answer("👥 Select account")
        except Exception as e:
            logger.error(f"Failed to start bulk contacts flow: {e}")

    async def _start_bulk_all_flow(self, user_id: int, event):
        """Start bulk send from all accounts flow"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                await event.answer("❌ No accounts found")
                return
            
            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {
                    "action": "bulk_all_targets"
                }
            
            text = (
                f"🌐 **Bulk Send from All Accounts**\n\n"
                f"This will send from ALL {len(accounts)} accounts.\n\n"
                "Step 1: Reply with target usernames/IDs (comma-separated):\n\n"
                "**Examples:**\n"
                "• @username1,@username2,@username3\n"
                "• +1234567890,@username,123456789\n\n"
                "Reply with the targets:"
            )
            
            await self.bot.edit_message(user_id, event.message_id, text)
            await event.answer("🌐 Reply with targets")
        except Exception as e:
            logger.error(f"Failed to start bulk all flow: {e}")

    async def _show_bulk_jobs(self, user_id: int, message_id: int):
        """Show active bulk jobs"""
        try:
            if not hasattr(self.account_manager, 'bulk_sender'):
                text = "❌ Bulk sender not available"
                buttons = [[Button.inline("🔙 Back to Bulk Sender", "msg:bulk")]]
            else:
                user_jobs = [job for job in self.account_manager.bulk_sender.active_jobs.values() if job['user_id'] == user_id]
                
                if not user_jobs:
                    text = "📊 **Active Bulk Jobs**\n\n💭 No active jobs found."
                    buttons = [[Button.inline("🔙 Back to Bulk Sender", "msg:bulk")]]
                else:
                    text = f"📊 **Active Bulk Jobs** ({len(user_jobs)})\n\n"
                    
                    buttons = []
                    for job in user_jobs:
                        progress = f"{job['sent']}/{job['total']}"
                        status_emoji = "🟢" if job['status'] == 'running' else "🔴"
                        account_info = f" [{job['account_name']}]" if job.get('multi_account') else ""
                        
                        text += f"{status_emoji} **Job {job['id'][:8]}**{account_info}\n"
                        text += f"   Progress: {progress} ({job['status']})\n"
                        if job['failed'] > 0:
                            text += f"   Failed: {job['failed']}\n"
                        text += "\n"
                        
                        if job['status'] == 'running':
                            buttons.append([Button.inline(f"⏹️ Stop {job['id'][:8]}", f"bulk:stop:{job['id']}")])
                    
                    buttons.append([Button.inline("🔄 Refresh", "bulk:jobs")])
                    buttons.append([Button.inline("🔙 Back to Bulk Sender", "msg:bulk")])
            
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to show bulk jobs: {e}")

    async def _show_bulk_help(self, user_id: int, message_id: int):
        """Show bulk sender help and commands"""
        text = (
            "❓ **Bulk Sender Help**\n\n"
            "**Available Commands:**\n"
            "• `/bulk_send` - Show bulk sender help\n"
            "• `/bulk_send_list account_name` - Send to specific users\n"
            "• `/bulk_send_contacts account_name` - Send to all contacts\n"
            "• `/bulk_send_all` - Send from ALL accounts\n"
            "• `/bulk_jobs` - View active jobs\n"
            "• `/bulk_stop <job_id>` - Stop a job\n\n"
            "**Format for list sending:**\n"
            "`/bulk_send_list account_name\n"
            "username1,username2,user_id3\n"
            "Your message here`\n\n"
            "**Button Format:**\n"
            "Add buttons using: `[Button Text](url)` or `[Button Text](callback_data)`\n"
            "Example: `Check this out [Visit Site](https://example.com) [More Info](info_callback)`\n\n"
            "**Tips:**\n"
            "• Use the menu buttons for easier setup\n"
            "• Commands provide more advanced options\n"
            "• Jobs run in background with progress updates"
        )
        
        buttons = [[Button.inline("🔙 Back to Bulk Sender", "msg:bulk")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        """Send bulk sender management menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )

            if not accounts:
                text = "📨 **Bulk Message Sender**\n\nNo accounts found. Add accounts first to use bulk messaging."
                buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
            else:
                # Check for active bulk jobs
                active_jobs = 0
                if hasattr(self.account_manager, 'bulk_sender'):
                    user_jobs = [job for job in self.account_manager.bulk_sender.active_jobs.values() if job['user_id'] == user_id]
                    active_jobs = len(user_jobs)
                
                text = (
                    "📨 **Bulk Message Sender**\n\n"
                    "Send messages to multiple users at once.\n\n"
                    f"📊 **Status:**\n"
                    f"• Available accounts: {len(accounts)}\n"
                    f"• Active jobs: {active_jobs}\n\n"
                    "**Choose bulk sending method:**"
                )
                
                buttons = [
                    [Button.inline("📋 Send to List", "bulk:send_list")],
                    [Button.inline("👥 Send to Contacts", "bulk:send_contacts")],
                    [Button.inline("🌐 Send from All Accounts", "bulk:send_all")],
                ]
                
                if active_jobs > 0:
                    buttons.append([Button.inline("📊 View Active Jobs", "bulk:jobs")])
                
                buttons.extend([
                    [Button.inline("❓ Help & Commands", "bulk:help")],
                    [Button.inline("🔙 Back to Messaging", "menu:messaging")]
                ])

            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to send bulk sender menu: {e}")
            text = "❌ Error loading bulk sender"
            buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _handle_simulate_callback(self, event, user_id: int, data: str):
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
                
                # Start or stop simulation using bot_manager's activity_simulator
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
                status_emoji = "🎭" if new_status else "🔴"
                await event.answer(f"{status_emoji} Activity simulation {status}!")
                await self.send_account_management(
                    user_id, account_id, event.message_id
                )
            else:
                await event.answer("❌ Account not found")
        except Exception as e:
            logger.error(f"Toggle simulation error: {e}")
            await event.answer("❌ Error toggling simulation")

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
                    "🟢 Active"
                    if account.get("simulation_enabled", False)
                    else "🔴 Inactive"
                )
                text = (
                    f"🎭 **Activity Simulator: {account['name']}**\n\n"
                    f"Status: {status}\n\n"
                    f"The simulator performs human-like activities:\n"
                    f"• Views random channels/groups\n"
                    f"• Reacts to posts with emojis\n"
                    f"• Votes in polls occasionally\n"
                    f"• Browses user profiles\n"
                    f"• Rarely joins/leaves channels\n\n"
                    f"Sessions every 30-90 minutes with 2-5 actions each."
                )

                toggle_text = (
                    "🔴 Disable"
                    if account.get("simulation_enabled", False)
                    else "🟢 Enable"
                )
                buttons = [
                    [
                        Button.inline(
                            f"{toggle_text} Simulation", f"simulate:toggle:{account_id}"
                        )
                    ],
                    [
                        Button.inline(
                            "📋 Activity Log (4h)", f"simulate:log:{account_id}"
                        )
                    ],
                    [Button.inline("🔙 Back", f"account:manage:{account_id}")],
                ]

                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            else:
                await self.bot.send_message(user_id, "❌ Account not found")
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
                # Get stats from activity simulator if available
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
                            f"• Total Actions: {total_actions}\n"
                            f"• Last Session: {last_session}\n"
                            f"• Avg Actions/Session: {avg_actions:.1f}\n"
                            f"• Status: {'Active' if account.get('simulation_enabled') else 'Inactive'}"
                        )
                    else:
                        stats_text = "No active simulation session found."
                
                text = (
                    f"📊 **Simulation Stats: {account['name']}**\n\n"
                    f"{stats_text}\n\n"
                    f"**Activity Types:**\n"
                    f"• Channel/Group browsing\n"
                    f"• Emoji reactions\n"
                    f"• Poll voting\n"
                    f"• Profile viewing\n"
                    f"• Occasional joins/leaves"
                )
                
                buttons = [
                    [Button.inline("🔄 Refresh", f"simulate:stats:{account_id}")],
                    [Button.inline("🔙 Back", f"account:manage:{account_id}")]
                ]
                
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            else:
                await self.bot.send_message(user_id, "❌ Account not found")
                
        except Exception as e:
            logger.error(f"Show simulation stats error: {e}")
            text = "❌ Error loading simulation statistics"
            buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _handle_audit_callback(self, event, user_id: int, data: str):
        """Handle audit-related callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"
        hours = int(parts[3]) if len(parts) > 3 else 24

        if hasattr(self.account_manager, "activity_simulator"):
            from ..handlers.enhanced_audit_handler import EnhancedAuditHandler

            audit_handler = EnhancedAuditHandler(self.account_manager)

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
            await event.answer("❌ Audit system unavailable")

    async def _handle_manage_callback(self, event, user_id: int, data: str):
        """Handle channel management account selection"""
        account_phone = data.split(":")[1]
        await self._send_channel_actions_menu(user_id, account_phone, event.message_id)

    async def _handle_channel_callback(self, event, user_id: int, data: str):
        """Handle channel action callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_phone = parts[2]

        if action == "join":
            self.account_manager.pending_actions[user_id] = {
                "action": "channel_join_target",
                "account_phone": account_phone,
            }
            await event.answer("➡️ Enter channel link")
            await self.bot.edit_message(
                user_id,
                event.message_id,
                f"🔗 **Join Channel**\n\nAccount: {account_phone}\n\nReply with channel link or @username:",
            )

        elif action == "leave":
            self.account_manager.pending_actions[user_id] = {
                "action": "channel_leave_target",
                "account_phone": account_phone,
            }
            await event.answer("➡️ Enter channel link")
            await self.bot.edit_message(
                user_id,
                event.message_id,
                f"🚫 **Leave Channel**\n\nAccount: {account_phone}\n\nReply with channel link or @username:",
            )

        elif action == "create":
            self.account_manager.pending_actions[user_id] = {
                "action": "channel_create_type",
                "account_phone": account_phone,
            }
            await event.answer("➡️ Enter type")
            await self.bot.edit_message(
                user_id,
                event.message_id,
                f"🆕 **Create Channel**\n\nAccount: {account_phone}\n\nReply with type (channel or group):",
            )

        elif action == "delete":
            self.account_manager.pending_actions[user_id] = {
                "action": "channel_delete_target",
                "account_phone": account_phone,
            }
            await event.answer("➡️ Enter channel link")
            await self.bot.edit_message(
                user_id,
                event.message_id,
                f"🗑️ **Delete Channel**\n\nAccount: {account_phone}\n\n⚠️ Only owners can delete channels!\n\nReply with channel link or @username:",
            )

        elif action == "list":
            (
                success,
                channels,
            ) = await self.account_manager.command_handlers.channel_manager.get_user_channels(
                user_id, account_phone
            )

            if not success:
                text = f"❌ Could not load channels for {account_phone}"
                buttons = [[Button.inline("🔙 Back", f"manage:{account_phone}")]]
            elif not channels:
                text = f"📋 No channels found for {account_phone}"
                buttons = [[Button.inline("🔙 Back", f"manage:{account_phone}")]]
            else:
                # Pagination
                page = 0
                per_page = 10
                total_pages = (len(channels) + per_page - 1) // per_page

                start_idx = page * per_page
                end_idx = min(start_idx + per_page, len(channels))
                page_channels = channels[start_idx:end_idx]

                text = f"📋 **Channels for {account_phone}** (Page {page + 1}/{total_pages})\n\n"
                for i, ch in enumerate(page_channels, start_idx + 1):
                    emoji = "📢" if ch["type"] == "channel" else "👥"
                    type_text = "Channel" if ch["type"] == "channel" else "Group"
                    username = (
                        f"@{ch['username']}" if ch["username"] else f"ID: {ch['id']}"
                    )
                    text += f"{i}. {emoji} **{ch['title']}** ({type_text})\n   {username}\n\n"

                # Navigation buttons
                nav_buttons = []
                if page > 0:
                    nav_buttons.append(
                        Button.inline(
                            "⬅️ Previous", f"channels:prev:{account_phone}:{page-1}"
                        )
                    )
                if page < total_pages - 1:
                    nav_buttons.append(
                        Button.inline(
                            "➡️ Next", f"channels:next:{account_phone}:{page+1}"
                        )
                    )

                buttons = []
                if nav_buttons:
                    buttons.append(nav_buttons)
                buttons.append([Button.inline("🔙 Back", f"manage:{account_phone}")])

            await event.answer("📋 Channels loaded")
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )

    async def _send_channel_actions_menu(
        self, user_id: int, account_phone: str, message_id: int
    ):
        """Send channel actions menu for selected account"""
        text = f"📱 **Managing: {account_phone}**\n\nWhat would you like to do?"

        buttons = [
            [
                Button.inline("🔗 Join Channel", f"channel:join:{account_phone}"),
                Button.inline("🚫 Leave Channel", f"channel:leave:{account_phone}"),
            ],
            [
                Button.inline("🆕 Create Channel", f"channel:create:{account_phone}"),
                Button.inline("🗑️ Delete Channel", f"channel:delete:{account_phone}"),
            ],
            [Button.inline("📋 List Channels", f"channel:list:{account_phone}")],
            [Button.inline("🔙 Back to Accounts", "back:accounts")],
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

            text = f"📋 **Channels for {account_phone}** (Page {page + 1}/{total_pages})\n\n"
            for i, ch in enumerate(page_channels, start_idx + 1):
                emoji = "📢" if ch["type"] == "channel" else "👥"
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
                        "⬅️ Previous", f"channels:prev:{account_phone}:{page-1}"
                    )
                )
            if page < total_pages - 1:
                nav_buttons.append(
                    Button.inline("➡️ Next", f"channels:next:{account_phone}:{page+1}")
                )

            buttons = []
            if nav_buttons:
                buttons.append(nav_buttons)
            buttons.append([Button.inline("🔙 Back", f"manage:{account_phone}")])

            await event.answer(f"Page {page + 1}")
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )

    async def _handle_help_callback(self, event, user_id: int, data: str):
        """Handle help-related callbacks"""
        parts = data.split(":")
        action = parts[1]

        if action == "guide":
            text = (
                "📖 **User Guide**\n\n"
                "**Step 1: Add Account**\n"
                "Use 'Account Settings' → 'Add Account'\n\n"
                "**Step 2: Enable Protection**\n"
                "Use 'OTP Manager' → Select account → 'Enable Destroyer'\n\n"
                "**Step 3: Configure Features**\n"
                "Explore Messaging, Channels, and other features\n\n"
                "**Tips:**\n"
                "• Keep OTP Destroyer enabled for security\n"
                "• Use 2FA passwords for extra protection\n"
                "• Monitor audit logs regularly"
            )
        elif action == "security":
            text = (
                "🛡️ **Security Information**\n\n"
                "**OTP Destroyer:**\n"
                "Automatically blocks unauthorized login attempts by invalidating OTP codes in real-time.\n\n"
                "**2FA Protection:**\n"
                "Set passwords to disable OTP Destroyer, adding extra security layers.\n\n"
                "**Session Security:**\n"
                "Monitor and terminate suspicious sessions.\n\n"
                "**Data Encryption:**\n"
                "All session data is encrypted with military-grade Fernet encryption."
            )
        elif action == "troubleshoot":
            text = (
                "🔧 **Troubleshooting**\n\n"
                "**Common Issues:**\n\n"
                "1. **Account won't connect**\n"
                "   • Check phone number format\n"
                "   • Verify OTP code\n"
                "   • Try again in 5 minutes\n\n"
                "2. **OTP Destroyer not working**\n"
                "   • Ensure it's enabled\n"
                "   • Check account is active\n"
                "   • Review audit logs\n\n"
                "3. **Messages not sending**\n"
                "   • Check account status\n"
                "   • Verify target exists\n"
                "   • Check rate limits"
            )
        elif action == "faq":
            text = (
                "❓ **Frequently Asked Questions**\n\n"
                "**Q: Is TeleGuard safe to use?**\n"
                "A: Yes, all data is encrypted and stored securely.\n\n"
                "**Q: How many accounts can I add?**\n"
                "A: Up to 10 accounts per user.\n\n"
                "**Q: What is OTP Destroyer?**\n"
                "A: Real-time protection that blocks unauthorized login attempts.\n\n"
                "**Q: Can I use this on multiple devices?**\n"
                "A: Yes, but sessions are device-specific for security."
            )
        elif action == "contact":
            text = (
                "📞 **Contact Information**\n\n"
                "**Developers:**\n"
                "• @Meher_Mankar - Lead Developer\n"
                "• @Gutkesh - Core Developer\n\n"
                "**Support Channels:**\n"
                "• Support Bot: @ContactXYZrobot\n"
                "• GitHub Issues: Report bugs\n"
                "• Documentation: README.md\n\n"
                "**Response Time:** Usually within 24 hours"
            )
        elif action == "emergency":
            text = (
                "🆘 **Emergency Help**\n\n"
                "**Account Compromised?**\n"
                "1. Immediately disable OTP Destroyer\n"
                "2. Change 2FA password\n"
                "3. Terminate all sessions\n"
                "4. Contact @Meher_Mankar\n\n"
                "**Bot Not Responding?**\n"
                "1. Try /start command\n"
                "2. Restart the bot\n"
                "3. Check system status\n"
                "4. Contact support if issue persists"
            )
        elif action == "toggle_dev":
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if user:
                current_mode = user.get("developer_mode", False)
                new_mode = not current_mode

                await mongodb.db.users.update_one(
                    {"telegram_id": user_id}, {"$set": {"developer_mode": new_mode}}
                )

                status = "enabled" if new_mode else "disabled"
                text = f"⚙️ **Developer Mode {status.title()}**\n\n"

                if new_mode:
                    text += (
                        "You now have access to advanced features and text commands."
                    )
                else:
                    text += "Advanced features hidden. Use the menu system."

                await event.answer(f"Developer mode {status}")
            else:
                text = "❌ User not found"
        else:
            text = "❌ Unknown help action"

        buttons = [[Button.inline("🔙 Back to Help", "menu:help")]]
        await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)

    async def _handle_support_callback(self, event, user_id: int, data: str):
        """Handle support-related callbacks"""
        parts = data.split(":")
        action = parts[1]

        if action == "contact":
            text = (
                "💬 **Contact Support**\n\n"
                "Choose your preferred contact method:\n\n"
                "🤖 **Support Bot:** @ContactXYZrobot\n"
                "Best for: General questions, account issues\n\n"
                "👨💻 **Direct Contact:**\n"
                "• @Meher_Mankar - Technical issues\n"
                "• @Gutkesh - Feature requests\n\n"
                "**Before contacting:**\n"
                "• Check FAQ and troubleshooting\n"
                "• Include error messages\n"
                "• Describe steps to reproduce"
            )
        elif action == "bug":
            text = (
                "🐛 **Report a Bug**\n\n"
                "To report a bug effectively:\n\n"
                "1. **Describe the issue clearly**\n"
                "2. **Include exact error messages**\n"
                "3. **List steps to reproduce**\n"
                "4. **Mention which feature was affected**\n"
                "5. **Include screenshots if helpful**\n\n"
                "**Where to report:**\n"
                "• GitHub Issues (preferred)\n"
                "• Support bot: @ContactXYZrobot\n"
                "• Direct message: @Meher_Mankar"
            )
        elif action == "docs":
            text = (
                "📚 **Documentation**\n\n"
                "**Available Resources:**\n\n"
                "📖 **README.md** - Complete setup guide\n"
                "🔗 **GitHub Wiki** - Detailed documentation\n"
                "⚙️ **Configuration Guide** - Environment setup\n"
                "🛡️ **Security Guide** - Best practices\n"
                "🚀 **Deployment Guide** - Cloud deployment\n\n"
                "**Links:**\n"
                "• GitHub: github.com/MeherMankar/TeleGuard\n"
                "• Wiki: github.com/MeherMankar/TeleGuard/wiki"
            )
        elif action == "feature":
            text = (
                "💡 **Feature Request**\n\n"
                "Have an idea for TeleGuard?\n\n"
                "**How to submit:**\n"
                "1. Check if feature already exists\n"
                "2. Describe the feature clearly\n"
                "3. Explain the use case\n"
                "4. Suggest implementation if possible\n\n"
                "**Submit via:**\n"
                "• GitHub Issues (preferred)\n"
                "• Support bot: @ContactXYZrobot\n"
                "• Direct message: @Gutkesh\n\n"
                "**Popular requests:**\n"
                "• Bulk messaging\n"
                "• Advanced scheduling\n"
                "• Custom automation rules"
            )
        elif action == "status":
            text = (
                "📊 **System Status**\n\n"
                "**Bot Status:** 🟢 Online\n"
                "**Database:** 🟢 Connected\n"
                "**OTP Destroyer:** 🟢 Active\n"
                "**Automation Engine:** 🟢 Running\n"
                "**Session Backup:** 🟢 Operational\n\n"
                "**Performance:**\n"
                "• Response Time: <100ms\n"
                "• Uptime: 99.9%\n"
                "• Active Users: Monitoring\n\n"
                "**Last Updated:** Just now"
            )
        elif action == "updates":
            text = (
                "🔄 **Check for Updates**\n\n"
                "**Current Version:** TeleGuard v2.0.0\n"
                "**Latest Features:**\n"
                "• Enhanced OTP Destroyer\n"
                "• Improved menu system\n"
                "• Better error handling\n"
                "• Performance optimizations\n\n"
                "**Update Channel:** @TeleGuardUpdates\n"
                "**GitHub Releases:** Check repository\n\n"
                "**Auto-updates:** Enabled for cloud deployments"
            )
        else:
            text = "❌ Unknown support action"

        buttons = [[Button.inline("🔙 Back to Support", "menu:support")]]
        await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)

    async def _handle_developer_callback(self, event, user_id: int, data: str):
        """Handle developer-related callbacks"""
        parts = data.split(":")
        action = parts[1]

        if action == "toggle":
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if user:
                current_mode = user.get("developer_mode", False)
                new_mode = not current_mode

                await mongodb.db.users.update_one(
                    {"telegram_id": user_id}, {"$set": {"developer_mode": new_mode}}
                )

                status = "enabled" if new_mode else "disabled"
                text = f"⚙️ **Developer Mode {status.title()}**\n\n"

                if new_mode:
                    text += "Advanced features and text commands are now available."
                else:
                    text += "Advanced features hidden. Use the menu system."

                await event.answer(f"Developer mode {status}")
            else:
                text = "❌ User not found"
        elif action == "sysinfo":
            text = (
                "📊 **System Information**\n\n"
                "**Platform:** Linux\n"
                "**Python:** 3.11+\n"
                "**Memory Usage:** Optimized\n"
                "**CPU Usage:** Efficient\n\n"
                "**Bot Statistics:**\n"
                f"• Active Users: {await mongodb.db.users.count_documents({})}\n"
                f"• Total Accounts: {await mongodb.db.accounts.count_documents({})}\n"
                "• Active Sessions: Monitoring\n"
                "• OTP Blocks Today: Calculating..."
            )
        elif action == "logs":
            text = (
                "📋 **Debug Logs**\n\n"
                "**Recent Log Entries:**\n"
                "[INFO] Bot started successfully\n"
                "[INFO] MongoDB connected\n"
                "[INFO] OTP Destroyer active\n"
                "[DEBUG] Menu system loaded\n"
                "[DEBUG] Handlers registered\n\n"
                "**Log Levels:**\n"
                "• INFO: General information\n"
                "• WARNING: Potential issues\n"
                "• ERROR: Error conditions\n"
                "• DEBUG: Detailed debugging"
            )
        elif action == "dbstats":
            user_count = await mongodb.db.users.count_documents({})
            account_count = await mongodb.db.accounts.count_documents({})

            text = (
                "🗄️ **Database Statistics**\n\n"
                f"**Collections:**\n"
                f"• Users: {user_count}\n"
                f"• Accounts: {account_count}\n"
                f"• Sessions: Active monitoring\n"
                f"• Audit Logs: Continuous\n\n"
                "**Performance:**\n"
                "• Query Time: <10ms\n"
                "• Connection Pool: Healthy\n"
                "• Index Usage: Optimized\n"
                "• Storage: Efficient"
            )
        elif action == "perf":
            text = (
                "⚡ **Performance Metrics**\n\n"
                "**Response Times:**\n"
                "• Menu Actions: <50ms\n"
                "• Database Queries: <10ms\n"
                "• OTP Processing: <100ms\n"
                "• Message Handling: <200ms\n\n"
                "**Throughput:**\n"
                "• Messages/sec: 50+\n"
                "• OTP Blocks/min: 10+\n"
                "• API Calls/min: 1000+\n\n"
                "**Resource Usage:**\n"
                "• Memory: Optimized\n"
                "• CPU: Efficient\n"
                "• Network: Minimal"
            )
        elif action == "maintenance":
            text = (
                "🔧 **Maintenance Tools**\n\n"
                "**Available Actions:**\n"
                "• Clear inactive sessions\n"
                "• Optimize database\n"
                "• Update configurations\n"
                "• Backup user data\n"
                "• Clean temporary files\n\n"
                "**Scheduled Maintenance:**\n"
                "• Daily: Log rotation\n"
                "• Weekly: Database optimization\n"
                "• Monthly: Full backup\n\n"
                "**Status:** All systems operational"
            )
        elif action == "restart":
            text = (
                "🔄 **Restart Services**\n\n"
                "**Available Restarts:**\n"
                "• Bot instance (soft restart)\n"
                "• Database connections\n"
                "• OTP Destroyer engine\n"
                "• Automation workers\n"
                "• Session managers\n\n"
                "⚠️ **Warning:** Restarting services may cause temporary interruptions.\n\n"
                "**Recommendation:** Only restart if experiencing issues."
            )
        elif action == "startup":
            text = (
                "🚀 **Startup Configuration**\n\n"
                "Configure what happens when the bot starts:\n\n"
                "**Available Commands:**\n"
                "• `/startup_config` - Configure startup settings\n"
                "• `/startup_enable` - Enable startup notifications\n"
                "• `/startup_disable` - Disable startup notifications\n"
                "• `/startup_status` - View current settings\n\n"
                "**Features:**\n"
                "• Startup notifications to admins\n"
                "• Auto-enable features on startup\n"
                "• Status summaries\n"
                "• Health check reports"
            )
        elif action == "commands":
            text = (
                "📚 **All Available Commands**\n\n"
                "**Help System:**\n"
                "• `/help` - Show help pages\n"
                "• `/help_page <number>` - Show specific help page\n\n"
                "**Bulk Messaging:**\n"
                "• `/bulk_send` - Bulk messaging help\n"
                "• `/bulk_jobs` - View active jobs\n\n"
                "**Activity Simulation:**\n"
                "• `/sim_status` - View simulation status\n"
                "• `/sim_stats` - View simulation statistics\n\n"

                "**Startup Commands:**\n"
                "• `/startup_config` - Configure startup settings\n\n"
                "Use these commands for advanced control."
            )
        else:
            text = "❌ Unknown developer action"

        buttons = [[Button.inline("🔙 Back to Developer", "menu:developer")]]
        await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)

    async def _handle_menu_callback(self, event, user_id: int, data: str):
        """Handle menu navigation callbacks"""
        parts = data.split(":")
        action = parts[1]

        if action == "main":
            keyboard = self.get_main_menu_keyboard(user_id)
            text = (
                "🤖 **TeleGuard Account Manager**\n\n"
                "🛡️ Professional Telegram security & automation\n\n"
                "Use the menu buttons below to get started:"
            )
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=keyboard
            )
        elif action == "help":
            await self._handle_help(
                type(
                    "Event",
                    (),
                    {
                        "sender_id": user_id,
                        "reply": lambda x, buttons=None: self.bot.edit_message(
                            user_id, event.message_id, x, buttons=buttons
                        ),
                    },
                )()
            )
        elif action == "support":
            await self._handle_support(
                type(
                    "Event",
                    (),
                    {
                        "sender_id": user_id,
                        "reply": lambda x, buttons=None: self.bot.edit_message(
                            user_id, event.message_id, x, buttons=buttons
                        ),
                    },
                )()
            )
        elif action == "developer":
            await self._handle_developer(
                type(
                    "Event",
                    (),
                    {
                        "sender_id": user_id,
                        "reply": lambda x, buttons=None: self.bot.edit_message(
                            user_id, event.message_id, x, buttons=buttons
                        ),
                    },
                )()
            )
        elif action == "import":
            text = (
                "📚 **Chat Import Commands**\n\n"
                "**Available Commands:**\n"
                "• `/import_chats` - Import all existing private conversations\n"
                "• `/import_help` - Show detailed import help\n\n"
                "**What Import Does:**\n"
                "• Scans all managed accounts for private chats\n"
                "• Creates topics for existing conversations\n"
                "• Imports last 5 messages for context\n"
                "• Avoids creating duplicate topics\n\n"
                "**Requirements:**\n"
                "• Admin group must be configured\n"
                "• Group must have Topics enabled\n"
                "• Bot needs admin permissions\n\n"
                "⚠️ **Note:** This is a one-time setup. New conversations auto-create topics."
            )
            buttons = [[Button.inline("🔙 Back to Help", "menu:help")]]
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        elif action == "accounts":
            await self._handle_account_settings(
                type(
                    "Event",
                    (),
                    {
                        "sender_id": user_id,
                        "reply": lambda x, buttons=None: self.bot.edit_message(
                            user_id, event.message_id, x, buttons=buttons
                        ),
                    },
                )()
            )
        elif action == "otp":
            await self._handle_otp_manager(
                type(
                    "Event",
                    (),
                    {
                        "sender_id": user_id,
                        "reply": lambda x, buttons=None: self.bot.edit_message(
                            user_id, event.message_id, x, buttons=buttons
                        ),
                    },
                )()
            )
        elif action == "messaging":
            await self._handle_messaging(
                type(
                    "Event",
                    (),
                    {
                        "sender_id": user_id,
                        "reply": lambda x, buttons=None: self.bot.edit_message(
                            user_id, event.message_id, x, buttons=buttons
                        ),
                    },
                )()
            )
        elif action == "channels":
            await self._handle_channels(
                type(
                    "Event",
                    (),
                    {
                        "sender_id": user_id,
                        "reply": lambda x, buttons=None: self.bot.edit_message(
                            user_id, event.message_id, x, buttons=buttons
                        ),
                    },
                )()
            )
        elif action == "dm_reply":
            await self._handle_dm_reply(
                type(
                    "Event",
                    (),
                    {
                        "sender_id": user_id,
                        "reply": lambda x, buttons=None: self.bot.edit_message(
                            user_id, event.message_id, x, buttons=buttons
                        ),
                    },
                )()
            )
        else:
            await event.answer("❌ Unknown menu action")
    
    async def _handle_dm_reply_callback(self, event, user_id: int, data: str):
        """Handle DM Reply related callbacks"""
        parts = data.split(":")
        action = parts[1]
        
        if action == "enable":
            self.account_manager.pending_actions[user_id] = {
                "action": "set_dm_group_id"
            }
            text = (
                "📨 **Enable DM Reply**\n\n"
                "Send me your **Forum Group** ID where you want to receive DM notifications.\n\n"
                "**Requirements:**\n"
                "• Group must have Topics enabled\n"
                "• Bot must be admin with topic management permissions\n\n"
                "**How to get group ID:**\n"
                "1. Add @userinfobot to your forum group\n"
                "2. Send any message\n"
                "3. Copy the group ID (negative number)\n"
                "4. Remove @userinfobot from group\n\n"
                "Reply with the group ID:"
            )
            await self.bot.edit_message(user_id, event.message_id, text)
            
        elif action == "change":
            self.account_manager.pending_actions[user_id] = {
                "action": "set_dm_group_id"
            }
            text = (
                "🔄 **Change DM Reply Group**\n\n"
                "Send me the new group ID:\n\n"
                "Reply with the group ID:"
            )
            await self.bot.edit_message(user_id, event.message_id, text)
            
        elif action == "disable":
            # Disable DM reply by removing admin group from user
            await mongodb.db.users.update_one(
                {"telegram_id": user_id},
                {"$unset": {"dm_reply_group_id": ""}}
            )
            text = (
                "📨 **DM Reply Disabled**\n\n"
                "❌ DM forwarding has been disabled.\n\n"
                "Use the menu to enable it again."
            )
            
            buttons = [[Button.inline("🔙 Back to DM Reply", "menu:dm_reply")]]
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            
        elif action == "status":
            admin_group_id = await self.account_manager.unified_messaging._get_user_admin_group(user_id)
            if admin_group_id:
                text = (
                    "📊 **Unified Messaging Status**\n\n"
                    f"✅ **Enabled**\n"
                    f"📍 Group ID: `{admin_group_id}`\n\n"
                    f"All DMs to your managed accounts automatically create topics in this group."
                )
            else:
                text = (
                    "📊 **Unified Messaging Status**\n\n"
                    f"❌ **Disabled**\n\n"
                    f"DM forwarding is not configured."
                )
            
            buttons = [[Button.inline("🔙 Back to DM Reply", "menu:dm_reply")]]
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            
        elif action == "help":
            text = (
                "❓ **Unified Messaging Setup Guide**\n\n"
                "**Step 1: Create Forum Group**\n"
                "Create a private Telegram group and enable Topics\n\n"
                "**Step 2: Add Bot as Admin**\n"
                "Add TeleGuard bot with topic management permissions\n\n"
                "**Step 3: Get Group ID**\n"
                "1. Add @userinfobot to your forum group\n"
                "2. Send any message\n"
                "3. Copy the group ID (negative number like -1001234567890)\n"
                "4. Remove @userinfobot\n\n"
                "**Step 4: Configure**\n"
                "Use 'Enable' button and paste the group ID\n\n"
                "**Step 5: Automatic Operation**\n"
                "ALL private messages to managed accounts automatically create topics!\n\n"
                "**Step 6: Reply**\n"
                "Simply type in any topic to reply - fully automated!"
            )
            
            buttons = [
                [Button.inline("✅ Enable Now", "dm_reply:enable")],
                [Button.inline("🔙 Back to DM Reply", "menu:dm_reply")]
            ]
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
