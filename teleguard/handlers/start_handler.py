"""Start command handler with persistent menu"""

import logging

from telethon import events

from ..core.device_snooper import DeviceSnooper
from ..core.mongo_database import mongodb

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
        self.bot.on(events.NewMessage(pattern=r"^/start(?:\s|$)"))(self._start_command)
        self.bot.on(events.NewMessage(pattern=r"^/menu(?:\s|$)"))(self._menu_command)

    async def _start_command(self, event):
        """Handle /start command"""
        user_id = event.sender_id
        try:
            is_new = await self._ensure_user_exists(user_id)
            account_count = await mongodb.db.accounts.count_documents({"user_id": user_id})

            if is_new:
                welcome_text = (
                    "🤖 **Welcome to TeleGuard!**\n\n"
                    "Your professional Telegram account manager with advanced OTP destroyer protection.\n\n"
                    "**🚀 Quick Start:**\n"
                    "1️⃣ Add your first account via '📱 Account Settings'\n"
                    "2️⃣ Enable OTP protection in '🛡️ OTP Manager'\n"
                    "3️⃣ Explore features using the menu below\n\n"
                    "**🛡️ Key Features:**\n"
                    "• Real-time OTP destroyer protection\n"
                    "• Multi-account management (up to 10)\n"
                    "• 2FA management & session control\n"
                    "• Activity simulation & automation\n"
                    "• Secure profile & channel management\n\n"
                    "**💬 Need Help?** Use '❓ Help' or contact @Meher_Mankar"
                )
                keyboard = self.menu_system.get_main_menu_keyboard(user_id)
                await event.reply(welcome_text, buttons=keyboard)
            elif account_count == 0:
                # Redirect to account settings for existing users with no accounts
                await self.menu_system.handlers.handle_account_settings(
                    type("Event", (), {"sender_id": user_id})()
                )
            else:
                await self.menu_system.send_main_menu(user_id)
        except Exception as e:
            logger.error(f"Start command error: {e}")
            await event.reply("❌ Error starting bot. Please try again.")

    async def _menu_command(self, event):
        """Re-send menu if user needs it"""
        await self.menu_system.send_main_menu(event.sender_id)

    async def _ensure_user_exists(self, user_id: int) -> bool:
        """Ensure user exists in database and return if they are new"""
        user = await mongodb.get_user(user_id)
        if not user:
            await mongodb.create_user(user_id)
            logger.debug(f"New user registered: {user_id}")
            await self._save_to_github_db(user_id)
            return True
        return False

    async def _save_to_github_db(self, user_id: int):
        """Save user to external database (stub — db_helpers module not present)"""
        # db_helpers is not part of this package; this is a no-op placeholder.
        # If you integrate an external DB helper, implement the logic here.
        pass
