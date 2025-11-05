"""Channels menu handlers"""
import logging
from telethon import Button
from ..core.mongo_database import mongodb
from ..utils.helpers import format_display_name

logger = logging.getLogger(__name__)

async def handle_channels_menu(bot, user_id, event):
    try:
        await _cleanup_old_messages(bot, user_id)
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
        if not accounts:
            text = "📢 **Channel Management Hub**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🚨 **No accounts available!**\n\nYou need active accounts to manage channels and groups.\n\n🎯 **Channel Features:**\n• 🔗 **Smart Join/Leave** - Bulk channel operations\n• 🆕 **Channel Creation** - Create channels & groups\n• 📋 **Management Tools** - List, organize, moderate\n• 🗑️ **Cleanup Tools** - Mass leave/delete operations\n• 📊 **Analytics** - Channel performance metrics\n\nAdd accounts to unlock channel management:"
            buttons = [[Button.inline("🚀 Add First Account", "account:add")], [Button.inline("❓ Channel Guide", "help:features")], [Button.inline("🔙 Back to Main Menu", "menu:main")]]
        else:
            active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
            text = f"📢 **Channel Management Hub**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📊 **System Overview:**\n• 📱 Active Accounts: {active_accounts}/{len(accounts)}\n• 🟢 Management Tools: Ready\n\n🎛️ **Select Account for Channel Operations:**\nChoose an account to manage its channels and groups:"
            buttons = []
            for account in accounts[:8]:
                status = "🟢" if account.get("is_active", False) else "🔴"
                display_name = format_display_name(account)
                button_text = f"{status} {display_name}"
                buttons.append([Button.inline(button_text, f"channel:select:{account['phone']}")])
            buttons.extend([[Button.inline("📊 Global Statistics", "channel:stats"), Button.inline("🔍 Channel Discovery", "channel:search")], [Button.inline("🔙 Back to Main Menu", "menu:main")]])
        if hasattr(event, 'message_id'):
            await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        else:
            await bot.send_message(user_id, text, buttons=buttons)
    except Exception as e:
        logger.error(f"Failed to handle channels: {e}")
        await event.reply("❌ Error loading channel manager")

async def _cleanup_old_messages(bot, user_id):
    try:
        user = await mongodb.db.users.find_one({"telegram_id": user_id})
        if user and user.get("main_menu_message_id"):
            try:
                await bot.delete_messages(user_id, user["main_menu_message_id"])
            except:
                pass
    except Exception as e:
        logger.debug(f"Cleanup old messages error: {e}")
