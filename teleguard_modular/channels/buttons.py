"""Menu system - channels module"""
import json
import logging
from typing import List, Optional
from telethon import Button, events
from ..core.config import ADMIN_IDS
from ..core.mongo_database import mongodb
from .secure_2fa_handlers import Secure2FAHandlers
from ..utils.network_helpers import format_display_name, format_phone_number


    async def _handle_channels(self, event):
        """Handle Channels menu"""
        user_id = event.sender_id
        try:
            # Delete previous messages to avoid collision
            await self._cleanup_old_messages(user_id)
            
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            if not accounts:
                text = (
                    "📢 **Channel Management Hub**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🚨 **No accounts available!**\n\n"
                    "You need active accounts to manage channels and groups.\n\n"
                    "🎯 **Channel Features:**\n"
                    "• 🔗 **Smart Join/Leave** - Bulk channel operations\n"
                    "• 🆕 **Channel Creation** - Create channels & groups\n"
                    "• 📋 **Management Tools** - List, organize, moderate\n"
                    "• 🗑️ **Cleanup Tools** - Mass leave/delete operations\n"
                    "• 📊 **Analytics** - Channel performance metrics\n\n"
                    "Add accounts to unlock channel management:"
                )
                buttons = [
                    [Button.inline("🚀 Add First Account", "account:add")],
                    [Button.inline("❓ Channel Guide", "help:features")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
                
                text = (
                    "📢 **Channel Management Hub**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📊 **System Overview:**\n"
                    f"• 📱 Active Accounts: {active_accounts}/{len(accounts)}\n"
                    f"• 🟢 Management Tools: Ready\n\n"
                    "🎛️ **Select Account for Channel Operations:**\n"
                    "Choose an account to manage its channels and groups:"
                )
                buttons = []
                for account in accounts[:8]:  # Limit to 8 accounts
                    status = "🟢" if account.get("is_active", False) else "🔴"
                    display_name = format_display_name(account)
                    button_text = f"{status} {display_name}"
                    buttons.append(
                        [
                            Button.inline(
                                button_text, f"channel:select:{account['phone']}"
                            )
                        ]
                    )
                buttons.extend([
                    [
                        Button.inline("📊 Global Statistics", "channel:stats"),
                        Button.inline("🔍 Channel Discovery", "channel:search"),
                    ],
                    [
                        Button.inline("🔙 Back to Main Menu", "menu:main"),
                    ],
                ])
            if hasattr(event, 'message_id'):
                await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            else:
                await self.bot.send_message(user_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to handle channels: {e}")
            await event.reply("❌ Error loading channel manager")
