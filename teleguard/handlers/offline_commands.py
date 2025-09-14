"""Offline commands - Force accounts offline"""

import logging
from telethon import events
from ..core.config import ADMIN_IDS

logger = logging.getLogger(__name__)


class OfflineCommands:
    """Handle offline-related commands"""
    
    def __init__(self, bot, bot_manager):
        self.bot = bot
        self.bot_manager = bot_manager
        
    def register_handlers(self):
        """Register offline command handlers"""
        
        @self.bot.on(events.NewMessage(pattern=r'^/force_offline$'))
        async def force_offline_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
                
            user_id = event.sender_id
            count = await self.bot_manager.online_maker.force_offline_all(user_id)
            
            if count > 0:
                await event.reply(f"✅ Forced {count} accounts offline")
            else:
                await event.reply("❌ No accounts to force offline")
        
        @self.bot.on(events.NewMessage(pattern=r'^/force_offline\s+(\S+)$'))
        async def force_offline_account_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
                
            user_id = event.sender_id
            account_name = event.pattern_match.group(1)
            
            success = await self.bot_manager.online_maker.force_offline(user_id, account_name)
            
            if success:
                await event.reply(f"✅ Forced {account_name} offline")
            else:
                await event.reply(f"❌ Failed to force {account_name} offline")