"""Essential handlers - all actions via buttons only"""

import logging

from telethon import Button, events

from ..core.config import MAX_ACCOUNTS
from ..core.mongo_database import mongodb
from ..core.proxy_manager import proxy_manager
from ..utils.network_helpers import format_phone_number

logger = logging.getLogger(__name__)


class CommandHandlers:
    """Handles all bot command events"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.menu_system = bot_manager.menu_system
        self.auth_manager = bot_manager.auth_manager
        self.pending_actions = bot_manager.pending_actions
        self.user_clients = bot_manager.user_clients
        self.messaging_manager = bot_manager.messaging_manager
        from .channel_manager import ChannelManager

        self.channel_manager = ChannelManager(bot_manager)

    def register_handlers(self):
        """Register only essential handlers - all actions via buttons"""
        self._register_command_handlers()
        self._register_callback_handlers()

    def _register_command_handlers(self):
        """Register command handlers"""
        self.bot.on(events.NewMessage(pattern=r"/cancel"))(self._handle_cancel)
        self.bot.on(events.NewMessage(pattern=r"/accs"))(self._handle_accs)
        self.bot.on(events.NewMessage(pattern=r"/add(?:\s|$)"))(self._handle_add)
        self.bot.on(events.NewMessage(pattern=r"/remove"))(self._handle_remove)
        self.bot.on(events.NewMessage(pattern=r"/reconnect"))(self._handle_reconnect)
        self.bot.on(events.NewMessage(pattern=r"/proxy"))(self._handle_proxy)
        self.bot.on(events.NewMessage(pattern=r"/appeal"))(self._handle_appeal)
        self.bot.on(events.NewMessage(pattern=r"/toggle_protection"))(self._handle_toggle_protection)
        self.bot.on(events.NewMessage(pattern=r"/sessions"))(self._handle_sessions)
        self.bot.on(events.NewMessage(pattern=r"/export_session"))(self._handle_export_session)
        self.bot.on(events.NewMessage(pattern=r"/import_session"))(self._handle_import_session)
        self.bot.on(events.NewMessage(pattern=r"/dm"))(self._handle_dm)
        self.bot.on(events.NewMessage(pattern=r"/reply"))(self._handle_reply)
        self.bot.on(events.NewMessage(pattern=r"/spam"))(self._handle_spam)

    def _register_callback_handlers(self):
        """Register callback handlers"""
        self.bot.on(events.CallbackQuery(pattern=r"^toggle_otp:(.+)$"))(self._handle_toggle_otp_callback)
        self.bot.on(events.CallbackQuery(pattern=r"^messaging_stats$"))(self._handle_messaging_stats)
        self.bot.on(events.CallbackQuery(pattern=r"^sim_stats:(.+)$"))(self._handle_sim_stats)
        self.bot.on(events.CallbackQuery(pattern=r"^export_contacts$"))(self._handle_export_contacts)

    async def _handle_start(self, event):
        user_id = event.sender_id
        user = await mongodb.get_user(user_id)
        is_new_user = user is None
        if not user:
            await mongodb.create_user(user_id)
        if is_new_user:
            welcome_text = (
                "🤖 **Welcome to TeleGuard!**\n\n"
                "Your professional Telegram account manager with advanced OTP destroyer protection.\n\n"
                "**🚀 Quick Start:**\n"
                "1️⃣ Add your first account via '📱 Account Settings'\n"
                "2️⃣ Enable OTP protection in '🛡️ OTP Manager'\n"
                "3️⃣ Explore features using the menu below\n\n"
                "**🛡️ Key Features:**\n"
                "• Real-time OTP destroyer protection\n"
                "• Multi-account management (up to 10)\n"
                "• 2FA management & session control\n"
                "• Activity simulation & automation\n"
                "• Secure profile & channel management\n\n"
                "**💬 Need Help?** Use '❓ Help' or contact @Meher_Mankar"
            )
        else:
            welcome_text = "🤖 **TeleGuard Account Manager**\n\nWelcome back! Use the menu below to manage your accounts."
        keyboard = self.menu_system.get_main_menu_keyboard(user_id)
        await event.reply(welcome_text, buttons=keyboard)

    async def _handle_cancel(self, event):
        user_id = event.sender_id
        if user_id in self.pending_actions:
            self.auth_manager.cancel_auth(user_id)
            self.pending_actions.pop(user_id, None)
            await event.reply("❌ Operation cancelled. Use the menu buttons to continue.")
        else:
            await event.reply("ℹ️ No operation to cancel. Use the menu buttons below.")

    async def _handle_accs(self, event):
        user_id = event.sender_id
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            if not accounts:
                await event.reply("❌ No accounts found. Use /add to add your first account.")
                return
            text = f"📱 **Your Accounts ({len(accounts)})**\n\n"
            for i, account in enumerate(accounts, 1):
                name = account.get("name", "Unknown")
                phone = account.get("phone", "Unknown")
                is_active = account.get("is_active", False)
                otp_enabled = account.get("otp_destroyer_enabled", False)
                status = "🟢" if is_active else "🔴"
                otp_status = "🛡️" if otp_enabled else "⚪"
                text += f"{i}. {status} **{name}**\n"
                text += f"   📞 {phone}\n"
                text += f"   {otp_status} OTP: {'Enabled' if otp_enabled else 'Disabled'}\n\n"
            text += "\n**Legend:**\n"
            text += "🟢 Active | 🔴 Inactive\n"
            text += "🛡️ OTP Protected | ⚪ No Protection"
            await event.reply(text)
        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}")

    async def _handle_add(self, event):
        user_id = event.sender_id
        try:
            account_count = await mongodb.db.accounts.count_documents({"user_id": user_id})
            if account_count >= MAX_ACCOUNTS:
                await event.reply(f"❌ Maximum account limit ({MAX_ACCOUNTS}) reached")
                return
            self.pending_actions[user_id] = {"action": "add_account"}
            await event.reply(
                "➕ **Add New Account**\n\n"
                "Reply with phone number (include country code):\n\n"
                "📱 Example: +1234567890\n"
                "💡 Tip: Enter OTP as 1-2-3-4-5 (with hyphens)"
            )
        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}")

    async def _handle_reconnect(self, event):
        user_id = event.sender_id
        await event.reply("🔄 Reconnecting all your accounts...")
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id, "is_active": True}).to_list(None)
            if not accounts:
                await event.reply("❌ No active accounts found to reconnect.")
                return
            success = 0
            failed = []
            for account in accounts:
                account_name = account.get("name")
                session_string = account.get("session_string")
                if not session_string:
                    failed.append(f"{account_name}: No session")
                    continue
                try:
                    await self.bot_manager.start_user_client(user_id, account_name, session_string)
                    success += 1
                except Exception as e:
                    failed.append(f"{account_name}: {str(e)[:50]}")
                    logger.error(f"Failed to reconnect {account_name}: {e}")
            msg = f"✅ Reconnected {success}/{len(accounts)} accounts."
            if failed:
                msg += "\n\n❌ Failed:\n" + "\n".join(f"• {f}" for f in failed[:5])
            await event.reply(msg)
        except Exception as e:
            await event.reply(f"❌ Reconnection failed: {str(e)}")

    async def _handle_proxy(self, event):
        user_id = event.sender_id
        if hasattr(self.menu_system, "proxy_handler"):
            proxies = await proxy_manager.get_user_proxies(user_id)
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            accounts_with_proxy = sum(1 for acc in accounts if acc.get("proxy_id"))
            text = (
                f"🌐 **Proxy Management**\n\n"
                f"📊 **Statistics:**\n"
                f"• Total Proxies: {len(proxies)}\n"
                f"• Accounts with Proxy: {accounts_with_proxy}/{len(accounts)}\n\n"
                f"**Supported Formats:**\n"
                f"• Telegram proxy links (t.me/proxy)\n"
                f"• MTProto proxies\n"
                f"• SOCKS5 proxies\n"
                f"• HTTP proxies\n\n"
                f"Select an option below:"
            )
            buttons = [
                [Button.inline("➕ Add Proxy", "proxy:add")],
                [Button.inline("📋 View Proxies", "proxy:list")],
                [Button.inline("🔗 Assign to Account", "proxy:assign")],
                [Button.inline("👥 View Accounts", "proxy:view_accounts")],
                [Button.inline("🔙 Back to Main Menu", "menu:main")],
            ]
            await event.reply(text, buttons=buttons)
        else:
            await event.reply("❌ Proxy management not available")

    async def _handle_appeal(self, event):
        user_id = event.sender_id
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id, "is_active": True}).to_list(None)
            if not accounts:
                await event.reply("❌ No active accounts found. Add an account first.")
                return
            text = "🚨 **Spam Appeal**\n\nSelect an account to appeal spam restriction:"
            buttons = []
            for account in accounts[:8]:
                button_text = f"📱 {account.get('name', 'Unknown')}"
                buttons.append([Button.inline(button_text, f"appeal:{account['_id']}")])
            buttons.append([Button.inline("🔙 Back", "menu:main")])
            await event.reply(text, buttons=buttons)
        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}")

    async def _handle_toggle_protection(self, event):
        user_id = event.sender_id
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id, "is_active": True}).to_list(None)
            if not accounts:
                await event.reply("❌ No active accounts found. Add an account first.")
                return
            if len(accounts) == 1:
                account = accounts[0]
                current_status = account.get("otp_destroyer_enabled", False)
                new_status = not current_status
                await mongodb.db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$set": {"otp_destroyer_enabled": new_status}},
                )
                status_text = "✅ Enabled" if new_status else "❌ Disabled"
                await event.reply(
                    f"🛡️ **OTP Destroyer {status_text}**\n\n"
                    f"Account: {account.get('name', 'Unknown')}\n"
                    f"Status: {status_text}\n\n"
                    f"{'Your account is now protected from unauthorized login attempts!' if new_status else 'OTP protection has been disabled.'}"
                )
            else:
                buttons = []
                for account in accounts[:8]:
                    status = "✅" if account.get("otp_destroyer_enabled", False) else "❌"
                    button_text = f"{status} {account.get('name', 'Unknown')}"
                    buttons.append([Button.inline(button_text, f"toggle_otp:{account['_id']}")])
                await event.reply(
                    "🛡️ **Toggle OTP Protection**\n\n"
                    "Select an account to toggle OTP destroyer protection:\n\n"
                    "✅ = Protection Enabled\n"
                    "❌ = Protection Disabled",
                    buttons=buttons,
                )
        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}")

    async def _handle_toggle_otp_callback(self, event):
        user_id = event.sender_id
        account_id = event.pattern_match.group(1).decode()
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                await event.answer("❌ Account not found")
                return
            current_status = account.get("otp_destroyer_enabled", False)
            new_status = not current_status
            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {"$set": {"otp_destroyer_enabled": new_status}},
            )
            status_text = "✅ Enabled" if new_status else "❌ Disabled"
            await event.edit(
                f"🛡️ **OTP Destroyer {status_text}**\n\n"
                f"Account: {account.get('name', 'Unknown')}\n"
                f"Status: {status_text}\n\n"
                f"{'Your account is now protected from unauthorized login attempts!' if new_status else 'OTP protection has been disabled.'}"
            )
        except Exception as e:
            await event.answer(f"❌ Error: {str(e)}")

    async def _handle_messaging_stats(self, event):
        user_id = event.sender_id
        try:
            user_clients = self.user_clients.get(user_id, {})
            active_accounts = len([c for c in user_clients.values() if c and c.is_connected()])
            stats = {"active_accounts": active_accounts, "total_messages_sent": 0, "auto_replies_sent": 0, "dm_topics_created": 0}
            if hasattr(self.bot_manager, "auto_reply_handler"):
                auto_reply_stats = self.bot_manager.auto_reply_handler.analytics
                stats["auto_replies_sent"] = auto_reply_stats.get("auto_replies_sent", 0)
                stats["total_messages_sent"] = auto_reply_stats.get("total_messages", 0)
            try:
                topic_count = await mongodb.db.topic_mappings.count_documents({})
                stats["dm_topics_created"] = topic_count
            except Exception:
                pass
            text = "📊 **Messaging Statistics**\n\n"
            text += f"📱 Active Accounts: {stats['active_accounts']}\n"
            text += f"📨 Messages Sent: {stats['total_messages_sent']}\n"
            text += f"🤖 Auto-Replies: {stats['auto_replies_sent']}\n"
            text += f"💬 DM Topics: {stats['dm_topics_created']}\n"
            buttons = [[Button.inline("🔙 Back", "messaging_menu")]]
            await event.edit(text, buttons=buttons)
        except Exception as e:
            await event.edit(f"❌ Error loading statistics: {str(e)}")

    async def _handle_sim_stats(self, event):
        user_id = event.sender_id
        account_name = event.pattern_match.group(1).decode()
        try:
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            if not account:
                await event.answer("❌ Account not found")
                return
            
            client = self.user_clients.get(user_id, {}).get(account_name)
            if not client or not client.is_connected():
                await event.edit("❌ Account not connected")
                return
            
            me = await client.get_me()
            text = self._build_sim_stats_text(account_name, me, account, client)
            buttons = [[Button.inline("🔙 Back", f"manage:{account_name}")]]
            await event.edit(text, buttons=buttons)
        except Exception as e:
            logger.error(f"SIM stats error: {e}")
            await event.edit(f"❌ Error loading SIM stats: {str(e)}")

    def _build_sim_stats_text(self, account_name, me, account, client):
        """Build SIM statistics text"""
        text = f"📊 **SIM Statistics - {account_name}**\n\n"
        text += "📱 **Account Info:**\n"
        text += f"• Name: {me.first_name} {me.last_name or ''}\n"
        text += f"• Username: @{me.username or 'None'}\n"
        text += f"• Phone: {me.phone or 'Hidden'}\n"
        text += f"• ID: {me.id}\n"
        text += f"• Premium: {'Yes' if me.premium else 'No'}\n"
        text += f"• Verified: {'Yes' if me.verified else 'No'}\n\n"
        text += self._build_usage_stats(account, client)
        return text

    def _build_usage_stats(self, account, client):
        """Build usage statistics section"""
        try:
            stats = "📈 **Usage Stats:**\n"
            stats += f"• Online Status: {'Online' if account.get('online_maker_enabled') else 'Offline'}\n"
            stats += f"• Auto-Reply: {'Enabled' if account.get('auto_reply_enabled') else 'Disabled'}\n"
            stats += f"• OTP Destroyer: {'Enabled' if account.get('otp_destroyer_enabled') else 'Disabled'}\n"
            return stats
        except Exception:
            return "📈 **Usage Stats:** Unable to load\n"

    async def _handle_export_contacts(self, event):
        user_id = event.sender_id
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id, "is_active": True}).to_list(None)
            if not accounts:
                await event.edit("❌ No active accounts found")
                return
            
            all_contacts = await self._collect_contacts(user_id, accounts)
            if not all_contacts:
                await event.edit("❌ No contacts found to export")
                return
            
            csv_data = self._generate_csv(all_contacts)
            await event.edit("📤 **Exporting contacts...**")
            await self.bot.send_file(
                user_id,
                csv_data,
                file_name=f"contacts_export_{user_id}.csv",
                caption=f"📤 **Contacts Export**\n\n📊 Total: {len(all_contacts)} contacts",
            )
        except Exception as e:
            await event.edit(f"❌ Export failed: {str(e)}")

    async def _collect_contacts(self, user_id, accounts):
        """Collect contacts from all accounts"""
        all_contacts = []
        for account in accounts:
            account_name = account.get("name", "Unknown")
            client = self.user_clients.get(user_id, {}).get(account_name)
            if client and client.is_connected():
                try:
                    from telethon.tl.functions.contacts import GetContactsRequest
                    from telethon.tl.types import User
                    result = await client(GetContactsRequest(hash=0))
                    for user in result.users:
                        if isinstance(user, User) and not user.bot:
                            all_contacts.append({
                                "ID": user.id,
                                "First Name": user.first_name or "",
                                "Last Name": user.last_name or "",
                                "Username": user.username or "",
                                "Phone": user.phone or "",
                                "Account": account_name,
                            })
                except Exception as e:
                    logger.error(f"Error getting contacts from {account_name}: {e}")
        return all_contacts

    def _generate_csv(self, contacts):
        """Generate CSV data from contacts"""
        import csv
        import io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["ID", "First Name", "Last Name", "Username", "Phone", "Account"])
        writer.writeheader()
        writer.writerows(contacts)
        return output.getvalue().encode("utf-8")

    async def _send_account_selection(self, user_id: int):


        """Send account selection menu for channel management"""
        try:
            accounts = await mongodb.db.accounts.find(
                {"user_id": user_id, "is_active": True}
            ).to_list(length=None)
            if not accounts:
                text = "📱 **Channel Management**\n\nNo active accounts found. Add accounts first to manage channels."
                buttons = [[Button.inline("➕ Add Account", "account:add")]]
                await self.bot.send_message(user_id, text, buttons=buttons)
                return
            text = "📱 **Channel Management**\n\nSelect an account to manage channels:"
            buttons = []
            for account in accounts[:8]:  # Limit to 8 accounts
                status = "🔗" if account.get("is_active", False) else "🔴"
                button_text = f"{status} {account['name']}"
                buttons.append(
                    [
                        Button.inline(
                            button_text,
                            f"manage:{format_phone_number(account['phone'])}",
                        )
                    ]
                )
            buttons.append([Button.inline("🔙 Back to Main Menu", "menu:main")])
            await self.bot.send_message(user_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to send account selection: {e}")
            await self.bot.send_message(user_id, "❌ Error loading accounts")

    async def _handle_remove(self, event):
        await event.reply("Use menu: Account Settings → Manage Account → Remove")

    async def _handle_sessions(self, event):
        await event.reply("Use menu: Account Settings → Session Management")

    async def _handle_export_session(self, event):
        await event.reply("Use menu: Account Settings → Session Management → Export")

    async def _handle_import_session(self, event):
        await event.reply("Use menu: Account Settings → Import Session")

    async def _handle_dm(self, event):
        await event.reply(
            "💬 **Direct Message**\n\n"
            "Use the menu to manage DM forwarding:\n"
            "• **Messaging → DM Reply** — configure auto-reply for DMs\n"
            "• **Messaging → DM Topics** — view DM topic mappings\n\n"
            "Or use /reply to configure auto-reply settings."
        )

    async def _handle_reply(self, event):
        await event.reply("Use menu: Messaging → Auto-Reply")

    async def _handle_spam(self, event):
        await event.reply("Use menu: Cleanup → Spam Appeal")
