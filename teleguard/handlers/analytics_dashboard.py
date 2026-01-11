"""Analytics dashboard handler"""

import logging

from telethon import Button, events

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class AnalyticsDashboard:
    def __init__(self, bot_manager):
        self.bot = bot_manager.bot
        self.bot_manager = bot_manager

    def register_handlers(self):
        """Register analytics handlers"""
        self.bot.add_event_handler(
            self._show_analytics, events.CallbackQuery(pattern=r"^analytics$")
        )
        self.bot.add_event_handler(
            self._show_account_stats,
            events.CallbackQuery(pattern=r"^analytics_account:(.+)$"),
        )
        logger.info("Analytics dashboard handlers registered")

    async def _show_analytics(self, event):
        """Show analytics dashboard"""
        user_id = event.sender_id

        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )

            active_accounts = len([a for a in accounts if a.get("is_active")])

            activity_logs = await mongodb.db.activity_logs.count_documents(
                {"user_id": user_id}
            )

            security_events = await mongodb.db.security_events.count_documents(
                {"user_id": user_id}
            )

            buttons = []
            for acc in accounts[:10]:
                name = acc.get("name", acc.get("phone", "Unknown"))
                buttons.append(
                    [Button.inline(f"📊 {name}", f"analytics_account:{name}")]
                )

            buttons.append([Button.inline("🔙 Back", "menu:main")])

            await event.edit(
                f"📊 **Analytics Dashboard**\n\n"
                f"**Overview:**\n"
                f"• Total Accounts: {len(accounts)}\n"
                f"• Active Accounts: {active_accounts}\n"
                f"• Activity Logs: {activity_logs}\n"
                f"• Security Events: {security_events}\n\n"
                f"Select account for details:",
                buttons=buttons,
            )
        except Exception as e:
            logger.error(f"Analytics error: {e}")
            await event.answer("❌ Error loading analytics", alert=True)

    async def _show_account_stats(self, event):
        """Show account statistics"""
        user_id = event.sender_id
        account_name = event.pattern_match.group(1).decode()

        try:
            account = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "name": account_name}
            )

            if not account:
                await event.answer("❌ Account not found", alert=True)
                return

            logs = await mongodb.db.activity_logs.count_documents(
                {"user_id": user_id, "details.account": account_name}
            )

            text = (
                f"📊 **Account Stats - {account_name}**\n\n"
                f"**Details:**\n"
                f"• Phone: {account.get('phone', 'N/A')}\n"
                f"• Status: {
                    '✅ Active' if account.get('is_active') else '❌ Inactive'}\n"
                f"• Activity Logs: {logs}\n"
                f"• OTP Destroyer: {
                    '✅ Enabled' if account.get('otp_destroyer_enabled') else '❌ Disabled'}\n"
            )

            buttons = [[Button.inline("🔙 Back", "analytics")]]
            await event.edit(text, buttons=buttons)
        except Exception as e:
            logger.error(f"Account stats error: {e}")
            await event.answer("❌ Error loading stats", alert=True)
