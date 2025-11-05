"""Developer panel menu handlers"""
import logging
from telethon import Button
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

async def handle_developer_menu(bot, user_id, event):
    try:
        await _cleanup_old_messages(bot, user_id)
        user = await mongodb.db.users.find_one({"telegram_id": user_id})
        if user:
            current_mode = user.get("developer_mode", False)
            account_count = await mongodb.db.accounts.count_documents({})
            user_count = await mongodb.db.users.count_documents({})
            text = f"⚙️ **Developer Control Panel**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🎛️ **Developer Mode:** {'🟢 **ACTIVE**' if current_mode else '🔴 **INACTIVE**'}\n\n📊 **System Overview:**\n• 👥 Total Users: {user_count:,}\n• 📱 Total Accounts: {account_count:,}\n• 🟢 System Status: Operational\n\n🛠️ **Administrative Tools:**\n• 🔧 **System Control** - Mode toggle, restart, maintenance\n• 📊 **Monitoring** - Real-time metrics & performance\n• 🐛 **Debugging** - Error logs & diagnostic tools\n• 🗄️ **Database** - Statistics & optimization tools\n• 🚀 **Deployment** - Configuration & startup management\n\n⚠️ **Administrator Access** - Advanced system operations only"
            mode_text = "🔴 Disable Developer Mode" if current_mode else "🟢 Enable Developer Mode"
            buttons = [[Button.inline(mode_text, "dev:toggle")], [Button.inline("📊 System Dashboard", "dev:sysinfo"), Button.inline("📋 System Logs", "dev:logs")], [Button.inline("🗄️ Database Tools", "dev:dbstats"), Button.inline("⚡ Performance Monitor", "dev:perf")], [Button.inline("🔧 Maintenance Tools", "dev:maintenance"), Button.inline("🔄 System Restart", "dev:restart")], [Button.inline("🚀 Startup Config", "dev:startup"), Button.inline("📚 Command Reference", "dev:commands")], [Button.inline("🔙 Back to Main Menu", "menu:main")]]
            if hasattr(event, 'message_id'):
                await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            else:
                await bot.send_message(user_id, text, buttons=buttons)
        else:
            await event.reply("❌ User not found")
    except Exception as e:
        logger.error(f"Failed to handle developer menu: {e}")
        await event.reply("❌ Error loading developer tools")

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
