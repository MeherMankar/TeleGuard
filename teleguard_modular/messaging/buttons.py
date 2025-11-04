"""Menu system - messaging module"""
import json
import logging
from typing import List, Optional
from telethon import Button, events
from ..core.config import ADMIN_IDS
from ..core.mongo_database import mongodb
from .secure_2fa_handlers import Secure2FAHandlers
from ..utils.network_helpers import format_display_name, format_phone_number


    async def _handle_messaging(self, event):
        """Handle Messaging menu"""
        user_id = event.sender_id
        try:
            # Delete previous messages to avoid collision
            await self._cleanup_old_messages(user_id)
            
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = (
                    "💬 **Advanced Messaging Center**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🚨 **No accounts available!**\n\n"
                    "You need active accounts to use messaging features.\n\n"
                    "🎯 **Available Features:**\n"
                    "• 📤 **Smart Messaging** - Send to users/groups\n"
                    "• 📨 **Bulk Operations** - Mass messaging campaigns\n"
                    "• 🤖 **Auto-Reply** - Intelligent response system\n"
                    "• 📝 **Templates** - Reusable message templates\n"
                    "• 📨 **DM Management** - Unified inbox system\n\n"
                    "Add accounts to unlock these powerful features:"
                )
                buttons = [
                    [Button.inline("🚀 Add First Account", "account:add")],
                    [Button.inline("❓ Messaging Guide", "help:features")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                # Get messaging statistics
                active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
                auto_reply_enabled = sum(1 for acc in accounts if acc.get("auto_reply_enabled", False))
                
                text = (
                    "💬 **Advanced Messaging Center**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📊 **System Status:**\n"
                    f"• 📱 Active Accounts: {active_accounts}/{len(accounts)}\n"
                    f"• 🤖 Auto-Reply: {auto_reply_enabled} enabled\n"
                    f"• 🟢 System: Operational\n\n"
                    "🚀 **Messaging Tools:**\n"
                    "Choose your messaging action below:"
                )
                buttons = [
                    [
                        Button.inline("📤 Smart Messaging", "msg:send"),
                        Button.inline("📨 Bulk Campaigns", "msg:bulk"),
                    ],
                    [
                        Button.inline("🤖 Auto-Reply System", "auto_reply:main"),
                        Button.inline("📝 Message Templates", "msg:templates"),
                    ],
                    [
                        Button.inline("📨 Unified DM Manager", "dm_reply:main"),
                        Button.inline("📊 Analytics", "msg:stats"),
                    ],
                    [
                        Button.inline("📋 Message History", "msg:history"),
                        Button.inline("⚙️ System Settings", "msg:settings"),
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
            logger.error(f"Failed to handle messaging: {e}")
            await event.reply("❌ Error loading messaging menu")
