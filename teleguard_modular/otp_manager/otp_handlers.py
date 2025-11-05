"""OTP Manager handlers"""
import logging
from telethon import Button
from ...core.mongo_database import mongodb
from ...utils.network_helpers import format_display_name

logger = logging.getLogger(__name__)

async def handle_otp_manager(bot, user_id, event):
    """Handle OTP Manager menu"""
    try:
        await _cleanup_old_messages(bot, user_id)
        
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
        if not accounts:
            text = (
                "🛡️ **OTP Security Manager**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "🚨 **No accounts found!**\n\n"
                "You need to add accounts first before configuring OTP protection.\n\n"
                "🎯 **What is OTP Protection?**\n"
                "• 🛡️ **Destroyer** - Blocks unauthorized login attempts\n"
                "• 📤 **Forward** - Forwards OTP codes to you\n"
                "• ⏰ **Temp Pass** - 5-minute security bypass\n\n"
                "Add your first account to get started:"
            )
            buttons = [
                [Button.inline("🚀 Add First Account", "account:add")],
                [Button.inline("❓ Security Guide", "help:security")],
                [Button.inline("🔙 Back to Main Menu", "menu:main")],
            ]
        else:
            destroyer_enabled = sum(1 for acc in accounts if acc.get("otp_destroyer_enabled", False))
            forward_enabled = sum(1 for acc in accounts if acc.get("otp_forward_enabled", False))
            temp_active = sum(1 for acc in accounts if acc.get("otp_temp_passthrough", False))
            
            security_score = int((destroyer_enabled/len(accounts))*100)
            security_emoji = "🟢" if security_score >= 80 else "🟡" if security_score >= 50 else "🔴"
            
            text = (
                "🛡️ **OTP Security Manager**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 **Security Dashboard:**\n"
                f"• {security_emoji} **Security Score:** {security_score}%\n"
                f"• 🛡️ **Destroyer Active:** {destroyer_enabled}/{len(accounts)} accounts\n"
                f"• 📤 **Forward Active:** {forward_enabled}/{len(accounts)} accounts\n"
                f"• ⏰ **Temp Bypass:** {temp_active} active\n\n"
                "🎛️ **Protection Controls:**\n"
                "Choose your security configuration below:"
            )
            buttons = [
                [Button.inline("🛡️ OTP Destroyer", "otp_setting:destroyer"), Button.inline("📤 OTP Forward", "otp_setting:forward")],
                [Button.inline("⏰ Temp Bypass", "otp_setting:temp"), Button.inline("📊 Statistics", "otp:stats")],
                [Button.inline("🟢 Enable All Protection", "otp:enable_all"), Button.inline("🔴 Disable All Protection", "otp:disable_all")],
                [Button.inline("📋 Security Audit Log", "otp:audit_all")],
                [Button.inline("🔙 Back to Main Menu", "menu:main")],
            ]
        
        if hasattr(event, 'message_id'):
            await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        else:
            await bot.send_message(user_id, text, buttons=buttons)
    except Exception as e:
        logger.error(f"Failed to handle OTP manager: {e}")
        await event.reply("❌ Error loading OTP manager. Please try again.")

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
