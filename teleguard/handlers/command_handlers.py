"""Essential handlers - all actions via buttons only"""
import logging
from telethon import Button, events
from ..core.config import MAX_ACCOUNTS
from ..core.mongo_database import mongodb
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
        @self.bot.on(events.NewMessage(pattern=r"/start"))
        async def start_handler(event):
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
        # Cancel handler for interrupting text input flows
        @self.bot.on(events.NewMessage(pattern=r"/cancel"))
        async def cancel_handler(event):
            user_id = event.sender_id
            if user_id in self.pending_actions:
                self.auth_manager.cancel_auth(user_id)
                self.pending_actions.pop(user_id, None)
                await event.reply(
                    "❌ Operation cancelled. Use the menu buttons to continue."
                )
            else:
                await event.reply(
                    "ℹ️ No operation to cancel. Use the menu buttons below."
                )
        
        @self.bot.on(events.CallbackQuery(pattern=r"^messaging_stats$"))
        async def show_messaging_stats(event):
            """Show messaging statistics"""
            user_id = event.sender_id
            try:
                user_clients = self.user_clients.get(user_id, {})
                active_accounts = len([c for c in user_clients.values() if c and c.is_connected()])
                
                stats = {
                    'active_accounts': active_accounts,
                    'total_messages_sent': 0,
                    'auto_replies_sent': 0,
                    'dm_topics_created': 0
                }
                
                if hasattr(self.bot_manager, 'auto_reply_handler'):
                    auto_reply_stats = self.bot_manager.auto_reply_handler.analytics
                    stats['auto_replies_sent'] = auto_reply_stats.get('auto_replies_sent', 0)
                    stats['total_messages_sent'] = auto_reply_stats.get('total_messages', 0)
                
                try:
                    topic_count = await mongodb.db.topic_mappings.count_documents({})
                    stats['dm_topics_created'] = topic_count
                except Exception:
                    pass
                
                text = f"📊 **Messaging Statistics**\n\n"
                text += f"📱 Active Accounts: {stats['active_accounts']}\n"
                text += f"📨 Messages Sent: {stats['total_messages_sent']}\n"
                text += f"🤖 Auto-Replies: {stats['auto_replies_sent']}\n"
                text += f"💬 DM Topics: {stats['dm_topics_created']}\n"
                
                buttons = [[Button.inline("🔙 Back", "messaging_menu")]]
                await event.edit(text, buttons=buttons)
            except Exception as e:
                await event.edit(f"❌ Error loading statistics: {str(e)}")
        
        @self.bot.on(events.CallbackQuery(pattern=r"^sim_stats:(.+)$"))
        async def show_sim_stats(event):
            """Show SIM statistics"""
            user_id = event.sender_id
            account_name = event.pattern_match.group(1).decode()
            
            try:
                account = await mongodb.db.accounts.find_one({
                    "user_id": user_id,
                    "name": account_name
                })
                
                if not account:
                    await event.answer("❌ Account not found")
                    return
                
                client = self.user_clients.get(user_id, {}).get(account_name)
                if not client or not client.is_connected():
                    await event.edit("❌ Account not connected")
                    return
                
                me = await client.get_me()
                
                text = f"📊 **SIM Statistics - {account_name}**\n\n"
                text += f"📱 **Account Info:**\n"
                text += f"• Name: {me.first_name} {me.last_name or ''}\n"
                text += f"• Username: @{me.username or 'None'}\n"
                text += f"• Phone: {me.phone or 'Hidden'}\n"
                text += f"• ID: {me.id}\n"
                text += f"• Premium: {'Yes' if me.premium else 'No'}\n"
                text += f"• Verified: {'Yes' if me.verified else 'No'}\n\n"
                
                try:
                    dialogs = await client.get_dialogs(limit=None)
                    text += f"📈 **Usage Stats:**\n"
                    text += f"• Total Chats: {len(dialogs)}\n"
                    text += f"• Online Status: {'Online' if account.get('online_maker_enabled') else 'Offline'}\n"
                    text += f"• Auto-Reply: {'Enabled' if account.get('auto_reply_enabled') else 'Disabled'}\n"
                    text += f"• OTP Destroyer: {'Enabled' if account.get('otp_destroyer_enabled') else 'Disabled'}\n"
                except Exception:
                    text += f"📈 **Usage Stats:** Unable to load\n"
                
                buttons = [[Button.inline("🔙 Back", f"manage:{account_name}")]]
                await event.edit(text, buttons=buttons)
                
            except Exception as e:
                logger.error(f"SIM stats error: {e}")
                await event.edit(f"❌ Error loading SIM stats: {str(e)}")
        
        @self.bot.on(events.CallbackQuery(pattern=r"^export_contacts$"))
        async def export_contacts(event):
            """Export contacts to CSV"""
            user_id = event.sender_id
            try:
                accounts = await mongodb.db.accounts.find({"user_id": user_id, "is_active": True}).to_list(None)
                if not accounts:
                    await event.edit("❌ No active accounts found")
                    return
                
                all_contacts = []
                for account in accounts:
                    account_name = account.get('name', 'Unknown')
                    client = self.user_clients.get(user_id, {}).get(account_name)
                    
                    if client and client.is_connected():
                        try:
                            from telethon.tl.functions.contacts import GetContactsRequest
                            from telethon.tl.types import User
                            
                            result = await client(GetContactsRequest(hash=0))
                            for user in result.users:
                                if isinstance(user, User) and not user.bot:
                                    all_contacts.append({
                                        'ID': user.id,
                                        'First Name': user.first_name or '',
                                        'Last Name': user.last_name or '',
                                        'Username': user.username or '',
                                        'Phone': user.phone or '',
                                        'Account': account_name
                                    })
                        except Exception as e:
                            logger.error(f"Error getting contacts from {account_name}: {e}")
                
                if not all_contacts:
                    await event.edit("❌ No contacts found to export")
                    return
                
                import csv
                import io
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=['ID', 'First Name', 'Last Name', 'Username', 'Phone', 'Account'])
                writer.writeheader()
                writer.writerows(all_contacts)
                
                csv_data = output.getvalue().encode('utf-8')
                
                await event.edit("📤 **Exporting contacts...**")
                await self.bot.send_file(
                    user_id,
                    csv_data,
                    file_name=f"contacts_export_{user_id}.csv",
                    caption=f"📤 **Contacts Export**\n\n📊 Total: {len(all_contacts)} contacts"
                )
                
            except Exception as e:
                await event.edit(f"❌ Export failed: {str(e)}")
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
                    [Button.inline(button_text, f"manage:{format_phone_number(account['phone'])}")]
                )
            buttons.append([Button.inline("🔙 Back to Main Menu", "menu:main")])
            await self.bot.send_message(user_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to send account selection: {e}")
            await self.bot.send_message(user_id, "❌ Error loading accounts")
