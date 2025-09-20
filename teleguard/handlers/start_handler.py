"""Start command handler with persistent menu"""

import logging
import asyncio

from telethon import events

from ..core.mongo_database import mongodb
from ..core.device_snooper import DeviceSnooper

logger = logging.getLogger(__name__)


class StartHandler:
    """Handles /start command and sends persistent menu"""

    def __init__(self, bot, menu_system, bot_manager=None):
        self.bot = bot
        self.menu_system = menu_system
        self.bot_manager = bot_manager
        self.device_snooper = DeviceSnooper(mongodb) if mongodb else None

    def register_handlers(self):
        """Register start command handler"""

        @self.bot.on(events.NewMessage(pattern=r"^/start$"))
        async def start_command(event):
            user_id = event.sender_id

            try:
                # Ensure user exists in database
                user = await mongodb.get_user(user_id)
                if not user:
                    await mongodb.create_user(user_id)
                    logger.info(f"New user registered: {user_id}")

                    # Also save to GitHub database
                    try:
                        from .. import db_helpers

                        if db_helpers.db:
                            db_helpers.save_user_settings(
                                user_id,
                                {
                                    "telegram_id": user_id,
                                    "registered_at": int(__import__("time").time()),
                                    "developer_mode": False,
                                },
                            )
                            logger.info(f"User {user_id} saved to GitHub database")
                    except Exception as e:
                        logger.error(f"Failed to save user to GitHub: {e}")

                # Send persistent menu
                await self.menu_system.send_main_menu(user_id)

            except Exception as e:
                logger.error(f"Start command error: {e}")
                await event.reply("❌ Error starting bot. Please try again.")
    


        @self.bot.on(events.NewMessage(pattern=r"^/menu$"))
        async def menu_command(event):
            """Re-send menu if user needs it"""
            await self.menu_system.send_main_menu(event.sender_id)
