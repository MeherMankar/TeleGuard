"""Enhanced OTP Destroyer - Real-time login code invalidation

This module implements the core OTP Destroyer functionality that automatically
invalidates Telegram login codes to prevent unauthorized access.

How it works:
1. Listens for messages from Telegram's login service (user ID 777000)
2. Extracts login codes from these messages using regex patterns
3. Immediately calls account.invalidateSignInCodes to make codes unusable
4. Logs all activity and notifies the account owner

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import json
import logging
import re
import time
from typing import List, Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from telethon import events, functions

from .mongo_database import mongodb

logger = logging.getLogger(__name__)


class EnhancedOTPDestroyer:
    """Enhanced OTP destroyer with audit logging and security features"""

    # Regex to match 5-7 digit codes with optional hyphens/spaces, no letters
    CODE_REGEX = re.compile(r"(?<!\w)(\d(?:[-\s]?\d){4,6})(?!\w)")

    def __init__(self, bot_instance):
        self.bot = bot_instance

    def normalize_codes(self, raw_codes: List[str]) -> List[str]:
        """Normalize and deduplicate OTP codes"""
        normalized = []
        for code in raw_codes:
            # Remove all non-digit characters (hyphens, spaces, etc.)
            clean_code = re.sub(r"[^0-9]", "", code)
            # Telegram login codes are typically 5-7 digits
            if 5 <= len(clean_code) <= 7 and clean_code.isdigit():
                normalized.append(clean_code)
        # Return unique codes only
        return list(set(normalized))

    def extract_codes_from_message(self, message: str) -> List[str]:
        """Extract OTP codes from service message"""
        if not message:
            return []

        # Find all potential codes using regex
        found_codes = self.CODE_REGEX.findall(message)

        # Normalize and validate codes
        normalized = self.normalize_codes(found_codes) if found_codes else []

        if normalized:
            logger.debug(f"Extracted codes from message: {normalized}")

        return normalized

    async def setup_otp_listener(self, client, user_id: int, account_name: str):
        """Set up OTP destroyer listener for an account"""

        @client.on(events.NewMessage(from_users=777000))
        async def otp_destroyer_handler(event):
            try:
                # Check if OTP destroyer is enabled for this account
                account = await mongodb.db.accounts.find_one(
                    {"user_id": user_id, "name": account_name}
                )

                if not account or not account.get("otp_destroyer_enabled", False):
                    return

                    message = event.message.message or ""
                    codes = self.extract_codes_from_message(message)

                    if not codes:
                        return

                    logger.info(
                        f"🛡️ OTP Destroyer: Found {len(codes)} codes for {account_name}"
                    )

                    # Invalidate codes using Telegram API immediately
                    try:
                        result = await client(
                            functions.account.InvalidateSignInCodesRequest(codes=codes)
                        )

                        # Log the action
                        audit_entry = {
                            "action": "invalidate_codes",
                            "codes": codes,
                            "result": bool(result),
                            "message_id": event.message.id,
                            "raw_message": message[:200],  # First 200 chars
                            "timestamp": int(time.time()),
                        }

                        # Update account with audit entry
                        from bson import ObjectId

                        await mongodb.db.accounts.update_one(
                            {"_id": account["_id"]},
                            {
                                "$push": {"audit_log": audit_entry},
                                "$set": {
                                    "otp_destroyed_at": time.strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    )
                                },
                            },
                        )

                        # Notify owner immediately
                        await self._send_destruction_alert(
                            user_id, account_name, codes, bool(result)
                        )

                        logger.info(
                            f"✅ Successfully invalidated {len(codes)} codes for {account_name}"
                        )

                    except Exception as e:
                        logger.error(
                            f"❌ Failed to invalidate codes for {account_name}: {e}"
                        )

                        # Log the failure
                        audit_entry = {
                            "action": "invalidate_error",
                            "codes": codes,
                            "error": str(e),
                            "timestamp": int(time.time()),
                        }

                        # Update account with error audit entry
                        await mongodb.db.accounts.update_one(
                            {"_id": account["_id"]},
                            {"$push": {"audit_log": audit_entry}},
                        )

                        # Still notify about the attempt
                        await self._send_destruction_alert(
                            user_id, account_name, codes, False
                        )

            except Exception as e:
                logger.error(f"OTP destroyer handler error for {account_name}: {e}")

    async def _send_destruction_alert(
        self, user_id: int, account_name: str, codes: List[str], success: bool
    ):
        """Send alert about OTP code destruction"""
        codes_str = ", ".join(codes)
        status = "✅ DESTROYED" if success else "❌ FAILED"

        alert_message = (
            f"🛡️ **OTP DESTROYER ACTIVATED**\n\n"
            f"📱 **Account:** {account_name}\n"
            f"🎯 **Status:** {status}\n"
            f"🔢 **Codes:** `{codes_str}`\n\n"
        )

        if success:
            alert_message += (
                f"✅ **Login codes permanently invalidated!**\n"
                f"🔒 Nobody can use these codes to sign in.\n\n"
            )
        else:
            alert_message += (
                f"❌ **Failed to invalidate codes!**\n"
                f"⚠️ Codes may still be usable for login.\n\n"
            )

        alert_message += f"🕒 **Time:** {time.strftime('%Y-%m-%d %H:%M:%S')}"

        try:
            await self.bot.send_message(user_id, alert_message, parse_mode="markdown")
        except Exception as e:
            logger.error(f"Failed to send destruction alert: {e}")
            # Fallback without markdown
            try:
                simple_message = (
                    f"🛡️ OTP DESTROYER: {status} for {account_name}. Codes: {codes_str}"
                )
                await self.bot.send_message(user_id, simple_message)
            except Exception as e2:
                logger.error(f"Failed to send fallback alert: {e2}")

    async def enable_otp_destroyer(
        self, user_id: int, account_id: str
    ) -> tuple[bool, str]:
        """Enable OTP destroyer for an account"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                return False, "Account not found"

            audit_entry = {
                "action": "enable_otp_destroyer",
                "user_id": user_id,
                "timestamp": int(time.time()),
            }

            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {
                    "$set": {"otp_destroyer_enabled": True},
                    "$push": {"audit_log": audit_entry},
                },
            )

            logger.info(f"🛡️ OTP destroyer enabled for account {account['name']}")
            return (
                True,
                f"OTP Destroyer enabled for {account['name']}. All login codes will now be automatically invalidated.",
            )

        except Exception as e:
            logger.error(f"Failed to enable OTP destroyer: {e}")
            return False, f"Error: {str(e)}"

    async def disable_otp_destroyer(
        self, user_id: int, account_id: str, auth_password: str = None
    ) -> tuple[bool, str]:
        """Disable OTP destroyer with authentication"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                return False, "Account not found"

            # Check if disable auth is required
            if account.get("otp_destroyer_disable_auth"):
                if not auth_password:
                    return (
                        False,
                        "Password required to disable OTP destroyer. Set one first if not configured.",
                    )

                # Verify password hash
                ph = PasswordHasher()
                try:
                    ph.verify(account["otp_destroyer_disable_auth"], auth_password)
                except VerifyMismatchError:
                    return (
                        False,
                        "Invalid password. OTP Destroyer remains enabled for security.",
                    )

            audit_entry = {
                "action": "disable_otp_destroyer",
                "user_id": user_id,
                "auth_used": bool(auth_password),
                "timestamp": int(time.time()),
            }

            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {
                    "$set": {"otp_destroyer_enabled": False},
                    "$push": {"audit_log": audit_entry},
                },
            )

            logger.info(f"🔴 OTP destroyer disabled for account {account['name']}")
            return (
                True,
                f"OTP Destroyer disabled for {account['name']}. Login codes will no longer be automatically invalidated.",
            )

        except Exception as e:
            logger.error(f"Failed to disable OTP destroyer: {e}")
            return False, f"Error: {str(e)}"

    async def set_disable_password(
        self, user_id: int, account_id: str, password: str
    ) -> tuple[bool, str]:
        """Set password required to disable OTP destroyer"""
        try:
            if len(password) < 6:
                return False, "Password must be at least 6 characters long"

            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                return False, "Account not found"

            ph = PasswordHasher()
            password_hash = ph.hash(password)

            audit_entry = {
                "action": "set_disable_password",
                "user_id": user_id,
                "timestamp": int(time.time()),
            }

            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {
                    "$set": {"otp_destroyer_disable_auth": password_hash},
                    "$push": {"audit_log": audit_entry},
                },
            )

            return (
                True,
                "Disable password set successfully. This password will be required to turn off OTP Destroyer.",
            )

        except Exception as e:
            logger.error(f"Failed to set disable password: {e}")
            return False, f"Error: {str(e)}"
