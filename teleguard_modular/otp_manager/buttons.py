"""Menu system - otp module"""
import json
import logging
from typing import List, Optional
from telethon import Button, events
from ..core.config import ADMIN_IDS
from ..core.mongo_database import mongodb
from .secure_2fa_handlers import Secure2FAHandlers
from ..utils.network_helpers import format_display_name, format_phone_number


    async def _handle_otp_manager(self, event):
        """Handle OTP Manager menu - Settings first approach"""
        user_id = event.sender_id
        try:
            # Delete previous messages to avoid collision
            await self._cleanup_old_messages(user_id)
            
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
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
                # Count enabled/disabled accounts
                destroyer_enabled = sum(1 for acc in accounts if acc.get("otp_destroyer_enabled", False))
                forward_enabled = sum(1 for acc in accounts if acc.get("otp_forward_enabled", False))
                
                # Count enabled/disabled accounts and calculate security metrics
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
                    [
                        Button.inline("🛡️ OTP Destroyer", "otp_setting:destroyer"),
                        Button.inline("📤 OTP Forward", "otp_setting:forward"),
                    ],
                    [
                        Button.inline("⏰ Temp Bypass", "otp_setting:temp"),
                        Button.inline("📊 Statistics", "otp:stats"),
                    ],
                    [
                        Button.inline("🟢 Enable All Protection", "otp:enable_all"),
                        Button.inline("🔴 Disable All Protection", "otp:disable_all"),
                    ],
                    [
                        Button.inline("📋 Security Audit Log", "otp:audit_all"),
                        # Button.inline("❓ Security Guide", "help:security"),
                    ],
                    [
                        Button.inline("🔙 Back to Main Menu", "menu:main"),
                    ],
                ]
            if hasattr(event, 'message_id'):
                await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            else:
                await self.bot.send_message(user_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to handle OTP manager: {e}")
            await event.reply("❌ Error loading OTP manager. Please try again.")
