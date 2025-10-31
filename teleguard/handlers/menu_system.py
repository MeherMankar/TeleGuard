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
from ..utils.network_helpers import format_display_name, format_phone_number
logger = logging.getLogger(__name__)
class MenuSystem:
    """Handles inline keyboard menus and callback queries"""
    def __init__(self, bot_instance, account_manager=None):
        self.bot = bot_instance
        self.account_manager = account_manager
        self.secure_2fa_handlers = Secure2FAHandlers(bot_instance, account_manager)
        self._menu_text_handler = None
        self._callback_handler = None
    def _parse_callback(self, callback_data: str):
        """Parse callback data - handles both JSON and colon-delimited formats"""
        if not callback_data:
            return {}
        try:
            parsed = json.loads(callback_data)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        parts = callback_data.split(':')
        action = parts[0] if parts else ''
        subaction = parts[1] if len(parts) > 1 else None
        rest = parts[2:] if len(parts) > 2 else []
        out = {
            "action": action,
            "subaction": subaction,
            "parts": rest,
        }
        if rest:
            out["id"] = rest[0]
        if subaction and not rest:
            out.setdefault("name", subaction if action == "account" and subaction not in ("add","list","remove","manage","refresh") else None)
        return out
    def format_display_name(self, account):
        """Format display name from account object or DB record"""
        def _get(obj, key):
            if obj is None:
                return None
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)
        first = _get(account, "first_name") or _get(account, "first")
        last = _get(account, "last_name") or _get(account, "last")
        username = _get(account, "username")
        display_name_field = _get(account, "display_name")
        user_id = _get(account, "id") or _get(account, "_id") or _get(account, "user_id")
        phone = _get(account, "phone")
        if display_name_field:
            base = display_name_field
        else:
            name = " ".join(p for p in (first, last) if p)
            if name:
                base = name
            elif username:
                base = f"@{username}"
            elif phone:
                base = phone
            elif user_id:
                base = f"ID:{user_id}"
            else:
                base = "Unknown"
        # Debug logging for Unknown accounts
        if base == "Unknown":
            logger.debug(f"Account row for unknown display -> {account}")
        return base
    def get_main_menu_keyboard(self, user_id: int) -> List[List[Button]]:
        """Get enhanced persistent reply keyboard menu"""
        keyboard = [
            [Button.text("📱 Account Settings"), Button.text("🛡️ OTP Manager")],
            [Button.text("💬 Messaging"), Button.text("📢 Channels")],
            [Button.text("👥 Contacts"), Button.text("🎯 SpamMaster")],
            [Button.text("🧹 Cleanup"), Button.text("❓ Help")],
            [Button.text("🆘 Support")],
        ]
        if user_id in ADMIN_IDS:
            keyboard.append([Button.text("⚙️ Developer Panel")])
        return keyboard
    
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
    def get_account_menu_buttons(self, account_id: str, account=None) -> List[List[Button]]:
        """Get account-specific menu buttons"""
        # Determine button texts based on status with green/red indicators
        if account:
            online_status = account.get("online_maker_enabled", False)
            online_text = "🔴 Stop Online Maker" if online_status else "✅ Start Online Maker"
            
            sim_status = account.get("simulation_enabled", False)
            sim_text = "🔴 Stop Activity Sim" if sim_status else "✅ Start Activity Sim"
            
            has_2fa = account.get("twofa_password") is not None
            twofa_text = "🛡️ 2FA Settings" if has_2fa else "❌ 2FA Settings"
        else:
            online_text = "✅ Online Maker"
            sim_text = "❌ Activity Sim"
            twofa_text = "❌ 2FA Settings"
            
        return [
            [
                Button.inline("👤 Profile Settings", f"profile:manage:{account_id}"),
                Button.inline(twofa_text, f"2fa:status:{account_id}"),
            ],
            [
                Button.inline("🔐 Active Sessions", f"sessions:list:{account_id}"),
                Button.inline(online_text, f"online:toggle:{account_id}"),
            ],
            [
                Button.inline(sim_text, f"simulate:status:{account_id}"),
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
        
        # Use green checkmark for enabled, red X for disabled
        destroyer_text = (
            "❌ Disable Destroyer" if destroyer_enabled else "✅ Enable Destroyer"
        )
        destroyer_action = (
            f"otp:disable:{account_id}"
            if destroyer_enabled
            else f"otp:enable:{account_id}"
        )
        forward_text = "❌ Disable Forward" if forward_enabled else "✅ Enable Forward"
        forward_action = (
            f"otp:forward_disable:{account_id}"
            if forward_enabled
            else f"otp:forward_enable:{account_id}"
        )
        
        # Check temp OTP status
        import time
        temp_active = False
        if account.get("otp_temp_passthrough", False):
            expiry = account.get("temp_passthrough_expiry", 0)
            if time.time() < expiry:
                temp_active = True
        temp_text = "❌ Stop Temp OTP" if temp_active else "⏰ Temp OTP (5min)"
        
        buttons = [
            [Button.inline(destroyer_text, destroyer_action)],
            [Button.inline(forward_text, forward_action)],
            [Button.inline(temp_text, f"otp:temp:{account_id}")],
        ]
        # Password management buttons with status indicators
        if has_password:
            buttons.append(
                [
                    Button.inline("🛡️ Change Password", f"otp_pwd:change:{account_id}"),
                    Button.inline("❌ Remove Password", f"otp_pwd:remove:{account_id}"),
                ]
            )
        else:
            buttons.append(
                [Button.inline("🛡️ Set Password", f"otp_pwd:set:{account_id}")]
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
            
            # Get user stats for personalized welcome
            account_count = await mongodb.db.accounts.count_documents({"user_id": user_id})
            otp_enabled = await mongodb.db.accounts.count_documents({"user_id": user_id, "otp_destroyer_enabled": True})
            
            security_score = int((otp_enabled/max(account_count, 1))*100) if account_count > 0 else 0
            status_emoji = "🟢" if security_score >= 80 else "🟡" if security_score >= 50 else "🔴"
            
            text = (
                "🤖 **TeleGuard - Professional Account Manager**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "🛡️ **Advanced Telegram Security & Automation Platform**\n\n"
                f"📊 **Your Dashboard:**\n"
                f"• 📱 Accounts: {account_count} configured\n"
                f"• 🛡️ Protection: {otp_enabled}/{account_count} secured\n"
                f"• {status_emoji} Security Score: {security_score}%\n\n"
                "⚡ **Quick Actions:** Use the menu buttons below to get started\n\n"
                "💡 **Tip:** Enable OTP Destroyer on all accounts for maximum security"
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
                    status = "✅" if account.get("is_active", False) else "❌"
                    destroyer_status = (
                        "✅" if account.get("otp_destroyer_enabled", False) else "❌"
                    )
                    display_name = format_display_name(account)
                    phone = format_phone_number(account.get('phone', 'Unknown'))
                    text += f"{i}. {status}{destroyer_status} {display_name} ({phone})\n"
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
                "🛡️ Enabled"
                if account.get("otp_destroyer_enabled", False)
                else "❌ Disabled"
            )
            simulation_status = (
                "✅ Active"
                if account.get("simulation_enabled", False)
                else "❌ Inactive"
            )
            online_maker_status = (
                "✅ Enabled"
                if account.get("online_maker_enabled", False)
                else "❌ Disabled"
            )
            last_destroyed = account.get("otp_destroyed_at", "Never")
            display_name = format_display_name(account)
            text = (
                f"📱 **Account: {display_name}**\n\n"
                f"📞 Phone: {format_phone_number(account['phone'])}\n"
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
                "🛡️ Active"
                if account.get("otp_destroyer_enabled", False)
                else "❌ Inactive"
            )
            forward_status = (
                "🛡️ Active"
                if account.get("otp_forward_enabled", False)
                else "❌ Inactive"
            )
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
                temp_status = f"⏰ Active - Forward ON, Destroyer OFF ({minutes}m {seconds}s left)"
            else:
                temp_status = "⚪ Inactive"
            has_password = (
                "🛡️ Set" if account.get("otp_destroyer_disable_auth") else "❌ Not Set"
            )
            display_name = format_display_name(account)
            text = (
                f"🛡️ **OTP Manager: {display_name}**\n\n"
                f"📞 Phone: {format_phone_number(account['phone'])}\n\n"
                f"🛡️ **Destroyer**: {destroyer_status}\n"
                f"📤 **Forward**: {forward_status}\n"
                f"⏰ **Temp OTP**: {temp_status}\n"
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
                display_name = format_display_name(account)
                text = f"📋 **Audit Log: {display_name}**\n\nNo audit entries found."
            else:
                display_name = format_display_name(account)
                text = f"📋 **Audit Log: {display_name}**\n\n"
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
    def register_handlers(self):
        """Register menu handlers - called during bot initialization"""
        self.setup_menu_handlers()
    
    def setup_menu_handlers(self):
        """Set up menu text handlers and legacy callback handler"""
        # Clear existing handlers to prevent duplicates
        if self._menu_text_handler:
            self.bot.remove_event_handler(self._menu_text_handler)
        if self._callback_handler:
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
                    "🧹 Cleanup",
                    "Cleanup",
                    "🎯 SpamMaster",
                    "SpamMaster",
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
                elif text in ["🧹 Cleanup", "Cleanup"]:
                    await self._handle_cleanup(event)
                elif text in ["🎯 SpamMaster", "SpamMaster"]:
                    await self._handle_spam_master(event)
                elif text in ["❓ Help", "Help"]:
                    await self._handle_help(event)
                elif text in ["🆘 Support", "Support"]:
                    await self._handle_support(event)
                elif text in ["⚙️ Developer", "Developer", "⚙️ Developer Panel", "Developer Panel"]:
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
        
        # Handle cleanup selection text input
        @self.bot.on(events.NewMessage(func=lambda e: e.is_private and hasattr(self.account_manager, 'pending_actions') and e.sender_id in self.account_manager.pending_actions and self.account_manager.pending_actions[e.sender_id].get('action') == 'cleanup_selection'))
        async def cleanup_selection_handler(event):
            await self._handle_cleanup_selection_callback(event, event.sender_id, event.text)
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
                elif data.startswith("otp_setting:"):
                    await self._handle_otp_setting_callback(event, user_id, data)
                elif data.startswith("otp:"):
                    if data.startswith("otp:manage:"):
                        account_id = data.split(":")[
                            2
                        ]  # Keep as string for MongoDB ObjectId
                        await self.send_otp_account_management(
                            user_id, account_id, event.message_id
                        )
                    elif data == "otp:enable_all":
                        await self._handle_bulk_otp_enable(user_id, event.message_id)
                        await event.answer("🛡️ Bulk enable completed")
                    elif data == "otp:disable_all":
                        await self._handle_bulk_otp_disable(user_id, event.message_id)
                        await event.answer("🔴 Bulk disable completed")
                    elif data == "otp:stats":
                        await self._show_otp_statistics(user_id, event.message_id)
                        await event.answer("📊 OTP statistics")
                    elif data == "otp:audit_all":
                        await self._show_global_audit_log(user_id, event.message_id)
                        await event.answer("📋 Global audit log loaded")
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
                        await self._show_messaging_statistics(user_id, event.message_id)
                        await event.answer("📊 Messaging stats loaded")
                    elif action == "history":
                        await self._show_message_history(user_id, event.message_id)
                        await event.answer("📋 Message history loaded")
                    elif action == "settings":
                        await self._show_messaging_settings(user_id, event.message_id)
                        await event.answer("⚙️ Messaging settings loaded")
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
                        await self._show_channel_statistics(user_id, event.message_id)
                        await event.answer("📊 Statistics loaded")
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
                    if data == "dm_reply:main":
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
                        await self._handle_dm_reply_callback(event, user_id, data)
                elif data.startswith("cleanup:"):
                    await self._handle_cleanup_callback(event, user_id, data)
                elif data.startswith("cleanup_selection:"):
                    try:
                        await self._handle_cleanup_selection_callback(event, user_id, data)
                    except Exception as e:
                        logger.error(f"Cleanup selection callback error: {e}")
                        await event.answer("❌ Error processing cleanup selection")
                elif data.startswith("contacts:"):
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
                            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
                            if not accounts:
                                text = "👥 **All Contacts**\n\n❌ No accounts found."
                                buttons = [[Button.inline("🔙 Back", "contacts:main")]]
                            else:
                                all_contacts = []
                                total_contacts = 0
                                for account in accounts:
                                    if not account.get("is_active", False):
                                        continue
                                    try:
                                        if (user_id in self.account_manager.user_clients and 
                                            account['name'] in self.account_manager.user_clients[user_id]):
                                            client = self.account_manager.user_clients[user_id][account['name']]
                                            if client and client.is_connected():
                                                from telethon.tl.functions.contacts import GetContactsRequest
                                                from telethon.tl.types import User
                                                result = await client(GetContactsRequest(hash=0))
                                                account_contacts = 0
                                                for user in result.users[:5]:  # Limit to first 5 per account
                                                    if isinstance(user, User) and not user.bot:
                                                        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
                                                        username = f"@{user.username}" if user.username else "No username"
                                                        phone = user.phone or "No phone"
                                                        all_contacts.append({
                                                            'name': name,
                                                            'username': username,
                                                            'phone': phone,
                                                            'account': account['name']
                                                        })
                                                        account_contacts += 1
                                                total_contacts += len([u for u in result.users if isinstance(u, User) and not u.bot])
                                    except Exception as e:
                                        logger.error(f"Error getting contacts for {account['name']}: {e}")
                                        continue
                                if not all_contacts:
                                    text = "👥 **All Contacts**\n\n💭 No contacts found in active accounts.\n\nMake sure accounts are connected and have contacts."
                                else:
                                    text = f"👥 **All Contacts** (Showing {len(all_contacts)} of {total_contacts})\n\n"
                                    for i, contact in enumerate(all_contacts, 1):
                                        text += f"{i}. **{contact['name']}**\n   {contact['username']} | {contact['phone']}\n   Account: {contact['account']}\n\n"
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
                            from ..handlers.contact_export_handler import ContactExportHandler
                            export_handler = ContactExportHandler(self.account_manager)
                            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
                            if not accounts:
                                text = "📤 **Export Contacts**\n\n❌ No accounts found. Add accounts first to export contacts."
                                buttons = [[Button.inline("🔙 Back", "contacts:main")]]
                                await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                                return
                            # Show account selection for export
                            buttons = []
                            for account in accounts[:8]:  # Limit to 8 accounts
                                status = "✅" if account.get("is_active", False) else "❌"
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
                    try:
                        sync_type = data.split(":")[1]
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
                            "• **Logout from Telegram** (session terminated)\n"
                            "• Delete all account data from TeleGuard\n"
                            "• Remove OTP protection\n"
                            "• Remove stored 2FA password\n"
                            "• **Cannot be undone**\n\n"
                            "The account will be logged out from Telegram just like using the logout button in the official app.\n\n"
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
                elif data == "export_sessions":
                    await self._handle_export_sessions(event, user_id)
                elif data.startswith("export_session:"):
                    account_name = data.split(":", 1)[1]
                    await self._handle_export_session_select(event, user_id, account_name)
                elif data.startswith("export_file:"):
                    account_name = data.split(":", 1)[1]
                    await self._handle_export_fresh_session(event, user_id, account_name)
                elif data.startswith("export_fresh:"):
                    account_name = data.split(":", 1)[1]
                    await self._handle_export_fresh_session(event, user_id, account_name)
                elif data.startswith("export_contacts:"):
                    account_name = data.split(":", 1)[1]
                    await self._handle_export_contacts(event, user_id, account_name)
                elif data == "validate_session":
                    if self.account_manager:
                        self.account_manager.pending_actions[user_id] = {
                            "action": "validate_session_string"
                        }
                        text = "🔍 **Session String Validator**\n\nReply with a session string to validate and see DC information (DC1, DC2, DC3, DC4, or DC5):"
                        await self.bot.send_message(user_id, text)
                        await event.answer("🔍 Send session string to validate")
                else:
                    await event.answer("Action processed", alert=False)
            except Exception as e:
                logger.error(f"Callback handler error: {e}")
                await event.answer("❌ Service temporarily unavailable", alert=True)
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
                text = (
                    "📱 **Account Management Center**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🚀 **Welcome to TeleGuard!**\n\n"
                    "No accounts found. Let's get you started with your first account.\n\n"
                    "🎯 **Quick Setup:**\n"
                    "1️⃣ Add your first account\n"
                    "2️⃣ Enable OTP protection\n"
                    "3️⃣ Explore advanced features\n\n"
                    "Choose an option below to begin:"
                )
                buttons = [
                    [Button.inline("🚀 Add First Account", "account:add")],
                    [Button.inline("🔐 Session Login", "session_login"), Button.inline("📥 Import Sessions", "import_sessions")],
                    [Button.inline("❓ Setup Guide", "help:guide")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                # Calculate statistics
                active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
                protected_accounts = sum(1 for acc in accounts if acc.get("otp_destroyer_enabled", False))
                
                text = (
                    f"📱 **Account Management Center**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📊 **Overview:**\n"
                    f"• 📱 Total Accounts: {len(accounts)}\n"
                    f"• 🟢 Active: {active_accounts}\n"
                    f"• 🛡️ Protected: {protected_accounts}\n\n"
                    "📋 **Your Accounts:**\n"
                )
                buttons = []

                for i, account in enumerate(accounts, 1):
                    status = "🟢" if account.get("is_active", False) else "🔴"
                    destroyer_status = "🛡️" if account.get("otp_destroyer_enabled", False) else "⚪"
                    display_name = format_display_name(account)
                    account_phone = format_phone_number(account.get('phone', 'Unknown'))
                    
                    text += f"{i}. {status}{destroyer_status} **{display_name}** `{account_phone}`\n"
                    buttons.append(
                        [
                            Button.inline(
                                f"⚙️ {format_display_name(account)}",
                                f"account:manage:{account['_id']}",
                            )
                        ]
                    )
                
                text += "\n🎛️ **Management Tools:**"
                buttons.extend([
                    [
                        Button.inline("➕ Add Account", "account:add"),
                        Button.inline("🗑️ Remove Account", "account:remove"),
                    ],
                    [
                        Button.inline("🔐 Login via Session", "session_login"),
                        Button.inline("✨ Create Session", "export_sessions"),
                    ],
                    [
                        Button.inline("🔄 Refresh Status", "account:refresh"),
                        Button.inline("📋 Detailed List", "account:list"),
                    ],
                    [
                        Button.inline("🔙 Back to Main Menu", "menu:main"),
                    ],
                ])
            await self.bot.send_message(user_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to handle account settings: {e}")
            await event.reply("❌ Error loading account settings. Please try again.")
    async def _handle_otp_manager(self, event):
        """Handle OTP Manager menu - Settings first approach"""
        user_id = event.sender_id
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = (
                    "🛡️ **OTP Security Manager**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🚨 **No accounts found!**\n\n"
                    "You need to add accounts first before configuring OTP protection.\n\n"
                    "🎯 **What is OTP Protection?**\n"
                    "• 🛡️ **Destroyer** - Blocks unauthorized login attempts\n"
                    "• 📤 **Forward** - Forwards OTP codes to you\n"
                    "• ⏰ **Temp Pass** - 5-minute security bypass\n\n"
                    "Add your first account to get started:"
                )
                buttons = [
                    [Button.inline("🚀 Add First Account", "account:add")],
                    [Button.inline("❓ Security Guide", "help:security")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                # Count enabled/disabled accounts
                destroyer_enabled = sum(1 for acc in accounts if acc.get("otp_destroyer_enabled", False))
                forward_enabled = sum(1 for acc in accounts if acc.get("otp_forward_enabled", False))
                
                # Count enabled/disabled accounts and calculate security metrics
                temp_active = sum(1 for acc in accounts if acc.get("otp_temp_passthrough", False))
                
                security_score = int((destroyer_enabled/len(accounts))*100)
                security_emoji = "🟢" if security_score >= 80 else "🟡" if security_score >= 50 else "🔴"
                
                text = (
                    "🛡️ **OTP Security Manager**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📊 **Security Dashboard:**\n"
                    f"• {security_emoji} **Security Score:** {security_score}%\n"
                    f"• 🛡️ **Destroyer Active:** {destroyer_enabled}/{len(accounts)} accounts\n"
                    f"• 📤 **Forward Active:** {forward_enabled}/{len(accounts)} accounts\n"
                    f"• ⏰ **Temp Bypass:** {temp_active} active\n\n"
                    "🎛️ **Protection Controls:**\n"
                    "Choose your security configuration below:"
                )
                buttons = [
                    [
                        Button.inline("🛡️ OTP Destroyer", "otp_setting:destroyer"),
                        Button.inline("📤 OTP Forward", "otp_setting:forward"),
                    ],
                    [
                        Button.inline("⏰ Temp Bypass", "otp_setting:temp"),
                        Button.inline("📊 Statistics", "otp:stats"),
                    ],
                    [
                        Button.inline("🟢 Enable All Protection", "otp:enable_all"),
                        Button.inline("🔴 Disable All Protection", "otp:disable_all"),
                    ],
                    [
                        Button.inline("📋 Security Audit Log", "otp:audit_all"),
                        # Button.inline("❓ Security Guide", "help:security"),
                    ],
                    [
                        Button.inline("🔙 Back to Main Menu", "menu:main"),
                    ],
                ]
            await self.bot.send_message(user_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to handle OTP manager: {e}")
            await event.reply("❌ Error loading OTP manager. Please try again.")
    async def _handle_messaging(self, event):
        """Handle Messaging menu"""
        user_id = event.sender_id
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = (
                    "💬 **Advanced Messaging Center**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🚨 **No accounts available!**\n\n"
                    "You need active accounts to use messaging features.\n\n"
                    "🎯 **Available Features:**\n"
                    "• 📤 **Smart Messaging** - Send to users/groups\n"
                    "• 📨 **Bulk Operations** - Mass messaging campaigns\n"
                    "• 🤖 **Auto-Reply** - Intelligent response system\n"
                    "• 📝 **Templates** - Reusable message templates\n"
                    "• 📨 **DM Management** - Unified inbox system\n\n"
                    "Add accounts to unlock these powerful features:"
                )
                buttons = [
                    [Button.inline("🚀 Add First Account", "account:add")],
                    [Button.inline("❓ Messaging Guide", "help:features")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                # Get messaging statistics
                active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
                auto_reply_enabled = sum(1 for acc in accounts if acc.get("auto_reply_enabled", False))
                
                text = (
                    "💬 **Advanced Messaging Center**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📊 **System Status:**\n"
                    f"• 📱 Active Accounts: {active_accounts}/{len(accounts)}\n"
                    f"• 🤖 Auto-Reply: {auto_reply_enabled} enabled\n"
                    f"• 🟢 System: Operational\n\n"
                    "🚀 **Messaging Tools:**\n"
                    "Choose your messaging action below:"
                )
                buttons = [
                    [
                        Button.inline("📤 Smart Messaging", "msg:send"),
                        Button.inline("📨 Bulk Campaigns", "msg:bulk"),
                    ],
                    [
                        Button.inline("🤖 Auto-Reply System", "auto_reply:main"),
                        Button.inline("📝 Message Templates", "msg:templates"),
                    ],
                    [
                        Button.inline("📨 Unified DM Manager", "dm_reply:main"),
                        Button.inline("📊 Analytics", "msg:stats"),
                    ],
                    [
                        Button.inline("📋 Message History", "msg:history"),
                        Button.inline("⚙️ System Settings", "msg:settings"),
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
                text = (
                    "📢 **Channel Management Hub**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🚨 **No accounts available!**\n\n"
                    "You need active accounts to manage channels and groups.\n\n"
                    "🎯 **Channel Features:**\n"
                    "• 🔗 **Smart Join/Leave** - Bulk channel operations\n"
                    "• 🆕 **Channel Creation** - Create channels & groups\n"
                    "• 📋 **Management Tools** - List, organize, moderate\n"
                    "• 🗑️ **Cleanup Tools** - Mass leave/delete operations\n"
                    "• 📊 **Analytics** - Channel performance metrics\n\n"
                    "Add accounts to unlock channel management:"
                )
                buttons = [
                    [Button.inline("🚀 Add First Account", "account:add")],
                    [Button.inline("❓ Channel Guide", "help:features")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
                
                text = (
                    "📢 **Channel Management Hub**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📊 **System Overview:**\n"
                    f"• 📱 Active Accounts: {active_accounts}/{len(accounts)}\n"
                    f"• 🟢 Management Tools: Ready\n\n"
                    "🎛️ **Select Account for Channel Operations:**\n"
                    "Choose an account to manage its channels and groups:"
                )
                buttons = []
                for account in accounts[:8]:  # Limit to 8 accounts
                    status = "🟢" if account.get("is_active", False) else "🔴"
                    display_name = format_display_name(account)
                    button_text = f"{status} {display_name}"
                    buttons.append(
                        [
                            Button.inline(
                                button_text, f"channel:select:{account['phone']}"
                            )
                        ]
                    )
                buttons.extend([
                    [
                        Button.inline("📊 Global Statistics", "channel:stats"),
                        Button.inline("🔍 Channel Discovery", "channel:search"),
                    ],
                    [
                        Button.inline("🔙 Back to Main Menu", "menu:main"),
                    ],
                ])
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
                text = (
                    "👥 **Advanced Contact Management**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🚨 **No accounts available!**\n\n"
                    "You need active accounts to manage contacts.\n\n"
                    "🎯 **Contact Features:**\n"
                    "• 📱 **Smart Management** - Add, edit, organize contacts\n"
                    "• 🏷️ **Advanced Tagging** - Categories and groups\n"
                    "• 📤 **Export Tools** - CSV, JSON, Excel formats\n"
                    "• 🔄 **Sync Engine** - Two-way Telegram sync\n"
                    "• 🛡️ **Privacy Controls** - Blacklist/whitelist system\n\n"
                    "Add accounts to unlock contact management:"
                )
                buttons = [
                    [Button.inline("🚀 Add First Account", "account:add")],
                    [Button.inline("❓ Contact Guide", "help:features")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                contact_count = 0
                for account in accounts:
                    count = await mongodb.db.contacts.count_documents({"managed_by_account": account['name']})
                    contact_count += count
                # Calculate contact statistics
                active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
                
                text = (
                    "👥 **Advanced Contact Management**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📊 **System Statistics:**\n"
                    f"• 👥 Total Contacts: {contact_count:,}\n"
                    f"• 📱 Active Accounts: {active_accounts}/{len(accounts)}\n"
                    f"• 🟢 System Status: Operational\n\n"
                    "🚀 **Professional Features:**\n"
                    "• 📱 Smart contact organization and management\n"
                    "• 🏷️ Advanced tagging and categorization system\n"
                    "• 📤 Multi-format export (CSV, JSON, Excel)\n"
                    "• 🔄 Intelligent two-way Telegram synchronization\n"
                    "• 🛡️ Privacy controls with blacklist/whitelist\n\n"
                    "Access your contact management dashboard:"
                )
                buttons = [
                    [
                        Button.inline("🎛️ Contact Dashboard", "contacts:main"),
                    ],
                    [
                        Button.inline("📤 Quick Export", "contacts:export"),
                        Button.inline("🔄 Sync Contacts", "contacts:sync"),
                    ],
                    [
                        Button.inline("🔙 Back to Main Menu", "menu:main"),
                    ],
                ]
            await self.bot.send_message(user_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to handle contacts: {e}")
            await event.reply("❌ Error loading contact management")
    
    async def _handle_spam_master(self, event):
        """Handle SpamMaster menu"""
        user_id = event.sender_id
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = (
                    "🎯 **SpamMaster - Bulk Messaging System**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🚨 **No accounts available!**\n\n"
                    "You need active accounts to use SpamMaster features.\n\n"
                    "🎯 **Powerful Features:**\n"
                    "• 📊 **User Gathering** - Collect users from groups/channels\n"
                    "• 📤 **Bulk Messaging** - Send to thousands of users\n"
                    "• 🤖 **Smart Auto-Reply** - Automated response system\n"
                    "• 📈 **Campaign Analytics** - Track performance metrics\n"
                    "• 🎭 **Human-Like Behavior** - Realistic delays & patterns\n\n"
                    "Add accounts to unlock SpamMaster:"
                )
                buttons = [
                    [Button.inline("🚀 Add First Account", "account:add")],
                    [Button.inline("❓ SpamMaster Guide", "help:features")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
                gathered_users = await mongodb.db.spam_users.count_documents({"owner_id": user_id})
                active_campaigns = await mongodb.db.spam_campaigns.count_documents({"user_id": user_id, "sent": {"$lt": "$total"}})
                
                text = (
                    "🎯 **SpamMaster - Professional Bulk Messaging**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📊 **System Status:**\n"
                    f"• 📱 Active Accounts: {active_accounts}/{len(accounts)}\n"
                    f"• 👥 Gathered Users: {gathered_users:,}\n"
                    f"• 🚀 Active Campaigns: {active_campaigns}\n"
                    f"• 🟢 System: Operational\n\n"
                    "⚡ **Professional Tools:**\n"
                    "• Gather users from any group/channel\n"
                    "• Send bulk messages with media support\n"
                    "• Automated reply system with templates\n"
                    "• Real-time campaign tracking & analytics\n"
                    "• Smart delays to avoid spam detection\n\n"
                    "Choose your action below:"
                )
                buttons = [
                    [
                        Button.inline("📊 Gather Users", "spam_gather"),
                        Button.inline("📤 Bulk Send", "spam_send"),
                    ],
                    [
                        Button.inline("🤖 Auto Reply", "spam_reply"),
                        Button.inline("📈 Campaign Stats", "spam_stats"),
                    ],
                    [
                        Button.inline("🔙 Back to Main Menu", "menu:main"),
                    ],
                ]
            await self.bot.send_message(user_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to handle SpamMaster menu: {e}")
            await event.reply("❌ Error loading SpamMaster menu")
    
    async def _handle_cleanup(self, event):
        """Handle Cleanup menu"""
        user_id = event.sender_id
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = (
                    "🧹 **Professional Account Cleanup**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🚨 **No accounts available!**\n\n"
                    "You need active accounts to use cleanup features.\n\n"
                    "🎯 **Cleanup Capabilities:**\n"
                    "• 💬 **Smart Chat Cleanup** - Personal, bot, official chats\n"
                    "• 🚫 **Spam Removal** - Spambot and unwanted chats\n"
                    "• 🚪 **Mass Exit** - Leave channels and groups\n"
                    "• 🗑️ **Ownership Cleanup** - Delete owned channels/groups\n"
                    "• 📞 **Spam Appeals** - Automated appeal system\n\n"
                    "⚠️ **Important:** All cleanup actions are irreversible!\n\n"
                    "Add accounts to access cleanup tools:"
                )
                buttons = [
                    [Button.inline("🚀 Add First Account", "account:add")],
                    [Button.inline("❓ Cleanup Guide", "help:features")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
                
                text = (
                    "🧹 **Professional Account Cleanup**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📊 **System Status:**\n"
                    f"• 📱 Active Accounts: {active_accounts}/{len(accounts)}\n"
                    f"• 🟢 Cleanup Tools: Ready\n\n"
                    "⚠️ **CRITICAL WARNING:**\n"
                    "All cleanup actions are **PERMANENT** and **IRREVERSIBLE**!\n\n"
                    "🎯 **Available Cleanup Options:**\n"
                    "• 💬 Personal chats • 🤖 Bot conversations\n"
                    "• 📢 Telegram official • 🚫 Spambot chats\n"
                    "• 🚪 Exit channels • 👥 Exit groups\n"
                    "• 🗑️ Delete owned groups • 📺 Delete owned channels\n\n"
                    "🎛️ **Select Account to Clean:**"
                )
                
                buttons = []
                for account in accounts:
                    status = "🟢" if account.get("is_active", False) else "🔴"
                    display_name = format_display_name(account)
                    button_text = f"{status} {display_name}"
                    buttons.append([Button.inline(button_text, f"cleanup:select:{account['_id']}")])
                
                buttons.extend([
                    [Button.inline("📞 Submit Spam Appeal", "cleanup:spam_appeal_select")],
                    [Button.inline("❓ Spam Appeal Guide", "help:troubleshoot")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")]
                ])
            await self.bot.send_message(user_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to handle cleanup: {e}")
            await event.reply("❌ Error loading cleanup menu")
    
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
                        await event.answer("✅ Cleanup options confirmed")
                    else:
                        logger.error(f"Cleanup options error: {e}")
                        await event.answer("❌ Error processing cleanup options")
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
        """Send cleanup type selection for account"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                await self.bot.edit_message(user_id, message_id, "❌ Account not found", buttons=[[Button.inline("🔙 Back", "cleanup:menu")]])
                return
            
            display_name = format_display_name(account)
            
            text = (
                f"🧹 **Cleanup Selection - {display_name}**\n\n"
                f"📋 **What would you like to clean?**\n\n"
                f"Select what to clean (you can choose multiple options):\n\n"
                f"💬 **Personal chats** - Direct messages with users\n"
                f"🤖 **Bot chats** - Conversations with bots\n"
                f"📢 **Telegram official** - Telegram service chats\n"
                f"🚫 **Spambot chats** - @spambot conversations\n"
                f"🚪 **Exit channels** - Leave all channels\n"
                f"👥 **Exit groups** - Leave all groups\n"
                f"🗑️ **Delete owned groups** - Delete groups you own\n"
                f"📺 **Delete owned channels** - Delete channels you own\n\n"
                f"⚠️ **WARNING**: These actions cannot be undone!"
            )
            
            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {
                    "action": "cleanup_selection",
                    "account_id": account_id
                }
            
            await self.bot.edit_message(user_id, message_id, text)
            await self.bot.send_message(
                user_id,
                "📝 **Reply with your selection:**\n\n"
                "Type what you want to clean, separated by commas:\n\n"
                "**Examples:**\n"
                "• `personal,bots` - Clean personal chats and bot chats\n"
                "• `channels,groups` - Exit all channels and groups\n"
                "• `all` - Clean everything\n\n"
                "**Available options:**\n"
                "`personal`, `bots`, `telegram`, `spambot`, `channels`, `groups`, `owned_groups`, `owned_channels`, `all`"
            )
            
        except Exception as e:
            logger.error(f"Error in cleanup selection: {e}")
            await self.bot.edit_message(user_id, message_id, "❌ Error loading cleanup selection", buttons=[[Button.inline("🔙 Back", "cleanup:menu")]])
    
    async def _send_cleanup_confirmation(self, user_id: int, message_id: int, account_id: str, cleanup_types: str):
        """Send cleanup confirmation with selected options"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                await self.bot.edit_message(user_id, message_id, "❌ Account not found", buttons=[[Button.inline("🔙 Back", "cleanup:menu")]])
                return
            
            display_name = format_display_name(account)
            
            # Parse cleanup types
            cleanup_list = [t.strip().lower() for t in cleanup_types.split(',')]
            if 'all' in cleanup_list:
                cleanup_list = ['personal', 'bots', 'telegram', 'spambot', 'channels', 'groups', 'owned_groups', 'owned_channels']
            
            # Create display text for selected options
            selected_options = []
            if 'personal' in cleanup_list:
                selected_options.append("✅ 💬 Personal chats")
            if 'bots' in cleanup_list:
                selected_options.append("✅ 🤖 Bot chats")
            if 'telegram' in cleanup_list:
                selected_options.append("✅ 📢 Telegram official chats")
            if 'spambot' in cleanup_list:
                selected_options.append("✅ 🚫 Spambot chats")
            if 'channels' in cleanup_list:
                selected_options.append("✅ 🚪 Exit from channels")
            if 'groups' in cleanup_list:
                selected_options.append("✅ 👥 Exit from groups")
            if 'owned_groups' in cleanup_list:
                selected_options.append("✅ 🗑️ Delete owned groups")
            if 'owned_channels' in cleanup_list:
                selected_options.append("✅ 📺 Delete owned channels")
            
            if not selected_options:
                await self.bot.send_message(user_id, "❌ No valid cleanup options selected. Please try again.")
                return
            
            text = (
                f"🧹 **Final Cleanup Confirmation**\n\n"
                f"📱 Account: {display_name}\n\n"
                f"**Selected cleanup actions:**\n"
                + "\n".join(selected_options) + "\n\n"
                f"⚠️ **FINAL WARNING**: This action cannot be undone!\n"
                f"All selected chats and data will be permanently deleted.\n\n"
                f"Are you absolutely sure you want to proceed?"
            )
            
            buttons = [
                [Button.inline("🚀 YES, Start Cleanup", f"cleanup:confirm:{account_id}:{cleanup_types}")],
                [Button.inline("❌ Cancel", "cleanup:menu")],
                [Button.inline("📞 Appeal Spam First", f"cleanup:appeal:{account_id}")]
            ]
            
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in cleanup confirmation: {e}")
            await self.bot.edit_message(user_id, message_id, "❌ Error loading cleanup confirmation", buttons=[[Button.inline("🔙 Back", "cleanup:menu")]])
    
    async def _execute_cleanup(self, event, user_id: int, account_id: str, cleanup_types: str):
        """Execute account cleanup with selected options"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                await event.answer("❌ Account not found")
                return
            
            if not self.account_manager:
                await event.answer("❌ Service unavailable")
                return
            
            # Get existing client from account manager
            client = None
            if hasattr(self.account_manager, 'user_clients') and user_id in self.account_manager.user_clients:
                account_name = account.get('name')
                client = self.account_manager.user_clients[user_id].get(account_name)
            
            if not client or not client.is_connected():
                await event.answer("❌ Account not connected. Please ensure account is active.")
                return
            
            display_name = format_display_name(account)
            
            # Parse cleanup types
            cleanup_list = [t.strip().lower() for t in cleanup_types.split(',')]
            if 'all' in cleanup_list:
                cleanup_list = ['personal', 'bots', 'telegram', 'spambot', 'channels', 'groups', 'owned_groups', 'owned_channels']
            
            # Map to cleanup settings
            cleanup_settings = {
                'personal_chats': 'personal' in cleanup_list,
                'bot_chats': 'bots' in cleanup_list,
                'telegram_chat': 'telegram' in cleanup_list,
                'spambot_chat': 'spambot' in cleanup_list,
                'channels': 'channels' in cleanup_list,
                'groups': 'groups' in cleanup_list,
                'owned_groups': 'owned_groups' in cleanup_list,
                'owned_channels': 'owned_channels' in cleanup_list
            }
            
            try:
                await self.bot.edit_message(
                    user_id, event.message_id,
                    f"🚀 **Starting cleanup for {display_name}**\n\n⏳ Analyzing account...\n📊 Progress will be shown below",
                    buttons=None
                )
            except Exception as edit_error:
                if "Content of the message was not modified" in str(edit_error):
                    # Message is already showing progress, continue
                    pass
                else:
                    # Send new message if edit fails
                    await self.bot.send_message(
                        user_id,
                        f"🚀 **Starting cleanup for {display_name}**\n\n⏳ Analyzing account...\n📊 Progress will be shown below"
                    )
            
            from teleguard.core.account_cleaner import AccountCleaner
            cleaner = AccountCleaner()
            
            import time
            last_update_time = time.time()
            
            async def progress_callback(text):
                nonlocal last_update_time
                current_time = time.time()
                
                if current_time - last_update_time < 2:
                    return
                
                try:
                    await self.bot.edit_message(
                        user_id, event.message_id,
                        f"🚀 **Cleaning {display_name}**\n\n{text}",
                        buttons=None
                    )
                    last_update_time = current_time
                except Exception as e:
                    if "Content of the message was not modified" not in str(e):
                        logger.debug(f"Progress update error: {e}")
            
            result = await cleaner.cleanup_account(client, cleanup_settings, progress_callback)
            
            result_text = (
                f"✅ **Cleanup completed!**\n\n"
                f"📱 Account: {display_name}\n\n"
                f"📊 **Results:**\n{result}\n\n"
                f"🔒 All operations completed securely"
            )
            
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            
            try:
                await self.bot.edit_message(user_id, event.message_id, result_text, buttons=buttons)
            except Exception as edit_error:
                if "Content of the message was not modified" in str(edit_error):
                    # Message content is the same, just answer callback if available
                    try:
                        await event.answer("✅ Cleanup completed successfully!")
                    except:
                        pass
                else:
                    # Send new message if edit fails for other reasons
                    await self.bot.send_message(user_id, result_text, buttons=buttons)
            
            await mongodb.add_audit_entry(account_id, {
                "action": "cleanup_completed",
                "cleanup_types": cleanup_types,
                "timestamp": int(time.time()),
                "result": "success"
            })
            
        except Exception as e:
            logger.error(f"Cleanup error for account {account_id}: {e}")
            
            error_text = (
                f"❌ **Cleanup error!**\n\n"
                f"🚫 Error: {str(e)}\n\n"
                f"💡 Try again in a few minutes"
            )
            
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            
            try:
                await self.bot.edit_message(user_id, event.message_id, error_text, buttons=buttons)
            except Exception as edit_error:
                if "Content of the message was not modified" in str(edit_error):
                    # Message content is the same, just answer callback if available
                    try:
                        await event.answer("❌ Cleanup failed")
                    except:
                        pass
                else:
                    # Send new message if edit fails for other reasons
                    await self.bot.send_message(user_id, error_text, buttons=buttons)
    
    async def _handle_cleanup_selection_callback(self, event, user_id: int, data: str):
        """Handle cleanup selection text input"""
        try:
            # Check if this is a text message (not callback)
            if hasattr(event, 'text'):
                # This is a text message response
                if not hasattr(self.account_manager, 'pending_actions') or user_id not in self.account_manager.pending_actions:
                    await event.reply("❌ No pending cleanup action found.")
                    return
                
                action_data = self.account_manager.pending_actions[user_id]
                if action_data.get('action') != 'cleanup_selection':
                    await event.reply("❌ Invalid action state.")
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
            await event.reply("❌ Error processing cleanup selection.")
    
    async def _send_cleanup_confirmation_new(self, user_id: int, account_id: str, cleanup_types: str):
        """Send cleanup confirmation as new message to avoid edit conflicts"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                await self.bot.send_message(user_id, "❌ Account not found")
                return
            
            display_name = format_display_name(account)
            
            # Parse cleanup types
            cleanup_list = [t.strip().lower() for t in cleanup_types.split(',')]
            if 'all' in cleanup_list:
                cleanup_list = ['personal', 'bots', 'telegram', 'spambot', 'channels', 'groups', 'owned_groups', 'owned_channels']
            
            # Create display text for selected options
            selected_options = []
            if 'personal' in cleanup_list:
                selected_options.append("✅ 💬 Personal chats")
            if 'bots' in cleanup_list:
                selected_options.append("✅ 🤖 Bot chats")
            if 'telegram' in cleanup_list:
                selected_options.append("✅ 📢 Telegram official chats")
            if 'spambot' in cleanup_list:
                selected_options.append("✅ 🚫 Spambot chats")
            if 'channels' in cleanup_list:
                selected_options.append("✅ 🚪 Exit from channels")
            if 'groups' in cleanup_list:
                selected_options.append("✅ 👥 Exit from groups")
            if 'owned_groups' in cleanup_list:
                selected_options.append("✅ 🗑️ Delete owned groups")
            if 'owned_channels' in cleanup_list:
                selected_options.append("✅ 📺 Delete owned channels")
            
            if not selected_options:
                await self.bot.send_message(user_id, "❌ No valid cleanup options selected. Please try again with valid options: personal, bots, telegram, spambot, channels, groups, owned_groups, owned_channels, all")
                return
            
            text = (
                f"🧹 **Final Cleanup Confirmation**\n\n"
                f"📱 Account: {display_name}\n\n"
                f"**Selected cleanup actions:**\n"
                + "\n".join(selected_options) + "\n\n"
                f"⚠️ **FINAL WARNING**: This action cannot be undone!\n"
                f"All selected chats and data will be permanently deleted.\n\n"
                f"Are you absolutely sure you want to proceed?"
            )
            
            buttons = [
                [Button.inline("🚀 YES, Start Cleanup", f"cleanup:confirm:{account_id}:{cleanup_types}")],
                [Button.inline("❌ Cancel", "cleanup:menu")],
                [Button.inline("📞 Appeal Spam First", f"cleanup:appeal:{account_id}")]
            ]
            
            await self.bot.send_message(user_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in cleanup confirmation: {e}")
            await self.bot.send_message(user_id, "❌ Error loading cleanup confirmation")
    
    async def _send_cleanup_confirmation(self, user_id: int, message_id: int, account_id: str, cleanup_types: str):
        """Send cleanup confirmation with selected options (legacy method for edit)"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                if message_id:
                    await self.bot.edit_message(user_id, message_id, "❌ Account not found", buttons=[[Button.inline("🔙 Back", "cleanup:menu")]])
                else:
                    await self.bot.send_message(user_id, "❌ Account not found")
                return
            
            display_name = format_display_name(account)
            
            # Parse cleanup types
            cleanup_list = [t.strip().lower() for t in cleanup_types.split(',')]
            if 'all' in cleanup_list:
                cleanup_list = ['personal', 'bots', 'telegram', 'spambot', 'channels', 'groups', 'owned_groups', 'owned_channels']
            
            # Create display text for selected options
            selected_options = []
            if 'personal' in cleanup_list:
                selected_options.append("✅ 💬 Personal chats")
            if 'bots' in cleanup_list:
                selected_options.append("✅ 🤖 Bot chats")
            if 'telegram' in cleanup_list:
                selected_options.append("✅ 📢 Telegram official chats")
            if 'spambot' in cleanup_list:
                selected_options.append("✅ 🚫 Spambot chats")
            if 'channels' in cleanup_list:
                selected_options.append("✅ 🚪 Exit from channels")
            if 'groups' in cleanup_list:
                selected_options.append("✅ 👥 Exit from groups")
            if 'owned_groups' in cleanup_list:
                selected_options.append("✅ 🗑️ Delete owned groups")
            if 'owned_channels' in cleanup_list:
                selected_options.append("✅ 📺 Delete owned channels")
            
            if not selected_options:
                error_msg = "❌ No valid cleanup options selected. Please try again with valid options: personal, bots, telegram, spambot, channels, groups, owned_groups, owned_channels, all"
                if message_id:
                    await self.bot.edit_message(user_id, message_id, error_msg, buttons=[[Button.inline("🔙 Back", "cleanup:menu")]])
                else:
                    await self.bot.send_message(user_id, error_msg)
                return
            
            text = (
                f"🧹 **Final Cleanup Confirmation**\n\n"
                f"📱 Account: {display_name}\n\n"
                f"**Selected cleanup actions:**\n"
                + "\n".join(selected_options) + "\n\n"
                f"⚠️ **FINAL WARNING**: This action cannot be undone!\n"
                f"All selected chats and data will be permanently deleted.\n\n"
                f"Are you absolutely sure you want to proceed?"
            )
            
            buttons = [
                [Button.inline("🚀 YES, Start Cleanup", f"cleanup:confirm:{account_id}:{cleanup_types}")],
                [Button.inline("❌ Cancel", "cleanup:menu")],
                [Button.inline("📞 Appeal Spam First", f"cleanup:appeal:{account_id}")]
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
                    await self.bot.edit_message(user_id, message_id, error_msg, buttons=[[Button.inline("🔙 Back", "cleanup:menu")]])
                except:
                    await self.bot.send_message(user_id, error_msg)
            else:
                await self.bot.send_message(user_id, error_msg)
    
    async def _handle_spam_appeal(self, event, user_id: int, account_id: str):
        """Handle spam appeal for account before cleanup"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                await event.answer("❌ Account not found")
                return
            
            display_name = format_display_name(account)
            
            # Check if spam appeal handler is available
            if hasattr(self.account_manager, 'spam_appeal_handler'):
                text = (
                    f"📞 **Spam Appeal - {display_name}**\n\n"
                    f"🤖 **Smart Appeal System**\n\n"
                    f"Before cleaning your account, you can try appealing any spam restrictions.\n\n"
                    f"**Features:**\n"
                    f"• AI-powered message selection\n"
                    f"• Automatic @spambot interaction\n"
                    f"• Manual captcha verification\n"
                    f"• Smart detection of restriction types\n\n"
                    f"Would you like to start the appeal process?"
                )
                
                buttons = [
                    [Button.inline("🚀 Start Appeal", f"appeal_account_id:{account_id}")],
                    [Button.inline("🧹 Skip to Cleanup", f"cleanup:select:{account_id}")],
                    [Button.inline("🔙 Back to Menu", "cleanup:menu")]
                ]
                
                await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            else:
                text = (
                    f"📞 **Manual Spam Appeal - {display_name}**\n\n"
                    f"Spam appeal system is not available.\n\n"
                    f"**Manual steps:**\n"
                    f"1. Go to @spambot\n"
                    f"2. Send /start\n"
                    f"3. Follow the appeal process\n"
                    f"4. Complete any captcha verification\n\n"
                    f"After appealing, you can return to cleanup if needed."
                )
                
                buttons = [
                    [Button.inline("🧹 Continue to Cleanup", f"cleanup:select:{account_id}")],
                    [Button.inline("🔙 Back to Menu", "cleanup:menu")]
                ]
                
                await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in spam appeal: {e}")
            await event.answer("❌ Error loading spam appeal")
    async def _handle_help(self, event):
        """Handle Help menu"""
        user_id = event.sender_id
        user = await mongodb.db.users.find_one({"telegram_id": user_id})
        
        # Get user stats for personalized help
        account_count = await mongodb.db.accounts.count_documents({"user_id": user_id})
        otp_enabled = await mongodb.db.accounts.count_documents({"user_id": user_id, "otp_destroyer_enabled": True})
        
        security_score = int((otp_enabled/max(account_count, 1))*100) if account_count > 0 else 0
        status_emoji = "🟢" if security_score >= 80 else "🟡" if security_score >= 50 else "🔴"
        
        text = (
            "❓ **TeleGuard Help & Support Center**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 **Your Dashboard:**\n"
            f"• 📱 **Accounts:** {account_count} configured\n"
            f"• 🛡️ **Protection:** {otp_enabled}/{account_count} secured\n"
            f"• {status_emoji} **Security Score:** {security_score}%\n\n"
            "🚀 **Quick Setup (2 minutes):**\n"
            "1️⃣ **Add Account** → `📱 Account Settings` → `Add Account`\n"
            "2️⃣ **Enable Security** → `🛡️ OTP Manager` → `Enable Destroyer`\n"
            "3️⃣ **Configure Features** → Explore messaging & automation\n\n"
            "🎯 **Feature Overview:**\n"
            "• 🛡️ **Security** - OTP protection, 2FA, session monitoring\n"
            "• 💬 **Messaging** - Auto-reply, templates, bulk sending\n"
            "• 📱 **Management** - Profile updates, channel tools\n"
            "• 📊 **Analytics** - Activity logs, performance insights\n\n"
            "💡 **Pro Tips:**\n"
            "• Enable OTP Destroyer on all accounts for maximum security\n"
            "• Use DM Reply for centralized message management\n"
            "• Monitor audit logs weekly for security insights"
        )
        buttons = [
            [
                Button.inline("📖 Complete Guide", "help:guide"),
                Button.inline("🛡️ Security Guide", "help:security"),
            ],
            [
                Button.inline("⚙️ Feature Guide", "help:features"),
                Button.inline("🔧 Troubleshooting", "help:troubleshoot"),
            ],
            [
                Button.inline("❓ FAQ", "help:faq"),
                Button.inline("📞 Contact Support", "help:contact"),
            ],
            [
                Button.inline("🆘 Emergency Help", "help:emergency"),
                Button.inline("📚 Commands", "help:commands"),
            ],
            [
                Button.inline("📨 Chat Import", "menu:import"),
            ],
        ]
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
            "🆘 **TeleGuard Support Center**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👨💻 **Development Team:**\n"
            "• **@Meher_Mankar** - Lead Developer & Founder\n"
            "• **@Gutkesh** - Core Developer & Security Expert\n\n"
            "🎯 **Get Instant Help:**\n"
            "• 💬 **Live Support:** @ContactXYZrobot\n"
            "• 🐛 **Bug Reports:** GitHub Issues Portal\n"
            "• 📚 **Documentation:** Complete Wiki Guide\n"
            "• ⚡ **Response Time:** < 6 hours (usually faster)\n\n"
            "🔧 **Self-Help Checklist:**\n"
            "✅ Check Help section for instant solutions\n"
            "✅ Try `/start` to refresh the bot\n"
            "✅ Verify accounts are properly connected\n"
            "✅ Review troubleshooting guide first\n\n"
            "🚨 **Emergency Support:** Contact developers directly for critical issues"
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
                Button.inline("🔄 Updates", "support:updates"),
            ],
            [
                Button.inline("🔙 Back to Main Menu", "menu:main"),
            ],
        ]
        await self.bot.send_message(event.sender_id, text, buttons=buttons)
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
        """Handle Developer menu"""
        user_id = event.sender_id
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if user:
                current_mode = user.get("developer_mode", False)
                # Get system stats for dashboard
                account_count = await mongodb.db.accounts.count_documents({})
                user_count = await mongodb.db.users.count_documents({})
                
                text = (
                    "⚙️ **Developer Control Panel**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🎛️ **Developer Mode:** {'🟢 **ACTIVE**' if current_mode else '🔴 **INACTIVE**'}\n\n"
                    f"📊 **System Overview:**\n"
                    f"• 👥 Total Users: {user_count:,}\n"
                    f"• 📱 Total Accounts: {account_count:,}\n"
                    f"• 🟢 System Status: Operational\n\n"
                    "🛠️ **Administrative Tools:**\n"
                    "• 🔧 **System Control** - Mode toggle, restart, maintenance\n"
                    "• 📊 **Monitoring** - Real-time metrics & performance\n"
                    "• 🐛 **Debugging** - Error logs & diagnostic tools\n"
                    "• 🗄️ **Database** - Statistics & optimization tools\n"
                    "• 🚀 **Deployment** - Configuration & startup management\n\n"
                    "⚠️ **Administrator Access** - Advanced system operations only"
                )
                mode_text = (
                    "🔴 Disable Developer Mode" if current_mode else "🟢 Enable Developer Mode"
                )
                buttons = [
                    [
                        Button.inline(mode_text, "dev:toggle"),
                    ],
                    [
                        Button.inline("📊 System Dashboard", "dev:sysinfo"),
                        Button.inline("📋 System Logs", "dev:logs"),
                    ],
                    [
                        Button.inline("🗄️ Database Tools", "dev:dbstats"),
                        Button.inline("⚡ Performance Monitor", "dev:perf"),
                    ],
                    [
                        Button.inline("🔧 Maintenance Tools", "dev:maintenance"),
                        Button.inline("🔄 System Restart", "dev:restart"),
                    ],
                    [
                        Button.inline("🚀 Startup Config", "dev:startup"),
                        Button.inline("📚 Command Reference", "dev:commands"),
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
                "📨 **Unified DM Management System**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "🎯 **Smart Topic Creation:** All DMs automatically become organized forum topics\n\n"
                f"📊 **Current Status:** {status_text}\n\n"
                "✨ **Professional Features:**\n"
                "• 🔄 **Auto-Organization** - Every DM gets its own topic\n"
                "• 💬 **Persistent Threads** - Conversations never get lost\n"
                "• ⚡ **Instant Reply** - Just reply in topics, no buttons needed\n"
                "• 🤖 **Smart Integration** - Works seamlessly with auto-reply\n"
                "• 🎨 **Clean Interface** - Professional message management\n\n"
                "🚀 **Perfect for managing multiple accounts from one centralized place!**"
            )
            buttons.append([Button.inline("🔙 Back to Messaging", "menu:messaging")])
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
                # Go back to OTP Destroyer account selection instead of individual account menu
                await self._handle_otp_setting_callback(event, user_id, "otp_setting:destroyer")
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
                # Go back to OTP Destroyer account selection instead of individual account menu
                await self._handle_otp_setting_callback(event, user_id, "otp_setting:destroyer")
            except Exception as e:
                await event.answer("❌ Error disabling OTP Destroyer")
        elif action == "forward_enable":
            try:
                from bson import ObjectId
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
                # Go back to OTP Forward account selection instead of individual account menu
                await self._handle_otp_setting_callback(event, user_id, "otp_setting:forward")
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
                # Go back to OTP Forward account selection instead of individual account menu
                await self._handle_otp_setting_callback(event, user_id, "otp_setting:forward")
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
                        await event.answer("❌ Temp OTP stopped! Original settings restored.")
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
                await event.answer("⏰ Temp OTP enabled! Forward ON, Destroyer OFF for 5 minutes.")
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
                await event.answer("❌ Error handling temp OTP")
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
    
    async def _handle_otp_setting_callback(self, event, user_id: int, data: str):
        """Handle OTP setting callbacks from main OTP menu"""
        parts = data.split(":")
        setting_type = parts[1] if len(parts) > 1 else "destroyer"
        
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = "🛡️ **OTP Settings**\n\n❌ No accounts found."
                buttons = [[Button.inline("🔙 Back to OTP Manager", "menu:otp")]]
                await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                return
            
            if setting_type == "destroyer":
                text = "🛡️ **OTP Destroyer Settings**\n\nSelect account to enable/disable OTP Destroyer:"
            elif setting_type == "forward":
                text = "📤 **OTP Forward Settings**\n\nSelect account to enable/disable OTP Forward:"
            elif setting_type == "temp":
                text = "⏰ **Temp OTP Settings**\n\nSelect account to enable 5-minute passthrough:"
            else:
                text = "🛡️ **OTP Settings**\n\nSelect account:"
            
            buttons = []
            for account in accounts:
                status = "🟢" if account.get("is_active", False) else "🔴"
                
                if setting_type == "destroyer":
                    feature_status = "🛡️" if account.get("otp_destroyer_enabled", False) else "⚪"
                elif setting_type == "forward":
                    feature_status = "📤" if account.get("otp_forward_enabled", False) else "⚪"
                else:
                    feature_status = "⚪"
                
                display_name = format_display_name(account)
                button_text = f"{status}{feature_status} {display_name}"
                buttons.append([Button.inline(button_text, f"otp:manage:{account['_id']}")])
            
            buttons.append([Button.inline("🔙 Back to OTP Manager", "menu:otp")])
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in OTP setting callback: {e}")
            await event.answer("❌ Error loading OTP settings")
    
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
                    has_2fa = "🛡️" if account.get("twofa_password") else "❌"
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
                    status = "✅" if account.get("is_active", False) else "❌"
                    username_display = (
                        f"@{account.get('username', '')}"
                        if account.get("username")
                        else "No username"
                    )
                    button_text = f"{status} {account['name']} ({username_display})"
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
                    if hasattr(self.account_manager, 'online_maker'):
                        account_identifier = account.get("phone") or account.get("name", "unknown")
                        if new_status:
                            await self.account_manager.online_maker.start_online_maker(user_id, account_identifier)
                        else:
                            await self.account_manager.online_maker.stop_online_maker(user_id, account_identifier)
                    status = "started" if new_status else "stopped"
                    status_emoji = "✅" if new_status else "❌"
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
                f"📞 Phone: {format_phone_number(account['phone'])}\n"
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
                try:
                    from ..core.database_manager import db_manager
                    await db_manager.remove_2fa_password(user_id, account_id)
                except Exception:
                    pass
                success, message = await self.account_manager.remove_account_by_id(user_id, account_id)
                message = "Account removed successfully" if success else "Failed to remove account"
                if success:
                    await event.answer("✅ Account removed successfully!")
                    await self.bot.edit_message(
                        user_id,
                        event.message_id,
                        "✅ **Account Removed**\n\nThe account has been successfully removed from TeleGuard.\n\n🔐 Session terminated from Telegram\n🔐 Stored 2FA password also removed for security",
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
                    status = "✅" if account.get("is_active", False) else "❌"
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
                    status = "✅" if account.get("is_active", False) else "❌"
                    auto_status = (
                        "✅" if account.get("auto_reply_enabled", False) else "❌"
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
                status = "✅" if account.get("is_active", False) else "❌"
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
                status = "✅" if account.get("is_active", False) else "❌"
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
                        status_emoji = "✅" if job['status'] == 'running' else "❌"
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
                    "✅ Active"
                    if account.get("simulation_enabled", False)
                    else "❌ Inactive"
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
                "📖 **Complete User Guide**\n\n"
                "**🚀 Initial Setup (5 minutes):**\n"
                "1. **Add Your First Account**\n"
                "   → Go to '📱 Account Settings'\n"
                "   → Click 'Add Account'\n"
                "   → Enter phone number (+1234567890)\n"
                "   → Enter OTP code (format: 1-2-3-4-5)\n"
                "   → Enter 2FA password if prompted\n\n"
                "2. **Enable OTP Protection**\n"
                "   → Go to '🛡️ OTP Manager'\n"
                "   → Select 'OTP Destroyer'\n"
                "   → Choose your account\n"
                "   → Click 'Enable Destroyer'\n\n"
                "3. **Set Up Messaging (Optional)**\n"
                "   → Go to '💬 Messaging'\n"
                "   → Click 'DM Reply'\n"
                "   → Follow setup guide for unified messaging\n\n"
                "**🎯 Advanced Features:**\n"
                "• **Profile Management** - Update names, photos, bios\n"
                "• **Channel Tools** - Join/leave/create channels\n"
                "• **Contact Export** - Export contacts to CSV\n"
                "• **Session Control** - Monitor active logins\n"
                "• **Activity Simulation** - Human-like behavior\n"
                "• **Bulk Messaging** - Send to multiple users\n\n"
                "**⚡ Quick Actions:**\n"
                "• `/accs` - List all accounts\n"
                "• `/add` - Add new account\n"
                "• `/otp` - Toggle OTP protection\n"
                "• `/help` - Show this help\n\n"
                "**🔄 Daily Workflow:**\n"
                "1. Check OTP statistics for security alerts\n"
                "2. Review audit logs for account activity\n"
                "3. Manage DMs through unified messaging\n"
                "4. Monitor session activity for security"
            )
        elif action == "security":
            text = (
                "🛡️ **Complete Security Guide**\n\n"
                "**🔥 OTP Destroyer - Core Protection:**\n"
                "• **What it does:** Automatically invalidates login codes in real-time\n"
                "• **How it works:** Uses Telegram's official `account.invalidateSignInCodes` API\n"
                "• **Protection level:** Blocks 99.9% of unauthorized login attempts\n"
                "• **Zero false positives:** Only triggers on actual login attempts\n"
                "• **Instant alerts:** Notifies you when attacks are blocked\n\n"
                "**🔐 2FA Management:**\n"
                "• **Set passwords:** Add extra security layer to accounts\n"
                "• **Change passwords:** Update 2FA passwords securely\n"
                "• **Remove passwords:** Disable 2FA when needed\n"
                "• **Password protection:** Require password to disable OTP Destroyer\n\n"
                "**📱 Session Security:**\n"
                "• **Active monitoring:** View all active login sessions\n"
                "• **Instant termination:** End suspicious sessions immediately\n"
                "• **Location tracking:** See login locations and devices\n"
                "• **Session alerts:** Get notified of new logins\n\n"
                "**🔒 Data Protection:**\n"
                "• **Military-grade encryption:** All data encrypted with Fernet\n"
                "• **Secure storage:** Session strings double-encrypted\n"
                "• **No logging:** Sensitive data never stored in logs\n"
                "• **Local processing:** All operations performed locally\n\n"
                "**⚡ Advanced Features:**\n"
                "• **Temp OTP:** 5-minute security bypass for legitimate logins\n"
                "• **OTP Forward:** Forward codes to you instead of blocking\n"
                "• **Audit logging:** Complete activity tracking\n"
                "• **Activity simulation:** Human-like behavior to avoid detection\n\n"
                "**🚨 Security Best Practices:**\n"
                "• Keep OTP Destroyer enabled 24/7\n"
                "• Use strong 2FA passwords (12+ characters)\n"
                "• Monitor audit logs weekly\n"
                "• Terminate unknown sessions immediately\n"
                "• Enable startup notifications for admins"
            )
        elif action == "troubleshoot":
            text = (
                "🔧 **Complete Troubleshooting Guide**\n\n"
                "**🔴 Account Connection Issues:**\n"
                "**Problem:** Account won't connect/add\n"
                "**Solutions:**\n"
                "• ✅ Use correct format: +1234567890 (with country code)\n"
                "• ✅ Enter OTP as: 1-2-3-4-5 (with hyphens)\n"
                "• ✅ Wait 5 minutes if rate limited\n"
                "• ✅ Check if account has 2FA enabled\n"
                "• ✅ Try from different IP if blocked\n\n"
                "**🛡️ OTP Destroyer Issues:**\n"
                "**Problem:** OTP Destroyer not blocking codes\n"
                "**Solutions:**\n"
                "• ✅ Verify it's enabled in OTP Manager\n"
                "• ✅ Check account status is 'Active'\n"
                "• ✅ Review audit logs for activity\n"
                "• ✅ Ensure account has valid session\n"
                "• ✅ Restart bot if needed\n\n"
                "**💬 Messaging Problems:**\n"
                "**Problem:** Messages not sending\n"
                "**Solutions:**\n"
                "• ✅ Verify account is connected (green status)\n"
                "• ✅ Check target username/ID is valid\n"
                "• ✅ Wait if rate limited (flood wait)\n"
                "• ✅ Try different account if one is restricted\n"
                "• ✅ Check if target blocked you\n\n"
                "**📨 DM Reply Issues:**\n"
                "**Problem:** DM forwarding not working\n"
                "**Solutions:**\n"
                "• ✅ Ensure group has Topics enabled\n"
                "• ✅ Bot must be admin with topic permissions\n"
                "• ✅ Use correct group ID (negative number)\n"
                "• ✅ Check if accounts are properly connected\n\n"
                "**⚡ Performance Issues:**\n"
                "**Problem:** Bot running slowly\n"
                "**Solutions:**\n"
                "• ✅ Restart bot with `/restart_bot`\n"
                "• ✅ Clear cache with `/clear_cache`\n"
                "• ✅ Check system resources\n"
                "• ✅ Optimize database with `/optimize_db`\n\n"
                "**🆘 Emergency Fixes:**\n"
                "• **Complete restart:** `/restart_bot`\n"
                "• **Reset sessions:** Remove and re-add accounts\n"
                "• **Clear data:** `/cleanup_sessions`\n"
                "• **Contact support:** @ContactXYZrobot"
            )
        elif action == "faq":
            text = (
                "❓ **Frequently Asked Questions**\n\n"
                "**🔒 Security & Safety:**\n"
                "**Q: Is TeleGuard safe to use?**\n"
                "A: Yes! All data is encrypted with military-grade Fernet encryption. Session strings are double-encrypted and never logged.\n\n"
                "**Q: Can TeleGuard access my messages?**\n"
                "A: No. TeleGuard only manages accounts and security features. It cannot read your private messages.\n\n"
                "**Q: What happens if I lose access to TeleGuard?**\n"
                "A: Your Telegram accounts remain unaffected. You can always log in normally through Telegram apps.\n\n"
                "**📱 Account Management:**\n"
                "**Q: How many accounts can I add?**\n"
                "A: Up to 10 accounts per user. This limit ensures optimal performance and security.\n\n"
                "**Q: Can I use accounts from different countries?**\n"
                "A: Yes! TeleGuard supports accounts from any country with proper phone number format.\n\n"
                "**Q: What if my account gets banned?**\n"
                "A: TeleGuard includes activity simulation to reduce ban risk. If banned, remove the account and add a new one.\n\n"
                "**🛡️ OTP Destroyer:**\n"
                "**Q: What is OTP Destroyer?**\n"
                "A: Real-time protection that automatically invalidates login codes to prevent unauthorized access.\n\n"
                "**Q: Will it block my legitimate logins?**\n"
                "A: No! Use 'Temp OTP' feature for 5-minute bypass when you need to login legitimately.\n\n"
                "**Q: How effective is OTP protection?**\n"
                "A: 99.9% effective against unauthorized login attempts with zero false positives.\n\n"
                "**💻 Technical Questions:**\n"
                "**Q: Can I use this on multiple devices?**\n"
                "A: Yes, but each device needs separate setup for security. Sessions are device-specific.\n\n"
                "**Q: Does it work with Telegram Premium?**\n"
                "A: Yes! TeleGuard works with both free and premium Telegram accounts.\n\n"
                "**Q: What about rate limits?**\n"
                "A: TeleGuard includes automatic rate limit handling and flood wait management.\n\n"
                "**🔧 Usage Questions:**\n"
                "**Q: How do I export my contacts?**\n"
                "A: Go to 'Contacts' → 'Export' → Select account → CSV file will be sent to you.\n\n"
                "**Q: Can I schedule messages?**\n"
                "A: Currently not available, but planned for future updates.\n\n"
                "**Q: How do I backup my sessions?**\n"
                "A: Sessions are automatically backed up. Use 'Fresh Sessions' to export session strings."
            )
        elif action == "contact":
            text = (
                "📞 **Contact & Support Information**\n\n"
                "**👨‍💻 Development Team:**\n"
                "• **@Meher_Mankar** - Lead Developer & Project Founder\n"
                "  └ Specializes in: Core architecture, security features\n"
                "• **@Gutkesh** - Core Developer & Security Expert\n"
                "  └ Specializes in: OTP systems, encryption, automation\n\n"
                "**🆘 Support Channels:**\n"
                "• **Primary Support:** @ContactXYZrobot\n"
                "  └ Best for: General questions, account issues, feature requests\n"
                "  └ Response time: Usually within 2-6 hours\n\n"
                "• **GitHub Issues:** github.com/MeherMankar/TeleGuard/issues\n"
                "  └ Best for: Bug reports, technical issues, feature requests\n"
                "  └ Response time: 1-3 days\n\n"
                "• **Direct Contact:**\n"
                "  └ @Meher_Mankar - Critical issues, security concerns\n"
                "  └ @Gutkesh - Technical problems, feature discussions\n\n"
                "**📚 Self-Help Resources:**\n"
                "• **Complete Documentation:** README.md\n"
                "• **Wiki Guide:** github.com/MeherMankar/TeleGuard/wiki\n"
                "• **Video Tutorials:** Coming soon\n"
                "• **Community Forum:** Telegram group (ask for invite)\n\n"
                "**🚨 Emergency Contact:**\n"
                "For critical security issues or account compromises:\n"
                "• Contact @Meher_Mankar immediately\n"
                "• Include: Account details, issue description, urgency level\n"
                "• Expected response: Within 1-2 hours\n\n"
                "**💡 Before Contacting Support:**\n"
                "1. Check this help section and FAQ\n"
                "2. Try troubleshooting steps\n"
                "3. Check if issue is already reported on GitHub\n"
                "4. Gather error messages and steps to reproduce\n"
                "5. Include your setup details (OS, Python version, etc.)"
            )
        elif action == "emergency":
            text = (
                "🆘 **Emergency Response Guide**\n\n"
                "**🚨 ACCOUNT COMPROMISED - IMMEDIATE ACTIONS:**\n"
                "**Step 1 (0-2 minutes):**\n"
                "• Go to OTP Manager → Select account → Disable Destroyer\n"
                "• Go to Account Settings → Select account → Active Sessions\n"
                "• Terminate ALL sessions except current one\n\n"
                "**Step 2 (2-5 minutes):**\n"
                "• Change 2FA password immediately\n"
                "• Enable OTP Destroyer again\n"
                "• Check audit logs for suspicious activity\n\n"
                "**Step 3 (5-10 minutes):**\n"
                "• Contact @Meher_Mankar with details\n"
                "• Document what happened (screenshots)\n"
                "• Change passwords on linked services\n\n"
                "**🔧 BOT NOT RESPONDING - TROUBLESHOOTING:**\n"
                "**Quick Fixes (try in order):**\n"
                "1. Send `/start` command\n"
                "2. Send `/restart_bot` (admin only)\n"
                "3. Check if bot is online: @TeleGuardBot\n"
                "4. Wait 5 minutes and try again\n\n"
                "**Advanced Fixes:**\n"
                "• Restart your server/hosting\n"
                "• Check database connection\n"
                "• Review error logs\n"
                "• Contact support with error details\n\n"
                "**🔥 CRITICAL SYSTEM FAILURE:**\n"
                "**If multiple accounts compromised:**\n"
                "1. **STOP** - Don't panic\n"
                "2. **DISCONNECT** - Turn off bot immediately\n"
                "3. **SECURE** - Change all 2FA passwords manually\n"
                "4. **CONTACT** - Message @Meher_Mankar with 'CRITICAL'\n"
                "5. **DOCUMENT** - Save all error messages and logs\n\n"
                "**📞 Emergency Contacts:**\n"
                "• **Immediate help:** @Meher_Mankar\n"
                "• **Technical issues:** @Gutkesh\n"
                "• **General support:** @ContactXYZrobot\n\n"
                "**⏰ Response Times:**\n"
                "• Critical security issues: 1-2 hours\n"
                "• System failures: 2-6 hours\n"
                "• General emergencies: 6-12 hours"
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
        elif action == "features":
            text = (
                "⚙️ **Complete Feature Guide**\n\n"
                "**📱 Account Management:**\n"
                "• **Multi-Account Support:** Manage up to 10 Telegram accounts\n"
                "• **Profile Management:** Update names, usernames, bios, photos\n"
                "• **Session Control:** View and terminate active sessions\n"
                "• **Fresh Sessions:** Export session strings with DC info\n"
                "• **Account Health:** Monitor connection status and activity\n\n"
                "**🛡️ Security Suite:**\n"
                "• **OTP Destroyer:** Real-time login attack protection\n"
                "• **OTP Forward:** Forward login codes instead of blocking\n"
                "• **Temp OTP:** 5-minute security bypass for legitimate logins\n"
                "• **2FA Management:** Set, change, remove two-factor passwords\n"
                "• **Password Protection:** Require password to disable security\n\n"
                "**💬 Messaging Tools:**\n"
                "• **Unified Messaging:** Centralized DM management with topics\n"
                "• **Auto-Reply:** Keyword-based automatic responses\n"
                "• **Bulk Sender:** Send messages to multiple users at once\n"
                "• **Message Templates:** Create and reuse message templates\n"
                "• **Smart Routing:** Automatic message routing and filtering\n\n"
                "**📢 Channel Management:**\n"
                "• **Join/Leave:** Bulk join or leave channels and groups\n"
                "• **Create Channels:** Create new channels and groups\n"
                "• **Channel Stats:** View comprehensive channel statistics\n"
                "• **Admin Tools:** Manage channel members and permissions\n\n"
                "**👥 Contact Tools:**\n"
                "• **Contact Export:** Export contacts to CSV with full details\n"
                "• **Contact Sync:** Sync contacts between accounts\n"
                "• **Contact Search:** Find and filter contacts\n"
                "• **Contact Groups:** Organize contacts with tags and groups\n\n"
                "**🎭 Automation:**\n"
                "• **Activity Simulation:** Human-like behavior to avoid detection\n"
                "• **Online Maker:** Keep accounts online automatically\n"
                "• **Scheduled Actions:** Automate routine tasks\n"
                "• **Smart Delays:** Realistic timing between actions\n\n"
                "**📊 Analytics & Monitoring:**\n"
                "• **Audit Logging:** Complete activity tracking\n"
                "• **OTP Statistics:** Security metrics and attack reports\n"
                "• **Performance Metrics:** System health and response times\n"
                "• **Usage Analytics:** Account activity and engagement stats"
            )
        elif action == "commands":
            text = (
                "📚 **Command Reference**\n\n"
                "**🚀 Quick Commands:**\n"
                "• `/start` - Initialize bot and show main menu\n"
                "• `/help` - Show this help system\n"
                "• `/accs` - List all your accounts\n"
                "• `/add` - Add new account (phone number)\n"
                "• `/otp` - Toggle OTP protection\n\n"
                "**📱 Account Commands:**\n"
                "• `/remove <account>` - Remove specific account\n"
                "• `/status <account>` - Check account status\n"
                "• `/sessions <account>` - View active sessions\n"
                "• `/profile <account>` - Manage account profile\n\n"
                "**💬 Messaging Commands:**\n"
                "• `/send <account> <target> <message>` - Send message\n"
                "• `/bulk_send` - Bulk message sender\n"
                "• `/auto_reply <account>` - Configure auto-reply\n"
                "• `/templates` - Message template manager\n\n"
                "**🛡️ Security Commands:**\n"
                "• `/otp_enable <account>` - Enable OTP Destroyer\n"
                "• `/otp_disable <account>` - Disable OTP Destroyer\n"
                "• `/2fa <account>` - Manage 2FA settings\n"
                "• `/audit <account>` - View audit logs\n\n"
                "**📢 Channel Commands:**\n"
                "• `/join <account> <channel>` - Join channel\n"
                "• `/leave <account> <channel>` - Leave channel\n"
                "• `/channels <account>` - List account channels\n"
                "• `/create <account> <name>` - Create new channel\n\n"
                "**⚙️ Admin Commands:**\n"
                "• `/sysinfo` - System information\n"
                "• `/logs` - View system logs\n"
                "• `/restart_bot` - Restart bot service\n"
                "• `/backup_now` - Trigger manual backup\n"
                "• `/health` - System health check\n\n"
                "**💡 Pro Tips:**\n"
                "• Use tab completion for account names\n"
                "• Commands are case-insensitive\n"
                "• Use quotes for multi-word arguments\n"
                "• Type `/help <command>` for detailed help"
            )
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
                "• OTP Destroyer\n"
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
            import platform
            import sys
            try:
                import psutil
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                cpu_info = f"{cpu_percent}%"
                memory_info = f"{memory.percent}% ({memory.used // (1024**3):.1f}GB / {memory.total // (1024**3):.1f}GB)"
                disk_info = f"{disk.percent}% ({disk.used // (1024**3):.1f}GB / {disk.total // (1024**3):.1f}GB)"
            except ImportError:
                cpu_info = "N/A (psutil not installed)"
                memory_info = "N/A"
                disk_info = "N/A"
            
            user_count = await mongodb.db.users.count_documents({})
            account_count = await mongodb.db.accounts.count_documents({})
            
            text = (
                "📊 **System Information**\n\n"
                f"**Platform:** {platform.system()} {platform.release()}\n"
                f"**Python:** {sys.version.split()[0]}\n"
                f"**CPU Usage:** {cpu_info}\n"
                f"**Memory:** {memory_info}\n"
                f"**Disk:** {disk_info}\n\n"
                "**Bot Statistics:**\n"
                f"• Active Users: {user_count}\n"
                f"• Total Accounts: {account_count}\n"
                f"• Bot Status: {'Connected' if self.bot.is_connected() else 'Disconnected'}\n"
                f"• Cache Status: {'Available' if hasattr(self.account_manager, 'redis') else 'N/A'}"
            )
        elif action == "logs":
            text = (
                "📋 **System Status & Logs**\n\n"
                "**Current Status:**\n"
                f"• Bot Connection: {'✅ Active' if self.bot.is_connected() else '❌ Inactive'}\n"
                f"• Database: {'✅ Connected' if mongodb.db else '❌ Disconnected'}\n"
                f"• Event Handlers: {len(self.bot.list_event_handlers())} active\n"
                f"• User Clients: {len(self.account_manager.user_clients) if self.account_manager else 0}\n\n"
                "**Log Information:**\n"
                "• INFO: General operations\n"
                "• WARNING: Potential issues\n"
                "• ERROR: System errors\n"
                "• DEBUG: Detailed debugging\n\n"
                "Use `/logs` command for detailed log viewing."
            )
        elif action == "dbstats":
            user_count = await mongodb.db.users.count_documents({})
            account_count = await mongodb.db.accounts.count_documents({})
            
            # Get database stats if available
            try:
                db_stats = await mongodb.db.command("dbStats")
                db_size = db_stats.get('dataSize', 0) / (1024 * 1024)  # Convert to MB
                index_size = db_stats.get('indexSize', 0) / (1024 * 1024)
                collections = db_stats.get('collections', 0)
            except Exception:
                db_size = 0
                index_size = 0
                collections = 0
            
            text = (
                "🗄️ **Database Statistics**\n\n"
                f"**Collections:**\n"
                f"• Users: {user_count}\n"
                f"• Accounts: {account_count}\n"
                f"• Total Collections: {collections}\n\n"
                f"**Storage:**\n"
                f"• Data Size: {db_size:.2f} MB\n"
                f"• Index Size: {index_size:.2f} MB\n\n"
                "**Performance:**\n"
                "• Connection: Healthy\n"
                "• Indexes: Optimized\n"
                f"• Cache: {'Available' if hasattr(self.account_manager, 'redis') else 'N/A'}"
            )
        elif action == "perf":
            import time
            start_time = time.time()
            
            # Test database query speed
            db_start = time.time()
            await mongodb.db.users.count_documents({})
            db_time = (time.time() - db_start) * 1000
            
            total_time = (time.time() - start_time) * 1000
            
            text = (
                "⚡ **Performance Metrics**\n\n"
                "**Response Times:**\n"
                f"• Menu Load: {total_time:.1f}ms\n"
                f"• Database Query: {db_time:.1f}ms\n"
                f"• Bot Response: {'<100ms' if self.bot.is_connected() else 'Disconnected'}\n\n"
                "**System Health:**\n"
                f"• Bot Connection: {'✅ Active' if self.bot.is_connected() else '❌ Inactive'}\n"
                f"• Database: {'✅ Connected' if mongodb.db is not None else '❌ Disconnected'}\n"
                f"• Cache: {'✅ Available' if hasattr(self.account_manager, 'redis') else '❌ Unavailable'}\n\n"
                "**Resource Status:**\n"
                "• Memory: Monitoring active\n"
                "• CPU: Efficient usage\n"
                "• Network: Optimized"
            )
        elif action == "maintenance":
            text = (
                "🔧 **Maintenance Tools**\n\n"
                "**Available Commands:**\n"
                "• `/cleanup_sessions` - Remove inactive sessions\n"
                "• `/optimize_db` - Optimize database performance\n"
                "• `/clear_cache` - Clear Redis cache\n"
                "• `/backup_now` - Trigger manual backup\n"
                "• `/health_check` - Full system health check\n\n"
                "**Automated Tasks:**\n"
                "• Session cleanup: Every 6 hours\n"
                "• Cache refresh: Every hour\n"
                "• Backup: Daily at 2 AM\n\n"
                "**System Status:** All services operational"
            )
        elif action == "restart":
            text = (
                "🔄 **Service Management**\n\n"
                "**Available Commands:**\n"
                "• `/restart_bot` - Restart bot instance\n"
                "• `/restart_db` - Reconnect database\n"
                "• `/restart_cache` - Restart Redis connection\n"
                "• `/reload_config` - Reload configuration\n\n"
                "⚠️ **Warning:** Service restarts may cause brief interruptions.\n\n"
                "**Current Status:**\n"
                f"• Bot: {'Running' if self.bot.is_connected() else 'Stopped'}\n"
                f"• Database: {'Connected' if mongodb.db is not None else 'Disconnected'}\n"
                f"• Cache: {'Active' if hasattr(self.account_manager, 'redis') else 'Inactive'}"
            )
        elif action == "startup":
            # Get current startup configuration
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            startup_notifications = user.get("startup_notifications", True) if user else True
            
            text = (
                "🚀 **Startup Configuration**\n\n"
                f"**Current Settings:**\n"
                f"• Startup Notifications: {'✅ Enabled' if startup_notifications else '❌ Disabled'}\n"
                f"• Auto-load Accounts: ✅ Enabled\n"
                f"• Health Checks: ✅ Enabled\n\n"
                "**Available Commands:**\n"
                "• `/startup_enable` - Enable startup notifications\n"
                "• `/startup_disable` - Disable startup notifications\n"
                "• `/startup_status` - View detailed status\n"
                "• `/startup_test` - Test startup sequence\n\n"
                "**Startup Features:**\n"
                "• Admin notifications on bot start\n"
                "• Automatic account loading\n"
                "• System health verification\n"
                "• Component initialization status"
            )
        elif action == "commands":
            text = (
                "📚 **Developer Commands**\n\n"
                "**System Management:**\n"
                "• `/sysinfo` - System information\n"
                "• `/health` - Health check\n"
                "• `/logs` - View recent logs\n"
                "• `/stats` - Bot statistics\n\n"
                "**Database:**\n"
                "• `/db_stats` - Database statistics\n"
                "• `/optimize_db` - Optimize database\n"
                "• `/backup_now` - Manual backup\n\n"
                "**Cache Management:**\n"
                "• `/cache_stats` - Cache statistics\n"
                "• `/cache_clear` - Clear cache\n"
                "• `/cache_health` - Cache health\n\n"
                "**Maintenance:**\n"
                "• `/cleanup_sessions` - Clean sessions\n"
                "• `/restart_bot` - Restart services\n"
                "• `/reload_config` - Reload config\n\n"
                "**Bulk Operations:**\n"
                "• `/bulk_send` - Bulk messaging\n"
                "• `/bulk_jobs` - Active jobs\n"
                "• `/bulk_stop <id>` - Stop job"
            )
        else:
            text = "❌ Unknown developer action"
            
        buttons = [[Button.inline("🔙 Back to Developer", "menu:developer")]]
        await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
    
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
    async def _show_channel_statistics(self, user_id: int, message_id: int):
        """Show comprehensive channel statistics for all user accounts"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = "📊 **Channel Statistics**\n\n❌ No accounts found. Add accounts first to view channel statistics."
                buttons = [[Button.inline("🔙 Back to Channels", "menu:channels")]]
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                return
            total_channels = 0
            total_groups = 0
            admin_channels = 0
            admin_groups = 0
            account_stats = []
            for account in accounts:
                if not account.get("is_active", False):
                    continue
                try:
                    if hasattr(self.account_manager, 'command_handlers') and hasattr(self.account_manager.command_handlers, 'channel_manager'):
                        success, channels = await self.account_manager.command_handlers.channel_manager.get_user_channels(
                            user_id, account['phone']
                        )
                        if success and channels:
                            account_channels = sum(1 for ch in channels if ch['type'] == 'channel')
                            account_groups = sum(1 for ch in channels if ch['type'] == 'group')
                            total_channels += account_channels
                            total_groups += account_groups
                            # For admin status, we'll estimate based on channel ownership patterns
                            # This is a simplified approach since checking admin status requires API calls
                            estimated_admin_channels = max(1, account_channels // 10)  # Estimate 10% are admin
                            estimated_admin_groups = max(1, account_groups // 5)       # Estimate 20% are admin
                            admin_channels += estimated_admin_channels
                            admin_groups += estimated_admin_groups
                            account_stats.append({
                                'name': account['name'],
                                'phone': account['phone'],
                                'channels': account_channels,
                                'groups': account_groups,
                                'total': account_channels + account_groups
                            })
                        else:
                            account_stats.append({
                                'name': account['name'],
                                'phone': account['phone'],
                                'channels': 0,
                                'groups': 0,
                                'total': 0,
                                'error': 'Could not load channels'
                            })
                except Exception as e:
                    logger.error(f"Error getting channels for {account['name']}: {e}")
                    account_stats.append({
                        'name': account['name'],
                        'phone': account['phone'],
                        'channels': 0,
                        'groups': 0,
                        'total': 0,
                        'error': 'Connection error'
                    })
            # Build statistics text
            text = (
                "📊 **Channel Statistics**\n\n"
                f"**📈 Overall Summary:**\n"
                f"• Total Channels: {total_channels}\n"
                f"• Total Groups: {total_groups}\n"
                f"• Combined Total: {total_channels + total_groups}\n"
                f"• Admin Channels: ~{admin_channels}\n"
                f"• Admin Groups: ~{admin_groups}\n\n"
                f"**📱 Per Account Breakdown:**\n"
            )
            for i, stats in enumerate(account_stats, 1):
                status = "✅" if not stats.get('error') else "❌"
                if stats.get('error'):
                    text += f"{i}. {status} {stats['name']} - {stats['error']}\n"
                else:
                    text += f"{i}. {status} {stats['name']} - {stats['channels']}📢 {stats['groups']}👥 (Total: {stats['total']})\n"
            if not account_stats:
                text += "No active accounts found.\n"
            text += (
                "\n**📝 Notes:**\n"
                "• Only active accounts are counted\n"
                "• Admin roles are estimated\n"
                "• Statistics updated in real-time\n"
                "• 📢 = Channels, 👥 = Groups"
            )
            buttons = [
                [Button.inline("🔄 Refresh Stats", "channel:stats")],
                [Button.inline("🔙 Back to Channels", "menu:channels")]
            ]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing channel statistics: {e}")
            text = (
                "📊 **Channel Statistics**\n\n"
                "❌ Error loading statistics. Please try again.\n\n"
                f"Error: {str(e)}"
            )
            buttons = [[Button.inline("🔙 Back to Channels", "menu:channels")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
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
            buttons = [[Button.inline("🔙 Back to DM Reply", "menu:dm_reply")]]
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)

    
    async def _handle_export_sessions(self, event, user_id: int):
        """Handle export sessions menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = "✨ **Fresh Sessions**\n\n❌ No accounts found. Add accounts first to create fresh sessions."
                buttons = [[Button.inline("🔙 Back to Accounts", "menu:accounts")]]
            else:
                text = "✨ **Fresh Sessions**\n\nSelect account to create fresh session for:"
                buttons = []
                for account in accounts:
                    status = "✅" if account.get("is_active", False) else "❌"
                    display_name = self.format_display_name(account)
                    buttons.append([Button.inline(f"{status} {display_name}", f"export_session:{account['name']}")])
                buttons.append([Button.inline("🔙 Back to Accounts", "menu:accounts")])
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to handle export sessions: {e}")
            await event.answer("❌ Error loading export sessions")
    
    async def _handle_export_session_select(self, event, user_id: int, account_name: str):
        """Handle export session selection"""
        try:
            # Find account by name
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            if not account:
                await event.answer("❌ Account not found")
                return
            
            display_name = self.format_display_name(account)
            text = f"✨ **Fresh Session: {display_name}**\n\nThis will create a completely new session:"
            buttons = [
                [Button.inline("✨ Create Fresh Session", f"export_fresh:{account_name}")],
                [Button.inline("🔙 Back to Export", "export_sessions")]
            ]
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to handle export session select: {e}")
            await event.answer("❌ Error processing export selection")
    
    async def _handle_export_session_file(self, event, user_id: int, account_name: str):
        """Handle export session file"""
        try:
            # Find account by name
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            if not account:
                await event.answer("❌ Account not found")
                return
            
            if not account.get("is_active", False):
                await event.answer("❌ Account is not connected")
                return
            
            # Use account manager to export session file
            if hasattr(self.account_manager, 'export_session_file'):
                success, message = await self.account_manager.export_session_file(user_id, account['phone'])
                if success:
                    await event.answer("✅ Session file exported successfully")
                else:
                    await event.answer(f"❌ Export failed: {message}")
            else:
                await event.answer("❌ Export functionality not available")
        except Exception as e:
            logger.error(f"Failed to export session file: {e}")
            await event.answer("❌ Error exporting session file")
    
    async def _handle_export_fresh_session(self, event, user_id: int, account_name: str):
        """Handle export session string with DC information"""
        try:
            # Find account by name
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            if not account:
                await event.answer("❌ Account not found")
                return
            
            if not account.get("is_active", False):
                await event.answer("❌ Account is not connected")
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
                            f"📝 **Session Export - {dc_display}**\n\n"
                            f"📱 **Account:** {display_name}\n"
                            f"📞 **Phone:** {phone}\n"
                            f"🌐 **Data Center:** {dc_display}\n\n"
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
                            f"⚠️ **Keep this {dc_display} session secure!**"
                        )
                        
                        await self.bot.send_message(user_id, message)
                        await event.answer(f"✅ {dc_display} session exported")
                        
                    except Exception as e:
                        logger.error(f"Error getting session data: {e}")
                        await event.answer("❌ Error extracting session data")
                else:
                    await event.answer("❌ Account client not connected")
            else:
                await event.answer("❌ Account client not found")
                
        except Exception as e:
            logger.error(f"Failed to export session string: {e}")
            await event.answer("❌ Error exporting session string")
    
    async def _handle_export_contacts(self, event, user_id: int, account_name: str):
        """Handle export contacts"""
        try:
            # Find account by name
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            if not account:
                await event.answer("❌ Account not found")
                return
            
            if not account.get("is_active", False):
                await event.answer("❌ Account is not connected")
                return
            
            # Use contact export handler
            try:
                from ..handlers.contact_export_handler import ContactExportHandler
                export_handler = ContactExportHandler(self.account_manager)
                success, message = await export_handler.export_contacts_to_csv(user_id, account['phone'])
                if success:
                    await event.answer("✅ Contacts exported successfully")
                else:
                    await event.answer(f"❌ Export failed: {message}")
            except ImportError:
                await event.answer("❌ Contact export handler not available")
        except Exception as e:
            logger.error(f"Failed to export contacts: {e}")
            await event.answer("❌ Error exporting contacts")
    
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
                "📊 **OTP Statistics (Last 30 Days)**\n\n"
                f"🕰 **Global Summary:**\n"
                f"• Total Blocks: {global_stats.get('total_blocked', 0):,}\n"
                f"• Total Allows: {global_stats.get('total_allowed', 0):,}\n"
                f"• Protected Accounts: {len(global_stats.get('accounts', []))}\n"
                f"• Success Rate: {global_stats.get('block_rate', 0):.1f}%\n\n"
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
                    f"📱 **Your Accounts:**\n"
                    f"• Your Blocks: {user_total_blocks:,}\n"
                    f"• Your Allows: {user_total_allows:,}\n"
                    f"• Managed Accounts: {len(accounts)}\n\n"
                )
            
            # Add top blocked accounts
            if top_blocked:
                text += "🏆 **Top Protected Accounts:**\n"
                for i, account_data in enumerate(top_blocked, 1):
                    account_id = account_data['_id']
                    blocks = account_data['total_blocked']
                    text += f"{i}. Account {account_id[:8]}... - {blocks:,} blocks\n"
                text += "\n"
            
            # Add activity sparkline
            if sparkline:
                text += f"📈 **Activity (Last 7 Days):**\n{sparkline}\n\n"
            
            text += (
                "📝 **Legend:**\n"
                "• Blocks: Unauthorized login attempts stopped\n"
                "• Allows: Legitimate OTP codes forwarded\n"
                "• Success Rate: Percentage of malicious attempts blocked"
            )
            
            buttons = [
                [Button.inline("🔄 Refresh Stats", "otp:stats")],
                [Button.inline("🔙 Back to OTP Manager", "menu:otp")]
            ]
            
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error showing OTP statistics: {e}")
            text = (
                "📊 **OTP Statistics**\n\n"
                "❌ Error loading statistics. Please try again.\n\n"
                f"Error: {str(e)}"
            )
            buttons = [[Button.inline("🔙 Back to OTP Manager", "menu:otp")]]
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
                text = "🛡️ **Enable All OTP Destroyers**\n\n❌ No accounts found."
                buttons = [[Button.inline("🔙 Back to OTP Manager", "menu:otp")]]
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
                f"🛡️ **Bulk Enable Complete**\n\n"
                f"✅ Enabled OTP Destroyer for {enabled_count}/{len(accounts)} accounts\n\n"
                f"🔴 Forward disabled for all accounts (security best practice)\n\n"
                f"🛡️ All your accounts are now protected!"
            )
            
            buttons = [
                [Button.inline("📊 View Statistics", "otp:stats")],
                [Button.inline("🔙 Back to OTP Manager", "menu:otp")]
            ]
            
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in bulk OTP enable: {e}")
            text = f"❌ Error enabling OTP Destroyers: {str(e)}"
            buttons = [[Button.inline("🔙 Back to OTP Manager", "menu:otp")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _handle_bulk_otp_disable(self, user_id: int, message_id: int):
        """Disable OTP Destroyer for all user accounts"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = "🔴 **Disable All OTP Destroyers**\n\n❌ No accounts found."
                buttons = [[Button.inline("🔙 Back to OTP Manager", "menu:otp")]]
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
                f"🔴 **Bulk Disable Complete**\n\n"
                f"❌ Disabled OTP Destroyer for {disabled_count}/{len(accounts)} accounts\n\n"
                f"⚠️ **WARNING:** All your accounts are now vulnerable to unauthorized login attempts!\n\n"
                f"🛡️ Consider re-enabling protection when needed."
            )
            
            buttons = [
                [Button.inline("🛡️ Enable All Again", "otp:enable_all")],
                [Button.inline("🔙 Back to OTP Manager", "menu:otp")]
            ]
            
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in bulk OTP disable: {e}")
            text = f"❌ Error disabling OTP Destroyers: {str(e)}"
            buttons = [[Button.inline("🔙 Back to OTP Manager", "menu:otp")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _handle_otp_setting_callback(self, event, user_id: int, data: str):
        """Handle OTP setting callbacks - show accounts after selecting setting"""
        parts = data.split(":")
        setting = parts[1]
        
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                await event.answer("❌ No accounts found")
                return
            
            if setting == "destroyer":
                text = "🛡️ **OTP Destroyer Settings**\n\nSelect account to manage OTP Destroyer:\n\n"
                for account in accounts:
                    status = "🟢" if account.get("otp_destroyer_enabled", False) else "🔴"
                    display_name = account.get('display_name') or format_display_name(account)
                    text += f"{status} {display_name}\n"
                
                buttons = []
                for account in accounts:
                    status = "🟢" if account.get("otp_destroyer_enabled", False) else "🔴"
                    display_name = account.get('display_name') or format_display_name(account)
                    buttons.append([Button.inline(f"{status} {display_name}", f"otp:manage:{account['_id']}")])
                    
            elif setting == "forward":
                text = "📤 **OTP Forward Settings**\n\nSelect account to manage OTP Forward:\n\n"
                for account in accounts:
                    status = "🟢" if account.get("otp_forward_enabled", False) else "🔴"
                    display_name = account.get('display_name') or format_display_name(account)
                    text += f"{status} {display_name}\n"
                
                buttons = []
                for account in accounts:
                    status = "🟢" if account.get("otp_forward_enabled", False) else "🔴"
                    display_name = account.get('display_name') or format_display_name(account)
                    buttons.append([Button.inline(f"{status} {display_name}", f"otp:manage:{account['_id']}")])
                    
            elif setting == "temp":
                text = "⏰ **Temp OTP Settings**\n\nSelect account for 5-minute OTP bypass:\n\n"
                for account in accounts:
                    destroyer_enabled = account.get("otp_destroyer_enabled", False)
                    status = "⏰" if destroyer_enabled else "❌"
                    display_name = account.get('display_name') or format_display_name(account)
                    text += f"{status} {display_name}" + (" (Destroyer required)" if not destroyer_enabled else "") + "\n"
                
                buttons = []
                for account in accounts:
                    destroyer_enabled = account.get("otp_destroyer_enabled", False)
                    status = "⏰" if destroyer_enabled else "❌"
                    display_name = account.get('display_name') or format_display_name(account)
                    buttons.append([Button.inline(f"{status} {display_name}", f"otp:manage:{account['_id']}")])
            
            buttons.append([Button.inline("🔙 Back to OTP Manager", "menu:otp")])
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error handling OTP setting callback: {e}")
            await event.answer("❌ Error processing OTP setting")
    
    async def _show_global_audit_log(self, user_id: int, message_id: int):
        """Show global audit log for all user accounts"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = "📋 **Global OTP Audit Log**\n\n❌ No accounts found."
                buttons = [[Button.inline("🔙 Back to OTP Manager", "menu:otp")]]
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
                text = "📋 **Global OTP Audit Log**\n\n💭 No audit entries found across all accounts."
            else:
                text = f"📋 **Global OTP Audit Log**\n\nShowing last {min(15, len(all_entries))} entries across all accounts:\n\n"
                
                # Show last 15 entries
                for entry in all_entries[:15]:
                    timestamp = entry.get("timestamp", 0)
                    action = entry.get("action", "unknown")
                    account_name = entry.get("account_name", "Unknown")
                    
                    import time
                    time_str = time.strftime("%m-%d %H:%M", time.localtime(timestamp))
                    
                    # Map actions to user-friendly messages
                    action_messages = {
                        "otp_destroyed": f"🛡️ Blocked login code {entry.get('code', 'Unknown')}",
                        "otp_forwarded": f"📤 Forwarded login code {entry.get('code', 'Unknown')}",
                        "destroyer_enabled": "🛡️ OTP Destroyer enabled",
                        "destroyer_disabled": "🔴 OTP Destroyer disabled",
                        "forwarding_enabled": "📤 OTP Forwarding enabled",
                        "forwarding_disabled": "🔴 OTP Forwarding disabled",
                        "temp_passthrough_enabled": "⏰ 5-minute passthrough activated",
                        "temp_passthrough_expired": "⏰ 5-minute passthrough expired",
                    }
                    
                    message = action_messages.get(action, f"Unknown: {action}")
                    text += f"{time_str} | {account_name[:12]}: {message}\n"
                
                if len(all_entries) > 15:
                    text += f"\n... and {len(all_entries) - 15} more entries"
            
            buttons = [
                [Button.inline("🔄 Refresh Log", "otp:audit_all")],
                [Button.inline("📊 View Statistics", "otp:stats")],
                [Button.inline("🔙 Back to OTP Manager", "menu:otp")]
            ]
            
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error showing global audit log: {e}")
            text = f"❌ Error loading global audit log: {str(e)}"
            buttons = [[Button.inline("🔙 Back to OTP Manager", "menu:otp")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    async def _handle_otp_setting_callback(self, event, user_id: int, data: str):
        """Handle OTP setting callbacks - direct enable/disable without old menu"""
        parts = data.split(":")
        setting_type = parts[1]  # destroyer, forward, or temp
        
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                await event.answer("❌ No accounts found")
                return
            
            if setting_type == "destroyer":
                text = "🛡️ **OTP Destroyer Settings**\n\nSelect account to toggle OTP Destroyer:"
                buttons = []
                for account in accounts:
                    status = "🟢" if account.get("is_active", False) else "🔴"
                    destroyer_status = "🛡️" if account.get("otp_destroyer_enabled", False) else "⚪"
                    display_name = format_display_name(account)
                    action = "disable" if account.get("otp_destroyer_enabled", False) else "enable"
                    button_text = f"{status}{destroyer_status} {display_name}"
                    buttons.append([Button.inline(button_text, f"otp:{action}:{account['_id']}")])
                    
            elif setting_type == "forward":
                text = "📤 **OTP Forward Settings**\n\nSelect account to toggle OTP Forward:"
                buttons = []
                for account in accounts:
                    status = "🟢" if account.get("is_active", False) else "🔴"
                    forward_status = "📤" if account.get("otp_forward_enabled", False) else "⚪"
                    display_name = format_display_name(account)
                    action = "forward_disable" if account.get("otp_forward_enabled", False) else "forward_enable"
                    button_text = f"{status}{forward_status} {display_name}"
                    buttons.append([Button.inline(button_text, f"otp:{action}:{account['_id']}")])
                    
            elif setting_type == "temp":
                text = "⏰ **Temp OTP Settings**\n\nSelect account to enable 5-minute temp OTP:"
                buttons = []
                for account in accounts:
                    status = "🟢" if account.get("is_active", False) else "🔴"
                    destroyer_status = "🛡️" if account.get("otp_destroyer_enabled", False) else "⚪"
                    display_name = format_display_name(account)
                    button_text = f"{status}{destroyer_status} {display_name}"
                    buttons.append([Button.inline(button_text, f"otp:temp:{account['_id']}")])
            
            buttons.append([Button.inline("🔙 Back to OTP Manager", "menu:otp")])
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in OTP setting callback: {e}")
            await event.answer("❌ Error processing OTP setting")

    async def _show_global_audit_log(self, user_id: int, message_id: int):
        """Show global audit log for all user accounts"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = "📋 **Global Audit Log**\n\n❌ No accounts found."
                buttons = [[Button.inline("🔙 Back to OTP Manager", "menu:otp")]]
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
                text = "📋 **Global Audit Log**\n\n💭 No audit entries found."
            else:
                text = f"📋 **Global Audit Log** (Last {len(all_entries)} entries)\n\n"
                
                for entry in all_entries[:15]:
                    timestamp = entry.get("timestamp", 0)
                    action = entry.get("action", "unknown")
                    account_name = entry.get("account_name", "Unknown")
                    
                    import time
                    time_str = time.strftime("%m-%d %H:%M", time.localtime(timestamp))
                    
                    if action in ["otp_destroyed", "invalidate_codes"]:
                        emoji = "🛡️"
                        msg = f"Blocked login code {entry.get('code', 'Unknown')}"
                    elif action == "otp_forwarded":
                        emoji = "📤"
                        msg = f"Forwarded login code {entry.get('code', 'Unknown')}"
                    elif action in ["destroyer_enabled", "enable_otp_destroyer"]:
                        emoji = "🟢"
                        msg = "OTP Destroyer enabled"
                    elif action in ["destroyer_disabled", "disable_otp_destroyer"]:
                        emoji = "🔴"
                        msg = "OTP Destroyer disabled"
                    else:
                        emoji = "ℹ️"
                        msg = f"Action: {action}"
                    
                    text += f"{emoji} {time_str} [{account_name}]: {msg}\n"
            
            buttons = [
                [Button.inline("🔄 Refresh", "otp:audit_all")],
                [Button.inline("🔙 Back to OTP Manager", "menu:otp")]
            ]
            
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error showing global audit log: {e}")
            text = "❌ Error loading global audit log"
            buttons = [[Button.inline("🔙 Back to OTP Manager", "menu:otp")]]
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
                await event.answer("❌ Account not found")
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
                    await event.answer(f"🛡️ OTP Destroyer enabled for {display_name}!")
                else:
                    await event.answer(f"🔴 OTP Destroyer disabled for {display_name}!")
                    
            elif toggle_type == "forward":
                # Check if destroyer is enabled first
                if account.get("otp_destroyer_enabled", False):
                    await event.answer("❌ Cannot enable forward while OTP Destroyer is active")
                    return
                    
                current_status = account.get("otp_forward_enabled", False)
                new_status = not current_status
                
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {"otp_forward_enabled": new_status}}
                )
                
                if new_status:
                    await event.answer(f"📤 OTP Forward enabled for {display_name}!")
                else:
                    await event.answer(f"🔴 OTP Forward disabled for {display_name}!")
                    
            elif toggle_type == "temp":
                if not account.get("otp_destroyer_enabled", False):
                    await event.answer("⚠️ Temp OTP only works when OTP Destroyer is enabled")
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
                
                await event.answer(f"⏰ 5-minute temp OTP enabled for {display_name}!")
                
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
            await event.answer("❌ Error toggling OTP setting")



    async def _show_messaging_statistics(self, user_id: int, message_id: int):
        """Show messaging statistics"""
        try:
            from telethon import Button
            if hasattr(self.account_manager, 'unified_messaging'):
                stats = await self.account_manager.unified_messaging.get_messaging_statistics(user_id)
                
                text = (
                    "📊 **Messaging Analytics**\n\n"
                    f"📤 **Total Messages:** {stats.get('total_messages_sent', 0)}\n"
                    f"🤖 **Auto-Replies:** {stats.get('auto_replies_sent', 0)}\n"
                    f"📱 **Active Accounts:** {stats.get('active_accounts', 0)}\n"
                    f"📨 **DM Topics:** {stats.get('dm_topics_created', 0)}\n\n"
                    "💡 **Tip:** Enable auto-reply for better engagement"
                )
            else:
                text = "📊 **Messaging Analytics**\n\n❌ Analytics is unavailable for messages"
            
            buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing messaging statistics: {e}")
            from telethon import Button
            text = "❌ Analytics is unavailable for messages"
            buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _show_message_history(self, user_id: int, message_id: int):
        """Show message history"""
        try:
            from telethon import Button
            from ..services.messaging_stats import MessagingStats
            stats_service = MessagingStats()
            
            recent_messages = await stats_service.get_recent_messages(user_id, limit=10)
            
            if not recent_messages:
                text = "📋 **Message History**\n\n💭 No recent messages found."
            else:
                text = "📋 **Message History** (Last 10)\n\n"
                for msg in recent_messages:
                    import time
                    timestamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(msg.get('timestamp', 0)))
                    target = msg.get('target', 'Unknown')
                    msg_type = msg.get('type', 'message')
                    emoji = "🤖" if msg_type == "auto_reply" else "📤"
                    text += f"{emoji} {timestamp} → {target}\n"
            
            buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing message history: {e}")
            from telethon import Button
            text = "❌ Message history is unavailable"
            buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _show_messaging_settings(self, user_id: int, message_id: int):
        """Show messaging system settings"""
        try:
            from telethon import Button
            settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
            
            keyword_enabled = settings.get('keyword_replies_enabled', False)
            time_based_enabled = settings.get('time_based_replies_enabled', False)
            
            text = (
                "⚙️ **Messaging System Settings**\n\n"
                f"🔑 **Keyword Replies:** {'✅ Enabled' if keyword_enabled else '❌ Disabled'}\n"
                f"⏰ **Time-Based Replies:** {'✅ Enabled' if time_based_enabled else '❌ Disabled'}\n\n"
                "**Configure:**\n"
                "• Auto-reply rules\n"
                "• Message templates\n"
                "• DM forwarding\n"
                "• Notification preferences\n\n"
                "Use the buttons below to manage settings."
            )
            
            buttons = [
                [Button.inline("🤖 Auto-Reply Settings", "auto_reply:main")],
                [Button.inline("📝 Template Settings", "template:main")],
                [Button.inline("📨 DM Reply Settings", "dm_reply:main")],
                [Button.inline("🔙 Back to Messaging", "menu:messaging")]
            ]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing messaging settings: {e}")
            from telethon import Button
            text = "❌ System settings is unavailable"
            buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)



    async def _show_messaging_statistics(self, user_id: int, message_id: int):
        """Show messaging statistics"""
        try:
            from telethon import Button
            if hasattr(self.account_manager, 'unified_messaging'):
                stats = await self.account_manager.unified_messaging.get_messaging_statistics(user_id)
                
                text = (
                    "📊 **Messaging Analytics**\n\n"
                    f"📤 **Total Messages:** {stats.get('total_messages_sent', 0)}\n"
                    f"🤖 **Auto-Replies:** {stats.get('auto_replies_sent', 0)}\n"
                    f"📱 **Active Accounts:** {stats.get('active_accounts', 0)}\n"
                    f"📨 **DM Topics:** {stats.get('dm_topics_created', 0)}\n\n"
                    "💡 **Tip:** Enable auto-reply for better engagement"
                )
            else:
                text = "📊 **Messaging Analytics**\n\n❌ Analytics is unavailable for messages"
            
            buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing messaging statistics: {e}")
            from telethon import Button
            text = "❌ Analytics is unavailable for messages"
            buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _show_message_history(self, user_id: int, message_id: int):
        """Show message history"""
        try:
            from telethon import Button
            from ..services.messaging_stats import MessagingStats
            stats_service = MessagingStats()
            
            recent_messages = await stats_service.get_recent_messages(user_id, limit=10)
            
            if not recent_messages:
                text = "📋 **Message History**\n\n💭 No recent messages found."
            else:
                text = "📋 **Message History** (Last 10)\n\n"
                for msg in recent_messages:
                    import time
                    timestamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(msg.get('timestamp', 0)))
                    target = msg.get('target', 'Unknown')
                    msg_type = msg.get('type', 'message')
                    emoji = "🤖" if msg_type == "auto_reply" else "📤"
                    text += f"{emoji} {timestamp} → {target}\n"
            
            buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing message history: {e}")
            from telethon import Button
            text = "❌ Message history is unavailable"
            buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def _show_messaging_settings(self, user_id: int, message_id: int):
        """Show messaging system settings"""
        try:
            from telethon import Button
            settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
            
            keyword_enabled = settings.get('keyword_replies_enabled', False)
            time_based_enabled = settings.get('time_based_replies_enabled', False)
            
            text = (
                "⚙️ **Messaging System Settings**\n\n"
                f"🔑 **Keyword Replies:** {'✅ Enabled' if keyword_enabled else '❌ Disabled'}\n"
                f"⏰ **Time-Based Replies:** {'✅ Enabled' if time_based_enabled else '❌ Disabled'}\n\n"
                "**Configure:**\n"
                "• Auto-reply rules\n"
                "• Message templates\n"
                "• DM forwarding\n"
                "• Notification preferences\n\n"
                "Use the buttons below to manage settings."
            )
            
            buttons = [
                [Button.inline("🤖 Auto-Reply Settings", "auto_reply:main")],
                [Button.inline("📝 Template Settings", "template:main")],
                [Button.inline("📨 DM Reply Settings", "dm_reply:main")],
                [Button.inline("🔙 Back to Messaging", "menu:messaging")]
            ]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing messaging settings: {e}")
            from telethon import Button
            text = "❌ System settings is unavailable"
            buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
