"""Automatic command registration with BotFather"""
import logging
from telethon.tl.functions.bots import SetBotCommandsRequest
from telethon.tl.types import BotCommand, BotCommandScopeDefault

logger = logging.getLogger(__name__)

async def register_bot_commands(bot):
    """Register all bot commands with BotFather automatically"""
    try:
        commands = [
            BotCommand(command="start", description="Start the bot and show main menu"),
            BotCommand(command="add", description="Add a new Telegram account"),
            BotCommand(command="accs", description="List all your accounts"),
            BotCommand(command="cancel", description="Cancel current operation"),
            BotCommand(command="reconnect", description="Reconnect all your accounts"),
            BotCommand(command="toggle_protection", description="Toggle OTP protection"),
            BotCommand(command="transfer", description="Transfer account ownership"),
            BotCommand(command="addcoowner", description="Add co-owner for all accounts"),
            BotCommand(command="help", description="Show help and documentation"),
        ]
        
        await bot(SetBotCommandsRequest(
            scope=BotCommandScopeDefault(),
            lang_code='',
            commands=commands
        ))
        
        logger.info(f"Registered {len(commands)} bot commands with BotFather")
        return True
    except Exception as e:
        logger.error(f"Failed to register bot commands: {e}")
        return False
