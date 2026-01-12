"""
Automatic Command Registry
Discovers and registers all bot commands automatically
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class CommandRegistry:
    """Registry for all bot commands"""

    # Command definitions with descriptions
    COMMANDS = {
        # Basic Commands
        "start": "Start the bot and show main menu",
        "help": "Show help and available commands",
        # Account Management
        "add": "Add a new Telegram account",
        "accs": "List all your accounts",
        "remove": "Remove an account",
        # OTP & Security
        "otp": "Toggle OTP Destroyer protection",
        "otp_debug": "Debug OTP functionality (admin)",
        # Proxy Management
        "proxy": "Manage proxies for accounts",
        # Session Management
        "sessions": "View active sessions",
        "export_session": "Export session string",
        "import_session": "Import session string",
        # Messaging
        "dm": "Manage direct messages",
        "reply": "Set up auto-reply",
        # Spam & Appeals
        "appeal": "Appeal spam restriction",
        "spam": "Advanced spam tools",
        # Rate Limiting & Health
        "limits": "View rate limits for accounts",
        "health": "Check session health",
        "reset_limits": "Reset rate limits for account",
        # Transfer & Sharing
        "transfer": "Transfer account ownership",
        "coowners": "Manage co-owners",
        # Admin Commands
        "stats": "Bot statistics (admin)",
        "broadcast": "Broadcast message (admin)",
        "users": "List all users (admin)",
        "logs": "View bot logs (admin)",
    }

    @classmethod
    def get_all_commands(cls) -> Dict[str, str]:
        """Get all registered commands"""
        return cls.COMMANDS.copy()

    @classmethod
    def get_command_list(cls) -> List[Dict[str, str]]:
        """Get commands in BotFather format"""
        return [
            {"command": cmd, "description": desc} for cmd, desc in cls.COMMANDS.items()
        ]

    @classmethod
    def get_help_text(cls, category: str = None) -> str:
        """Generate help text for commands"""
        if category:
            # Filter by category (implement if needed)
            pass

        help_text = "📋 **Available Commands**\n\n"

        categories = {
            "🏠 Basic": ["start", "help", "menu"],
            "📱 Accounts": ["add", "accs", "remove", "switch"],
            "🛡️ Security": ["otp", "twofa", "set_2fa", "get_2fa", "sessions"],
            "💬 Messaging": ["dm", "reply", "bulk_send"],
            "📢 Channels": ["channels", "join", "leave"],
            "👥 Contacts": ["contacts", "export_contacts"],
            "🧹 Cleanup": ["cleanup", "appeal"],
            "🤖 Automation": ["online", "simulate"],
            "📊 Monitoring": ["limits", "health", "session_health"],
        }

        for category_name, commands in categories.items():
            help_text += f"\n**{category_name}**\n"
            for cmd in commands:
                if cmd in cls.COMMANDS:
                    help_text += f"  /{cmd} - {cls.COMMANDS[cmd]}\n"

        return help_text

    @classmethod
    async def register_with_botfather(cls, bot) -> bool:
        """Register commands with BotFather"""
        try:
            from telethon.tl.functions.bots import SetBotCommandsRequest
            from telethon.tl.types import BotCommand, BotCommandScopeDefault

            commands = [
                BotCommand(command=cmd, description=desc[:64])  # BotFather limit
                for cmd, desc in cls.COMMANDS.items()
                if not cmd.endswith("_debug")
                and not cmd.endswith("_fix")  # Skip debug commands
            ]

            await bot(
                SetBotCommandsRequest(
                    scope=BotCommandScopeDefault(),
                    lang_code="en",
                    commands=commands
                )
            )

            logger.info(f"Registered {len(commands)} commands with BotFather")
            return True

        except Exception as e:
            logger.error(f"Failed to register commands: {e}")
            return False


# Global registry instance
command_registry = CommandRegistry()
