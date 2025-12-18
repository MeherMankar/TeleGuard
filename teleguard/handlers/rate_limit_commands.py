"""
Rate Limit and Health Monitoring Commands
"""
import logging
from telethon import events
from ..core.rate_limiter import rate_limiter
from ..core.session_health import session_health
from ..core.mongo_database import mongodb
from ..core.config import ADMIN_IDS

logger = logging.getLogger(__name__)

class RateLimitCommands:
    """Handle rate limit and health monitoring commands"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
    
    def register_handlers(self):
        """Register command handlers"""
        
        @self.bot.on(events.NewMessage(pattern=r'^/limits$'))
        async def limits_command(event):
            """Show rate limits for all accounts"""
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
            
            try:
                user_id = event.sender_id
                accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
                
                if not accounts:
                    await event.reply("❌ No accounts found")
                    return
                
                response = "📊 **Rate Limits Status**\n\n"
                
                for account in accounts:
                    phone = account.get('phone', 'Unknown')
                    name = account.get('name', phone)
                    stats = rate_limiter.get_stats(phone)
                    
                    response += f"**{name}** ({phone})\n"
                    
                    for operation, data in stats.items():
                        count = data['count']
                        limit = data['limit']
                        remaining = data['remaining']
                        cooldown = data['cooldown_remaining']
                        
                        # Progress bar
                        pct = int((count / limit) * 10) if limit > 0 else 0
                        bar = '■' * pct + '░' * (10 - pct)
                        
                        status = "🟢" if remaining > limit * 0.5 else "🟡" if remaining > 0 else "🔴"
                        
                        response += f"  {status} {operation}: {count}/{limit} {bar}\n"
                        
                        if cooldown > 0:
                            mins = cooldown // 60
                            secs = cooldown % 60
                            response += f"     ⏳ Cooldown: {mins}m {secs}s\n"
                    
                    response += "\n"
                
                await event.reply(response)
                
            except Exception as e:
                logger.error(f"Limits command error: {e}")
                await event.reply(f"❌ Error: {str(e)}")
        
        @self.bot.on(events.NewMessage(pattern=r'^/health$'))
        async def health_command(event):
            """Check session health for all accounts"""
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
            
            try:
                user_id = event.sender_id
                user_clients = self.user_clients.get(user_id, {})
                
                if not user_clients:
                    await event.reply("❌ No active accounts found")
                    return
                
                response = "🏥 **Session Health Status**\n\n"
                
                for account_name, client in user_clients.items():
                    # Get account phone
                    account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
                    phone = account.get('phone') if account else account_name
                    
                    # Check health
                    is_healthy, health_msg = await session_health.check_session(client, phone)
                    status = session_health.get_status(phone)
                    
                    # Status emoji
                    if status['status'] == 'healthy':
                        emoji = "✅"
                    elif status['status'] == 'warning':
                        emoji = "⚠️"
                    else:
                        emoji = "❌"
                    
                    response += f"{emoji} **{account_name}**\n"
                    response += f"   Status: {status['status']}\n"
                    response += f"   Errors: {status['errors']}\n"
                    
                    if status['warnings']:
                        response += f"   Last warning: {status['warnings'][-1]}\n"
                    
                    response += "\n"
                
                # Show unhealthy accounts
                unhealthy = session_health.get_all_unhealthy()
                if unhealthy:
                    response += "\n⚠️ **Unhealthy Accounts:**\n"
                    for acc in unhealthy:
                        response += f"• {acc['phone']}: {acc['status']} ({acc['errors']} errors)\n"
                
                await event.reply(response)
                
            except Exception as e:
                logger.error(f"Health command error: {e}")
                await event.reply(f"❌ Error: {str(e)}")
        
        @self.bot.on(events.NewMessage(pattern=r'^/reset_limits\s+(.+)$'))
        async def reset_limits_command(event):
            """Reset rate limits for an account"""
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
            
            try:
                account_name = event.pattern_match.group(1).strip()
                user_id = event.sender_id
                
                # Find account
                account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
                if not account:
                    await event.reply(f"❌ Account `{account_name}` not found")
                    return
                
                phone = account.get('phone')
                rate_limiter.reset_account(phone)
                session_health.reset_account(phone)
                
                await event.reply(f"✅ Reset limits and health status for `{account_name}`")
                
            except Exception as e:
                logger.error(f"Reset limits command error: {e}")
                await event.reply(f"❌ Error: {str(e)}")
