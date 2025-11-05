"""Cleanup menu handlers"""
import logging
from telethon import Button
from ..core.mongo_database import mongodb
from ..utils.helpers import format_display_name

logger = logging.getLogger(__name__)

async def handle_cleanup_menu(bot, user_id, event):
    try:
        await _cleanup_old_messages(bot, user_id)
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
        if not accounts:
            text = "🧹 **Professional Account Cleanup**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🚨 **No accounts available!**\n\nYou need active accounts to use cleanup features.\n\n🎯 **Cleanup Capabilities:**\n• 💬 **Smart Chat Cleanup** - Personal, bot, official chats\n• 🚫 **Spam Removal** - Spambot and unwanted chats\n• 🚪 **Mass Exit** - Leave channels and groups\n• 🗑️ **Ownership Cleanup** - Delete owned channels/groups\n• 📞 **Spam Appeals** - Automated appeal system\n\n⚠️ **Important:** All cleanup actions are irreversible!\n\nAdd accounts to access cleanup tools:"
            buttons = [[Button.inline("🚀 Add First Account", "account:add")], [Button.inline("❓ Cleanup Guide", "help:features")], [Button.inline("🔙 Back to Main Menu", "menu:main")]]
        else:
            active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
            text = f"🧹 **Professional Account Cleanup**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📊 **System Status:**\n• 📱 Active Accounts: {active_accounts}/{len(accounts)}\n• 🟢 Cleanup Tools: Ready\n\n⚠️ **CRITICAL WARNING:**\nAll cleanup actions are **PERMANENT** and **IRREVERSIBLE**!\n\n🎯 **Available Cleanup Options:**\n• 💬 Personal chats • 🤖 Bot conversations\n• 📢 Telegram official • 🚫 Spambot chats\n• 🚪 Exit channels • 👥 Exit groups\n• 🗑️ Delete owned groups • 📺 Delete owned channels\n\n🎛️ **Select Account to Clean:**"
            buttons = []
            for account in accounts:
                status = "🟢" if account.get("is_active", False) else "🔴"
                display_name = format_display_name(account)
                button_text = f"{status} {display_name}"
                buttons.append([Button.inline(button_text, f"cleanup:select:{account['_id']}")])
            buttons.append([Button.inline("🔙 Back to Main Menu", "menu:main")])
        if hasattr(event, 'message_id'):
            await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        else:
            await bot.send_message(user_id, text, buttons=buttons)
    except Exception as e:
        logger.error(f"Failed to handle cleanup: {e}")
        await event.reply("❌ Error loading cleanup menu")

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
