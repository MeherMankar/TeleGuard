"""Secure 2FA input handlers for menu system

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import logging

from telethon import Button

from ..core.database import get_session
from ..core.models import Account, User

logger = logging.getLogger(__name__)


class Secure2FAHandlers:
    """Handles secure 2FA input processing"""

    def __init__(self, bot, account_manager):
        self.bot = bot
        self.account_manager = account_manager

    async def handle_secure_2fa_input(self, event, user_id: int, data: str):
        """Handle secure 2FA keypad input"""
        try:
            parts = data.split(":")
            if len(parts) < 2:
                await event.answer("❌ Invalid input format")
                return
            input_type = parts[0]  # 2fa_input, 2fa_current, 2fa_remove, 2fa_new
            key = parts[1]

            if not self.account_manager:
                await event.answer("❌ Service unavailable")
                return

            # Handle keypad input
            (
                completed,
                buffer,
                action,
            ) = self.account_manager.secure_input.handle_keypad_input(user_id, key)

            if action == "cancel":
                await event.answer("❌ Cancelled")
                await self.bot.edit_message(
                    user_id,
                    event.message_id,
                    "❌ **2FA Setup Cancelled**\n\nOperation cancelled by user.",
                    buttons=[[Button.inline("🔙 Back to 2FA", "menu:2fa")]],
                )
                return

            elif action == "complete":
                if not buffer:
                    await event.answer("❌ Password cannot be empty")
                    return

                # Get session info
                session_info = self.account_manager.secure_input.pending_inputs.get(
                    user_id
                )
                if not session_info:
                    await event.answer("❌ Session expired")
                    return

                account_id = session_info["account_id"]
                session_type = session_info["type"]

                await event.answer("⚙️ Processing...")

                # Process based on input type
                if session_type == "set_2fa_password":
                    await self.process_set_2fa_password(
                        user_id, account_id, buffer, event.message_id
                    )
                elif session_type == "change_2fa_current":
                    await self.process_change_2fa_current(
                        user_id, account_id, buffer, event.message_id
                    )
                elif session_type == "change_2fa_new":
                    await self.process_change_2fa_new(
                        user_id, account_id, buffer, event.message_id
                    )
                elif session_type == "remove_2fa_password":
                    await self.process_remove_2fa_password(
                        user_id, account_id, buffer, event.message_id
                    )

            else:
                # Update display with masked password (skip shift_toggle)
                if action != "shift_toggle":
                    masked = self.account_manager.secure_input.get_masked_display(
                        buffer
                    )
                    await event.answer(f"Password: {masked}")
                else:
                    await event.answer("⇧ Shift toggled")

        except Exception as e:
            logger.error(f"Secure 2FA input error: {e}")
            await event.answer("❌ Input error")

    async def process_set_2fa_password(
        self, user_id: int, account_id: int, password: str, message_id: int
    ):
        """Process setting new 2FA password"""
        try:
            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()

                if not account:
                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        "❌ **Account Not Found**",
                        buttons=[[Button.inline("🔙 Back", "menu:2fa")]],
                    )
                    return

                # Get client
                client = self.account_manager.user_clients.get(user_id, {}).get(
                    account.name
                )
                if not client:
                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        "❌ **Client Not Found**\n\nPlease restart the bot.",
                        buttons=[[Button.inline("🔙 Back", "menu:2fa")]],
                    )
                    return

                # Use secure 2FA helper
                (
                    success,
                    result_msg,
                ) = await self.account_manager.secure_2fa.set_2fa_password(
                    client, password, hint="Set via RambaZamba Bot"
                )

                if success:
                    # Store hashed password
                    hashed_password = (
                        self.account_manager.secure_2fa.hash_password_for_storage(
                            password
                        )
                    )
                    account.twofa_password = hashed_password

                    # Add audit log
                    account.add_audit_entry(
                        {
                            "action": "set_2fa_password",
                            "user_id": user_id,
                            "result": True,
                        }
                    )

                    await session.commit()

                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        f"✅ **2FA Password Set**\n\n{result_msg} for {account.name}",
                        buttons=[[Button.inline("🔙 Back to 2FA", "menu:2fa")]],
                    )
                else:
                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        f"❌ **2FA Setup Failed**\n\n{result_msg}",
                        buttons=[
                            [
                                Button.inline("🔄 Try Again", f"2fa:set:{account_id}"),
                                Button.inline("🔙 Back", "menu:2fa"),
                            ]
                        ],
                    )

        except Exception as e:
            logger.error(f"2FA set password error: {e}")
            await self.bot.edit_message(
                user_id,
                message_id,
                f"❌ **Unexpected Error**\n\n{type(e).__name__}",
                buttons=[[Button.inline("🔙 Back", "menu:2fa")]],
            )

    async def process_change_2fa_current(
        self, user_id: int, account_id: int, current_password: str, message_id: int
    ):
        """Process current password for 2FA change"""
        # Store current password and prompt for new password
        if self.account_manager:
            # Store current password temporarily
            self.account_manager.pending_actions[user_id] = {
                "action": "change_2fa_new",
                "account_id": account_id,
                "current_password": current_password,
            }

            # Start new password input with extended timeout
            session_id = self.account_manager.secure_input.start_secure_input(
                user_id, "change_2fa_new", account_id
            )
            # Refresh session timestamp
            import time

            if user_id in self.account_manager.secure_input.pending_inputs:
                self.account_manager.secure_input.pending_inputs[user_id][
                    "started_at"
                ] = time.time()

            keypad = self.account_manager.secure_input.get_full_keypad("2fa_new")
            text = (
                "🔑 **Change 2FA Password**\n\n"
                "Now enter your new 2FA password:\n\n"
                "🔒 Secure input - not stored in chat history."
            )

            await self.bot.edit_message(user_id, message_id, text, buttons=keypad)

    async def process_change_2fa_new(
        self, user_id: int, account_id: int, new_password: str, message_id: int
    ):
        """Process new password for 2FA change"""
        try:
            # Get current password from pending actions
            pending = self.account_manager.pending_actions.get(user_id, {})
            current_password = pending.get("current_password")

            if not current_password:
                await self.bot.edit_message(
                    user_id,
                    message_id,
                    "❌ **Session Expired**\n\nPlease start over.",
                    buttons=[[Button.inline("🔙 Back", "menu:2fa")]],
                )
                return

            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()

                if not account:
                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        "❌ **Account Not Found**",
                        buttons=[[Button.inline("🔙 Back", "menu:2fa")]],
                    )
                    return

                # Get client
                client = self.account_manager.user_clients.get(user_id, {}).get(
                    account.name
                )
                if not client:
                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        "❌ **Client Not Found**\n\nPlease restart the bot.",
                        buttons=[[Button.inline("🔙 Back", "menu:2fa")]],
                    )
                    return

                # Use secure 2FA helper to change password
                (
                    success,
                    result_msg,
                ) = await self.account_manager.secure_2fa.change_2fa_password(
                    client,
                    current_password,
                    new_password,
                    hint="Changed via RambaZamba Bot",
                )

                if success:
                    # Update stored password hash
                    hashed_password = (
                        self.account_manager.secure_2fa.hash_password_for_storage(
                            new_password
                        )
                    )
                    account.twofa_password = hashed_password

                    # Add audit log
                    account.add_audit_entry(
                        {
                            "action": "change_2fa_password",
                            "user_id": user_id,
                            "result": True,
                        }
                    )

                    await session.commit()

                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        f"✅ **2FA Password Changed**\n\n{result_msg} for {account.name}",
                        buttons=[[Button.inline("🔙 Back to 2FA", "menu:2fa")]],
                    )
                else:
                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        f"❌ **2FA Change Failed**\n\n{result_msg}",
                        buttons=[
                            [
                                Button.inline(
                                    "🔄 Try Again", f"2fa:change:{account_id}"
                                ),
                                Button.inline("🔙 Back", "menu:2fa"),
                            ]
                        ],
                    )

                # Clear pending action
                self.account_manager.pending_actions.pop(user_id, None)

        except Exception as e:
            logger.error(f"2FA change password error: {e}")
            await self.bot.edit_message(
                user_id,
                message_id,
                f"❌ **Unexpected Error**\n\n{type(e).__name__}",
                buttons=[[Button.inline("🔙 Back", "menu:2fa")]],
            )

    async def process_remove_2fa_password(
        self, user_id: int, account_id: int, password: str, message_id: int
    ):
        """Process 2FA password removal"""
        try:
            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()

                if not account:
                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        "❌ **Account Not Found**",
                        buttons=[[Button.inline("🔙 Back", "menu:2fa")]],
                    )
                    return

                # Get client
                client = self.account_manager.user_clients.get(user_id, {}).get(
                    account.name
                )
                if not client:
                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        "❌ **Client Not Found**\n\nPlease restart the bot.",
                        buttons=[[Button.inline("🔙 Back", "menu:2fa")]],
                    )
                    return

                # Use secure 2FA helper to remove password
                (
                    success,
                    result_msg,
                ) = await self.account_manager.secure_2fa.remove_2fa_password(
                    client, password
                )

                if success:
                    # Clear stored password
                    account.twofa_password = None

                    # Add audit log
                    account.add_audit_entry(
                        {
                            "action": "remove_2fa_password",
                            "user_id": user_id,
                            "result": True,
                        }
                    )

                    await session.commit()

                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        f"✅ **2FA Password Removed**\n\n{result_msg} for {account.name}\n\n⚠️ 2FA protection is now disabled.",
                        buttons=[[Button.inline("🔙 Back to 2FA", "menu:2fa")]],
                    )
                else:
                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        f"❌ **2FA Removal Failed**\n\n{result_msg}",
                        buttons=[
                            [
                                Button.inline(
                                    "🔄 Try Again", f"2fa:remove:{account_id}"
                                ),
                                Button.inline("🔙 Back", "menu:2fa"),
                            ]
                        ],
                    )

        except Exception as e:
            logger.error(f"2FA remove password error: {e}")
            await self.bot.edit_message(
                user_id,
                message_id,
                f"❌ **Unexpected Error**\n\n{type(e).__name__}",
                buttons=[[Button.inline("🔙 Back", "menu:2fa")]],
            )

    async def show_2fa_status(self, user_id: int, account_id: int, message_id: int):
        """Show 2FA status for account"""
        try:
            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()

                if not account:
                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        "❌ **Account Not Found**",
                        buttons=[[Button.inline("🔙 Back", "menu:2fa")]],
                    )
                    return

                # Get client and check 2FA status
                client = self.account_manager.user_clients.get(user_id, {}).get(
                    account.name
                )
                if client:
                    (
                        success,
                        status_info,
                    ) = await self.account_manager.secure_2fa.check_2fa_status(client)

                    if success:
                        has_password = status_info.get("has_password", False)
                        hint = status_info.get("hint", "No hint")
                        has_recovery = status_info.get("has_recovery", False)

                        status_text = "✅ Enabled" if has_password else "❌ Disabled"
                        recovery_text = "✅ Set" if has_recovery else "❌ Not set"

                        text = (
                            f"🔑 **2FA Status: {account.name}**\n\n"
                            f"Status: {status_text}\n"
                            f"Hint: {hint}\n"
                            f"Recovery Email: {recovery_text}\n\n"
                        )

                        buttons = []
                        if has_password:
                            buttons.extend(
                                [
                                    [
                                        Button.inline(
                                            "🔄 Change Password",
                                            f"2fa:change:{account_id}",
                                        )
                                    ],
                                    [
                                        Button.inline(
                                            "❌ Remove 2FA", f"2fa:remove:{account_id}"
                                        )
                                    ],
                                ]
                            )
                        else:
                            buttons.append(
                                [
                                    Button.inline(
                                        "➕ Set 2FA Password", f"2fa:set:{account_id}"
                                    )
                                ]
                            )

                        buttons.append([Button.inline("🔙 Back", "menu:2fa")])

                        await self.bot.edit_message(
                            user_id, message_id, text, buttons=buttons
                        )
                    else:
                        await self.bot.edit_message(
                            user_id,
                            message_id,
                            f"❌ **Cannot Check 2FA Status**\n\nClient connection issue.",
                            buttons=[[Button.inline("🔙 Back", "menu:2fa")]],
                        )
                else:
                    await self.bot.edit_message(
                        user_id,
                        message_id,
                        f"❌ **Client Not Found**\n\nPlease restart the bot.",
                        buttons=[[Button.inline("🔙 Back", "menu:2fa")]],
                    )

        except Exception as e:
            logger.error(f"2FA status check error: {e}")
            await self.bot.edit_message(
                user_id,
                message_id,
                f"❌ **Status Check Failed**\n\n{type(e).__name__}",
                buttons=[[Button.inline("🔙 Back", "menu:2fa")]],
            )
