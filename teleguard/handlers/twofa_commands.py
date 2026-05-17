"""2FA command handlers with proper status detection"""

import logging

from telethon import Button

from ..core.mongo_database import mongodb
from ..utils.auth_helpers import Secure2FAManager, SecureInputManager

logger = logging.getLogger(__name__)


class TwoFACommands:
    def __init__(self, bot_instance, account_manager):
        self.bot = bot_instance
        self.account_manager = account_manager
        self.secure_2fa = Secure2FAManager()
        self.input_manager = SecureInputManager()

    async def handle_2fa_callback(self, event, user_id: int, data: str):
        """Handle 2FA callback buttons"""
        try:
            parts = data.split(":")
            if len(parts) < 2:
                return
            action = parts[1]
            account_id = parts[2] if len(parts) > 2 else None
            if action == "set":
                await self._start_set_2fa(event, user_id, account_id)
            elif action == "change":
                await self._start_change_2fa(event, user_id, account_id)
            elif action == "remove":
                await self._start_remove_2fa(event, user_id, account_id)
            elif action == "cancel":
                self.account_manager.pending_actions.pop(user_id, None)
                await event.edit("❌ 2FA operation cancelled")
                await event.answer("Cancelled")
        except Exception as e:
            logger.error(f"2FA callback error: {e}")
            await event.answer("❌ Error processing request")

    async def _start_set_2fa(self, event, user_id: int, account_id: str):
        """Start setting new 2FA password"""
        try:
            account, client = await self._get_account_and_client(user_id, account_id)
            if not account or not client:
                await event.answer("❌ Account not found or not connected")
                return
            success, status = await self.secure_2fa.check_2fa_status(client)
            if success and status.get("has_password", False):
                await event.answer(
                    "⚠️ 2FA is already enabled. Use 'Change Password' instead."
                )
                return
            # Store pending action
            if not hasattr(self.account_manager, "pending_actions"):
                self.account_manager.pending_actions = {}
            self.account_manager.pending_actions[user_id] = {
                "action": "set_2fa",
                "account_id": account_id,
                "step": "password",
            }
            logger.info(f"Started set 2FA for user {user_id}, account {account_id}")
            text = (
                f"🔒 **Set 2FA Password: {account['name']}**\n\n"
                f"Please send your new 2FA password (4+ characters):\n\n"
                f"⚠️ Make sure it's strong and memorable!"
            )
            await event.edit(text, buttons=[[Button.inline("❌ Cancel", "2fa:cancel")]])
            await event.answer("🔒 Setting up 2FA...")
        except Exception as e:
            logger.error(f"Start set 2FA error: {e}")
            await event.answer("❌ Failed to start 2FA setup")

    async def _start_change_2fa(self, event, user_id: int, account_id: str):
        """Start changing existing 2FA password"""
        try:
            account, client = await self._get_account_and_client(user_id, account_id)
            if not account or not client:
                await event.answer("❌ Account not found or not connected")
                return
            success, status = await self.secure_2fa.check_2fa_status(client)
            if not success or not status.get("has_password", False):
                await event.answer("⚠️ 2FA is not enabled. Use 'Set Password' instead.")
                return
            # Store pending action
            if not hasattr(self.account_manager, "pending_actions"):
                self.account_manager.pending_actions = {}
            self.account_manager.pending_actions[user_id] = {
                "action": "change_2fa",
                "account_id": account_id,
                "step": "current_password",
            }
            logger.info(f"Started change 2FA for user {user_id}, account {account_id}")
            hint = status.get("hint", "No hint")
            text = (
                f"🔄 **Change 2FA Password: {account['name']}**\n\n"
                f"First, send your current password:\n"
                f"Hint: {hint}\n\n"
                f"Then I'll ask for your new password."
            )
            await event.edit(text, buttons=[[Button.inline("❌ Cancel", "2fa:cancel")]])
            await event.answer("🔄 Changing 2FA password...")
        except Exception as e:
            logger.error(f"Start change 2FA error: {e}")
            await event.answer("❌ Failed to start password change")

    async def _start_remove_2fa(self, event, user_id: int, account_id: str):
        """Start removing 2FA password"""
        try:
            account, client = await self._get_account_and_client(user_id, account_id)
            if not account or not client:
                await event.answer("❌ Account not found or not connected")
                return
            success, status = await self.secure_2fa.check_2fa_status(client)
            if not success or not status.get("has_password", False):
                await event.answer("⚠️ 2FA is not enabled.")
                return
            # Store pending action
            if not hasattr(self.account_manager, "pending_actions"):
                self.account_manager.pending_actions = {}
            self.account_manager.pending_actions[user_id] = {
                "action": "remove_2fa",
                "account_id": account_id,
                "step": "password",
            }
            logger.info(f"Started remove 2FA for user {user_id}, account {account_id}")
            hint = status.get("hint", "No hint")
            text = (
                f"🗑️ **Remove 2FA Password: {account['name']}**\n\n"
                f"⚠️ **Warning**: This will disable 2FA protection!\n\n"
                f"Send your current password to confirm:\n"
                f"Hint: {hint}"
            )
            await event.edit(text, buttons=[[Button.inline("❌ Cancel", "2fa:cancel")]])
            await event.answer("🗑️ Removing 2FA...")
        except Exception as e:
            logger.error(f"Start remove 2FA error: {e}")
            await event.answer("❌ Failed to start 2FA removal")

    async def handle_text_message(self, event, user_id: int, text: str):
        """Handle text message for 2FA operations"""
        try:
            if user_id not in self.account_manager.pending_actions:
                return False  # Not handling this message
            action_data = self.account_manager.pending_actions.get(user_id, {})
            action = action_data.get("action", "")
            if action == "verify_2fa":
                # This is 2FA during account creation - handle in message_handlers
                return False
            if not (
                action.endswith("_2fa")
                or action in ["change_2fa", "set_2fa", "remove_2fa"]
            ):
                return False  # Not a 2FA action
            account_id = action_data.get("account_id")
            step = action_data.get("step")
            if not account_id:
                logger.error(f"Missing account_id in action data: {action_data}")
                await event.reply("❌ Session error. Please start over.")
                self.account_manager.pending_actions.pop(user_id, None)
                return True
            logger.info(
                f"Processing 2FA text input: action={action}, step={step}, user={user_id}"
            )
            if action == "set_2fa" and step == "password":
                await self._process_set_2fa(event, user_id, account_id, text)
            elif action == "change_2fa" and step == "current_password":
                await self._process_change_2fa_current(event, user_id, account_id, text)
            elif action == "change_2fa" and step == "new_password":
                await self._process_change_2fa_new(event, user_id, account_id, text)
            elif action == "remove_2fa" and step == "password":
                await self._process_remove_2fa(event, user_id, account_id, text)
            else:
                logger.warning(f"Unknown 2FA step: {action}, {step}")
                await event.reply("❌ Invalid 2FA step. Please start over.")
                self.account_manager.pending_actions.pop(user_id, None)
            return True  # Message was handled
        except Exception as e:
            logger.error(f"2FA text input error: {e}")
            await event.reply("❌ Error processing 2FA input")
            self.account_manager.pending_actions.pop(user_id, None)
            return True

    async def _process_set_2fa(
        self, event, user_id: int, account_id: str, password: str
    ):
        """Process set 2FA password"""
        try:
            if len(password) < 4:
                await event.reply(
                    "❌ Password must be at least 4 characters long. Try again:"
                )
                return
            account, client = await self._get_account_and_client(user_id, account_id)
            if not account or not client:
                await event.reply("❌ Account not available")
                self.account_manager.pending_actions.pop(user_id, None)
                return
            success, message = await self.secure_2fa.set_2fa_password(client, password)
            if success:
                await event.reply(f"✅ **2FA Enabled Successfully**\n\n{message}")
            else:
                await event.reply(f"❌ **Failed to Enable 2FA**\n\n{message}")
            self.account_manager.pending_actions.pop(user_id, None)
        except Exception as e:
            logger.error(f"Process set 2FA error: {e}")
            await event.reply("❌ Failed to set 2FA password")
            self.account_manager.pending_actions.pop(user_id, None)

    async def _process_change_2fa_current(
        self, event, user_id: int, account_id: str, current_password: str
    ):
        """Process current password for change 2FA"""
        try:
            account, client = await self._get_account_and_client(user_id, account_id)
            if not account or not client:
                await event.reply("❌ Account not available")
                self.account_manager.pending_actions.pop(user_id, None)
                return

            # Simply store the password and move to next step
            # Password will be verified when actually changing it
            if user_id in self.account_manager.pending_actions:
                self.account_manager.pending_actions[user_id].update(
                    {"step": "new_password", "current_password": current_password}
                )
                await event.reply(
                    "✅ Current password received.\n\n"
                    "Now send your new 2FA password (4+ characters):"
                )
            else:
                await event.reply("❌ Session expired. Please start over.")

        except Exception as e:
            logger.error(f"Process change 2FA current error: {e}")
            await event.reply("❌ Error processing current password")
            self.account_manager.pending_actions.pop(user_id, None)

    async def _process_change_2fa_new(
        self, event, user_id: int, account_id: str, new_password: str
    ):
        """Process new password for change 2FA"""
        try:
            if len(new_password) < 4:
                await event.reply(
                    "❌ New password must be at least 4 characters long. Try again:"
                )
                return
            action_data = self.account_manager.pending_actions.get(user_id)
            if not action_data:
                await event.reply("❌ Session expired. Please start over.")
                return
            current_password = action_data.get("current_password")
            if not current_password:
                await event.reply("❌ Current password not found. Please start over.")
                self.account_manager.pending_actions.pop(user_id, None)
                return
            account, client = await self._get_account_and_client(user_id, account_id)
            if not account or not client:
                await event.reply("❌ Account not available")
                self.account_manager.pending_actions.pop(user_id, None)
                return
            success, message = await self.secure_2fa.change_2fa_password(
                client, current_password, new_password
            )
            if success:
                # Store the new password in database
                from ..utils.twofa_helper import twofa_helper

                phone = account.get("phone")
                if phone:
                    await twofa_helper.store_password(user_id, phone, new_password)

                await event.reply(
                    f"✅ **2FA Password Changed Successfully**\n\n{message}\n\n🔐 Password stored for automatic use"
                )
            else:
                await event.reply(f"❌ **Failed to Change 2FA Password**\n\n{message}")
            self.account_manager.pending_actions.pop(user_id, None)
        except Exception as e:
            logger.error(f"Process change 2FA new error: {e}")
            await event.reply("❌ Failed to change 2FA password")
            self.account_manager.pending_actions.pop(user_id, None)

    async def _process_remove_2fa(
        self, event, user_id: int, account_id: str, password: str
    ):
        """Process remove 2FA password"""
        try:
            account, client = await self._get_account_and_client(user_id, account_id)
            if not account or not client:
                await event.reply("❌ Account not available")
                self.account_manager.pending_actions.pop(user_id, None)
                return
            success, message = await self.secure_2fa.remove_2fa_password(
                client, password
            )
            if success:
                await event.reply(f"✅ **2FA Removed Successfully**\n\n{message}")
            else:
                await event.reply(f"❌ **Failed to Remove 2FA**\n\n{message}")
            self.account_manager.pending_actions.pop(user_id, None)
        except Exception as e:
            logger.error(f"Process remove 2FA error: {e}")
            await event.reply("❌ Failed to remove 2FA password")
            self.account_manager.pending_actions.pop(user_id, None)

    async def _get_account_and_client(self, user_id: int, account_id: str):
        """Get account and client"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return None, None
            client = self.account_manager.get_client(user_id, account)
            return account, client
        except Exception as e:
            logger.error(f"Get account and client error: {e}")
            return None, None
