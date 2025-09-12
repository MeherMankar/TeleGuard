"""OTP Disable Password Handler - Manages password protection for OTP Destroyer"""

import logging

from telethon import events

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class OTPPasswordHandler:
    """Handles OTP disable password management"""

    def __init__(self, bot, bot_manager):
        self.bot = bot
        self.bot_manager = bot_manager
        self.otp_manager = bot_manager.otp_manager

        # Track password input states
        self.password_states = {}

    def register_handlers(self):
        """Register password management handlers"""

        @self.bot.on(events.CallbackQuery(pattern=r"^otp_pwd:"))
        async def handle_password_callback(event):
            user_id = event.sender_id
            data = event.data.decode("utf-8")

            try:
                _, action, account_id = data.split(":")
                # account_id is already a string (MongoDB ObjectId)

                if action == "set":
                    await self._handle_set_password(event, user_id, account_id)
                elif action == "change":
                    await self._handle_change_password(event, user_id, account_id)
                elif action == "remove":
                    await self._handle_remove_password(event, user_id, account_id)
                elif action == "status":
                    await self._handle_password_status(event, user_id, account_id)

            except Exception as e:
                logger.error(f"Password callback error: {e}")
                await event.answer("❌ Error processing request", alert=True)

        @self.bot.on(events.NewMessage)
        async def handle_password_input(event):
            if not event.is_private or not event.text:
                return

            user_id = event.sender_id
            if user_id not in self.password_states:
                return

            state = self.password_states[user_id]
            text = event.text.strip()

            if text == "/cancel":
                del self.password_states[user_id]
                await event.reply("❌ Password setup cancelled")
                return

            try:
                if state["action"] == "set_new":
                    await self._process_new_password(
                        event, user_id, state["account_id"], text
                    )
                elif state["action"] == "change_old":
                    await self._process_old_password(
                        event, user_id, state["account_id"], text
                    )
                elif state["action"] == "change_new":
                    await self._process_change_new_password(
                        event, user_id, state["account_id"], text, state["old_password"]
                    )
                elif state["action"] == "remove_current":
                    await self._process_remove_password(
                        event, user_id, state["account_id"], text
                    )

            except Exception as e:
                logger.error(f"Password input error: {e}")
                await event.reply("❌ Error processing password")
                if user_id in self.password_states:
                    del self.password_states[user_id]

    async def _handle_set_password(self, event, user_id: int, account_id: str):
        """Handle setting new disable password"""
        # Check if password already exists
        success, has_password = await self.otp_manager.check_disable_password_status(
            user_id, account_id
        )
        if not success:
            await event.answer("❌ Error checking password status", alert=True)
            return

        if has_password:
            await event.answer(
                "⚠️ Password already set. Use 'Change Password' instead.", alert=True
            )
            return

        # Get account name
        account_name = await self._get_account_name(user_id, account_id)
        if not account_name:
            await event.answer("❌ Account not found", alert=True)
            return

        self.password_states[user_id] = {
            "action": "set_new",
            "account_id": account_id,
            "account_name": account_name,
        }

        await event.edit(
            f"🔐 **Set Disable Password: {account_name}**\n\n"
            f"🔒 This password will be required to:\n"
            f"• Disable OTP Destroyer\n"
            f"• Enable Temp OTP\n"
            f"• Pause OTP Destroyer\n\n"
            f"📝 **Enter new password:**\n"
            f"(Type /cancel to abort)",
            buttons=None,
        )

    async def _handle_change_password(self, event, user_id: int, account_id: str):
        """Handle changing existing disable password"""
        # Check if password exists
        success, has_password = await self.otp_manager.check_disable_password_status(
            user_id, account_id
        )
        if not success:
            await event.answer("❌ Error checking password status", alert=True)
            return

        if not has_password:
            await event.answer(
                "⚠️ No password set. Use 'Set Password' instead.", alert=True
            )
            return

        # Get account name
        account_name = await self._get_account_name(user_id, account_id)
        if not account_name:
            await event.answer("❌ Account not found", alert=True)
            return

        self.password_states[user_id] = {
            "action": "change_old",
            "account_id": account_id,
            "account_name": account_name,
        }

        await event.edit(
            f"🔐 **Change Disable Password: {account_name}**\n\n"
            f"🔑 **Enter current password:**\n"
            f"(Type /cancel to abort)",
            buttons=None,
        )

    async def _handle_remove_password(self, event, user_id: int, account_id: str):
        """Handle removing disable password"""
        # Check if password exists
        success, has_password = await self.otp_manager.check_disable_password_status(
            user_id, account_id
        )
        if not success:
            await event.answer("❌ Error checking password status", alert=True)
            return

        if not has_password:
            await event.answer("⚠️ No password is set", alert=True)
            return

        # Get account name
        account_name = await self._get_account_name(user_id, account_id)
        if not account_name:
            await event.answer("❌ Account not found", alert=True)
            return

        self.password_states[user_id] = {
            "action": "remove_current",
            "account_id": account_id,
            "account_name": account_name,
        }

        await event.edit(
            f"🔐 **Remove Disable Password: {account_name}**\n\n"
            f"⚠️ **Warning:** After removal, OTP Destroyer can be disabled without password!\n\n"
            f"🔑 **Enter current password to confirm:**\n"
            f"(Type /cancel to abort)",
            buttons=None,
        )

    async def _handle_password_status(self, event, user_id: int, account_id: str):
        """Show password status"""
        success, has_password = await self.otp_manager.check_disable_password_status(
            user_id, account_id
        )
        if not success:
            await event.answer("❌ Error checking password status", alert=True)
            return

        account_name = await self._get_account_name(user_id, account_id)
        if not account_name:
            await event.answer("❌ Account not found", alert=True)
            return

        status = "🔒 Set" if has_password else "🔓 Not Set"
        protection = "✅ Protected" if has_password else "⚠️ Unprotected"

        await event.edit(
            f"🔐 **Disable Password Status: {account_name}**\n\n"
            f"📊 **Status:** {status}\n"
            f"🛡️ **Protection:** {protection}\n\n"
            f"{'🔒 Password required to disable OTP Destroyer' if has_password else '⚠️ OTP Destroyer can be disabled without password'}"
        )

    async def _process_new_password(
        self, event, user_id: int, account_id: str, password: str
    ):
        """Process new password setting"""
        if len(password) < 4:
            await event.reply("❌ Password must be at least 4 characters long")
            return

        success, message = await self.otp_manager.set_disable_password(
            user_id, account_id, password
        )

        if success:
            await event.reply(f"✅ {message}")
        else:
            await event.reply(f"❌ {message}")

        del self.password_states[user_id]

    async def _process_old_password(
        self, event, user_id: int, account_id: str, old_password: str
    ):
        """Process old password verification for change"""
        # Verify old password
        import hashlib

        from bson import ObjectId

        account = await mongodb.db.accounts.find_one(
            {"_id": ObjectId(account_id), "user_id": user_id}
        )

        if not account:
            await event.reply("❌ Account not found")
            del self.password_states[user_id]
            return

        stored_hash = account.get("otp_destroyer_disable_auth")
        if not stored_hash:
            await event.reply("❌ No password is set")
            del self.password_states[user_id]
            return

        old_password_hash = hashlib.sha256(old_password.encode()).hexdigest()
        if old_password_hash != stored_hash:
            await event.reply("❌ Current password is incorrect")
            del self.password_states[user_id]
            return

        # Password verified, ask for new password
        self.password_states[user_id]["action"] = "change_new"
        self.password_states[user_id]["old_password"] = old_password

        await event.reply(
            f"✅ Current password verified\n\n"
            f"🔑 **Enter new password:**\n"
            f"(Type /cancel to abort)"
        )

    async def _process_change_new_password(
        self, event, user_id: int, account_id: str, new_password: str, old_password: str
    ):
        """Process new password for change"""
        if len(new_password) < 4:
            await event.reply("❌ Password must be at least 4 characters long")
            return

        success, message = await self.otp_manager.set_disable_password(
            user_id, account_id, new_password, old_password
        )

        if success:
            await event.reply(f"✅ {message}")
        else:
            await event.reply(f"❌ {message}")

        del self.password_states[user_id]

    async def _process_remove_password(
        self, event, user_id: int, account_id: str, current_password: str
    ):
        """Process password removal"""
        success, message = await self.otp_manager.remove_disable_password(
            user_id, account_id, current_password
        )

        if success:
            await event.reply(f"✅ {message}")
        else:
            await event.reply(f"❌ {message}")

        del self.password_states[user_id]

    async def _get_account_name(self, user_id: int, account_id: str) -> str:
        """Get account name by ID"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            return account["name"] if account else None
        except Exception as e:
            logger.error(f"Error getting account name: {e}")
            return None
