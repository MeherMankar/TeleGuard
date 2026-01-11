"""
OTP Command Handlers
Professional OTP management system for handling OTP forwarding and destroying.
Provides secure command processing with comprehensive validation and error handling.
Authors: @Meher_Mankar, @Gutkesh
Repository: https://github.com/mehermankar/teleguard
"""

import logging
from typing import Any, Dict, Optional

from telethon import events

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class OTPCommandError(Exception):
    """Custom exception for OTP command operations"""



class OTPCommandHandlers:
    """
    Professional OTP command handler with comprehensive validation.
    Manages OTP destroyer, forwarding, and temporary passthrough functionality
    with proper error handling and user feedback.
    """

    # Command patterns
    DESTROYER_PATTERN = r"/otpdestroyer\s+(on|off)"
    FORWARD_PATTERN = r"/otpforward\s+(on|off)"
    TEMP_PATTERN = r"/otptemp"
    # Response messages
    MESSAGES = {
        "no_accounts": "❌ No accounts found. Add an account first.",
        "service_unavailable": "❌ OTP Manager not available",
        "temp_success": (
            "⏰ **OTP Passthrough Active**\n\n"
            "Duration: 5 minutes\n"
            "Status: OTPs will be forwarded but not deleted\n\n"
            "Request your login code now!"
        ),
        "temp_failed": "❌ Failed to enable temporary passthrough",
    }

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self._validate_dependencies()

    def _validate_dependencies(self) -> None:
        """Validate required dependencies are available"""
        if not self.bot_manager:
            raise ValueError("Bot manager is required")
        if not self.bot:
            raise ValueError("Bot instance is required")

    def register_handlers(self) -> None:
        """Register all OTP command handlers with the bot"""
        handlers = [
            (self.DESTROYER_PATTERN, self._handle_otp_destroyer),
            (self.FORWARD_PATTERN, self._handle_otp_forward),
            (self.TEMP_PATTERN, self._handle_otp_temp),
        ]
        for pattern, handler in handlers:
            self.bot.on(events.NewMessage(pattern=pattern))(handler)
        logger.info("OTP command handlers registered successfully")

    async def _get_user_account(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the first active account for a user.
        Args:
            user_id: User's Telegram ID
        Returns:
            Account document or None if not found
        """
        try:
            return await mongodb.db.accounts.find_one(
                {"user_id": user_id, "is_active": True}
            )
        except Exception as e:
            logger.error(f"Database error getting account for user {user_id}: {e}")
            return None

    def _is_otp_manager_available(self) -> bool:
        """Check if OTP manager is available and functional"""
        return (
            hasattr(self.bot_manager, "otp_manager")
            and self.bot_manager.otp_manager is not None
        )

    async def _send_response(self, event, message: str, emoji: str = "🛡️") -> None:
        """Send formatted response message"""
        await event.reply(f"{emoji} {message}")

    async def _handle_otp_destroyer(self, event) -> None:
        """
        Handle OTP destroyer on/off command.
        Command: /otpdestroyer on|off
        """
        try:
            user_id = event.sender_id
            state = event.pattern_match.group(1).lower()
            enabled = state == "on"
            account = await self._get_user_account(user_id)
            if not account:
                await self._send_response(event, self.MESSAGES["no_accounts"], "❌")
                return
            if not self._is_otp_manager_available():
                await self._send_response(
                    event, self.MESSAGES["service_unavailable"], "❌"
                )
                return
            success, message = await self.bot_manager.otp_manager.set_destroyer_state(
                user_id, account.get("name"), enabled
            )
            await self._send_response(event, message, "🛡️")
            # Log the operation
            logger.info(
                f"OTP destroyer {
                    'enabled' if enabled else 'disabled'} for user {user_id}, account {
                    account.get('name')}"
            )
        except Exception as e:
            logger.error(f"OTP destroyer command error for user {event.sender_id}: {e}")
            await self._send_response(
                event, "An error occurred while processing your request.", "❌"
            )

    async def _handle_otp_forward(self, event) -> None:
        """
        Handle OTP forwarding on/off command.
        Command: /otpforward on|off
        """
        try:
            user_id = event.sender_id
            state = event.pattern_match.group(1).lower()
            enabled = state == "on"
            account = await self._get_user_account(user_id)
            if not account:
                await self._send_response(event, self.MESSAGES["no_accounts"], "❌")
                return
            if not self._is_otp_manager_available():
                await self._send_response(
                    event, self.MESSAGES["service_unavailable"], "❌"
                )
                return
            success, message = await self.bot_manager.otp_manager.set_forwarding_state(
                user_id, account.get("name"), enabled
            )
            await self._send_response(event, message, "📨")
            # Log the operation
            logger.info(
                f"OTP forwarding {
                    'enabled' if enabled else 'disabled'} for user {user_id}, account {
                    account.get('name')}"
            )
        except Exception as e:
            logger.error(f"OTP forward command error for user {event.sender_id}: {e}")
            await self._send_response(
                event, "An error occurred while processing your request.", "❌"
            )

    async def _handle_otp_temp(self, event) -> None:
        """
        Handle temporary OTP passthrough command.
        Command: /otptemp
        Enables temporary OTP passthrough for 5 minutes.
        """
        try:
            user_id = event.sender_id
            account = await self._get_user_account(user_id)
            if not account:
                await self._send_response(event, self.MESSAGES["no_accounts"], "❌")
                return
            if not self._is_otp_manager_available():
                await self._send_response(
                    event, self.MESSAGES["service_unavailable"], "❌"
                )
                return
            success = await self.bot_manager.otp_manager.enable_temp_passthrough(
                user_id, account.get("name")
            )
            if success:
                await event.reply(self.MESSAGES["temp_success"])
                logger.info(
                    f"Temporary OTP passthrough enabled for user {user_id}, account {
                        account.get('name')}"
                )
            else:
                await self._send_response(event, self.MESSAGES["temp_failed"], "❌")
                logger.warning(
                    f"Failed to enable temporary OTP passthrough for user {user_id}"
                )
        except Exception as e:
            logger.error(f"OTP temp command error for user {event.sender_id}: {e}")
            await self._send_response(
                event, "An error occurred while processing your request.", "❌"
            )

    async def get_otp_status(self, user_id: int) -> Dict[str, Any]:
        """
        Get comprehensive OTP status for a user.
        Args:
            user_id: User's Telegram ID
        Returns:
            Dictionary containing OTP status information
        """
        try:
            account = await self._get_user_account(user_id)
            if not account:
                return {"success": False, "error": "No active accounts found"}
            if not self._is_otp_manager_available():
                return {"success": False, "error": "OTP Manager not available"}
            destroyer_enabled = account.get("otp_destroyer_enabled", False)
            forward_enabled = account.get("otp_forward_enabled", False)
            return {
                "success": True,
                "account_name": account.get("name"),
                "destroyer_enabled": destroyer_enabled,
                "forward_enabled": forward_enabled,
                "temp_passthrough_active": False,  # This would need to be checked from OTP manager
            }
        except Exception as e:
            logger.error(f"Error getting OTP status for user {user_id}: {e}")
            return {"success": False, "error": f"Status check failed: {str(e)}"}
