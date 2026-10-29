# -*- coding: utf-8 -*-
"""Menu text handlers"""
import logging
import time

from telethon import Button
from telethon.errors import MessageIdInvalidError, MessageNotModifiedError

from ...core.config import ADMIN_IDS
from ...core.mongo_database import mongodb
from ...utils.network_helpers import format_display_name, format_phone_number

logger = logging.getLogger(__name__)


class MenuHandlers:
    def __init__(self, menu_system):
        self.menu = menu_system
        self.bot = menu_system.bot
        self.account_manager = menu_system.account_manager

    async def _render_menu(self, user_id, message_id, text, buttons):
        if not message_id:
            await self.bot.send_message(user_id, text, buttons=buttons)
            return

        try:
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except MessageNotModifiedError:
            return
        except MessageIdInvalidError as error:
            logger.warning(
                "Could not edit menu message %s for user %s; sending a new message: %s",
                message_id,
                user_id,
                error,
            )
            await self.bot.send_message(user_id, text, buttons=buttons)

    @staticmethod
    def _is_temp_bypass_active(account, now):
        if not account.get("otp_temp_passthrough"):
            return False
        try:
            expiry = float(account.get("temp_passthrough_expiry") or 0)
        except (TypeError, ValueError):
            return False
        return expiry > now

    @staticmethod
    def _otp_coverage(accounts, bypassed_account_ids):
        if not accounts:
            return 0
        protected = sum(
            1
            for account in accounts
            if account.get("otp_destroyer_enabled", False)
            and account.get("_id") not in bypassed_account_ids
        )
        return int((protected / len(accounts)) * 100)

    def _is_cleanup_account_available(self, user_id, account):
        if not account.get("is_active", False) or not self.account_manager:
            return False
        clients = (
            getattr(self.account_manager, "user_clients", {}).get(user_id, {}) or {}
        )
        client = clients.get(account.get("name"))
        return bool(client and client.is_connected())

    async def handle_account_settings(self, event):
        user_id = event.sender_id
        await self.menu._cleanup_old_messages(user_id)
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        if not accounts:
            text = "📱 **Account Management Center**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🚀 **Welcome to TeleGuard!**\n\nNo accounts found. Let's get you started with your first account.\n\n🎯 **Quick Setup:**\n1️⃣ Add your first account\n2️⃣ Enable OTP protection\n3️⃣ Explore advanced features\n\nChoose an option below to begin:"
            buttons = [
                [Button.inline("🚀 Add First Account", "account:add")],
                [
                    Button.inline("🔐 Session Login", "session_login"),
                    Button.inline("📥 Import Sessions", "import_sessions"),
                ],
                [Button.inline("❓ Setup Guide", "help:guide")],
                [Button.inline("🔙 Back to Main Menu", "menu:main")],
            ]
        else:
            active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
            protected_accounts = sum(
                1 for acc in accounts if acc.get("otp_destroyer_enabled", False)
            )
            text = f"📱 **Account Management Center**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📊 **Overview:**\n• 📱 Total Accounts: {
                len(accounts)}\n• 🟢 Active: {active_accounts}\n• 🛡️ Protected: {protected_accounts}\n\n📋 **Your Accounts:**\n"
            buttons = []
            for i, account in enumerate(accounts, 1):
                status = "🟢" if account.get("is_active", False) else "🔴"
                destroyer_status = (
                    "🛡️" if account.get("otp_destroyer_enabled", False) else "⚪"
                )
                display_name = format_display_name(account)
                account_phone = format_phone_number(account.get("phone", "Unknown"))
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
            buttons.extend(
                [
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
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            )
        await self._render_menu(
            user_id, getattr(event, "message_id", None), text, buttons
        )

    async def handle_otp_manager(self, event):
        user_id = event.sender_id
        await self.menu._cleanup_old_messages(user_id)
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        if not accounts:
            text = "🛡️ **Protection Manager**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🚨 **No accounts found!**\n\nYou need to add accounts first before configuring protection.\n\n🎯 **Available Protections:**\n• 🔥 **Session Destroyer** - Monitors and responds to session changes based on your trust settings\n• 🛡️ **OTP Destroyer** - Handles incoming login codes according to your protection settings\n• 📩 **OTP Forward** - Forwards OTP codes to you\n• ⏰ **Temp Bypass** - Temporarily pauses configured protections\n\nAdd your first account to get started:"
            buttons = [
                [Button.inline("🚀 Add First Account", "account:add")],
                [Button.inline("❓ Security Guide", "help:security")],
                [Button.inline("🔙 Back to Main Menu", "menu:main")],
            ]
        else:
            destroyer_enabled = sum(
                1 for acc in accounts if acc.get("otp_destroyer_enabled", False)
            )
            forward_enabled = sum(
                1 for acc in accounts if acc.get("otp_forward_enabled", False)
            )
            now = time.time()
            bypassed_account_ids = {
                account.get("_id")
                for account in accounts
                if self._is_temp_bypass_active(account, now)
            }
            temp_active = len(bypassed_account_ids)
            
            from ...services.protection_storage import ProtectionStorage

            protection_settings = await ProtectionStorage.get_settings(user_id)
            session_destroyer_enabled = protection_settings.get(
                "session_destroyer_enabled", False
            )
            sd_enabled = "🔥" if session_destroyer_enabled else "⚪"
            
            security_score = self._otp_coverage(
                accounts, bypassed_account_ids
            )
                
            security_emoji = (
                "🟢" if security_score >= 80 else "🟡" if security_score >= 50 else "🔴"
            )
            
            text = (
                f"🛡️ **Protection Manager**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 **Security Dashboard:**\n"
                f"• {security_emoji} **Configured OTP Coverage (excluding bypasses):** {security_score}%\n"
                f"• {sd_enabled} **Session Destroyer:** {'Enabled' if session_destroyer_enabled else 'Disabled'}\n"
                f"• 🛡️ **OTP Destroyer:** {destroyer_enabled}/{len(accounts)} accounts\n"
                f"• 📩 **OTP Forward:** {forward_enabled}/{len(accounts)} accounts\n\n"
                f"• ⏰ **Temporary Bypass:** {temp_active}/{len(accounts)} accounts\n\n"
                f"🎛️ **Protection Controls:**\n"
                f"Choose your security configuration below:"
            )
            
            buttons = [
                [
                    Button.inline("🔥 Session Destroyer", "sd:main"),
                    Button.inline("🛡️ OTP Destroyer", "otp_setting:destroyer"),
                ],
                [
                    Button.inline("📩 OTP Forward", "otp_setting:forward"),
                    Button.inline("⏰ Temp Bypass", "otp_setting:temp"),
                ],
                [
                    Button.inline("📊 Statistics", "otp:stats"),
                ],
                [
                    Button.inline("🟢 Enable All Protection", "otp:enable_all"),
                    Button.inline("🔴 Disable All Protection", "otp:disable_all"),
                ],
                [Button.inline("📋 Security Audit Log", "otp:audit_all")],
                [Button.inline("🔙 Back to Main Menu", "menu:main")],
            ]
        await self._render_menu(
            user_id, getattr(event, "message_id", None), text, buttons
        )

    async def handle_messaging(self, event):
        user_id = event.sender_id
        await self.menu._cleanup_old_messages(user_id)
        await self.show_messaging_menu(user_id, getattr(event, "message_id", None))

    async def show_messaging_menu(self, user_id, message_id=None):
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        if not accounts:
            text = "💬 **Advanced Messaging Center**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🚨 **No accounts available!**\n\nYou need active accounts to use messaging features.\n\n🎯 **Available Features:**\n• 📤 **Smart Messaging** - Send to users/groups\n• 📨 **Bulk Operations** - Mass messaging campaigns\n• 🤖 **Auto-Reply** - Intelligent response system\n• 📝 **Templates** - Reusable message templates\n• 📨 **DM Management** - Unified inbox system\n\nAdd accounts to unlock these powerful features:"
            buttons = [
                [Button.inline("🚀 Add First Account", "account:add")],
                [Button.inline("❓ Messaging Guide", "help:features")],
                [Button.inline("🔙 Back to Main Menu", "menu:main")],
            ]
        else:
            active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
            auto_reply_enabled = sum(
                1 for acc in accounts if acc.get("auto_reply_enabled", False)
            )
            text = f"💬 **Advanced Messaging Center**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📊 **Configured Status:**\n• 📱 Active Accounts: {active_accounts}/{
                len(accounts)}\n• 🤖 Auto-Reply: {auto_reply_enabled} enabled\n\n🚀 **Messaging Tools:**\nChoose your messaging action below:"
            buttons = [
                [
                    Button.inline("📤 Smart Messaging", "msg:send"),
                    Button.inline("📨 Bulk Campaigns", "msg:bulk"),
                ],
                [
                    Button.inline("🤖 Auto-Reply System", "auto_reply:main"),
                    Button.inline("📝 Message Templates", "msg:templates"),
                ],
                [Button.inline("⏰ Scheduled Messages", "schedule_msg")],
                [
                    Button.inline("📨 Unified DM Manager", "dm_reply:main"),
                    Button.inline("📊 Analytics", "msg:stats"),
                ],
                [Button.inline("📋 Message History", "msg:history")],
                [Button.inline("🔙 Back to Main Menu", "menu:main")],
            ]
        await self._render_menu(
            user_id, message_id, text, buttons
        )

    async def handle_channels(self, event):
        user_id = event.sender_id
        await self.menu._cleanup_old_messages(user_id)
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        if not accounts:
            text = "📢 **Channel Management Hub**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🚨 **No accounts available!**\n\nYou need active accounts to manage channels and groups.\n\n🎯 **Channel Features:**\n• 🔗 **Smart Join/Leave** - Bulk channel operations\n• 🆕 **Channel Creation** - Create channels & groups\n• 📋 **Management Tools** - List, organize, moderate\n• 🗑️ **Cleanup Tools** - Mass leave/delete operations\n• 📊 **Analytics** - Channel performance metrics\n\nAdd accounts to unlock channel management:"
            buttons = [
                [Button.inline("🚀 Add First Account", "account:add")],
                [Button.inline("❓ Channel Guide", "help:features")],
                [Button.inline("🔙 Back to Main Menu", "menu:main")],
            ]
        else:
            active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
            text = f"📢 **Channel Management Hub**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📊 **System Overview:**\n• 📱 Active Accounts: {active_accounts}/{
                len(accounts)}\n• 🟢 Management Tools: Ready\n\n🎛️ **Select Account for Channel Operations:**\nChoose an account to manage its channels and groups:"
            buttons = []
            active_channel_accounts = [
                account for account in accounts if account.get("is_active", False)
            ]
            for account in active_channel_accounts:
                status = "🟢" if account.get("is_active", False) else "🔴"
                display_name = format_display_name(account)
                button_text = f"{status} {display_name}"
                buttons.append(
                    [Button.inline(button_text, f"channel:select:{account['phone']}")]
                )
            buttons.extend(
                [
                    [
                        Button.inline("📊 Global Statistics", "channel:stats"),
                        Button.inline("🔍 Channel Discovery", "channel:search"),
                    ],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            )
            if not active_channel_accounts:
                text += "\n\n⚠️ Activate an account before managing its channels."
        await self._render_menu(
            user_id, getattr(event, "message_id", None), text, buttons
        )

    async def handle_cleanup(self, event):
        user_id = event.sender_id
        await self.menu._cleanup_old_messages(user_id)
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        if not accounts:
            text = "🧹 **Professional Account Cleanup**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🚨 **No accounts available!**\n\nYou need active accounts to use cleanup features.\n\n🎯 **Cleanup Capabilities:**\n• 💬 **Smart Chat Cleanup** - Personal, bot, official chats\n• 🚫 **Spam Removal** - Spambot and unwanted chats\n• 🚪 **Mass Exit** - Leave channels and groups\n• 🗑️ **Ownership Cleanup** - Delete owned channels/groups\n• 📞 **Spam Appeals** - Automated appeal system\n\n⚠️ **Important:** All cleanup actions are irreversible!\n\nAdd accounts to access cleanup tools:"
            buttons = [
                [Button.inline("🚀 Add First Account", "account:add")],
                [Button.inline("❓ Cleanup Guide", "help:features")],
                [Button.inline("🔙 Back to Main Menu", "menu:main")],
            ]
        else:
            available_accounts = [
                account
                for account in accounts
                if self._is_cleanup_account_available(user_id, account)
            ]
            text = (
                "🧹 **Professional Account Cleanup**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 **Connected active accounts:** {len(available_accounts)}/{len(accounts)}\n\n"
            )
            buttons = []
            if not available_accounts:
                text += (
                    "No active, connected accounts are available for cleanup. "
                    "Reconnect or activate an account in Account Settings first."
                )
            else:
                text += (
                    "⚠️ **CRITICAL WARNING:** All cleanup actions are **PERMANENT** "
                    "and **IRREVERSIBLE**!\n\n"
                    "🎯 **Available Cleanup Options:**\n"
                    "• 💬 Personal chats • 🤖 Bot conversations\n"
                    "• 📢 Telegram official • 🚫 Spambot chats\n"
                    "• 🚪 Exit channels • 👥 Exit groups\n"
                    "• 🗑️ Delete owned groups • 📺 Delete owned channels\n\n"
                    "🎛️ **Select a connected account to clean:**"
                )
                for account in available_accounts:
                    display_name = format_display_name(account)
                    buttons.append(
                        [
                            Button.inline(
                                f"🟢 {display_name}",
                                f"cleanup:select:{account['_id']}",
                            )
                        ]
                    )
            buttons.append([Button.inline("🔙 Back to Main Menu", "menu:main")])

        await self._render_menu(
            user_id, getattr(event, "message_id", None), text, buttons
        )

    async def handle_help(self, event):
        user_id = event.sender_id
        await self.menu._cleanup_old_messages(user_id)
        user = await mongodb.db.users.find_one({"telegram_id": user_id})
        account_count = await mongodb.db.accounts.count_documents({"user_id": user_id})
        otp_enabled = await mongodb.db.accounts.count_documents(
            {"user_id": user_id, "otp_destroyer_enabled": True}
        )
        security_score = (
            int((otp_enabled / max(account_count, 1)) * 100) if account_count > 0 else 0
        )
        status_emoji = (
            "🟢" if security_score >= 80 else "🟡" if security_score >= 50 else "🔴"
        )
        text = (
            "❓ **TeleGuard Help & Support Center**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📊 **Your Dashboard:**\n"
            f"• 📱 **Accounts:** {account_count} configured\n"
            f"• 🛡️ **OTP Destroyer:** {otp_enabled}/{account_count} enabled\n"
            f"• {status_emoji} **OTP Coverage:** {security_score}%\n\n"
            "🚀 **Quick Setup:**\n"
            "1️⃣ Add an account in **📱 Account Settings**.\n"
            "2️⃣ Configure OTP and session protections in **🛡️ Protection Manager**.\n"
            "3️⃣ Open another main-menu feature to configure it before use.\n\n"
            "Use the guides below for setup, security, and troubleshooting. "
            "Never share login codes, passwords, or session data with support."
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
            [Button.inline("📨 Chat Import", "menu:import")],
        ]
        if user_id in ADMIN_IDS:
            dev_mode = user.get("developer_mode", False) if user else False
            dev_text = "🔴 Disable Dev Mode" if dev_mode else "⚙️ Enable Dev Mode"
            buttons.append([Button.inline(dev_text, "help:toggle_dev")])
        buttons.append([Button.inline("🔙 Back to Main Menu", "menu:main")])
        
        await self._render_menu(
            user_id, getattr(event, "message_id", None), text, buttons
        )

    async def handle_support(self, event):
        user_id = event.sender_id
        await self.menu._cleanup_old_messages(user_id)
        text = (
            "🆘 **TeleGuard Support Center**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Choose a support option below or review the Help menu first.\n\n"
            "When reporting an issue, include the feature, steps to reproduce, "
            "and a redacted error message. Never send login codes, passwords, "
            "API keys, session files, or session strings."
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
            [Button.inline("🔙 Back to Main Menu", "menu:main")],
        ]

        await self._render_menu(
            user_id, getattr(event, "message_id", None), text, buttons
        )

    async def handle_developer(self, event):
        user_id = event.sender_id
        if user_id not in ADMIN_IDS:
            if hasattr(event, "answer"):
                await event.answer(
                    "❌ You don't have access to Developer tools.", alert=True
                )
            else:
                await event.reply("❌ You don't have access to Developer tools.")
            return

        await self.menu._cleanup_old_messages(user_id)
        user = await mongodb.db.users.find_one({"telegram_id": user_id})
        current_mode = user.get("developer_mode", False) if user else False
        account_count = await mongodb.db.accounts.count_documents({})
        user_count = await mongodb.db.users.count_documents({})
        text = (
            "⚙️ **Developer Control Panel**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎛️ **Developer Mode:** {'🟢 ACTIVE' if current_mode else '🔴 INACTIVE'}\n\n"
            "📊 **System Overview:**\n"
            f"• 👥 Total users: {user_count:,}\n"
            f"• 📱 Total accounts: {account_count:,}\n\n"
            "Use the controls below to inspect runtime health and settings. "
            "Restart is not available from this panel."
        )
        mode_text = (
            "🔴 Disable Developer Mode"
            if current_mode
            else "🟢 Enable Developer Mode"
        )
        buttons = [
            [Button.inline(mode_text, "dev:toggle")],
            [
                Button.inline("📊 System Dashboard", "dev:sysinfo"),
                Button.inline("📋 Runtime Diagnostics", "dev:logs"),
            ],
            [
                Button.inline("🗄️ Database Statistics", "dev:dbstats"),
                Button.inline("⚡ Performance", "dev:perf"),
            ],
            [
                Button.inline("🔧 Session Maintenance", "dev:maintenance"),
                Button.inline("🔄 Restart Status", "dev:restart"),
            ],
            [
                Button.inline("🚀 Startup Config", "dev:startup"),
                Button.inline("📚 Command Reference", "dev:commands"),
            ],
            [Button.inline("🔙 Back to Main Menu", "menu:main")],
        ]

        await self._render_menu(
            user_id, getattr(event, "message_id", None), text, buttons
        )
