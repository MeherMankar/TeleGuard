from datetime import datetime, timezone
import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


def otp_expiry_fields(expires_at: int) -> dict:
    timestamp = int(expires_at)
    return {
        "expires_at": timestamp,
        "expires_at_dt": datetime.fromtimestamp(timestamp, tz=timezone.utc),
    }


class OtpBypassContext:
    """
    Async context manager that fully suppresses the OTP destroyer for a
    specific phone number while the bot is performing an internal action
    (login, session creation, vault creation, fresh backup, etc.).

    Usage:
        async with OtpBypassContext(user_id, phone, duration_seconds=120):
            client, hash = await session_login._request_otp_code(phone)
            otp = await fetch_otp(...)
            await client.sign_in(phone, otp, ...)

    What it does on __aenter__:
      1. Disables otp_destroyer_enabled on ALL accounts for user_id so no
         bystander account can destroy the incoming code.
      2. Writes a wildcard otp_protections entry for the target phone so
         even if another instance re-enables the destroyer mid-flight the
         allowlist check in protection_manager still passes.
      3. Sets pending_actions[user_id] = {action:"session_creation", phone}
         so _has_active_otp_auth_flow returns True.

    What it does on __aexit__:
      1. Restores each account's otp_destroyer_enabled to its original value.
      2. Removes the wildcard otp_protections entry.
      3. Clears the pending_actions entry.

    Safe to nest: each call tracks its own original states independently.
    Safe on failure: __aexit__ always runs (use as `async with`, or in try/finally).
    """

    def __init__(
        self,
        bot_manager,
        user_id: int,
        phone: str,
        duration_seconds: int = 180,
        reason: str = "bot_internal",
    ):
        self._bot_manager = bot_manager
        self._user_id = user_id
        self._phone = phone
        self._duration = duration_seconds
        self._reason = reason
        self._original_states: dict = {}   # {str(account_id): bool}
        self._entered = False

    async def __aenter__(self):
        from ..core.mongo_database import mongodb

        try:
            # 1. Snapshot then disable OTP destroyer on all user accounts
            accounts = await mongodb.db.accounts.find(
                {"user_id": self._user_id}
            ).to_list(None)
            self._original_states = {
                str(acc["_id"]): acc.get("otp_destroyer_enabled", False)
                for acc in accounts
            }
            await mongodb.db.accounts.update_many(
                {"user_id": self._user_id},
                {"$set": {"otp_destroyer_enabled": False}},
            )

            # 2. Write wildcard allowlist entry for the target phone
            expires_at = int(time.time()) + self._duration
            await mongodb.db.otp_protections.update_one(
                {
                    "phone": self._phone,
                    "user_id": self._user_id,
                    "wildcard": True,
                    "reason": self._reason,
                },
                {
                    "$set": {
                        "phone": self._phone,
                        "user_id": self._user_id,
                        "wildcard": True,
                        "reason": self._reason,
                        **otp_expiry_fields(expires_at),
                    }
                },
                upsert=True,
            )

            # 3. Mark pending_actions so _has_active_otp_auth_flow returns True
            pending = getattr(self._bot_manager, "pending_actions", {})
            # Only set if not already in a user-initiated auth flow
            if self._user_id not in pending:
                pending[self._user_id] = {
                    "action": "session_creation",
                    "phone": self._phone,
                    "_bypass_ctx": True,  # marker so __aexit__ knows to remove it
                }

            self._entered = True
            logger.debug(
                "OtpBypassContext entered for %s / %s (reason=%s, duration=%ds)",
                self._user_id, self._phone, self._reason, self._duration,
            )
        except Exception as e:
            logger.warning(
                "OtpBypassContext __aenter__ failed for %s/%s: %s — continuing without bypass",
                self._user_id, self._phone, e,
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not self._entered:
            return False

        from bson import ObjectId
        from ..core.mongo_database import mongodb

        # 1. Restore each account's original otp_destroyer_enabled
        for acc_id_str, was_enabled in self._original_states.items():
            try:
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(acc_id_str), "user_id": self._user_id},
                    {"$set": {"otp_destroyer_enabled": was_enabled}},
                )
            except Exception as e:
                logger.warning(
                    "OtpBypassContext: could not restore destroyer for %s: %s",
                    acc_id_str, e,
                )

        # 2. Remove wildcard allowlist entry
        try:
            await mongodb.db.otp_protections.delete_many(
                {
                    "phone": self._phone,
                    "user_id": self._user_id,
                    "wildcard": True,
                    "reason": self._reason,
                }
            )
        except Exception as e:
            logger.warning(
                "OtpBypassContext: could not remove allowlist entry for %s: %s",
                self._phone, e,
            )

        # 3. Remove the pending_actions entry if we set it
        try:
            pending = getattr(self._bot_manager, "pending_actions", {})
            entry = pending.get(self._user_id)
            if isinstance(entry, dict) and entry.get("_bypass_ctx"):
                pending.pop(self._user_id, None)
        except Exception:
            pass

        logger.debug(
            "OtpBypassContext exited for %s / %s (reason=%s)",
            self._user_id, self._phone, self._reason,
        )
        return False  # don't suppress exceptions
