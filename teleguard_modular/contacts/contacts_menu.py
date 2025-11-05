"""Contacts menu handlers"""
import logging
from telethon import Button
from ..core.mongo_database import mongodb
from ..utils.helpers import format_display_name

logger = logging.getLogger(__name__)

async def handle_contacts_menu(bot, user_id, event, account_manager):
    try:
        await _cleanup_old_messages(bot, user_id)
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
        if not accounts:
            text = "👥 **Advanced Contact Management**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🚨 **No accounts available!**\n\nYou need active accounts to manage contacts.\n\n🎯 **Contact Features:**\n• 📱 **Smart Management** - Add, edit, organize contacts\n• 🏷️ **Advanced Tagging** - Categories and groups\n• 📤 **Export Tools** - CSV, JSON, Excel formats\n• 🔄 **Sync Engine** - Two-way Telegram sync\n• 🛡️ **Privacy Controls** - Blacklist/whitelist system\n\nAdd accounts to unlock contact management:"
            buttons = [[Button.inline("🚀 Add First Account", "account:add")], [Button.inline("❓ Contact Guide", "help:features")], [Button.inline("🔙 Back to Main Menu", "menu:main")]]
        else:
            contact_count = sum([await mongodb.db.contacts.count_documents({"managed_by_account": acc['name']}) for acc in accounts])
            active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
            text = f"👥 **Advanced Contact Management**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📊 **System Statistics:**\n• 👥 Total Contacts: {contact_count:,}\n• 📱 Active Accounts: {active_accounts}/{len(accounts)}\n• 🟢 System Status: Operational\n\n🚀 **Professional Features:**\n• 📱 Smart contact organization and management\n• 🏷️ Advanced tagging and categorization system\n• 📤 Multi-format export (CSV, JSON, Excel)\n• 🔄 Intelligent two-way Telegram synchronization\n• 🛡️ Privacy controls with blacklist/whitelist\n\nAccess your contact management dashboard:"
            buttons = [[Button.inline("🎛️ Contact Dashboard", "contacts:main")], [Button.inline("📤 Quick Export", "contacts:export"), Button.inline("🔄 Sync Contacts", "contacts:sync")], [Button.inline("🔙 Back to Main Menu", "menu:main")]]
        if hasattr(event, 'message_id'):
            await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        else:
            await bot.send_message(user_id, text, buttons=buttons)
    except Exception as e:
        logger.error(f"Failed to handle contacts: {e}")
        await event.reply("❌ Error loading contact management")

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
