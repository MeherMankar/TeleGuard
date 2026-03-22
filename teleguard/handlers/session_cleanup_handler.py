"""Session Cleanup Handler - Manage session health and cleanup
Integrated from SessTg project
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List

from telethon import Button, events

from ..core.mongo_database import mongodb
from ..utils.session_validator import SessionValidator

logger = logging.getLogger(__name__)


class SessionCleanupHandler:
    """Handle session validation and cleanup"""
    
    def __init__(self, bot_manager):
        self.bot = bot_manager.bot
        self.bot_manager = bot_manager
        self.user_clients = bot_manager.user_clients
        self.validator = None
        self.cleanup_tasks = {}
    
    def register_handlers(self):
        """Register session cleanup handlers"""
        
        @self.bot.on(events.CallbackQuery(pattern=r"^session_cleanup$"))
        async def session_cleanup_menu(event):
            user_id = event.sender_id
            await self._show_cleanup_menu(event, user_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^cleanup_validate_all$"))
        async def validate_all_sessions(event):
            user_id = event.sender_id
            await self._validate_all_sessions(event, user_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^cleanup_invalid$"))
        async def cleanup_invalid(event):
            user_id = event.sender_id
            await self._cleanup_invalid_sessions(event, user_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^cleanup_need_auth$"))
        async def cleanup_need_auth(event):
            user_id = event.sender_id
            await self._cleanup_need_auth_sessions(event, user_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^cleanup_stats$"))
        async def show_cleanup_stats(event):
            user_id = event.sender_id
            await self._show_cleanup_stats(event, user_id)
    
    async def _show_cleanup_menu(self, event, user_id):
        """Show session cleanup menu"""
        try:
            # Get account statistics
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            
            total = len(accounts)
            active = sum(1 for acc in accounts if acc.get('is_active', False))
            inactive = total - active
            
            text = (
                "🧹 **Session Cleanup & Validation**\n\n"
                "Manage and validate your account sessions:\n\n"
                f"📊 **Statistics:**\n"
                f"• Total accounts: {total}\n"
                f"• Active: {active}\n"
                f"• Inactive: {inactive}\n\n"
                "**Available Actions:**\n"
                "• Validate all sessions\n"
                "• Remove invalid sessions\n"
                "• Remove unauthorized sessions\n"
                "• View cleanup statistics\n\n"
                "Choose an action:"
            )
            
            buttons = [
                [Button.inline("🔍 Validate All Sessions", "cleanup_validate_all")],
                [Button.inline("🗑️ Remove Invalid", "cleanup_invalid")],
                [Button.inline("⚠️ Remove Unauthorized", "cleanup_need_auth")],
                [Button.inline("📊 Cleanup Statistics", "cleanup_stats")],
                [Button.inline("🔙 Back to Account Settings", "menu:accounts")],
            ]
            
            await event.edit(text, buttons=buttons)
        
        except Exception as e:
            logger.error(f"Cleanup menu error: {e}")
            await event.edit("❌ Error loading cleanup menu")
    
    async def _validate_all_sessions(self, event, user_id):
        """Validate all user sessions"""
        try:
            await event.edit("🔍 **Validating Sessions**\n\n⏳ Please wait...")
            
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            
            if not accounts:
                await event.edit("❌ No accounts found to validate")
                return
            
            # Initialize validator
            from ..core.config import config
            validator = SessionValidator(config.telegram.api_id, config.telegram.api_hash)
            
            valid_count = 0
            need_auth_count = 0
            invalid_count = 0
            results = []
            
            for i, account in enumerate(accounts, 1):
                account_name = account.get('name', account.get('phone', 'Unknown'))
                session_string = account.get('session_string')
                
                if not session_string:
                    invalid_count += 1
                    results.append(f"❌ {account_name}: No session string")
                    continue
                
                # Update progress
                if i % 5 == 0:
                    await event.edit(
                        f"🔍 **Validating Sessions**\n\n"
                        f"Progress: {i}/{len(accounts)}\n"
                        f"⏳ Please wait..."
                    )
                
                # Validate session
                is_valid, status, user_info = await validator.validate_session_string(session_string)
                
                if status == 'valid':
                    valid_count += 1
                    results.append(f"✅ {account_name}")
                    
                    # Update account info if needed
                    if user_info:
                        await mongodb.db.accounts.update_one(
                            {"_id": account["_id"]},
                            {
                                "$set": {
                                    "is_active": True,
                                    "last_validated": datetime.now(),
                                    "validation_status": "valid",
                                }
                            }
                        )
                
                elif status == 'need_auth':
                    need_auth_count += 1
                    results.append(f"⚠️ {account_name}: Needs authorization")
                    
                    await mongodb.db.accounts.update_one(
                        {"_id": account["_id"]},
                        {
                            "$set": {
                                "is_active": False,
                                "last_validated": datetime.now(),
                                "validation_status": "need_auth",
                            }
                        }
                    )
                
                else:
                    invalid_count += 1
                    results.append(f"❌ {account_name}: Invalid")
                    
                    await mongodb.db.accounts.update_one(
                        {"_id": account["_id"]},
                        {
                            "$set": {
                                "is_active": False,
                                "last_validated": datetime.now(),
                                "validation_status": "invalid",
                            }
                        }
                    )
                
                await asyncio.sleep(0.5)
            
            # Show results
            summary = (
                f"📊 **Validation Complete**\n\n"
                f"✅ Valid: {valid_count}\n"
                f"⚠️ Need Authorization: {need_auth_count}\n"
                f"❌ Invalid: {invalid_count}\n"
                f"📁 Total: {len(accounts)}\n\n"
                f"**Details:**\n" + "\n".join(results[:15])
            )
            
            if len(results) > 15:
                summary += f"\n\n... and {len(results) - 15} more"
            
            buttons = [
                [Button.inline("🗑️ Remove Invalid", "cleanup_invalid")],
                [Button.inline("🔙 Back", "session_cleanup")],
            ]
            
            await event.edit(summary, buttons=buttons)
        
        except Exception as e:
            logger.error(f"Validation error: {e}")
            await event.edit(f"❌ Validation failed: {str(e)}")
    
    async def _cleanup_invalid_sessions(self, event, user_id):
        """Remove invalid sessions"""
        try:
            await event.edit("🔍 **Finding Invalid Sessions**\n\n⏳ Please wait...")
            
            # Find invalid accounts
            invalid_accounts = await mongodb.db.accounts.find({
                "user_id": user_id,
                "validation_status": "invalid"
            }).to_list(None)
            
            if not invalid_accounts:
                await event.edit(
                    "✅ **No Invalid Sessions Found**\n\n"
                    "All your sessions are valid or need authorization."
                )
                return
            
            # Show confirmation
            account_names = [acc.get('name', acc.get('phone', 'Unknown')) for acc in invalid_accounts]
            
            text = (
                f"⚠️ **Confirm Deletion**\n\n"
                f"Found {len(invalid_accounts)} invalid session(s):\n\n"
                + "\n".join([f"• {name}" for name in account_names[:10]])
            )
            
            if len(account_names) > 10:
                text += f"\n... and {len(account_names) - 10} more"
            
            text += "\n\n**This action cannot be undone!**"
            
            buttons = [
                [Button.inline("✅ Confirm Delete", "cleanup_invalid_confirm")],
                [Button.inline("❌ Cancel", "session_cleanup")],
            ]
            
            await event.edit(text, buttons=buttons)
        
        except Exception as e:
            logger.error(f"Cleanup invalid error: {e}")
            await event.edit(f"❌ Error: {str(e)}")
    
    async def _cleanup_need_auth_sessions(self, event, user_id):
        """Remove sessions needing authorization"""
        try:
            await event.edit("🔍 **Finding Unauthorized Sessions**\n\n⏳ Please wait...")
            
            # Find accounts needing auth
            need_auth_accounts = await mongodb.db.accounts.find({
                "user_id": user_id,
                "validation_status": "need_auth"
            }).to_list(None)
            
            if not need_auth_accounts:
                await event.edit(
                    "✅ **No Unauthorized Sessions Found**\n\n"
                    "All your sessions are authorized."
                )
                return
            
            # Show confirmation
            account_names = [acc.get('name', acc.get('phone', 'Unknown')) for acc in need_auth_accounts]
            
            text = (
                f"⚠️ **Confirm Deletion**\n\n"
                f"Found {len(need_auth_accounts)} unauthorized session(s):\n\n"
                + "\n".join([f"• {name}" for name in account_names[:10]])
            )
            
            if len(account_names) > 10:
                text += f"\n... and {len(account_names) - 10} more"
            
            text += "\n\n**This action cannot be undone!**"
            
            buttons = [
                [Button.inline("✅ Confirm Delete", "cleanup_need_auth_confirm")],
                [Button.inline("❌ Cancel", "session_cleanup")],
            ]
            
            await event.edit(text, buttons=buttons)
        
        except Exception as e:
            logger.error(f"Cleanup need auth error: {e}")
            await event.edit(f"❌ Error: {str(e)}")
    
    async def _show_cleanup_stats(self, event, user_id):
        """Show cleanup statistics"""
        try:
            # Get validation statistics
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            
            total = len(accounts)
            valid = sum(1 for acc in accounts if acc.get('validation_status') == 'valid')
            need_auth = sum(1 for acc in accounts if acc.get('validation_status') == 'need_auth')
            invalid = sum(1 for acc in accounts if acc.get('validation_status') == 'invalid')
            not_validated = total - valid - need_auth - invalid
            
            # Get last validation times
            validated_accounts = [acc for acc in accounts if acc.get('last_validated')]
            if validated_accounts:
                last_validation = max(acc['last_validated'] for acc in validated_accounts)
                last_validation_str = last_validation.strftime('%Y-%m-%d %H:%M:%S')
            else:
                last_validation_str = "Never"
            
            text = (
                "📊 **Cleanup Statistics**\n\n"
                f"**Session Status:**\n"
                f"✅ Valid: {valid}\n"
                f"⚠️ Need Authorization: {need_auth}\n"
                f"❌ Invalid: {invalid}\n"
                f"❓ Not Validated: {not_validated}\n"
                f"📁 Total: {total}\n\n"
                f"**Last Validation:**\n"
                f"{last_validation_str}\n\n"
                "Run validation to update statistics."
            )
            
            buttons = [
                [Button.inline("🔍 Validate Now", "cleanup_validate_all")],
                [Button.inline("🔙 Back", "session_cleanup")],
            ]
            
            await event.edit(text, buttons=buttons)
        
        except Exception as e:
            logger.error(f"Cleanup stats error: {e}")
            await event.edit(f"❌ Error: {str(e)}")
