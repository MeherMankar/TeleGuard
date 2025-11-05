"""Support menu handlers"""
import logging
from telethon import Button
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

async def handle_support_menu(bot, user_id, event):
    await _cleanup_old_messages(bot, user_id)
    text = "🆘 **TeleGuard Support Center**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n👨💻 **Development Team:**\n• **@Meher_Mankar** - Lead Developer & Founder\n• **@Gutkesh** - Core Developer & Security Expert\n\n🎯 **Get Instant Help:**\n• 💬 **Live Support:** @ContactXYZrobot\n• 🐛 **Bug Reports:** GitHub Issues Portal\n• 📚 **Documentation:** Complete Wiki Guide\n• ⚡ **Response Time:** < 6 hours (usually faster)\n\n🔧 **Self-Help Checklist:**\n✅ Check Help section for instant solutions\n✅ Try `/start` to refresh the bot\n✅ Verify accounts are properly connected\n✅ Review troubleshooting guide first\n\n🚨 **Emergency Support:** Contact developers directly for critical issues"
    buttons = [[Button.inline("💬 Contact Support", "support:contact"), Button.inline("🐛 Report Bug", "support:bug")], [Button.inline("📚 Documentation", "support:docs"), Button.inline("💡 Feature Request", "support:feature")], [Button.inline("📊 System Status", "support:status"), Button.inline("🔄 Updates", "support:updates")], [Button.inline("🔙 Back to Main Menu", "menu:main")]]
    if hasattr(event, 'message_id'):
        await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
    else:
        await bot.send_message(user_id, text, buttons=buttons)

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
