"""Simulation Command Handlers
Handles /simulate commands for Human-like Activity Simulator
Integrated with comprehensive audit logging for transparency.
Developed by:
- @Meher_Mankar
- @Gutkesh
"""
import logging
from telethon import Button, events
from ..core.mongo_database import mongodb
from .audit_handler import AuditHandler
logger = logging.getLogger(__name__)
class SimulationHandlers:
    """Handles simulation-related commands"""
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.activity_simulator = getattr(bot_manager, "activity_simulator", None)
        self.audit_handler = AuditHandler(bot_manager)
    def register_handlers(self):
        """Register simulation command handlers"""
        self.register_callback_handlers()
        @self.bot.on(
            events.NewMessage(pattern=r"/simulate\s+(start|stop|status)(?:\s+(.+))?")
        )
        async def simulate_handler(event):
            user_id = event.sender_id
            command = event.pattern_match.group(1).lower()
            account_name = event.pattern_match.group(2)
            user = await mongodb.get_user(user_id)
            if not user:
                await event.reply("Please start the bot first with /start")
                return
            if command == "start":
                await self._handle_start_simulation(event, user_id, account_name)
            elif command == "stop":
                await self._handle_stop_simulation(event, user_id, account_name)
            elif command == "status":
                await self._handle_simulation_status(event, user_id, account_name)
        @self.bot.on(events.NewMessage(pattern=r"/simulate$"))
        async def simulate_help_handler(event):
            help_text = """
🎭 **Human-like Activity Simulator**
**Commands:**
• `/simulate start [account_name]` - Start simulation
• `/simulate stop [account_name]` - Stop simulation
• `/simulate status [account_name]` - Check status
• `/simulate audit [account_name]` - View audit log
**Examples:**
• `/simulate start MyAccount` - Start for specific account
• `/simulate start` - Start for all accounts
• `/simulate audit MyAccount` - View activity log
**What it does:**
• Randomly views channels/groups
• Reacts to posts with emojis
• Votes in polls occasionally
• Browses user profiles
• Rarely joins/leaves public channels
• Occasionally sends messages/comments
**Transparency:**
• All actions are logged and auditable
• Complete activity history available
• Real-time activity monitoring
• Detailed statistics and summaries
**Safety:**
• Randomized timing (30-90 min intervals)
• Natural delays between actions
• Respects rate limits
• No suspicious patterns
            """
            await event.reply(help_text)
        @self.bot.on(events.NewMessage(pattern=r"/simulate\s+audit(?:\s+(.+))?"))
        async def simulate_audit_handler(event):
            user_id = event.sender_id
            account_name = event.pattern_match.group(1)
            user = await mongodb.get_user(user_id)
            if not user:
                await event.reply("Please start the bot first with /start")
                return
            await self._handle_audit_log(event, user_id, account_name)
    async def _handle_start_simulation(
        self, event, user_id: int, account_name: str = None
    ):
        """Handle start simulation command"""
        try:
            if not self.activity_simulator:
                await event.reply("❌ Activity Simulator not available")
                return
            if account_name:
                account = await self._get_account_by_name(user_id, account_name)
                if not account:
                    await event.reply(f"❌ Account '{account_name}' not found")
                    return
                success, message = await self.activity_simulator.enable_simulation(
                    user_id, str(account["_id"])
                )
                if success:
                    await event.reply(f"🎭 Simulation started for {account_name}")
                else:
                    await event.reply(f"❌ Failed to start simulation: {message}")
            else:
                accounts = await self._get_user_accounts(user_id)
                if not accounts:
                    await event.reply("❌ No accounts found")
                    return
                started_count = 0
                for account in accounts:
                    success, _ = await self.activity_simulator.enable_simulation(
                        user_id, str(account["_id"])
                    )
                    if success:
                        started_count += 1
                await event.reply(
                    f"🎭 Simulation started for {started_count}/{len(accounts)} accounts"
                )
        except Exception as e:
            logger.error(f"Start simulation error: {e}")
            await event.reply(f"❌ Error: {str(e)}")
    async def _handle_stop_simulation(
        self, event, user_id: int, account_name: str = None
    ):
        """Handle stop simulation command"""
        try:
            if not self.activity_simulator:
                await event.reply("❌ Activity Simulator not available")
                return
            if account_name:
                account = await self._get_account_by_name(user_id, account_name)
                if not account:
                    await event.reply(f"❌ Account '{account_name}' not found")
                    return
                success, message = await self.activity_simulator.disable_simulation(
                    user_id, str(account["_id"])
                )
                if success:
                    await event.reply(f"🛑 Simulation stopped for {account_name}")
                else:
                    await event.reply(f"❌ Failed to stop simulation: {message}")
            else:
                accounts = await self._get_user_accounts(user_id)
                if not accounts:
                    await event.reply("❌ No accounts found")
                    return
                stopped_count = 0
                for account in accounts:
                    success, _ = await self.activity_simulator.disable_simulation(
                        user_id, str(account["_id"])
                    )
                    if success:
                        stopped_count += 1
                await event.reply(
                    f"🛑 Simulation stopped for {stopped_count}/{len(accounts)} accounts"
                )
        except Exception as e:
            logger.error(f"Stop simulation error: {e}")
            await event.reply(f"❌ Error: {str(e)}")
    async def _handle_simulation_status(
        self, event, user_id: int, account_name: str = None
    ):
        """Handle simulation status command"""
        try:
            if account_name:
                # Status for specific account
                account = await self._get_account_by_name(user_id, account_name)
                if not account:
                    await event.reply(f"❌ Account '{account_name}' not found")
                    return
                status = "🟢 Active" if account.get("simulation_enabled", False) else "🔴 Inactive"
                status_text = f"🎭 **Simulation Status for {account_name}:**\n\n"
                status_text += f"Status: {status}\n\n"
                if account.get("simulation_enabled", False):
                    status_text += "**Available Actions:**\n"
                    status_text += "• View comprehensive audit log\n"
                    status_text += "• Check activity statistics\n"
                    status_text += "• Monitor real-time activities\n"
                buttons = [
                    [
                        Button.inline(
                            "📋 View Audit Log", f"audit:refresh:{account['_id']}:24"
                        )
                    ],
                    [
                        Button.inline(
                            "📊 Activity Summary", f"audit:summary:{account['_id']}"
                        )
                    ],
                    [Button.inline("📈 Statistics", f"audit:stats:{account['_id']}")],
                ]
                sent_message = await event.reply(status_text, buttons=buttons)
            else:
                # Status for all accounts
                accounts = await self._get_user_accounts(user_id)
                if not accounts:
                    await event.reply("❌ No accounts found")
                    return
                status_text = "🎭 **Simulation Status:**\n\n"
                active_count = 0
                for account in accounts:
                    status = "🟢" if account.get("simulation_enabled", False) else "🔴"
                    status_text += f"{status} {account['name']}\n"
                    if account.get("simulation_enabled", False):
                        active_count += 1
                status_text += (
                    f"\n**Summary:** {active_count}/{len(accounts)} accounts active\n\n"
                )
                status_text += (
                    "Use `/simulate audit [account_name]` to view detailed logs."
                )
                await event.reply(status_text)
        except Exception as e:
            logger.error(f"Simulation status error: {e}")
            await event.reply(f"❌ Error: {str(e)}")
    async def _get_account_by_name(self, user_id: int, account_name: str):
        """Get account by name for user"""
        try:
            account = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "name": account_name}
            )
            return account
        except Exception as e:
            logger.error(f"Get account by name error: {e}")
            return None
    async def _get_user_accounts(self, user_id: int):
        """Get all accounts for user"""
        try:
            accounts = await mongodb.db.accounts.find(
                {"user_id": user_id, "is_active": True}
            ).to_list(length=None)
            return accounts
        except Exception as e:
            logger.error(f"Get user accounts error: {e}")
            return []
    async def _handle_audit_log(self, event, user_id: int, account_name: str = None):
        """Handle audit log command"""
        try:
            if account_name:
                # Show audit for specific account
                account = await self._get_account_by_name(user_id, account_name)
                if not account:
                    await event.reply(f"❌ Account '{account_name}' not found")
                    return
                # Send initial message and then show audit log
                sent_message = await event.reply(
                    f"📋 Loading audit log for {account_name}..."
                )
                await self.audit_handler.show_comprehensive_audit_log(
                    self.bot, user_id, str(account["_id"]), sent_message.id
                )
            else:
                # Show list of accounts to choose from
                accounts = await self._get_user_accounts(user_id)
                if not accounts:
                    await event.reply("❌ No accounts found")
                    return
                text = "📋 **Select Account for Audit Log:**\n\n"
                buttons = []
                for account in accounts:
                    status = "🟢" if account.get("simulation_enabled", False) else "🔴"
                    text += f"{status} {account['name']}\n"
                    buttons.append(
                        [
                            Button.inline(
                                f"📋 {account['name']}", f"audit:refresh:{account['_id']}:24"
                            )
                        ]
                    )
                await event.reply(text, buttons=buttons)
        except Exception as e:
            logger.error(f"Audit log error: {e}")
            await event.reply(f"❌ Error: {str(e)}")
    def register_callback_handlers(self):
        """Register callback handlers for audit buttons"""
        @self.bot.on(events.CallbackQuery(pattern=r"audit:refresh:(\d+):(\d+)"))
        async def audit_refresh_callback(event):
            account_id = int(event.pattern_match.group(1))
            hours = int(event.pattern_match.group(2))
            user_id = event.sender_id
            await self.audit_handler.show_comprehensive_audit_log(
                self.bot, user_id, account_id, event.message_id, hours
            )
            await event.answer()
        @self.bot.on(events.CallbackQuery(pattern=r"audit:summary:(\d+)"))
        async def audit_summary_callback(event):
            account_id = int(event.pattern_match.group(1))
            user_id = event.sender_id
            await self.audit_handler.show_activity_summary(
                self.bot, user_id, account_id, event.message_id
            )
            await event.answer()
        @self.bot.on(events.CallbackQuery(pattern=r"audit:stats:(\d+)"))
        async def audit_stats_callback(event):
            account_id = int(event.pattern_match.group(1))
            user_id = event.sender_id
            await self.audit_handler.show_activity_stats(
                self.bot, user_id, account_id, event.message_id
            )
            await event.answer()
