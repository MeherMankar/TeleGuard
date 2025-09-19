"""Secure 2FA helpers using Telethon's high-level API

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import hashlib
import logging
import time
from typing import Optional, Tuple

from telethon import errors, TelegramClient

logger = logging.getLogger(__name__)


class Secure2FAManager:
    """Secure 2FA management using Telethon's built-in helpers"""

    def __init__(self):
        self.rate_limits = {}  # user_id -> last_attempt_time
        self.failed_attempts = {}  # user_id -> count
        self.MAX_ATTEMPTS = 5
        self.COOLDOWN_SECONDS = 3600  # 1 hour

    async def set_2fa_password(
        self,
        client: TelegramClient,
        new_password: str,
        hint: str = "",
        email: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Set a new 2FA password using Telethon's secure edit_2fa method.

        Args:
            client: Authenticated Telethon client
            new_password: New 2FA password (4+ characters)
            hint: Optional password hint
            email: Optional recovery email

        Returns:
            (success: bool, message: str)
        """
        try:
            # Validate password
            if len(new_password) < 4:
                return False, "Password must be at least 4 characters long"

            if len(new_password) > 256:
                return False, "Password too long (max 256 characters)"

            # Use Telethon's secure edit_2fa method
            await client.edit_2fa(
                new_password=new_password, hint=hint or "", email=email
            )

            logger.info("2FA password set successfully using Telethon helper")
            return True, "2FA password set successfully"

        except errors.EmailUnconfirmedError as e:
            # Email confirmation required
            logger.info(f"Email confirmation required: {e}")
            import html
            safe_email = html.escape(str(email)) if email else "your email"
            return (
                False,
                f"Email confirmation required. A code was sent to {safe_email}. Please confirm and try again.",
            )

        except errors.PasswordHashInvalidError:
            logger.warning("Invalid password hash during 2FA setup")
            return False, "Invalid password format. Please try again."

        except errors.PasswordTooFreshError:
            logger.warning("Password changed too recently")
            return False, "Please wait before changing password again (rate limited)."

        except errors.EmailInvalidError:
            logger.warning("Invalid email provided")
            return False, "Invalid email address provided."

        except Exception as e:
            logger.error(f"Unexpected error setting 2FA: {type(e).__name__}: {e}")
            return False, f"Failed to set 2FA: {type(e).__name__}"

    async def change_2fa_password(
        self,
        client: TelegramClient,
        current_password: str,
        new_password: str,
        hint: str = "",
        email: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Change existing 2FA password using Telethon's secure method.

        Args:
            client: Authenticated Telethon client
            current_password: Current 2FA password
            new_password: New 2FA password
            hint: Optional new password hint
            email: Optional recovery email

        Returns:
            (success: bool, message: str)
        """
        try:
            # Validate new password
            if len(new_password) < 4:
                return False, "New password must be at least 4 characters long"

            # Use Telethon's secure edit_2fa method with current password
            await client.edit_2fa(
                current_password=current_password,
                new_password=new_password,
                hint=hint or "",
                email=email,
            )

            logger.info("2FA password changed successfully")
            return True, "2FA password changed successfully"

        except errors.PasswordHashInvalidError:
            logger.warning("Invalid current password provided")
            return False, "Current password is incorrect"

        except errors.EmailUnconfirmedError as e:
            logger.info(f"Email confirmation required: {e}")
            import html
            safe_email = html.escape(str(email)) if email else "your email"
            return (
                False,
                f"Email confirmation required. A code was sent to {safe_email}. Please confirm and try again.",
            )

        except errors.PasswordTooFreshError:
            logger.warning("Password changed too recently")
            return False, "Please wait before changing password again (rate limited)."

        except Exception as e:
            logger.error(f"Unexpected error changing 2FA: {type(e).__name__}: {e}")
            return False, f"Failed to change 2FA: {type(e).__name__}"

    async def remove_2fa_password(
        self, client: TelegramClient, current_password: str
    ) -> Tuple[bool, str]:
        """
        Remove 2FA password using Telethon's secure method.

        Args:
            client: Authenticated Telethon client
            current_password: Current 2FA password

        Returns:
            (success: bool, message: str)
        """
        try:
            # Use Telethon's edit_2fa with new_password=None to remove
            await client.edit_2fa(current_password=current_password, new_password=None)

            logger.info("2FA password removed successfully")
            return True, "2FA password removed successfully"

        except errors.PasswordHashInvalidError:
            logger.warning("Invalid current password for 2FA removal")
            return False, "Current password is incorrect"

        except Exception as e:
            logger.error(f"Unexpected error removing 2FA: {type(e).__name__}: {e}")
            return False, f"Failed to remove 2FA: {type(e).__name__}"

    async def check_2fa_status(self, client: TelegramClient) -> Tuple[bool, dict]:
        """
        Check current 2FA status for account.

        Args:
            client: Authenticated Telethon client

        Returns:
            (success: bool, status_info: dict)
        """
        try:
            from telethon import functions

            # Get password info
            password_info = await client(functions.account.GetPasswordRequest())

            has_password = password_info.has_password
            hint = password_info.hint or "No hint set"
            has_recovery = password_info.has_recovery

            status = {
                "has_password": has_password,
                "hint": hint,
                "has_recovery": has_recovery,
                "email_unconfirmed_pattern": getattr(
                    password_info, "email_unconfirmed_pattern", None
                ),
            }

            return True, status

        except Exception as e:
            logger.error(f"Failed to check 2FA status: {e}")
            return False, {}

    def check_rate_limit(self, user_id: int) -> Tuple[bool, str]:
        """
        Check if user is rate limited for 2FA operations.

        Args:
            user_id: Telegram user ID

        Returns:
            (allowed: bool, message: str)
        """
        current_time = time.time()

        # Check failed attempts
        failed_count = self.failed_attempts.get(user_id, 0)
        if failed_count >= self.MAX_ATTEMPTS:
            last_attempt = self.rate_limits.get(user_id, 0)
            time_since_last = current_time - last_attempt

            if time_since_last < self.COOLDOWN_SECONDS:
                remaining = int(self.COOLDOWN_SECONDS - time_since_last)
                minutes = remaining // 60
                return (
                    False,
                    f"Too many failed attempts. Try again in {minutes} minutes.",
                )

        return True, "OK"

    def record_attempt(self, user_id: int, success: bool):
        """Record 2FA attempt for rate limiting"""
        current_time = time.time()
        self.rate_limits[user_id] = current_time

        if success:
            # Reset failed attempts on success
            self.failed_attempts.pop(user_id, None)
        else:
            # Increment failed attempts
            self.failed_attempts[user_id] = self.failed_attempts.get(user_id, 0) + 1

    def hash_password_for_storage(self, password: str) -> str:
        """
        Hash password for secure database storage.

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_stored_password(self, password: str, stored_hash: str) -> bool:
        """
        Verify password against stored hash.

        Args:
            password: Plain text password
            stored_hash: Stored password hash

        Returns:
            True if password matches
        """
        return self.hash_password_for_storage(password) == stored_hash


class SecureInputManager:
    """Manages secure password input via inline keyboards"""

    def __init__(self):
        self.pending_inputs = {}  # user_id -> input_data

    def get_numeric_keypad(self, callback_prefix: str) -> list:
        """Get numeric keypad buttons for secure input"""
        from telethon import Button

        return [
            [
                Button.inline("1", f"{callback_prefix}:1"),
                Button.inline("2", f"{callback_prefix}:2"),
                Button.inline("3", f"{callback_prefix}:3"),
            ],
            [
                Button.inline("4", f"{callback_prefix}:4"),
                Button.inline("5", f"{callback_prefix}:5"),
                Button.inline("6", f"{callback_prefix}:6"),
            ],
            [
                Button.inline("7", f"{callback_prefix}:7"),
                Button.inline("8", f"{callback_prefix}:8"),
                Button.inline("9", f"{callback_prefix}:9"),
            ],
            [
                Button.inline("0", f"{callback_prefix}:0"),
                Button.inline("⌫", f"{callback_prefix}:back"),
                Button.inline("✅", f"{callback_prefix}:ok"),
            ],
            [Button.inline("❌ Cancel", f"{callback_prefix}:cancel")],
        ]

    def get_full_keypad(self, callback_prefix: str) -> list:
        """Get full alphanumeric keypad for secure input"""
        from telethon import Button

        return [
            [
                Button.inline("1", f"{callback_prefix}:1"),
                Button.inline("2", f"{callback_prefix}:2"),
                Button.inline("3", f"{callback_prefix}:3"),
                Button.inline("4", f"{callback_prefix}:4"),
                Button.inline("5", f"{callback_prefix}:5"),
            ],
            [
                Button.inline("6", f"{callback_prefix}:6"),
                Button.inline("7", f"{callback_prefix}:7"),
                Button.inline("8", f"{callback_prefix}:8"),
                Button.inline("9", f"{callback_prefix}:9"),
                Button.inline("0", f"{callback_prefix}:0"),
            ],
            [
                Button.inline("q", f"{callback_prefix}:q"),
                Button.inline("w", f"{callback_prefix}:w"),
                Button.inline("e", f"{callback_prefix}:e"),
                Button.inline("r", f"{callback_prefix}:r"),
                Button.inline("t", f"{callback_prefix}:t"),
            ],
            [
                Button.inline("y", f"{callback_prefix}:y"),
                Button.inline("u", f"{callback_prefix}:u"),
                Button.inline("i", f"{callback_prefix}:i"),
                Button.inline("o", f"{callback_prefix}:o"),
                Button.inline("p", f"{callback_prefix}:p"),
            ],
            [
                Button.inline("a", f"{callback_prefix}:a"),
                Button.inline("s", f"{callback_prefix}:s"),
                Button.inline("d", f"{callback_prefix}:d"),
                Button.inline("f", f"{callback_prefix}:f"),
                Button.inline("g", f"{callback_prefix}:g"),
            ],
            [
                Button.inline("h", f"{callback_prefix}:h"),
                Button.inline("j", f"{callback_prefix}:j"),
                Button.inline("k", f"{callback_prefix}:k"),
                Button.inline("l", f"{callback_prefix}:l"),
                Button.inline("⇧", f"{callback_prefix}:shift"),
            ],
            [
                Button.inline("z", f"{callback_prefix}:z"),
                Button.inline("x", f"{callback_prefix}:x"),
                Button.inline("c", f"{callback_prefix}:c"),
                Button.inline("v", f"{callback_prefix}:v"),
                Button.inline("b", f"{callback_prefix}:b"),
            ],
            [
                Button.inline("n", f"{callback_prefix}:n"),
                Button.inline("m", f"{callback_prefix}:m"),
                Button.inline("⌫", f"{callback_prefix}:back"),
                Button.inline("✅ Done", f"{callback_prefix}:ok"),
                Button.inline("❌ Cancel", f"{callback_prefix}:cancel"),
            ],
        ]

    def start_secure_input(
        self, user_id: int, input_type: str, account_id: int = None
    ) -> str:
        """Start secure input session"""
        session_id = f"{user_id}_{int(time.time())}"
        self.pending_inputs[user_id] = {
            "session_id": session_id,
            "type": input_type,
            "account_id": account_id,
            "buffer": "",
            "started_at": time.time(),
        }
        return session_id

    def handle_keypad_input(self, user_id: int, key: str) -> Tuple[bool, str, str]:
        """
        Handle keypad input.

        Returns:
            (completed: bool, buffer: str, action: str)
        """
        if user_id not in self.pending_inputs:
            return False, "", "no_session"

        session = self.pending_inputs[user_id]

        if key == "back":
            # Remove last character
            session["buffer"] = session["buffer"][:-1]
            return False, session["buffer"], "backspace"

        elif key == "ok":
            # Complete input
            buffer = session["buffer"]
            self.pending_inputs.pop(user_id, None)
            return True, buffer, "complete"

        elif key == "cancel":
            # Cancel input
            self.pending_inputs.pop(user_id, None)
            return True, "", "cancel"

        elif key == "shift":
            # Toggle shift mode
            session["shift_mode"] = not session.get("shift_mode", False)
            return False, session["buffer"], "shift_toggle"

        else:
            # Add character to buffer
            if len(session["buffer"]) < 256:  # Max password length
                char = key.upper() if session.get("shift_mode", False) else key
                session["buffer"] += char
                # Auto-disable shift after one character
                if session.get("shift_mode", False):
                    session["shift_mode"] = False
            return False, session["buffer"], "input"

    def get_masked_display(self, buffer: str) -> str:
        """Get masked display of password buffer"""
        return "•" * len(buffer)

    def cleanup_expired_sessions(self):
        """Clean up expired input sessions"""
        current_time = time.time()
        expired_users = []

        for user_id, session in self.pending_inputs.items():
            if current_time - session["started_at"] > 600:  # 10 minutes timeout
                expired_users.append(user_id)

        for user_id in expired_users:
            self.pending_inputs.pop(user_id, None)
