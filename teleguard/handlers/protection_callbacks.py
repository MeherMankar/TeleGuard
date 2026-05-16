"""Protection Manager Callbacks - Handle button interactions"""

import logging
from telethon import events, Button
from .protection_menu import ProtectionMenu
from ..services.protection_storage import ProtectionStorage

logger = logging.getLogger(__name__)

class ProtectionCallbacks:
    """Handle callback queries for the Protection system"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.menu = ProtectionMenu(bot_manager)
        self.protection_manager = bot_manager.otp_manager # We'll update the name in BotManager later

    def register_handlers(self):
        """Register callback handlers"""
        self.bot_manager.bot.add_event_handler(
            self.handle_callbacks, 
            events.CallbackQuery(pattern=r"prot_")
        )

    async def handle_callbacks(self, event):
        """Main dispatcher for protection callbacks"""
        user_id = event.sender_id
        data = event.data.decode()
        
        try:
            if data == "prot_main" or data == "prot_refresh":
                await self.menu.send_main_menu(event, user_id, edit=True)
                await event.answer("Updated ✅")

            elif data == "prot_otp_settings":
                settings = await ProtectionStorage.get_settings(user_id)
                current = settings.get("otp_destroyer_enabled", False)
                await self.protection_manager.toggle_otp_destroyer(user_id, not current)
                await self.menu.send_main_menu(event, user_id, edit=True)
                await event.answer(f"OTP Destroyer {'Enabled' if not current else 'Disabled'}")

            elif data == "prot_session_settings":
                settings = await ProtectionStorage.get_settings(user_id)
                current = settings.get("session_destroyer_enabled", False)
                await self.protection_manager.toggle_session_destroyer(user_id, not current)
                await self.menu.send_main_menu(event, user_id, edit=True)
                await event.answer(f"Session Destroyer {'Enabled' if not current else 'Disabled'}")

            elif data == "prot_pause_menu":
                await self.menu.send_pause_menu(event, user_id)

            elif data.startswith("prot_pause_"):
                minutes = int(data.split("_")[-1])
                await self.protection_manager.pause_protection(user_id, minutes)
                await self.menu.send_main_menu(event, user_id, edit=True)
                await event.answer(f"Protection paused for {minutes}m")

            elif data == "prot_allow_next":
                await self.protection_manager.allow_next_login(user_id)
                await event.answer("🔓 Next login will be trusted automatically", alert=True)
                await self.menu.send_main_menu(event, user_id, edit=True)

            elif data == "prot_stats":
                await self.menu.send_stats(event, user_id)

            elif data == "prot_logs":
                await event.answer("Feature coming soon: Detailed protection logs", alert=True)

        except Exception as e:
            logger.error(f"Error handling protection callback {data}: {e}")
            await event.answer("⚠️ An error occurred while processing your request")
