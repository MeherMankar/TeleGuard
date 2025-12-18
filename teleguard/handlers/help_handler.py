"""
Enhanced Help Handler with Auto-Generated Command List
"""
import logging
from telethon import events, Button
from ..core.config import ADMIN_IDS
from ..utils.command_registry import command_registry

logger = logging.getLogger(__name__)

class HelpHandler:
    """Enhanced help system with automatic command discovery"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
    
    def register_handlers(self):
        """Register help command handlers"""
        
        @self.bot.on(events.NewMessage(pattern=r'^/help$'))
        async def help_command(event):
            """Show comprehensive help"""
            user_id = event.sender_id
            is_admin = user_id in ADMIN_IDS
            
            help_text = self._generate_help_text(is_admin)
            
            buttons = [
                [Button.inline("📱 Account Commands", b"help_accounts")],
                [Button.inline("🛡️ Security Commands", b"help_security")],
                [Button.inline("💬 Messaging Commands", b"help_messaging")],
                [Button.inline("📊 Monitoring Commands", b"help_monitoring")],
                [Button.inline("🤖 Automation Commands", b"help_automation")],
            ]
            
            if is_admin:
                buttons.append([Button.inline("👨‍💼 Admin Commands", b"help_admin")])
            
            buttons.append([Button.inline("❌ Close", b"help_close")])
            
            await event.reply(help_text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"help_(.+)"))
        async def help_category_callback(event):
            """Handle help category selection"""
            category = event.data.decode().split('_', 1)[1]
            
            if category == "close":
                await event.delete()
                return
            
            await event.answer()
            
            help_text = self._get_category_help(category)
            
            buttons = [
                [Button.inline("⬅️ Back to Help", b"help_main")],
                [Button.inline("❌ Close", b"help_close")]
            ]
            
            await event.edit(help_text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"help_main"))
        async def help_main_callback(event):
            """Return to main help"""
            await event.answer()
            user_id = event.sender_id
            is_admin = user_id in ADMIN_IDS
            
            help_text = self._generate_help_text(is_admin)
            
            buttons = [
                [Button.inline("📱 Account Commands", b"help_accounts")],
                [Button.inline("🛡️ Security Commands", b"help_security")],
                [Button.inline("💬 Messaging Commands", b"help_messaging")],
                [Button.inline("📊 Monitoring Commands", b"help_monitoring")],
                [Button.inline("🤖 Automation Commands", b"help_automation")],
            ]
            
            if is_admin:
                buttons.append([Button.inline("👨‍💼 Admin Commands", b"help_admin")])
            
            buttons.append([Button.inline("❌ Close", b"help_close")])
            
            await event.edit(help_text, buttons=buttons)
    
    def _generate_help_text(self, is_admin: bool = False) -> str:
        """Generate main help text"""
        text = (
            "🤖 **TeleGuard Help Center**\n\n"
            "Welcome to TeleGuard! Here's what you can do:\n\n"
            "**Quick Start:**\n"
            "• /start - Open main menu\n"
            "• /add - Add your first account\n"
            "• /otp - Enable OTP protection\n\n"
            "**Select a category below for detailed commands:**"
        )
        return text
    
    def _get_category_help(self, category: str) -> str:
        """Get help for specific category"""
        
        categories = {
            "accounts": {
                "title": "📱 Account Management",
                "commands": {
                    'add': 'Add a new Telegram account',
                    'accs': 'List all your accounts',
                    'remove': 'Remove an account',
                    'switch': 'Switch between accounts',
                    'export_session': 'Export session string',
                    'import_session': 'Import session string',
                }
            },
            "security": {
                "title": "🛡️ Security & Protection",
                "commands": {
                    'otp': 'Toggle OTP Destroyer protection',
                    'twofa': 'Manage 2FA passwords',
                    'set_2fa': 'Set 2FA password for account',
                    'get_2fa': 'Get stored 2FA password',
                    'sessions': 'View active sessions',
                    'session_health': 'Check session health',
                }
            },
            "messaging": {
                "title": "💬 Messaging Tools",
                "commands": {
                    'dm': 'Manage direct messages',
                    'reply': 'Set up auto-reply',
                    'bulk_send': 'Send bulk messages',
                    'bulk_send_list': 'Send to list of users',
                    'bulk_send_contacts': 'Send to all contacts',
                    'bulk_jobs': 'View active bulk jobs',
                }
            },
            "monitoring": {
                "title": "📊 Monitoring & Limits",
                "commands": {
                    'limits': 'View rate limits for accounts',
                    'health': 'Check session health status',
                    'reset_limits': 'Reset rate limits',
                    'session_health': 'Detailed session health',
                }
            },
            "automation": {
                "title": "🤖 Automation Tools",
                "commands": {
                    'online': 'Keep accounts online',
                    'simulate': 'Simulate human activity',
                    'appeal': 'Appeal spam restriction',
                    'cleanup': 'Clean up chats',
                }
            },
            "admin": {
                "title": "👨‍💼 Admin Commands",
                "commands": {
                    'stats': 'Bot statistics',
                    'broadcast': 'Broadcast message',
                    'users': 'List all users',
                    'cleanup_accounts': 'Remove inactive accounts',
                    'otp_debug': 'Debug OTP system',
                    'auto_reply_debug': 'Debug auto-reply',
                }
            }
        }
        
        if category not in categories:
            return "❌ Category not found"
        
        cat_data = categories[category]
        text = f"**{cat_data['title']}**\n\n"
        
        for cmd, desc in cat_data['commands'].items():
            text += f"/{cmd}\n  └ {desc}\n\n"
        
        text += "\n💡 **Tip:** Type any command to use it!"
        
        return text
