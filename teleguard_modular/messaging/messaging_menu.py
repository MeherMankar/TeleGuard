"""Messaging menu handlers"""
import logging
from telethon import Button
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

async def handle_messaging_menu(bot, user_id, event):
    try:
        await _cleanup_old_messages(bot, user_id)
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
        if not accounts:
            text = "💬 **Advanced Messaging Center**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🚨 **No accounts available!**\n\nYou need active accounts to use messaging features.\n\n🎯 **Available Features:**\n• 📤 **Smart Messaging** - Send to users/groups\n• 📨 **Bulk Operations** - Mass messaging campaigns\n• 🤖 **Auto-Reply** - Intelligent response system\n• 📝 **Templates** - Reusable message templates\n• 📨 **DM Management** - Unified inbox system\n\nAdd accounts to unlock these powerful features:"
            buttons = [[Button.inline("🚀 Add First Account", "account:add")], [Button.inline("❓ Messaging Guide", "help:features")], [Button.inline("🔙 Back to Main Menu", "menu:main")]]
        else:
            active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
            auto_reply_enabled = sum(1 for acc in accounts if acc.get("auto_reply_enabled", False))
            text = f"💬 **Advanced Messaging Center**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📊 **System Status:**\n• 📱 Active Accounts: {active_accounts}/{len(accounts)}\n• 🤖 Auto-Reply: {auto_reply_enabled} enabled\n• 🟢 System: Operational\n\n🚀 **Messaging Tools:**\nChoose your messaging action below:"
            buttons = [[Button.inline("📤 Smart Messaging", "msg:send"), Button.inline("📨 Bulk Campaigns", "msg:bulk")], [Button.inline("🤖 Auto-Reply System", "auto_reply:main"), Button.inline("📝 Message Templates", "msg:templates")], [Button.inline("📨 Unified DM Manager", "dm_reply:main"), Button.inline("📊 Analytics", "msg:stats")], [Button.inline("📋 Message History", "msg:history"), Button.inline("⚙️ System Settings", "msg:settings")], [Button.inline("🔙 Back to Main Menu", "menu:main")]]
        if hasattr(event, 'message_id'):
            await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        else:
            await bot.send_message(user_id, text, buttons=buttons)
    except Exception as e:
        logger.error(f"Failed to handle messaging: {e}")
        await event.reply("❌ Error loading messaging menu")

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
