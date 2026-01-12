"""
Rate Limit and Health Monitoring Commands
"""

import logging

from telethon import events

from ..core.config import ADMIN_IDS
from ..core.mongo_database import mongodb
from ..core.rate_limiter import rate_limiter
from ..core.session_health import session_health

logger = logging.getLogger(__name__)


class RateLimitCommands:
    """Handle rate limit and health monitoring commands"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients

    def register_handlers(self):
        """Register command handlers"""
        self.bot.on(events.NewMessage(pattern=r"^/limits$"))(self._limits_command)
        self.bot.on(events.NewMessage(pattern=r"^/health$"))(self._health_command)
        self.bot.on(events.NewMessage(pattern=r"^/reset_limits\s+(.+)$"))(self._reset_limits_command)

    async def _limits_command(self, event):
        """Show rate limits for all accounts"""
        if not event.is_private or event.sender_id not in ADMIN_IDS:
            return
        try:
            accounts = await mongodb.db.accounts.find({"user_id": event.sender_id}).to_list(length=None)
            if not accounts:
                await event.reply("❌ No accounts found")
                return
            response = self._build_limits_response(accounts)
            await event.reply(response)
        except Exception as e:
            logger.error(f"Limits command error: {e}")
            await event.reply(f"❌ Error: {str(e)}")

    async def _health_command(self, event):
        """Check session health for all accounts"""
        if not event.is_private or event.sender_id not in ADMIN_IDS:
            return
        try:
            user_clients = self.user_clients.get(event.sender_id, {})
            if not user_clients:
                await event.reply("❌ No active accounts found")
                return
            response = await self._build_health_response(event.sender_id, user_clients)
            await event.reply(response)
        except Exception as e:
            logger.error(f"Health command error: {e}")
            await event.reply(f"❌ Error: {str(e)}")

    async def _reset_limits_command(self, event):
        """Reset rate limits for an account"""
        if not event.is_private or event.sender_id not in ADMIN_IDS:
            return
        try:
            account_name = event.pattern_match.group(1).strip()
            account = await mongodb.db.accounts.find_one({"user_id": event.sender_id, "name": account_name})
            if not account:
                await event.reply(f"❌ Account `{account_name}` not found")
                return
            phone = account.get("phone")
            rate_limiter.reset_account(phone)
            session_health.reset_account(phone)
            await event.reply(f"✅ Reset limits and health status for `{account_name}`")
        except Exception as e:
            logger.error(f"Reset limits command error: {e}")
            await event.reply(f"❌ Error: {str(e)}")

    def _build_limits_response(self, accounts):
        """Build rate limits response text"""
        response = "📊 **Rate Limits Status**\n\n"
        for account in accounts:
            phone = account.get("phone", "Unknown")
            name = account.get("name", phone)
            stats = rate_limiter.get_stats(phone)
            response += f"**{name}** ({phone})\n"
            for operation, data in stats.items():
                count = data["count"]
                limit = data["limit"]
                remaining = data["remaining"]
                cooldown = data["cooldown_remaining"]
                pct = int((count / limit) * 10) if limit > 0 else 0
                bar = "■" * pct + "░" * (10 - pct)
                status = "🟢" if remaining > limit * 0.5 else "🟡" if remaining > 0 else "🔴"
                response += f"  {status} {operation}: {count}/{limit} {bar}\n"
                if cooldown > 0:
                    mins = cooldown // 60
                    secs = cooldown % 60
                    response += f"     ⏳ Cooldown: {mins}m {secs}s\n"
            response += "\n"
        return response

    async def _build_health_response(self, user_id, user_clients):
        """Build health status response text"""
        response = "🏥 **Session Health Status**\n\n"
        for account_name, client in user_clients.items():
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            phone = account.get("phone") if account else account_name
            is_healthy, health_msg = await session_health.check_session(client, phone)
            status = session_health.get_status(phone)
            emoji = "✅" if status["status"] == "healthy" else "⚠️" if status["status"] == "warning" else "❌"
            response += f"{emoji} **{account_name}**\n"
            response += f"   Status: {status['status']}\n"
            response += f"   Errors: {status['errors']}\n"
            if status["warnings"]:
                response += f"   Last warning: {status['warnings'][-1]}\n"
            response += "\n"
        unhealthy = session_health.get_all_unhealthy()
        if unhealthy:
            response += "\n⚠️ **Unhealthy Accounts:**\n"
            for acc in unhealthy:
                response += f"• {acc['phone']}: {acc['status']} ({acc['errors']} errors)\n"
        return response
