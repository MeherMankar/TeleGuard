"""Protection Manager Callbacks - Handle button interactions"""

import logging
from telethon import events, Button
from .protection_menu import ProtectionMenu
from ..core.mongo_database import mongodb
from ..services.protection_storage import ProtectionStorage

logger = logging.getLogger(__name__)

class ProtectionCallbacks:
    """Handle callback queries for the Protection system"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.menu = ProtectionMenu(bot_manager)
        self.protection_manager = bot_manager.protection_manager

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

            elif data == "prot_close":
                await event.delete()
                await event.answer("Protection dashboard closed")

            elif data == "prot_otp_settings":
                accounts = await mongodb.db.accounts.find(
                    {"user_id": user_id}
                ).to_list(length=None)
                current = bool(accounts) and all(
                    account.get("otp_destroyer_enabled", False)
                    for account in accounts
                )
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
                if minutes not in {5, 30, 60, 1440}:
                    await event.answer("⚠️ Invalid pause duration")
                    return
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
                await self.menu.send_logs(event, user_id)
                await event.answer()

            elif data == "prot_trusted":
                await self.menu.send_trusted_sessions(event, user_id)
                await event.answer()

            elif data.startswith(("prot_trust_", "prot_untrust_")):
                is_trusted = data.startswith("prot_trust_")
                prefix = "prot_trust_" if is_trusted else "prot_untrust_"
                try:
                    session_hash = int(data.removeprefix(prefix))
                except ValueError:
                    await event.answer("⚠️ Invalid session selection", alert=True)
                    return
                updated = await self.menu.set_session_trust(
                    user_id, session_hash, is_trusted
                )
                if not updated:
                    await event.answer(
                        "⚠️ Session is no longer available or cannot be changed.",
                        alert=True,
                    )
                else:
                    await event.answer(
                        "✅ Session trusted" if is_trusted else "🔓 Session untrusted"
                    )
                await self.menu.send_trusted_sessions(event, user_id)

        except Exception as e:
            logger.error(f"Error handling protection callback {data}: {e}")
            try:
                await event.answer("⚠️ An error occurred while processing your request")
            except Exception:
                logger.debug("Protection callback was already answered")
