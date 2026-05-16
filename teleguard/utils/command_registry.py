"""
Automatic Command Registry
Discovers and registers all bot commands automatically
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class CommandRegistry:
    """Registry for all bot commands"""

    # Command definitions - only commands that exist in command_handlers.py
    COMMANDS = {
        # Basic Commands
        "start": "Start the bot and show main menu",
        "cancel": "Cancel current operation",
        # Account Management
        "add": "Add a new Telegram account",
        "accs": "List all your accounts",
        "remove": "Remove an account (use menu)",
        "reconnect": "Reconnect all accounts",
        # OTP & Security
        "otp": "OTP Manager (use menu)",
        "toggle_protection": "Toggle OTP protection",
        # Proxy Management
        "proxy": "Manage proxies for accounts",
        # Session Management
        "sessions": "Session Management (use menu)",
        "export_session": "Export session (use menu)",
        "import_session": "Import session (use menu)",
        # DM Topics
        "enable_topics": "Enable DM topics for account",
        "disable_topics": "Disable DM topics for account",
        # Spam & Appeals
        "appeal": "Appeal spam restriction",
        "spam": "Spam tools (use menu)",
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
        help_text = "📋 **Available Commands**\n\n"

        categories = {
            "🏠 Basic": ["start", "cancel"],
            "📱 Accounts": ["add", "accs", "remove", "reconnect"],
            "🛡️ Security": ["otp", "toggle_protection", "sessions"],
            "🌐 Proxy": ["proxy"],
            "📤 Sessions": ["export_session", "import_session"],
            "💬 DM Topics": ["enable_topics", "disable_topics"],
            "🧹 Spam": ["appeal", "spam"],
        }

        for category_name, commands in categories.items():
            help_text += f"\n**{category_name}**\n"
            for cmd in commands:
                if cmd in cls.COMMANDS:
                    help_text += f"  /{cmd} - {cls.COMMANDS[cmd]}\n"

        help_text += "\n💡 **Tip:** Most features are accessible via the menu buttons!"
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

            logger.debug(f"Registered {len(commands)} commands with BotFather")
            return True

        except Exception as e:
            logger.error(f"Failed to register commands: {e}")
            return False


# Global registry instance
command_registry = CommandRegistry()
