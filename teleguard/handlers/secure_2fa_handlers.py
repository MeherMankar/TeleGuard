"""Secure 2FA handlers for menu system"""
import logging
from telethon import Button
from ..core.mongo_database import mongodb
from ..utils.auth_helpers import Secure2FAManager
logger = logging.getLogger(__name__)
class Secure2FAHandlers:
    """Handles secure 2FA operations"""
    def __init__(self, bot_instance, account_manager):
        self.bot = bot_instance
        self.account_manager = account_manager
        self.secure_2fa = Secure2FAManager()
    async def show_2fa_status(self, user_id: int, account_id: str, message_id: int):
        """Show 2FA status for account"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                await self.bot.send_message(user_id, "❌ Account not found")
                return
            client = await self._get_client(user_id, account["phone"])
            if not client:
                await self.bot.edit_message(
                    user_id, message_id, "❌ Account not connected"
                )
                return
            success, status_info = await self.secure_2fa.check_2fa_status(client)
            if success:
                has_2fa = status_info.get("has_password", False)
                hint = status_info.get("hint", "No hint")
                has_recovery = status_info.get("has_recovery", False)
                status_text = "🔒 Enabled" if has_2fa else "⚪ Disabled"
                text = (
                    f"🔑 **2FA Status: {account['name']}**\n\n"
                    f"Status: {status_text}\n"
                )
                if has_2fa:
                    text += f"Hint: {hint}\n"
                    text += f"Recovery Email: {'✅ Set' if has_recovery else '❌ Not Set'}\n\n"
                    text += "Manage your 2FA:"
                else:
                    text += "\nSet up 2FA to secure your account:"
                buttons = []
                if has_2fa:
                    buttons.extend(
                        [
                            [
                                Button.inline(
                                    "🔄 Change Password", f"2fa:change:{account_id}"
                                )
                            ],
                            [Button.inline("🗑️ Remove 2FA", f"2fa:remove:{account_id}")],
                        ]
                    )
                else:
                    buttons.append(
                        [Button.inline("🔒 Set Password", f"2fa:set:{account_id}")]
                    )
                buttons.append([Button.inline("🔙 Back", "menu:2fa")])
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            else:
                await self.bot.edit_message(
                    user_id, message_id, "❌ Failed to check 2FA status"
                )
        except Exception as e:
            logger.error(f"Failed to show 2FA status: {e}")
    async def _get_client(self, user_id: int, phone: str):
        """Get client for account"""
        try:
            user_clients = self.account_manager.user_clients.get(user_id, {})
            for account_name, client in user_clients.items():
                # Find client by checking phone or account name
                if phone in account_name or account_name in phone:
                    return client
            return None
        except Exception as e:
            logger.error(f"Failed to get client: {e}")
            return None
    async def handle_secure_2fa_input(self, event, user_id: int, data: str):
        """Handle secure 2FA input callbacks"""
        try:
            await event.answer("🔑 2FA operation processed")
        except Exception as e:
            logger.error(f"Failed to handle 2FA input: {e}")
