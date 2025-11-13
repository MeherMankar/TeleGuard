"""Cleanup operations module"""
import logging
from telethon import Button
from ...core.mongo_database import mongodb
from ...utils.network_helpers import format_display_name

logger = logging.getLogger(__name__)

class CleanupOperations:
    def __init__(self, menu_system):
        self.menu = menu_system
        self.bot = menu_system.bot
        self.account_manager = menu_system.account_manager
    
    async def send_cleanup_selection(self, user_id, message_id, account_id):
        from bson import ObjectId
        account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
        if not account:
            await self.bot.edit_message(user_id, message_id, "❌ Account not found", buttons=[[Button.inline("🔙 Back", "cleanup:menu")]])
            return
        display_name = format_display_name(account)
        text = f"🧹 **Cleanup Selection - {display_name}**\n\n📋 **What would you like to clean?**\n\nSelect what to clean (you can choose multiple options):\n\n💬 **Personal chats** - Direct messages with users\n🤖 **Bot chats** - Conversations with bots\n📢 **Telegram official** - Telegram service chats\n🚫 **Spambot chats** - @spambot conversations\n🚪 **Exit channels** - Leave all channels\n👥 **Exit groups** - Leave all groups\n🗑️ **Delete owned groups** - Delete groups you own\n📺 **Delete owned channels** - Delete channels you own\n\n⚠️ **WARNING**: These actions cannot be undone!"
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {"action": "cleanup_selection", "account_id": account_id}
        await self.bot.edit_message(user_id, message_id, text)
        await self.bot.send_message(user_id, "📝 **Reply with your selection:**\n\nType what you want to clean, separated by commas:\n\n**Examples:**\n• `personal,bots` - Clean personal chats and bot chats\n• `channels,groups` - Exit all channels and groups\n• `all` - Clean everything\n\n**Available options:**\n`personal`, `bots`, `telegram`, `spambot`, `channels`, `groups`, `owned_groups`, `owned_channels`, `all`")
    
    async def execute_cleanup(self, event, user_id, account_id, cleanup_types):
        from bson import ObjectId
        account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
        if not account:
            await event.answer("❌ Account not found")
            return
        if not self.account_manager:
            await event.answer("❌ Service unavailable")
            return
        client = None
        if hasattr(self.account_manager, 'user_clients') and user_id in self.account_manager.user_clients:
            account_name = account.get('name')
            client = self.account_manager.user_clients[user_id].get(account_name)
        if not client or not client.is_connected():
            await event.answer("❌ Account not connected. Please ensure account is active.")
            return
        display_name = format_display_name(account)
        cleanup_list = [t.strip().lower() for t in cleanup_types.split(',')]
        if 'all' in cleanup_list:
            cleanup_list = ['personal', 'bots', 'telegram', 'spambot', 'channels', 'groups', 'owned_groups', 'owned_channels']
        cleanup_settings = {'personal_chats': 'personal' in cleanup_list, 'bot_chats': 'bots' in cleanup_list, 'telegram_chat': 'telegram' in cleanup_list, 'spambot_chat': 'spambot' in cleanup_list, 'channels': 'channels' in cleanup_list, 'groups': 'groups' in cleanup_list, 'owned_groups': 'owned_groups' in cleanup_list, 'owned_channels': 'owned_channels' in cleanup_list}
        try:
            await self.bot.edit_message(user_id, event.message_id, f"🚀 **Starting cleanup for {display_name}**\n\n⏳ Analyzing account...\n📊 Progress will be shown below", buttons=None)
        except Exception:
            pass
        from ...core.account_cleaner import AccountCleaner
        cleaner = AccountCleaner()
        import time
        last_update_time = time.time()
        async def progress_callback(text):
            nonlocal last_update_time
            current_time = time.time()
            if current_time - last_update_time < 2:
                return
            try:
                await self.bot.edit_message(user_id, event.message_id, f"🚀 **Cleaning {display_name}**\n\n{text}", buttons=None)
                last_update_time = current_time
            except Exception:
                pass
        result = await cleaner.cleanup_account(client, cleanup_settings, progress_callback)
        result_text = f"✅ **Cleanup completed!**\n\n📱 Account: {display_name}\n\n📊 **Results:**\n{result}\n\n🔒 All operations completed securely"
        buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
        try:
            await self.bot.edit_message(user_id, event.message_id, result_text, buttons=buttons)
        except Exception:
            try:
                await event.answer("✅ Cleanup completed successfully!")
            except:
                pass
        try:
            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {"$push": {"audit_log": {
                    "action": "cleanup_completed",
                    "cleanup_types": cleanup_types,
                    "timestamp": int(time.time()),
                    "result": "success"
                }}}
            )
        except Exception as e:
            logger.error(f"Failed to add audit entry: {e}")
