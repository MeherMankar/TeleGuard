"""Help menu handlers"""
import logging
from telethon import Button
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

async def handle_help_menu(bot, user_id, event):
    await _cleanup_old_messages(bot, user_id)
    user = await mongodb.db.users.find_one({"telegram_id": user_id})
    account_count = await mongodb.db.accounts.count_documents({"user_id": user_id})
    otp_enabled = await mongodb.db.accounts.count_documents({"user_id": user_id, "otp_destroyer_enabled": True})
    security_score = int((otp_enabled/max(account_count, 1))*100) if account_count > 0 else 0
    status_emoji = "🟢" if security_score >= 80 else "🟡" if security_score >= 50 else "🔴"
    text = f"❓ **TeleGuard Help & Support Center**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📊 **Your Dashboard:**\n• 📱 **Accounts:** {account_count} configured\n• 🛡️ **Protection:** {otp_enabled}/{account_count} secured\n• {status_emoji} **Security Score:** {security_score}%\n\n🚀 **Quick Setup (2 minutes):**\n1️⃣ **Add Account** → `📱 Account Settings` → `Add Account`\n2️⃣ **Enable Security** → `🛡️ OTP Manager` → `Enable Destroyer`\n3️⃣ **Configure Features** → Explore messaging & automation\n\n🎯 **Feature Overview:**\n• 🛡️ **Security** - OTP protection, 2FA, session monitoring\n• 💬 **Messaging** - Auto-reply, templates, bulk sending\n• 📱 **Management** - Profile updates, channel tools\n• 📊 **Analytics** - Activity logs, performance insights\n\n💡 **Pro Tips:**\n• Enable OTP Destroyer on all accounts for maximum security\n• Use DM Reply for centralized message management\n• Monitor audit logs weekly for security insights"
    buttons = [[Button.inline("📖 Complete Guide", "help:guide"), Button.inline("🛡️ Security Guide", "help:security")], [Button.inline("⚙️ Feature Guide", "help:features"), Button.inline("🔧 Troubleshooting", "help:troubleshoot")], [Button.inline("❓ FAQ", "help:faq"), Button.inline("📞 Contact Support", "help:contact")], [Button.inline("🆘 Emergency Help", "help:emergency"), Button.inline("📚 Commands", "help:commands")], [Button.inline("📨 Chat Import", "menu:import")]]
    from ..core.config import ADMIN_IDS
    if user and user_id in ADMIN_IDS:
        dev_mode = user.get("developer_mode", False)
        dev_text = "🔴 Disable Dev Mode" if dev_mode else "⚙️ Enable Dev Mode"
        buttons.append([Button.inline(dev_text, "help:toggle_dev")])
    buttons.append([Button.inline("🔙 Back to Main Menu", "menu:main")])
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
