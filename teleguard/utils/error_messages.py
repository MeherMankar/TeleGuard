"""User-friendly error message mapping"""

from typing import Dict

ERROR_MESSAGES: Dict[str, str] = {
    # Authentication errors
    "PHONE_NUMBER_INVALID": "❌ Invalid phone number. Please use format: +1234567890",
    "PHONE_CODE_INVALID": "❌ Invalid verification code. Please check and try again.",
    "PHONE_CODE_EXPIRED": "❌ Verification code expired. Please request a new one.",
    "SESSION_PASSWORD_NEEDED": "🔐 Two-factor authentication required. Please enter your password.",
    "PASSWORD_HASH_INVALID": "❌ Incorrect 2FA password. Please try again.",
    # Rate limiting
    "FLOOD_WAIT": "⏳ Too many requests. Please wait {} seconds before trying again.",
    "SLOWMODE_WAIT": "⏳ Slow mode active. Please wait {} seconds.",
    # Channel/Group errors
    "CHANNEL_PRIVATE": "🔒 This channel is private or doesn't exist.",
    "USER_ALREADY_PARTICIPANT": "✅ You're already a member of this channel.",
    "INVITE_HASH_EXPIRED": "❌ Invite link has expired. Please get a new one.",
    "CHAT_ADMIN_REQUIRED": "❌ Admin permissions required for this action.",
    # Account errors
    "USER_DEACTIVATED": "❌ This account has been deactivated.",
    "AUTH_KEY_UNREGISTERED": "❌ Session expired. Please re-add your account.",
    "USER_MIGRATE": "🔄 Account migrated. Please reconnect.",
    # Generic errors
    "NETWORK_ERROR": "🌐 Network error. Please check your connection and try again.",
    "TIMEOUT": "⏰ Request timed out. Please try again.",
    "UNKNOWN_ERROR": "❌ Something went wrong. Please try again or contact support.",
}


def get_user_friendly_error(error_type: str, **kwargs) -> str:
    """Get user-friendly error message"""
    message = ERROR_MESSAGES.get(error_type, ERROR_MESSAGES["UNKNOWN_ERROR"])

    # Format message with parameters if needed
    try:
        return message.format(**kwargs)
    except KeyError as e:
        import logging

        logging.getLogger(__name__).error(
            f"Missing format key in error message '{message}': {e}"
        )
        return message
