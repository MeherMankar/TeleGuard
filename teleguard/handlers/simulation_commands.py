"""Activity Simulation Commands"""

import logging
from telethon import events
from ..core.config import ADMIN_IDS

logger = logging.getLogger(__name__)


class SimulationCommands:
    """Handle activity simulation commands"""
    
    def __init__(self, bot, bot_manager):
        self.bot = bot
        self.bot_manager = bot_manager
        
    def register_handlers(self):
        """Register simulation command handlers"""
        
        @self.bot.on(events.NewMessage(pattern=r'^/sim_stats$'))
        async def sim_stats_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
                
            user_id = event.sender_id
            stats = await self.bot_manager.activity_simulator.get_simulation_stats(user_id)
            
            if "error" in stats:
                await event.reply(f"❌ Error: {stats['error']}")
                return
            
            status_text = (
                f"🎭 **Activity Simulation Stats**\n\n"
                f"📊 **Overview:**\n"
                f"• Total accounts: {stats['total_accounts']}\n"
                f"• Active simulations: {stats['active_simulations']}\n\n"
                f"📱 **Accounts:**\n"
            )
            
            for account in stats['accounts']:
                status_emoji = "🟢" if account['active'] else "🔴"
                enabled_emoji = "✅" if account['enabled'] else "❌"
                status_text += f"{status_emoji} {account['name']} (Enabled: {enabled_emoji})\n"
            
            await event.reply(status_text)
        
        @self.bot.on(events.NewMessage(pattern=r'^/sim_help$'))
        async def sim_help_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
                
            help_text = (
                "🎭 **Activity Simulation Help**\n\n"
                "**Commands:**\n"
                "• `/sim_stats` - View simulation statistics\n"
                "• `/sim_help` - Show this help\n\n"
                "**Enhanced Features:**\n"
                "• 📖 Realistic scrolling and reading\n"
                "• ⌨️ Typing indicators (without sending)\n"
                "• 👀 Profile browsing with natural timing\n"
                "• 👍 Smart reactions to posts\n"
                "• 🗳️ Poll voting simulation\n"
                "• 💬 Rare message sending (very conservative)\n"
                "• ⏰ Human-like timing patterns\n\n"
                "**Timing:**\n"
                "• Sessions: 30min - 4hrs apart\n"
                "• Actions: 1-7 per session\n"
                "• Delays: 10-120 seconds between actions\n\n"
                "**Safety:**\n"
                "• All activities logged and auditable\n"
                "• Conservative message sending (1% chance)\n"
                "• Respects rate limits\n"
                "• Natural human-like patterns"
            )
            
            await event.reply(help_text)