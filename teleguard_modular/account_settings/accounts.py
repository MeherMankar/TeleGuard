"""Menu system - accounts module"""
import json
import logging
from typing import List, Optional
from telethon import Button, events
from ..core.config import ADMIN_IDS
from ..core.mongo_database import mongodb
from ..utils.helpers import format_display_name
from ..utils.network_helpers import format_phone_number


    async def _handle_account_settings(self, event):
        """Handle Account Settings menu"""
        user_id = event.sender_id
        try:
            # Delete previous messages to avoid collision
            await self._cleanup_old_messages(user_id)
            
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
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
                # Calculate statistics
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
                    buttons.append(
                        [
                            Button.inline(
                                f"⚙️ {format_display_name(account)}",
                                f"account:manage:{account['_id']}",
                            )
                        ]
                    )
                
                text += "\n🎛️ **Management Tools:**"
                buttons.extend([
                    [
                        Button.inline("➕ Add Account", "account:add"),
                        Button.inline("🗑️ Remove Account", "account:remove"),
                    ],
                    [
                        Button.inline("🔐 Login via Session", "session_login"),
                        Button.inline("✨ Create Session", "export_sessions"),
                    ],
                    [
                        Button.inline("🔄 Refresh Status", "account:refresh"),
                        Button.inline("📋 Detailed List", "account:list"),
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
            logger.error(f"Failed to handle account settings: {e}")
            await event.reply("❌ Error loading account settings. Please try again.")
