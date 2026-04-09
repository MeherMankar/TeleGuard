"""Unified logging system with correlation IDs and bot logging"""

import json
import logging
import os
import sys
import traceback
import uuid
from datetime import datetime, timezone
from typing import Optional


class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.correlation_id: Optional[str] = None
        self.name = name

    def set_correlation_id(self, correlation_id: str = None):
        """Set correlation ID for request tracking"""
        self.correlation_id = correlation_id or str(uuid.uuid4())[:8]

    def _format_message(self, level: str, message: str, **kwargs) -> str:
        """Format message with structured data"""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            "correlation_id": self.correlation_id,
            **kwargs,
        }
        return json.dumps(log_data, default=str)

    def info(self, message: str, *args, **kwargs):
        """Log info message with support for format args"""
        if args:
            formatted_message = message % args
        else:
            formatted_message = message
        self.logger.info(self._format_message("INFO", formatted_message, **kwargs))

    def warning(self, message: str, *args, **kwargs):
        """Log warning message with support for format args"""
        if args:
            formatted_message = message % args
        else:
            formatted_message = message
        self.logger.warning(
            self._format_message("WARNING", formatted_message, **kwargs)
        )

    def error(self, message: str, *args, **kwargs):
        """Log error message with support for format args"""
        if args:
            formatted_message = message % args
        else:
            formatted_message = message
        self.logger.error(self._format_message("ERROR", formatted_message, **kwargs))

    def debug(self, message: str, *args, **kwargs):
        """Log debug message with support for format args"""
        if args:
            formatted_message = message % args
        else:
            formatted_message = message
        self.logger.debug(self._format_message("DEBUG", formatted_message, **kwargs))


class BotLogger:
    """Send all user actions and errors to logs bot"""

    _bot = None
    _logs_bot = None
    _log_chat_id = None

    @classmethod
    async def init(cls, bot):
        """Initialize with bot instance"""
        cls._bot = bot

        logs_bot_token = os.getenv("LOGS_BOT_TOKEN")
        if logs_bot_token:
            try:
                from telethon import TelegramClient

                from ..core.config import config

                cls._logs_bot = TelegramClient(
                    "logs_bot", config.telegram.api_id, config.telegram.api_hash
                )
                await cls._logs_bot.start(bot_token=logs_bot_token)
            except Exception as e:
                logging.error(f"Failed to initialize logs bot: {e}")
                cls._logs_bot = bot
        else:
            cls._logs_bot = bot

        log_chat_id = os.getenv("LOG_CHAT_ID")
        if log_chat_id:
            try:
                cls._log_chat_id = int(log_chat_id)
            except ValueError:
                logging.error(f"Invalid LOG_CHAT_ID: {log_chat_id}")

    @classmethod
    async def log(
        cls,
        user_id: int,
        action: str,
        details: str = "",
        username: Optional[str] = None,
    ):
        """Send log to logs bot"""
        if not cls._logs_bot or not cls._log_chat_id:
            return

        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user_info = f"@{username}" if username else f"ID: {user_id}"
            message = f"📋 **User Action Log**\n🕐 {timestamp}\n👤 {user_info}\n⚡ **{action}**"
            if details:
                message += f"\n📝 {details}"

            await cls._logs_bot.send_message(cls._log_chat_id, message)
        except Exception as e:
            logging.debug(f"Failed to send log: {e}")

    @classmethod
    async def log_error(
        cls,
        error_type: str,
        error_msg: str,
        user_id: Optional[int] = None,
        context: str = "",
    ):
        """Log errors to logs bot"""
        if not cls._logs_bot or not cls._log_chat_id:
            return

        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user_info = f"User ID: {user_id}" if user_id else "System"
            message = f"🚨 **Error Log**\n🕐 {timestamp}\n👤 {user_info}\n❌ **{error_type}**\n📝 {error_msg}"
            if context:
                message += f"\n🔍 Context: {context}"

            await cls._logs_bot.send_message(cls._log_chat_id, message)
        except Exception:
            pass

    @classmethod
    def setup_global_error_handler(cls):
        """Setup global exception handler"""

        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return

            error_msg = "".join(
                traceback.format_exception(exc_type, exc_value, exc_traceback)
            )
            logging.error(f"Uncaught exception: {error_msg}")

            try:
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(
                        cls.log_error(
                            f"{exc_type.__name__}",
                            str(exc_value)[:500],
                            context="Global handler",
                        )
                    )
            except BaseException:
                pass

        sys.excepthook = handle_exception


def get_logger(name: str) -> StructuredLogger:
    """Get structured logger instance"""
    return StructuredLogger(name)


# Create default logger instance
logger = get_logger(__name__)
