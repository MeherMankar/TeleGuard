"""Account management handlers"""
import logging
from telethon import Button
from ...core.mongo_database import mongodb
from ...utils.network_helpers import format_display_name, format_phone_number

logger = logging.getLogger(__name__)

async def handle_account_settings(bot, user_id, event):
    """Handle Account Settings menu"""
    try:
        await _cleanup_old_messages(bot, user_id)
        
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
        if not accounts:
            text = (
                "📱 **Account Management Center**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "🚀 **Welcome to TeleGuard!**\n\n"
                "No accounts found. Let's get you started with your first account.\n\n"
                "🎯 **Quick Setup:**\n"
                "1️⃣ Add your first account\n"
                "2️⃣ Enable OTP protection\n"
                "3️⃣ Explore advanced features\n\n"
                "Choose an option below to begin:"
            )
            buttons = [
                [Button.inline("🚀 Add First Account", "account:add")],
                [Button.inline("🔐 Session Login", "session_login"), Button.inline("📥 Import Sessions", "import_sessions")],
                [Button.inline("❓ Setup Guide", "help:guide")],
                [Button.inline("🔙 Back to Main Menu", "menu:main")],
            ]
        else:
            active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
            protected_accounts = sum(1 for acc in accounts if acc.get("otp_destroyer_enabled", False))
            
            text = (
                f"📱 **Account Management Center**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 **Overview:**\n"
                f"• 📱 Total Accounts: {len(accounts)}\n"
                f"• 🟢 Active: {active_accounts}\n"
                f"• 🛡️ Protected: {protected_accounts}\n\n"
                "📋 **Your Accounts:**\n"
            )
            buttons = []

            for i, account in enumerate(accounts, 1):
                status = "🟢" if account.get("is_active", False) else "🔴"
                destroyer_status = "🛡️" if account.get("otp_destroyer_enabled", False) else "⚪"
                display_name = format_display_name(account)
                account_phone = format_phone_number(account.get('phone', 'Unknown'))
                
                text += f"{i}. {status}{destroyer_status} **{display_name}** `{account_phone}`\n"
                buttons.append([Button.inline(f"⚙️ {format_display_name(account)}", f"account:manage:{account['_id']}")])
            
            text += "\n🎛️ **Management Tools:**"
            buttons.extend([
                [Button.inline("➕ Add Account", "account:add"), Button.inline("🗑️ Remove Account", "account:remove")],
                [Button.inline("🔐 Login via Session", "session_login"), Button.inline("✨ Create Session", "export_sessions")],
                [Button.inline("🔄 Refresh Status", "account:refresh"), Button.inline("📋 Detailed List", "account:list")],
                [Button.inline("🔙 Back to Main Menu", "menu:main")],
            ])
        
        if hasattr(event, 'message_id'):
            await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        else:
            await bot.send_message(user_id, text, buttons=buttons)
    except Exception as e:
        logger.error(f"Failed to handle account settings: {e}")
        await event.reply("❌ Error loading account settings. Please try again.")

async def _cleanup_old_messages(bot, user_id):
    """Delete old menu messages"""
    try:
        user = await mongodb.db.users.find_one({"telegram_id": user_id})
        if user and user.get("main_menu_message_id"):
            try:
                await bot.delete_messages(user_id, user["main_menu_message_id"])
            except:
                pass
    except Exception as e:
        logger.debug(f"Cleanup old messages error: {e}")
