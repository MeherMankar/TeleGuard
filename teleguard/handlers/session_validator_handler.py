"""Session Validator Handler - UI for session validation
Integrated from SessTg project
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List

from telethon import Button, events

from ..core.config import config
from ..utils.session_validator import SessionValidator

logger = logging.getLogger(__name__)


class SessionValidatorHandler:
    """Handler for session validation UI"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.validator = SessionValidator(
            config.telegram.api_id,
            config.telegram.api_hash
        )
    
    def register_handlers(self):
        """Register callback handlers"""
        
        @self.bot.on(events.CallbackQuery(pattern=b"session_validator"))
        async def show_validator_menu(event):
            user_id = event.sender_id
            
            # Get validation stats
            stats = self.validator.get_validation_stats()
            
            stats_text = ""
            if stats:
                stats_text = (
                    f"\n📊 Last Check: {stats['last_check'].strftime('%Y-%m-%d %H:%M')}\n"
                    f"✅ Valid: {stats['valid']}\n"
                    f"⚠️ Need Auth: {stats['need_auth']}\n"
                    f"❌ Invalid: {stats['invalid']}\n"
                )
            
            text = (
                "🔍 **Session Validator**\n\n"
                "Validate and manage session health.\n"
                f"{stats_text}\n"
                "Choose an action:"
            )
            
            buttons = [
                [Button.inline("🔍 Validate All Sessions", b"validator:validate_all")],
                [Button.inline("📊 Show Session Details", b"validator:show_details")],
                [Button.inline("🗑️ Cleanup Invalid", b"validator:cleanup_menu")],
                [Button.inline("🔙 Back", b"menu:main")]
            ]
            
            await event.edit(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"validator:validate_all"))
        async def validate_all(event):
            user_id = event.sender_id
            
            await event.edit("🔍 Validating all sessions...\n\nThis may take a moment.")
            
            sessions_dir = Path("sessions")
            results = await self.validator.validate_all_sessions(str(sessions_dir))
            
            if not results:
                await event.edit(
                    "❌ No sessions found in sessions directory.",
                    buttons=[[Button.inline("🔙 Back", b"session_validator")]]
                )
                return
            
            valid = sum(1 for r in results.values() if r['status'] == 'valid')
            need_auth = sum(1 for r in results.values() if r['status'] == 'need_auth')
            invalid = sum(1 for r in results.values() if r['status'] == 'invalid')
            
            text = (
                "✅ **Validation Complete**\n\n"
                f"📁 Total Sessions: {len(results)}\n"
                f"✅ Valid: {valid}\n"
                f"⚠️ Need Authorization: {need_auth}\n"
                f"❌ Invalid: {invalid}\n"
            )
            
            buttons = [
                [Button.inline("📊 View Details", b"validator:show_details")],
                [Button.inline("🗑️ Cleanup", b"validator:cleanup_menu")],
                [Button.inline("🔙 Back", b"session_validator")]
            ]
            
            await event.edit(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"validator:show_details"))
        async def show_details(event):
            user_id = event.sender_id
            
            sessions_dir = Path("sessions")
            results = await self.validator.validate_all_sessions(str(sessions_dir))
            
            if not results:
                await event.edit(
                    "❌ No sessions found.",
                    buttons=[[Button.inline("🔙 Back", b"session_validator")]]
                )
                return
            
            # Build detailed report
            text = "📊 **Session Details**\n\n"
            
            for name, info in list(results.items())[:10]:  # Limit to 10
                status_icon = {
                    'valid': '✅',
                    'need_auth': '⚠️',
                    'invalid': '❌'
                }.get(info['status'], '❓')
                
                text += f"{status_icon} **{name}**\n"
                text += f"   Size: {info['size']:.1f} KB\n"
                
                if info['status'] == 'valid' and info['user_info']:
                    ui = info['user_info']
                    text += f"   📱 +{ui['phone']}\n"
                    text += f"   👤 {ui['name']}\n"
                    if ui['username']:
                        text += f"   @{ui['username']}\n"
                
                text += "\n"
            
            if len(results) > 10:
                text += f"\n... and {len(results) - 10} more sessions"
            
            buttons = [
                [Button.inline("🔄 Refresh", b"validator:show_details")],
                [Button.inline("🔙 Back", b"session_validator")]
            ]
            
            await event.edit(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"validator:cleanup_menu"))
        async def cleanup_menu(event):
            text = (
                "🗑️ **Cleanup Options**\n\n"
                "Choose what to cleanup:\n\n"
                "⚠️ Warning: This action cannot be undone!"
            )
            
            buttons = [
                [Button.inline("🗑️ Delete Invalid Only", b"validator:cleanup:invalid")],
                [Button.inline("🗑️ Delete Need Auth", b"validator:cleanup:need_auth")],
                [Button.inline("🗑️ Delete All Non-Valid", b"validator:cleanup:all")],
                [Button.inline("🔙 Back", b"session_validator")]
            ]
            
            await event.edit(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"validator:cleanup:(.+)"))
        async def cleanup_sessions(event):
            cleanup_type = event.pattern_match.group(1).decode()
            
            await event.edit("🗑️ Cleaning up sessions...\n\nPlease wait.")
            
            sessions_dir = Path("sessions")
            
            delete_invalid = cleanup_type in ['invalid', 'all']
            delete_need_auth = cleanup_type in ['need_auth', 'all']
            
            deleted = await self.validator.cleanup_invalid_sessions(
                str(sessions_dir),
                delete_invalid=delete_invalid,
                delete_need_auth=delete_need_auth
            )
            
            text = (
                "✅ **Cleanup Complete**\n\n"
                f"🗑️ Invalid Deleted: {deleted['invalid']}\n"
                f"🗑️ Need Auth Deleted: {deleted['need_auth']}\n"
            )
            
            buttons = [
                [Button.inline("🔍 Validate Again", b"validator:validate_all")],
                [Button.inline("🔙 Back", b"session_validator")]
            ]
            
            await event.edit(text, buttons=buttons)
    
    async def cleanup(self):
        """Cleanup resources"""
        pass
