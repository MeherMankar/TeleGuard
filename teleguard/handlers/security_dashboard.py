"""Security dashboard handler"""
import logging
from telethon import events, Button
from ..utils.security_monitor import security_monitor
from ..utils.activity_logger import activity_logger

logger = logging.getLogger(__name__)


class SecurityDashboard:
    def __init__(self, bot_manager):
        self.bot = bot_manager.bot
        self.bot_manager = bot_manager
    
    def register_handlers(self):
        """Register security dashboard handlers"""
        self.bot.add_event_handler(
            self._show_security_dashboard,
            events.CallbackQuery(pattern=r"^security_dashboard$")
        )
        self.bot.add_event_handler(
            self._show_activity_log,
            events.CallbackQuery(pattern=r"^security_activity$")
        )
        self.bot.add_event_handler(
            self._show_security_report,
            events.CallbackQuery(pattern=r"^security_report$")
        )
    
    async def _show_security_dashboard(self, event):
        """Show security dashboard"""
        user_id = event.sender_id
        
        try:
            report = await security_monitor.get_security_report(user_id)
            
            buttons = [
                [Button.inline("📊 Security Report", "security_report")],
                [Button.inline("📝 Activity Log", "security_activity")],
                [Button.inline("🔔 Security Alerts", "security_alerts")],
                [Button.inline("🔙 Back", "menu:main")]
            ]
            
            await event.edit(
                f"🛡️ **Security Dashboard**\n\n"
                f"📊 **Overview:**\n"
                f"• Total Events: {report['total_events']}\n"
                f"• Failed Logins: {report['failed_logins']}\n"
                f"• Suspicious Activities: {report['suspicious_activities']}\n\n"
                f"Select an option:",
                buttons=buttons
            )
        except Exception as e:
            logger.error(f"Security dashboard error: {e}")
            await event.answer("❌ Error loading dashboard", alert=True)
    
    async def _show_activity_log(self, event):
        """Show activity log"""
        user_id = event.sender_id
        
        try:
            activities = await activity_logger.get_user_activity(user_id, limit=10)
            
            if not activities:
                text = "📝 **Activity Log**\n\nNo recent activities."
            else:
                text = "📝 **Activity Log**\n\n"
                for act in activities[:10]:
                    timestamp = act['timestamp'].strftime("%Y-%m-%d %H:%M")
                    text += f"• {timestamp} - {act['action']}\n"
            
            buttons = [[Button.inline("🔙 Back", "security_dashboard")]]
            await event.edit(text, buttons=buttons)
        except Exception as e:
            logger.error(f"Activity log error: {e}")
            await event.answer("❌ Error loading log", alert=True)
    
    async def _show_security_report(self, event):
        """Show detailed security report"""
        user_id = event.sender_id
        
        try:
            report = await security_monitor.get_security_report(user_id)
            
            text = (
                f"📊 **Security Report**\n\n"
                f"**Statistics:**\n"
                f"• Total Events: {report['total_events']}\n"
                f"• Failed Logins: {report['failed_logins']}\n"
                f"• Suspicious Activities: {report['suspicious_activities']}\n\n"
                f"**Recent Events:**\n"
            )
            
            for event_data in report['recent_events'][:5]:
                timestamp = event_data['timestamp'].strftime("%Y-%m-%d %H:%M")
                text += f"• {timestamp} - {event_data['event_type']} ({event_data['severity']})\n"
            
            buttons = [[Button.inline("🔙 Back", "security_dashboard")]]
            await event.edit(text, buttons=buttons)
        except Exception as e:
            logger.error(f"Security report error: {e}")
            await event.answer("❌ Error loading report", alert=True)
