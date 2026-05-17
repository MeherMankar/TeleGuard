# -*- coding: utf-8 -*-
"""Menu text handlers"""
import logging

from telethon import Button

from ...core.config import ADMIN_IDS
from ...core.mongo_database import mongodb
from ...utils.network_helpers import format_display_name, format_phone_number

logger = logging.getLogger(__name__)


class MenuHandlers:
    def __init__(self, menu_system):
        self.menu = menu_system
        self.bot = menu_system.bot
        self.account_manager = menu_system.account_manager

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
        # Edit if called from a callback, otherwise send new message
        message_id = getattr(event, "message_id", None)
        if message_id:
            try:
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                return
            except Exception:
                pass
        await self.bot.send_message(user_id, text, buttons=buttons)

    async def handle_otp_manager(self, event):
        user_id = event.sender_id
        await self.menu._cleanup_old_messages(user_id)
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        if not accounts:
            text = "🛡️ **Protection Manager**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🚨 **No accounts found!**\n\nYou need to add accounts first before configuring protection.\n\n🎯 **Available Protections:**\n• 🔥 **Session Destroyer** - Blocks unauthorized logins\n• 🛡️ **OTP Destroyer** - Blocks unauthorized OTP use\n• 📩 **OTP Forward** - Forwards OTP codes to you\n• ⏰ **Temp Bypass** - Temporary security pause\n\nAdd your first account to get started:"
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
            temp_active = sum(
                1 for acc in accounts if acc.get("otp_temp_passthrough", False)
            )
            
            # Session Destroyer stats
            from ..session_destroyer_handler import SessionDestroyerHandler
            from ...sync.session_destroyer_db import SessionDestroyerDB
            
            sd_settings = await SessionDestroyerDB.get_settings(user_id)
            sd_enabled = "🔥" if sd_settings.get("enabled") else "⚪"
            
            security_score = int((destroyer_enabled / len(accounts)) * 100)
            if sd_settings.get("enabled"):
                security_score = min(100, security_score + 20)
                
            security_emoji = (
                "🟢" if security_score >= 80 else "🟡" if security_score >= 50 else "🔴"
            )
            
            text = (
                f"🛡️ **Protection Manager**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 **Security Dashboard:**\n"
                f"• {security_emoji} **Security Score:** {security_score}%\n"
                f"• {sd_enabled} **Session Destroyer:** {'Enabled' if sd_settings.get('enabled') else 'Disabled'}\n"
                f"• 🛡️ **OTP Destroyer:** {destroyer_enabled}/{len(accounts)} accounts\n"
                f"• 📩 **OTP Forward:** {forward_enabled}/{len(accounts)} accounts\n\n"
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
        message_id = getattr(event, "message_id", None)
        if message_id:
            try:
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                return
            except Exception:
                pass
        await self.bot.send_message(user_id, text, buttons=buttons)

    async def handle_messaging(self, event):
        user_id = event.sender_id
        await self.menu._cleanup_old_messages(user_id)
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
            text = f"💬 **Advanced Messaging Center**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📊 **System Status:**\n• 📱 Active Accounts: {active_accounts}/{
                len(accounts)}\n• 🤖 Auto-Reply: {auto_reply_enabled} enabled\n• 🟢 System: Operational\n\n🚀 **Messaging Tools:**\nChoose your messaging action below:"
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
                [Button.inline("🔙 Back to Main Menu", "menu:main")],
            ]
        # Edit if called from a callback, otherwise send new message
        message_id = getattr(event, "message_id", None)
        if message_id:
            try:
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                return
            except Exception:
                pass
        await self.bot.send_message(user_id, text, buttons=buttons)

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
            for account in accounts[:8]:
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
        message_id = getattr(event, "message_id", None)
        if message_id:
            try:
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                return
            except Exception:
                pass
        await self.bot.send_message(user_id, text, buttons=buttons)

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
            active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
            text = f"🧹 **Professional Account Cleanup**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📊 **System Status:**\n• 📱 Active Accounts: {active_accounts}/{
                len(accounts)}\n• 🟢 Cleanup Tools: Ready\n\n⚠️ **CRITICAL WARNING:**\nAll cleanup actions are **PERMANENT** and **IRREVERSIBLE**!\n\n🎯 **Available Cleanup Options:**\n• 💬 Personal chats • 🤖 Bot conversations\n• 📢 Telegram official • 🚫 Spambot chats\n• 🚪 Exit channels • 👥 Exit groups\n• 🗑️ Delete owned groups • 📺 Delete owned channels\n\n🎛️ **Select Account to Clean:**"
            buttons = []
            for account in accounts:
                status = "🟢" if account.get("is_active", False) else "🔴"
                display_name = format_display_name(account)
                button_text = f"{status} {display_name}"
                buttons.append(
                    [Button.inline(button_text, f"cleanup:select:{account['_id']}")]
                )
            buttons.append([Button.inline("🔙 Back to Main Menu", "menu:main")])
        
        message_id = getattr(event, "message_id", None)
        if message_id:
            try:
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                return
            except Exception:
                pass
        await self.bot.send_message(user_id, text, buttons=buttons)

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
        text = f"❓ **TeleGuard Help & Support Center**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📊 **Your Dashboard:**\n• 📱 **Accounts:** {account_count} configured\n• 🛡️ **Protection:** {otp_enabled}/{account_count} secured\n• {status_emoji} **Security Score:** {security_score}%\n\n🚀 **Quick Setup (2 minutes):**\n1️⃣ **Add Account** → `📱 Account Settings` → `Add Account`\n2️⃣ **Enable Security** → `🛡️ OTP Manager` → `Enable Destroyer`\n3️⃣ **Configure Features** → Explore messaging & automation\n\n🎯 **Feature Overview:**\n• 🛡️ **Security** - OTP protection, 2FA, session monitoring\n• 💬 **Messaging** - Auto-reply, templates, bulk sending\n• 📱 **Management** - Profile updates, channel tools\n• 📊 **Analytics** - Activity logs, performance insights\n\n💡 **Pro Tips:**\n• Enable OTP Destroyer on all accounts for maximum security\n• Use DM Reply for centralized message management\n• Monitor audit logs weekly for security insights"
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
        if user and user_id in ADMIN_IDS:
            dev_mode = user.get("developer_mode", False)
            dev_text = "🔴 Disable Dev Mode" if dev_mode else "⚙️ Enable Dev Mode"
            buttons.append([Button.inline(dev_text, "help:toggle_dev")])
        buttons.append([Button.inline("🔙 Back to Main Menu", "menu:main")])
        
        message_id = getattr(event, "message_id", None)
        if message_id:
            try:
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                return
            except Exception:
                pass
        await self.bot.send_message(user_id, text, buttons=buttons)

    async def handle_support(self, event):
        user_id = event.sender_id
        await self.menu._cleanup_old_messages(user_id)
        text = "🆘 **TeleGuard Support Center**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n👨💻 **Development Team:**\n• **@Meher_Mankar** - Lead Developer & Founder\n• **@Gutkesh** - Core Developer & Security Expert\n\n🎯 **Get Instant Help:**\n• 💬 **Live Support:** @ContactXYZrobot\n• 🐛 **Bug Reports:** GitHub Issues Portal\n• 📚 **Documentation:** Complete Wiki Guide\n• ⚡ **Response Time:** < 6 hours (usually faster)\n\n🔧 **Self-Help Checklist:**\n✅ Check Help section for instant solutions\n✅ Try `/start` to refresh the bot\n✅ Verify accounts are properly connected\n✅ Review troubleshooting guide first\n\n🚨 **Emergency Support:** Contact developers directly for critical issues"
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
        
        message_id = getattr(event, "message_id", None)
        if message_id:
            try:
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                return
            except Exception:
                pass
        await self.bot.send_message(user_id, text, buttons=buttons)

    async def handle_developer(self, event):
        user_id = event.sender_id
        await self.menu._cleanup_old_messages(user_id)
        user = await mongodb.db.users.find_one({"telegram_id": user_id})
        if user:
            current_mode = user.get("developer_mode", False)
            account_count = await mongodb.db.accounts.count_documents({})
            user_count = await mongodb.db.users.count_documents({})
            text = f"⚙️ **Developer Control Panel**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🎛️ **Developer Mode:** {
                '🟢 **ACTIVE**' if current_mode else '🔴 **INACTIVE**'}\n\n📊 **System Overview:**\n• 👥 Total Users: {
                user_count:,    }\n• 📱 Total Accounts: {
                account_count:,        }\n• 🟢 System Status: Operational\n\n🛠️ **Administrative Tools:**\n• 🔧 **System Control** - Mode toggle, restart, maintenance\n• 📊 **Monitoring** - Real-time metrics & performance\n• 🐛 **Debugging** - Error logs & diagnostic tools\n• 🗄️ **Database** - Statistics & optimization tools\n• 🚀 **Deployment** - Configuration & startup management\n\n⚠️ **Administrator Access** - Advanced system operations only"
            mode_text = (
                "🔴 Disable Developer Mode"
                if current_mode
                else "🟢 Enable Developer Mode"
            )
            buttons = [
                [Button.inline(mode_text, "dev:toggle")],
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
                [Button.inline("🔙 Back to Main Menu", "menu:main")],
            ]
            
            message_id = getattr(event, "message_id", None)
            if message_id:
                try:
                    await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                    return
                except Exception:
                    pass
            await self.bot.send_message(user_id, text, buttons=buttons)
        else:
            await event.reply("❌ User not found")
