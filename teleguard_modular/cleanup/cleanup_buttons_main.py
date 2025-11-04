"""Split from buttons.py - cleanup_buttons_main"""
"""Menu system - cleanup module"""
import json
import logging
from typing import List, Optional
from telethon import Button, events
from ..core.config import ADMIN_IDS
from ..core.mongo_database import mongodb
from .secure_2fa_handlers import Secure2FAHandlers
from ..utils.network_helpers import format_display_name, format_phone_number


    async def _handle_spam_master(self, event):
        """Handle SpamMaster menu - redirect to advanced spam handler"""
        user_id = event.sender_id
        try:
            # Redirect to advanced spam handler
            if hasattr(self.account_manager, 'advanced_spam_handler'):
                await self.account_manager.advanced_spam_handler._handle_spam_master_menu(event)
            else:
                await event.reply("❌ SpamMaster not available")
        except Exception as e:
            logger.error(f"Failed to handle SpamMaster menu: {e}")
            await event.reply("❌ Error loading SpamMaster menu")
    
    async def _handle_cleanup(self, event):
        """Handle Cleanup menu"""
        user_id = event.sender_id
        try:
            # Delete previous messages to avoid collision
            await self._cleanup_old_messages(user_id)
            
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = (
                    "🧹 **Professional Account Cleanup**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🚨 **No accounts available!**\n\n"
                    "You need active accounts to use cleanup features.\n\n"
                    "🎯 **Cleanup Capabilities:**\n"
                    "• 💬 **Smart Chat Cleanup** - Personal, bot, official chats\n"
                    "• 🚫 **Spam Removal** - Spambot and unwanted chats\n"
                    "• 🚪 **Mass Exit** - Leave channels and groups\n"
                    "• 🗑️ **Ownership Cleanup** - Delete owned channels/groups\n"
                    "• 📞 **Spam Appeals** - Automated appeal system\n\n"
                    "⚠️ **Important:** All cleanup actions are irreversible!\n\n"
                    "Add accounts to access cleanup tools:"
                )
                buttons = [
                    [Button.inline("🚀 Add First Account", "account:add")],
                    [Button.inline("❓ Cleanup Guide", "help:features")],
                    [Button.inline("🔙 Back to Main Menu", "menu:main")],
                ]
            else:
                active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
                
                text = (
                    "🧹 **Professional Account Cleanup**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📊 **System Status:**\n"
                    f"• 📱 Active Accounts: {active_accounts}/{len(accounts)}\n"
                    f"• 🟢 Cleanup Tools: Ready\n\n"
                    "⚠️ **CRITICAL WARNING:**\n"
                    "All cleanup actions are **PERMANENT** and **IRREVERSIBLE**!\n\n"
                    "🎯 **Available Cleanup Options:**\n"
                    "• 💬 Personal chats • 🤖 Bot conversations\n"
                    "• 📢 Telegram official • 🚫 Spambot chats\n"
                    "• 🚪 Exit channels • 👥 Exit groups\n"
                    "• 🗑️ Delete owned groups • 📺 Delete owned channels\n\n"
                    "🎛️ **Select Account to Clean:**"
                )
                
                buttons = []
                for account in accounts:
                    status = "🟢" if account.get("is_active", False) else "🔴"
                    display_name = format_display_name(account)
                    button_text = f"{status} {display_name}"
                    buttons.append([Button.inline(button_text, f"cleanup:select:{account['_id']}")])
                
                buttons.append([Button.inline("🔙 Back to Main Menu", "menu:main")])
            if hasattr(event, 'message_id'):
                await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            else:
                await self.bot.send_message(user_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to handle cleanup: {e}")
            await event.reply("❌ Error loading cleanup menu")
    
    async def _handle_cleanup_callback(self, event, user_id: int, data: str):
        """Handle account cleanup callbacks"""
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else "menu"
        
        if action == "menu":
            # Redirect to main cleanup handler
            await self._handle_cleanup(type("Event", (), {"sender_id": user_id, "reply": lambda x, buttons=None: self.bot.edit_message(user_id, event.message_id, x, buttons=buttons)})())
        elif action == "select":
            account_id = parts[2] if len(parts) > 2 else None
            if account_id:
                await self._send_cleanup_selection(user_id, event.message_id, account_id)
        elif action == "options":
            account_id = parts[2] if len(parts) > 2 else None
            cleanup_types = parts[3] if len(parts) > 3 else None
            if account_id and cleanup_types:
                try:
                    await self._send_cleanup_confirmation(user_id, event.message_id, account_id, cleanup_types)
                except Exception as e:
                    if "Content of the message was not modified" in str(e):
                        # Message content is the same, just answer the callback
                        await event.answer("✅ Cleanup options confirmed")
                    else:
                        logger.error(f"Cleanup options error: {e}")
                        await event.answer("❌ Error processing cleanup options")
        elif action == "confirm":
            account_id = parts[2] if len(parts) > 2 else None
            cleanup_types = parts[3] if len(parts) > 3 else None
            if account_id and cleanup_types:
                await self._execute_cleanup(event, user_id, account_id, cleanup_types)
        elif action == "appeal":
            account_id = parts[2] if len(parts) > 2 else None
            if account_id:
                await self._handle_spam_appeal(event, user_id, account_id)
        elif action == "spam_appeal_select":
            await self._handle_spam_appeal_select(event, user_id)
    

    
    async def _send_cleanup_selection(self, user_id: int, message_id: int, account_id: str):
        """Send cleanup type selection for account"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                await self.bot.edit_message(user_id, message_id, "❌ Account not found", buttons=[[Button.inline("🔙 Back", "cleanup:menu")]])
                return
            
            display_name = format_display_name(account)
            
            text = (
                f"🧹 **Cleanup Selection - {display_name}**\n\n"
                f"📋 **What would you like to clean?**\n\n"
                f"Select what to clean (you can choose multiple options):\n\n"
                f"💬 **Personal chats** - Direct messages with users\n"
                f"🤖 **Bot chats** - Conversations with bots\n"
                f"📢 **Telegram official** - Telegram service chats\n"
                f"🚫 **Spambot chats** - @spambot conversations\n"
                f"🚪 **Exit channels** - Leave all channels\n"
                f"👥 **Exit groups** - Leave all groups\n"
                f"🗑️ **Delete owned groups** - Delete groups you own\n"
                f"📺 **Delete owned channels** - Delete channels you own\n\n"
                f"⚠️ **WARNING**: These actions cannot be undone!"
            )
            
            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {
                    "action": "cleanup_selection",
                    "account_id": account_id
                }
            
            await self.bot.edit_message(user_id, message_id, text)
            await self.bot.send_message(
                user_id,
                "📝 **Reply with your selection:**\n\n"
                "Type what you want to clean, separated by commas:\n\n"
                "**Examples:**\n"
                "• `personal,bots` - Clean personal chats and bot chats\n"
                "• `channels,groups` - Exit all channels and groups\n"
                "• `all` - Clean everything\n\n"
                "**Available options:**\n"
                "`personal`, `bots`, `telegram`, `spambot`, `channels`, `groups`, `owned_groups`, `owned_channels`, `all`"
            )
            
        except Exception as e:
            logger.error(f"Error in cleanup selection: {e}")
            await self.bot.edit_message(user_id, message_id, "❌ Error loading cleanup selection", buttons=[[Button.inline("🔙 Back", "cleanup:menu")]])
    
    async def _send_cleanup_confirmation(self, user_id: int, message_id: int, account_id: str, cleanup_types: str):
        """Send cleanup confirmation with selected options"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                await self.bot.edit_message(user_id, message_id, "❌ Account not found", buttons=[[Button.inline("🔙 Back", "cleanup:menu")]])
                return
            
            display_name = format_display_name(account)
            
            # Parse cleanup types
            cleanup_list = [t.strip().lower() for t in cleanup_types.split(',')]
            if 'all' in cleanup_list:
                cleanup_list = ['personal', 'bots', 'telegram', 'spambot', 'channels', 'groups', 'owned_groups', 'owned_channels']
            
            # Create display text for selected options
            selected_options = []
            if 'personal' in cleanup_list:
                selected_options.append("✅ 💬 Personal chats")
            if 'bots' in cleanup_list:
                selected_options.append("✅ 🤖 Bot chats")
            if 'telegram' in cleanup_list:
                selected_options.append("✅ 📢 Telegram official chats")
            if 'spambot' in cleanup_list:
                selected_options.append("✅ 🚫 Spambot chats")
            if 'channels' in cleanup_list:
                selected_options.append("✅ 🚪 Exit from channels")
            if 'groups' in cleanup_list:
                selected_options.append("✅ 👥 Exit from groups")
            if 'owned_groups' in cleanup_list:
                selected_options.append("✅ 🗑️ Delete owned groups")
            if 'owned_channels' in cleanup_list:
                selected_options.append("✅ 📺 Delete owned channels")
            
            if not selected_options:
                await self.bot.send_message(user_id, "❌ No valid cleanup options selected. Please try again.")
                return
            
            text = (
                f"🧹 **Final Cleanup Confirmation**\n\n"
                f"📱 Account: {display_name}\n\n"
                f"**Selected cleanup actions:**\n"
                + "\n".join(selected_options) + "\n\n"
                f"⚠️ **FINAL WARNING**: This action cannot be undone!\n"
                f"All selected chats and data will be permanently deleted.\n\n"
                f"Are you absolutely sure you want to proceed?"
            )
            
            buttons = [
                [Button.inline("🚀 YES, Start Cleanup", f"cleanup:confirm:{account_id}:{cleanup_types}")],
                [Button.inline("❌ Cancel", "cleanup:menu")]
            ]
            
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in cleanup confirmation: {e}")
            await self.bot.edit_message(user_id, message_id, "❌ Error loading cleanup confirmation", buttons=[[Button.inline("🔙 Back", "cleanup:menu")]])
    
    async def _execute_cleanup(self, event, user_id: int, account_id: str, cleanup_types: str):
        """Execute account cleanup with selected options"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                await event.answer("❌ Account not found")
                return
            
            if not self.account_manager:
                await event.answer("❌ Service unavailable")
                return
            
            # Get existing client from account manager
            client = None
            if hasattr(self.account_manager, 'user_clients') and user_id in self.account_manager.user_clients:
                account_name = account.get('name')
                client = self.account_manager.user_clients[user_id].get(account_name)
            
            if not client or not client.is_connected():
                await event.answer("❌ Account not connected. Please ensure account is active.")
                return
            
            display_name = format_display_name(account)
            
            # Parse cleanup types
            cleanup_list = [t.strip().lower() for t in cleanup_types.split(',')]
            if 'all' in cleanup_list:
                cleanup_list = ['personal', 'bots', 'telegram', 'spambot', 'channels', 'groups', 'owned_groups', 'owned_channels']
            
            # Map to cleanup settings
            cleanup_settings = {
                'personal_chats': 'personal' in cleanup_list,
                'bot_chats': 'bots' in cleanup_list,
                'telegram_chat': 'telegram' in cleanup_list,
                'spambot_chat': 'spambot' in cleanup_list,
                'channels': 'channels' in cleanup_list,
                'groups': 'groups' in cleanup_list,
                'owned_groups': 'owned_groups' in cleanup_list,
                'owned_channels': 'owned_channels' in cleanup_list
            }
            
            try:
                await self.bot.edit_message(
                    user_id, event.message_id,
                    f"🚀 **Starting cleanup for {display_name}**\n\n⏳ Analyzing account...\n📊 Progress will be shown below",
                    buttons=None
                )
            except Exception as edit_error:
                if "Content of the message was not modified" in str(edit_error):
                    # Message is already showing progress, continue
                    pass
                else:
                    # Send new message if edit fails
                    await self.bot.send_message(
                        user_id,
                        f"🚀 **Starting cleanup for {display_name}**\n\n⏳ Analyzing account...\n📊 Progress will be shown below"
                    )
            
            from teleguard.core.account_cleaner import AccountCleaner
            cleaner = AccountCleaner()
            
            import time
            last_update_time = time.time()
            
            async def progress_callback(text):
                nonlocal last_update_time
                current_time = time.time()
                
                if current_time - last_update_time < 2:
                    return
                
                try:
                    await self.bot.edit_message(
                        user_id, event.message_id,
                        f"🚀 **Cleaning {display_name}**\n\n{text}",
                        buttons=None
                    )
                    last_update_time = current_time
                except Exception as e:
                    if "Content of the message was not modified" not in str(e):
                        logger.debug(f"Progress update error: {e}")
            
            result = await cleaner.cleanup_account(client, cleanup_settings, progress_callback)
            
            result_text = (
                f"✅ **Cleanup completed!**\n\n"
                f"📱 Account: {display_name}\n\n"
                f"📊 **Results:**\n{result}\n\n"
                f"🔒 All operations completed securely"
            )
            
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            
            try:
                await self.bot.edit_message(user_id, event.message_id, result_text, buttons=buttons)
            except Exception as edit_error:
                if "Content of the message was not modified" in str(edit_error):
                    # Message content is the same, just answer callback if available
                    try:
                        await event.answer("✅ Cleanup completed successfully!")
                    except:
                        pass
                else:
                    # Send new message if edit fails for other reasons
                    await self.bot.send_message(user_id, result_text, buttons=buttons)
            
            await mongodb.add_audit_entry(account_id, {
                "action": "cleanup_completed",
                "cleanup_types": cleanup_types,
                "timestamp": int(time.time()),
                "result": "success"
            })
            
        except Exception as e:
