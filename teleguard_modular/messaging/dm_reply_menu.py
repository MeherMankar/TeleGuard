"""DM Reply menu handlers"""
import logging
from telethon import Button
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

async def handle_dm_reply_menu(bot, user_id, event, account_manager):
    try:
        await _cleanup_old_messages(bot, user_id)
        admin_group_id = await account_manager.unified_messaging._get_user_admin_group(user_id)
        if admin_group_id:
            status_text = f"✅ **Enabled** - Group ID: `{admin_group_id}`"
            buttons = [[Button.inline("🔄 Change Group", "dm_reply:change")], [Button.inline("❌ Disable", "dm_reply:disable")], [Button.inline("📊 Status", "dm_reply:status")]]
        else:
            status_text = "❌ **Disabled**"
            buttons = [[Button.inline("✅ Enable", "dm_reply:enable")], [Button.inline("❓ How to Setup", "dm_reply:help")]]
        text = f"📨 **Unified DM Management System**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🎯 **Smart Topic Creation:** All DMs automatically become organized forum topics\n\n📊 **Current Status:** {status_text}\n\n✨ **Professional Features:**\n• 🔄 **Auto-Organization** - Every DM gets its own topic\n• 💬 **Persistent Threads** - Conversations never get lost\n• ⚡ **Instant Reply** - Just reply in topics, no buttons needed\n• 🤖 **Smart Integration** - Works seamlessly with auto-reply\n• 🎨 **Clean Interface** - Professional message management\n\n🚀 **Perfect for managing multiple accounts from one centralized place!**"
        buttons.append([Button.inline("🔙 Back to Messaging", "menu:messaging")])
        if hasattr(event, 'message_id'):
            await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        else:
            await bot.send_message(user_id, text, buttons=buttons)
    except Exception as e:
        logger.error(f"Failed to handle DM reply menu: {e}")
        await event.reply("❌ Error loading DM reply menu")

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
