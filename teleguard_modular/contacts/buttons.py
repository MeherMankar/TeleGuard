"""Menu system - contacts module"""
import json
import logging
from typing import List, Optional
from telethon import Button, events
from ..core.config import ADMIN_IDS
from ..core.mongo_database import mongodb
from .secure_2fa_handlers import Secure2FAHandlers
from ..utils.network_helpers import format_display_name, format_phone_number


    async def _handle_contacts(self, event):
        """Handle Contacts menu"""
        user_id = event.sender_id
        try:
            # Delete previous messages to avoid collision
            await self._cleanup_old_messages(user_id)
            
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = (
                    "👥 **Advanced Contact Management**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🚨 **No accounts available!**\n\n"
                    "You need active accounts to manage contacts.\n\n"
                    "🎯 **Contact Features:**\n"
                    "• 📱 **Smart Management** - Add, edit, organize contacts\n"
                    "• 🏷️ **Advanced Tagging** - Categories and groups\n"
                    "• 📤 **Export Tools** - CSV, JSON, Excel formats\n"
                    "• 🔄 **Sync Engine** - Two-way Telegram sync\n"
                    "• 🛡️ **Privacy Controls** - Blacklist/whitelist system\n\n"
                    "Add accounts to unlock contact management:"
                )
                buttons = [
                    [Button.inline("🚀 Add First Account", "account:add")],
                    [Button.inline("❓ Contact Guide", "help:features")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                contact_count = 0
                for account in accounts:
                    count = await mongodb.db.contacts.count_documents({"managed_by_account": account['name']})
                    contact_count += count
                # Calculate contact statistics
                active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
                
                text = (
                    "👥 **Advanced Contact Management**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📊 **System Statistics:**\n"
                    f"• 👥 Total Contacts: {contact_count:,}\n"
                    f"• 📱 Active Accounts: {active_accounts}/{len(accounts)}\n"
                    f"• 🟢 System Status: Operational\n\n"
                    "🚀 **Professional Features:**\n"
                    "• 📱 Smart contact organization and management\n"
                    "• 🏷️ Advanced tagging and categorization system\n"
                    "• 📤 Multi-format export (CSV, JSON, Excel)\n"
                    "• 🔄 Intelligent two-way Telegram synchronization\n"
                    "• 🛡️ Privacy controls with blacklist/whitelist\n\n"
                    "Access your contact management dashboard:"
                )
                buttons = [
                    [
                        Button.inline("🎛️ Contact Dashboard", "contacts:main"),
                    ],
                    [
                        Button.inline("📤 Quick Export", "contacts:export"),
                        Button.inline("🔄 Sync Contacts", "contacts:sync"),
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
            logger.error(f"Failed to handle contacts: {e}")
            await event.reply("❌ Error loading contact management")
    
