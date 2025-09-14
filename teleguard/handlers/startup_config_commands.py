"""Startup Configuration Commands"""

import logging
from telethon import events
from ..core.config import ADMIN_IDS

logger = logging.getLogger(__name__)


class StartupConfigCommands:
    """Handle startup configuration commands"""
    
    def __init__(self, bot, bot_manager):
        self.bot = bot
        self.bot_manager = bot_manager
        
    def register_handlers(self):
        """Register startup configuration command handlers"""
        
        @self.bot.on(events.NewMessage(pattern=r'^/startup_config$'))
        async def startup_config_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
                
            config_text = (
                "🚀 **Startup Configuration**\n\n"
                "Configure which features to auto-enable when bot starts:\n\n"
                "**Commands:**\n"
                "• `/auto_online on/off` - Auto-enable online maker\n"
                "• `/auto_sim on/off` - Auto-enable activity simulator\n"
                "• `/startup_status` - View current settings\n\n"
                "**Current Features:**\n"
                "• Automatic startup notifications\n"
                "• System status summary\n"
                "• Feature auto-enabling\n"
                "• Account statistics"
            )
            
            await event.reply(config_text)
        
        @self.bot.on(events.NewMessage(pattern=r'^/auto_online\s+(on|off)$'))
        async def auto_online_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
                
            user_id = event.sender_id
            enabled = event.pattern_match.group(1) == "on"
            
            success = await self.bot_manager.startup_commands.set_auto_startup_feature(
                user_id, "online_maker", enabled
            )
            
            if success:
                status = "enabled" if enabled else "disabled"
                await event.reply(f"✅ Auto online maker {status} for startup")
            else:
                await event.reply("❌ Failed to update setting")
        
        @self.bot.on(events.NewMessage(pattern=r'^/auto_sim\s+(on|off)$'))
        async def auto_sim_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
                
            user_id = event.sender_id
            enabled = event.pattern_match.group(1) == "on"
            
            success = await self.bot_manager.startup_commands.set_auto_startup_feature(
                user_id, "activity_simulator", enabled
            )
            
            if success:
                status = "enabled" if enabled else "disabled"
                await event.reply(f"✅ Auto activity simulator {status} for startup")
            else:
                await event.reply("❌ Failed to update setting")
        
        @self.bot.on(events.NewMessage(pattern=r'^/startup_status$'))
        async def startup_status_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
                
            try:
                from ..core.mongo_database import mongodb
                
                user_id = event.sender_id
                user = await mongodb.db.users.find_one({"telegram_id": user_id})
                
                auto_features = user.get("auto_startup_features", {}) if user else {}
                
                online_maker_status = "✅ Enabled" if auto_features.get("online_maker", False) else "❌ Disabled"
                activity_sim_status = "✅ Enabled" if auto_features.get("activity_simulator", False) else "❌ Disabled"
                
                status_text = (
                    f"🚀 **Startup Configuration Status**\n\n"
                    f"**Auto-Enable Features:**\n"
                    f"• Online Maker: {online_maker_status}\n"
                    f"• Activity Simulator: {activity_sim_status}\n\n"
                    f"**Always Active:**\n"
                    f"• ✅ Startup notifications\n"
                    f"• ✅ Status summaries\n"
                    f"• ✅ Account statistics\n"
                    f"• ✅ System health checks"
                )
                
                await event.reply(status_text)
                
            except Exception as e:
                await event.reply(f"❌ Error getting status: {str(e)}")