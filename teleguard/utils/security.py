"""
Secure 2FA Input Handlers
Professional 2FA management system with secure keypad input processing.
Handles password setting, changing, and removal with comprehensive error handling.
Authors: @Meher_Mankar, @Gutkesh
Repository: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from telethon import Button

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class TwoFactorAuthError(Exception):
    """Custom exception for 2FA operations"""



class Secure2FAHandlers:
    """
    Professional 2FA input handler with secure keypad processing.
    Provides secure password input, validation, and database operations
    for two-factor authentication management.
    """

    # Constants
    SESSION_TIMEOUT = 300  # 5 minutes
    PASSWORD_HINT = "Set via TeleGuard Bot"

    def __init__(self, bot, account_manager):
        self.bot = bot
        self.account_manager = account_manager
        self._validate_dependencies()

    def _validate_dependencies(self) -> None:
        """Validate required dependencies are available"""
        if not self.bot:
            raise ValueError("Bot instance is required")
        if not self.account_manager:
            raise ValueError("Account manager is required")

    async def handle_secure_2fa_input(self, event, user_id: int, data: str) -> None:
        """
        Handle secure 2FA keypad input with comprehensive validation.
        Args:
            event: Telegram event object
            user_id: User's Telegram ID
            data: Input data string in format "type:key"
        """
        try:
            input_type, key = self._parse_input_data(data)
            if not self._is_service_available():
                await event.answer("❌ Service unavailable")
                return
            completed, buffer, action = (
                self.account_manager.secure_input.handle_keypad_input(user_id, key)
            )
            await self._process_keypad_action(event, user_id, action, buffer, completed)
        except ValueError as e:
            logger.warning(f"Invalid input from user {user_id}: {e}")
            await event.answer("❌ Invalid input format")
        except Exception as e:
            logger.error(f"2FA input error for user {user_id}: {e}")
            await event.answer("❌ Input processing error")

    def _parse_input_data(self, data: str) -> Tuple[str, str]:
        """Parse and validate input data format"""
        parts = data.split(":", 1)
        if len(parts) < 2:
            raise ValueError("Invalid input format - expected 'type:key'")
        return parts[0], parts[1]

    def _is_service_available(self) -> bool:
        """Check if required services are available"""
        return (
            self.account_manager is not None
            and hasattr(self.account_manager, "secure_input")
            and hasattr(self.account_manager, "secure_2fa")
        )

    async def _process_keypad_action(
        self, event, user_id: int, action: str, buffer: str, completed: bool
    ) -> None:
        """Process different keypad actions"""
        if action == "cancel":
            await self._handle_cancel_action(event, user_id)
        elif action == "complete":
            await self._handle_complete_action(event, user_id, buffer)
        elif action != "shift_toggle":
            await self._handle_input_feedback(event, buffer)
        else:
            await event.answer("⇧ Shift toggled")

    async def _handle_cancel_action(self, event, user_id: int) -> None:
        """Handle cancellation of 2FA input"""
        await event.answer("❌ Cancelled")
        await self.bot.edit_message(
            user_id,
            event.message_id,
            "❌ **2FA Setup Cancelled**\n\nOperation cancelled by user.",
            buttons=[[Button.inline("🔙 Back to 2FA", "menu:2fa")]],
        )

    async def _handle_complete_action(self, event, user_id: int, buffer: str) -> None:
        """Handle completion of password input"""
        if not buffer:
            await event.answer("❌ Password cannot be empty")
            return
        session_info = self._get_session_info(user_id)
        if not session_info:
            await event.answer("❌ Session expired")
            return
        await event.answer("⚙️ Processing...")
        await self._route_to_processor(event, user_id, session_info, buffer)

    def _get_session_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get session information for user"""
        return self.account_manager.secure_input.pending_inputs.get(user_id)

    async def _route_to_processor(
        self, event, user_id: int, session_info: Dict[str, Any], buffer: str
    ) -> None:
        """Route to appropriate processor based on session type"""
        account_id = session_info["account_id"]
        session_type = session_info["type"]
        message_id = event.message_id
        processors = {
            "set_2fa_password": self.process_set_2fa_password,
            "change_2fa_current": self.process_change_2fa_current,
            "change_2fa_new": self.process_change_2fa_new,
            "remove_2fa_password": self.process_remove_2fa_password,
        }
        processor = processors.get(session_type)
        if processor:
            await processor(user_id, account_id, buffer, message_id)
        else:
            logger.error(f"Unknown session type: {session_type}")
            await event.answer("❌ Unknown operation type")

    async def _handle_input_feedback(self, event, buffer: str) -> None:
        """Provide masked feedback for password input"""
        masked = self.account_manager.secure_input.get_masked_display(buffer)
        await event.answer(f"Password: {masked}")

    async def _get_account(
        self, user_id: int, account_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get account from database with validation"""
        try:
            return await mongodb.db.accounts.find_one(
                {"user_id": user_id, "_id": account_id}
            )
        except Exception as e:
            logger.error(
                f"Database error getting account {account_id} for user {user_id}: {e}"
            )
            return None

    def _get_client(self, user_id: int, account_name: str):
        """Get Telegram client for account"""
        return self.account_manager.user_clients.get(user_id, {}).get(account_name)

    async def _send_error_message(
        self, user_id: int, message_id: int, title: str, error: str
    ) -> None:
        """Send standardized error message"""
        await self.bot.edit_message(
            user_id,
            message_id,
            f"❌ **{title}**\n\n{error}",
            buttons=[[Button.inline("🔙 Back", "menu:2fa")]],
        )

    async def _log_audit_event(
        self, account_id: str, action: str, user_id: int, success: bool
    ) -> None:
        """Log audit event to database"""
        try:
            await mongodb.db.accounts.update_one(
                {"_id": account_id},
                {
                    "$push": {
                        "audit_log": {
                            "action": action,
                            "user_id": user_id,
                            "result": success,
                            "timestamp": datetime.utcnow(),
                        }
                    }
                },
            )
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")

    async def process_set_2fa_password(
        self, user_id: int, account_id: int, password: str, message_id: int
    ) -> None:
        """Process setting new 2FA password with comprehensive validation"""
        try:
            account = await self._get_account(user_id, account_id)
            if not account:
                await self._send_error_message(
                    user_id,
                    message_id,
                    "Account Not Found",
                    "Account not found in database.",
                )
                return
            client = self._get_client(user_id, account.get("name"))
            if not client:
                await self._send_error_message(
                    user_id, message_id, "Client Not Found", "Please restart the bot."
                )
                return
            success, result_msg = (
                await self.account_manager.secure_2fa.set_2fa_password(
                    client, password, hint=self.PASSWORD_HINT
                )
            )
            if success:
                await self._handle_2fa_success(
                    user_id, account, password, message_id, "set", result_msg
                )
            else:
                await self._handle_2fa_failure(
                    user_id,
                    message_id,
                    "2FA Setup Failed",
                    result_msg,
                    account_id,
                    "set",
                )
        except Exception as e:
            logger.error(f"2FA set password error for user {user_id}: {e}")
            await self._send_error_message(
                user_id, message_id, "Unexpected Error", f"{type(e).__name__}"
            )

    async def _handle_2fa_success(
        self,
        user_id: int,
        account: Dict[str, Any],
        password: str,
        message_id: int,
        action: str,
        result_msg: str,
    ) -> None:
        """Handle successful 2FA operation"""
        from ..utils.crypto_utils import DataEncryption as _DE
        encrypted_password = _DE.encrypt_field(password)
        await mongodb.db.accounts.update_one(
            {"_id": account["_id"]}, {"$set": {"twofa_password": encrypted_password}}
        )
        await self._log_audit_event(
            account["_id"], f"{action}_2fa_password", user_id, True
        )
        action_text = {"set": "Set", "change": "Changed", "remove": "Removed"}.get(
            action, "Updated"
        )
        await self.bot.edit_message(
            user_id,
            message_id,
            f"✅ **2FA Password {action_text}**\n\n{result_msg} for {
                account.get('name')}",
            buttons=[[Button.inline("🔙 Back to 2FA", "menu:2fa")]],
        )

    async def _handle_2fa_failure(
        self,
        user_id: int,
        message_id: int,
        title: str,
        error_msg: str,
        account_id: int,
        action: str,
    ) -> None:
        """Handle failed 2FA operation"""
        action_map = {"set": "set", "change": "change", "remove": "remove"}
        retry_action = action_map.get(action, "set")
        await self.bot.edit_message(
            user_id,
            message_id,
            f"❌ **{title}**\n\n{error_msg}",
            buttons=[
                [
                    Button.inline("🔄 Try Again", f"2fa:{retry_action}:{account_id}"),
                    Button.inline("🔙 Back", "menu:2fa"),
                ]
            ],
        )

    async def process_change_2fa_current(
        self, user_id: int, account_id: int, current_password: str, message_id: int
    ) -> None:
        """Process current password for 2FA change"""
        if not self.account_manager:
            await self._send_error_message(
                user_id, message_id, "Service Error", "Account manager unavailable."
            )
            return
        # Store current password temporarily
        self.account_manager.pending_actions[user_id] = {
            "action": "change_2fa_new",
            "account_id": account_id,
            "current_password": current_password,
        }
        self.account_manager.secure_input.start_secure_input(
            user_id, "change_2fa_new", account_id
        )
        # Refresh session timestamp
        if user_id in self.account_manager.secure_input.pending_inputs:
            self.account_manager.secure_input.pending_inputs[user_id][
                "started_at"
            ] = time.time()
        keypad = self.account_manager.secure_input.get_full_keypad("2fa_new")
        await self.bot.edit_message(
            user_id,
            message_id,
            "🔑 **Change 2FA Password**\n\nNow enter your new 2FA password:\n\n🔒 Secure input - not stored in chat history.",
            buttons=keypad,
        )

    async def process_change_2fa_new(
        self, user_id: int, account_id: int, new_password: str, message_id: int
    ) -> None:
        """Process new password for 2FA change"""
        try:
            pending = self.account_manager.pending_actions.get(user_id, {})
            current_password = pending.get("current_password")
            if not current_password:
                await self._send_error_message(
                    user_id, message_id, "Session Expired", "Please start over."
                )
                return
            account = await self._get_account(user_id, account_id)
            if not account:
                await self._send_error_message(
                    user_id,
                    message_id,
                    "Account Not Found",
                    "Account not found in database.",
                )
                return
            client = self._get_client(user_id, account.get("name"))
            if not client:
                await self._send_error_message(
                    user_id, message_id, "Client Not Found", "Please restart the bot."
                )
                return
            success, result_msg = (
                await self.account_manager.secure_2fa.change_2fa_password(
                    client,
                    current_password,
                    new_password,
                    hint="Changed via TeleGuard Bot",
                )
            )
            if success:
                await self._handle_2fa_success(
                    user_id, account, new_password, message_id, "change", result_msg
                )
            else:
                await self._handle_2fa_failure(
                    user_id,
                    message_id,
                    "2FA Change Failed",
                    result_msg,
                    account_id,
                    "change",
                )
            # Clear pending action
            self.account_manager.pending_actions.pop(user_id, None)
        except Exception as e:
            logger.error(f"2FA change password error for user {user_id}: {e}")
            await self._send_error_message(
                user_id, message_id, "Unexpected Error", f"{type(e).__name__}"
            )

    async def process_remove_2fa_password(
        self, user_id: int, account_id: int, password: str, message_id: int
    ) -> None:
        """Process 2FA password removal"""
        try:
            account = await self._get_account(user_id, account_id)
            if not account:
                await self._send_error_message(
                    user_id,
                    message_id,
                    "Account Not Found",
                    "Account not found in database.",
                )
                return
            client = self._get_client(user_id, account.get("name"))
            if not client:
                await self._send_error_message(
                    user_id, message_id, "Client Not Found", "Please restart the bot."
                )
                return
            success, result_msg = (
                await self.account_manager.secure_2fa.remove_2fa_password(
                    client, password
                )
            )
            if success:
                # Clear stored password
                await mongodb.db.accounts.update_one(
                    {"_id": account["_id"]}, {"$unset": {"twofa_password": ""}}
                )
                await self._log_audit_event(
                    account["_id"], "remove_2fa_password", user_id, True
                )
                await self.bot.edit_message(
                    user_id,
                    message_id,
                    f"✅ **2FA Password Removed**\n\n{result_msg} for {
                        account.get('name')}\n\n⚠️ 2FA protection is now disabled.",
                    buttons=[[Button.inline("🔙 Back to 2FA", "menu:2fa")]],
                )
            else:
                await self._handle_2fa_failure(
                    user_id,
                    message_id,
                    "2FA Removal Failed",
                    result_msg,
                    account_id,
                    "remove",
                )
        except Exception as e:
            logger.error(f"2FA remove password error for user {user_id}: {e}")
            await self._send_error_message(
                user_id, message_id, "Unexpected Error", f"{type(e).__name__}"
            )

    async def show_2fa_status(
        self, user_id: int, account_id: int, message_id: int
    ) -> None:
        """Show comprehensive 2FA status for account"""
        try:
            account = await self._get_account(user_id, account_id)
            if not account:
                await self._send_error_message(
                    user_id,
                    message_id,
                    "Account Not Found",
                    "Account not found in database.",
                )
                return
            client = self._get_client(user_id, account.get("name"))
            if not client:
                await self._send_error_message(
                    user_id, message_id, "Client Not Found", "Please restart the bot."
                )
                return
            success, status_info = (
                await self.account_manager.secure_2fa.check_2fa_status(client)
            )
            if success:
                await self._display_2fa_status(
                    user_id, message_id, account, status_info, account_id
                )
            else:
                await self._send_error_message(
                    user_id,
                    message_id,
                    "Cannot Check 2FA Status",
                    "Client connection issue.",
                )
        except Exception as e:
            logger.error(f"2FA status check error for user {user_id}: {e}")
            await self._send_error_message(
                user_id, message_id, "Status Check Failed", f"{type(e).__name__}"
            )

    async def _display_2fa_status(
        self,
        user_id: int,
        message_id: int,
        account: Dict[str, Any],
        status_info: Dict[str, Any],
        account_id: int,
    ) -> None:
        """Display formatted 2FA status information"""
        has_password = status_info.get("has_password", False)
        hint = status_info.get("hint", "No hint")
        has_recovery = status_info.get("has_recovery", False)
        status_text = "✅ Enabled" if has_password else "❌ Disabled"
        recovery_text = "✅ Set" if has_recovery else "❌ Not set"
        text = (
            f"🔑 **2FA Status: {account.get('name')}**\n\n"
            f"Status: {status_text}\n"
            f"Hint: {hint}\n"
            f"Recovery Email: {recovery_text}\n\n"
        )
        buttons = self._build_2fa_status_buttons(has_password, account_id)
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    def _build_2fa_status_buttons(self, has_password: bool, account_id: int) -> list:
        """Build appropriate buttons based on 2FA status"""
        buttons = []
        if has_password:
            buttons.extend(
                [
                    [Button.inline("🔄 Change Password", f"2fa:change:{account_id}")],
                    [Button.inline("❌ Remove 2FA", f"2fa:remove:{account_id}")],
                ]
            )
        else:
            buttons.append(
                [Button.inline("➕ Set 2FA Password", f"2fa:set:{account_id}")]
            )
        buttons.append([Button.inline("🔙 Back", "menu:2fa")])
        return buttons
