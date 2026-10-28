"""Protection Manager - Orchestrates OTP Destroyer and Session Destroyer systems"""

import asyncio
import hashlib
import logging
import os
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Set, Any

from telethon import events, functions

from .mongo_database import mongodb
from .session_destroyer import SessionDestroyer
from ..services.protection_storage import ProtectionStorage
from ..services.protection_notifier import ProtectionNotifier
from ..utils.crypto_utils import DataEncryption

logger = logging.getLogger(__name__)

class ProtectionManager:
    """Manages both OTP Destroyer and Session Destroyer protection systems"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        
        # Sub-modules
        self.session_destroyer = SessionDestroyer(bot_manager)
        self.notifier = ProtectionNotifier(self.bot)
        
        # --- OTP Destroyer State (Legacy Logic) ---
        self.temp_passthrough: Dict[int, Dict[str, float]] = {}
        self.registered_handlers = set()
        self.processed_otps = set()
        self.fresh_session_otps = set()
        self.sent_notifications = set()
        self.last_cleanup = time.time()
        self._processed_messages = set()
        self._client_handlers = {}
        self._temp_bypass_tasks: Dict[tuple[int, str], asyncio.Task] = {}

    async def start(self):
        """Start the protection manager and its background workers"""
        await self._restore_or_schedule_temp_bypasses()
        # On cloud platforms (Koyeb, Railway, Heroku) a rolling restart keeps
        # the old instance alive for ~30 s.  Delaying watcher startup avoids
        # AUTH_KEY_DUPLICATED errors from GetAuthorizationsRequest.
        is_cloud = (
            os.environ.get("DYNO")
            or os.environ.get("KOYEB_DEPLOYMENT_ID")
            or os.environ.get("RAILWAY_ENVIRONMENT")
        )
        if is_cloud:
            logger.info("☁️ Cloud environment detected — delaying Session Destroyer start by 50s to allow rolling restart to complete")
            await asyncio.sleep(50)
        await self.session_destroyer.start_all()
        logger.info("🛡️ Protection Manager started (OTP & Session systems active)")

    async def stop(self):
        """Stop all background workers"""
        await self.session_destroyer.stop_all()
        tasks = list(self._temp_bypass_tasks.values())
        self._temp_bypass_tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _notify_webapp_otp_event(
        self, user_id: int, account_name: str, action: str
    ) -> None:
        try:
            from backend.notifier import notify

            await notify(user_id, {
                "type": "otp_event",
                "account_name": account_name,
                "action": action,
            })
        except Exception:
            logger.exception("Could not notify webapp about OTP event")

    async def _restore_or_schedule_temp_bypasses(self):
        """Resume persisted temporary-bypass expiry handling after startup."""
        accounts = await mongodb.db.accounts.find(
            {"otp_temp_passthrough": True}
        ).to_list(length=None)
        now = time.time()
        for account in accounts:
            account_id = str(account["_id"])
            try:
                expiry = float(account.get("temp_passthrough_expiry") or 0)
            except (TypeError, ValueError):
                expiry = 0
            if expiry <= now:
                await self._restore_temp_passthrough(
                    account["user_id"], account_id, account
                )
            else:
                self._schedule_temp_bypass_expiry(
                    account["user_id"], account_id, expiry
                )

    def _schedule_temp_bypass_expiry(
        self, user_id: int, account_id: str, expiry: float
    ):
        key = (user_id, account_id)
        existing_task = self._temp_bypass_tasks.get(key)
        if existing_task and not existing_task.done():
            return
        task = asyncio.create_task(
            self._expire_temp_bypass(user_id, account_id, expiry)
        )
        self._temp_bypass_tasks[key] = task

    async def _expire_temp_bypass(
        self, user_id: int, account_id: str, expiry: float
    ):
        key = (user_id, account_id)
        try:
            await asyncio.sleep(max(0, expiry - time.time()))
            account = await mongodb.db.accounts.find_one(
                {"_id": self._object_id(account_id), "user_id": user_id}
            )
            if not account or not account.get("otp_temp_passthrough"):
                return
            try:
                current_expiry = float(
                    account.get("temp_passthrough_expiry") or 0
                )
            except (TypeError, ValueError):
                current_expiry = 0
            if current_expiry == expiry:
                await self._restore_temp_passthrough(
                    user_id, account_id, account
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Failed to restore expired temporary OTP bypass for account %s",
                account_id,
            )
            try:
                await self.bot.send_message(
                    user_id,
                    "⚠️ Automatic OTP-bypass restoration failed. Please open "
                    "Protection Manager and review this account's settings.",
                )
            except Exception:
                logger.exception(
                    "Could not notify user %s about temporary bypass restoration",
                    user_id,
                )
        finally:
            if self._temp_bypass_tasks.get(key) is asyncio.current_task():
                self._temp_bypass_tasks.pop(key, None)

    @staticmethod
    def _object_id(account_id: str):
        from bson import ObjectId

        return ObjectId(account_id)

    # --- OTP Destroyer Logic (Ported from OTPManager) ---

    def _periodic_cleanup(self):
        """Periodically clean up tracking sets to prevent memory buildup"""
        current_time = time.time()
        if current_time - self.last_cleanup > 300:
            if len(self.processed_otps) > 100:
                self.processed_otps = set(list(self.processed_otps)[-50:])
            if len(self.sent_notifications) > 100:
                self.sent_notifications = set(list(self.sent_notifications)[-50:])
            if len(self.fresh_session_otps) > 50:
                self.fresh_session_otps = set(list(self.fresh_session_otps)[-25:])
            self.last_cleanup = current_time

    def register_handlers(self):
        """Register OTP message handler for all user clients"""
        if hasattr(self.bot_manager, "registered_handlers"):
            self.bot_manager.registered_handlers["otp"].clear()

        # Remove ALL existing Telethon handlers before re-registering so we
        # never accumulate duplicate copies on the same client (each call to
        # toggle_destroyer / toggle_forward previously added another copy).
        for (uid, aname), handler in list(self._client_handlers.items()):
            try:
                client = self.bot_manager.user_clients.get(uid, {}).get(aname)
                if client and handler:
                    client.remove_event_handler(handler)
            except Exception:
                pass
        self._client_handlers.clear()
        self.registered_handlers.clear()

        handler_count = 0
        for user_id, clients in self.user_clients.items():
            for account_name, client in clients.items():
                handler_key = f"{user_id}:{account_name}"
                if not client or not hasattr(client, "is_connected") or not client.is_connected():
                    continue
                try:
                    client.add_event_handler(
                        self._handle_otp_message, events.NewMessage(chats=[777000, 42777])
                    )
                    self._client_handlers[(int(user_id), str(account_name))] = self._handle_otp_message
                    self.registered_handlers.add(handler_key)
                    handler_count += 1
                except Exception as e:
                    logger.error(f"Failed to register OTP handler for {handler_key}: {e}")

        if hasattr(self.bot_manager, "registered_handlers"):
            for handler_key in self.registered_handlers:
                self.bot_manager.registered_handlers["otp"].add(handler_key)

    def register_handler_for_client(
        self, user_id: int, account_name: str, client
    ) -> bool:
        """Register OTP handler for a specific client"""
        if not client or not client.is_connected():
            return False
        handler_key = f"{user_id}:{account_name}"
        if handler_key in self.registered_handlers:
            return True
        
        try:
            client.add_event_handler(
                self._handle_otp_message, events.NewMessage(chats=[777000, 42777])
            )
            self._client_handlers[(int(user_id), str(account_name))] = self._handle_otp_message
            self.registered_handlers.add(handler_key)
            if hasattr(self.bot_manager, "registered_handlers"):
                self.bot_manager.registered_handlers["otp"].add(handler_key)
            logger.debug(f"Registered OTP handler for {handler_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to register OTP handler for {handler_key}: {e}")
            return False

    def unregister_handler_for_client(self, user_id: int, account_name: str, client):
        """Unregister OTP handler for a specific client if previously registered"""
        try:
            key = (int(user_id), str(account_name))
            handler = self._client_handlers.pop(key, None)
            if handler and client:
                try:
                    client.remove_event_handler(handler)
                    logger.debug(f"Removed OTP event handler for {user_id}:{account_name}")
                except Exception as e:
                    logger.error(f"Failed to remove event handler for {key}: {e}")

            handler_key = f"{user_id}:{account_name}"
            self.registered_handlers.discard(handler_key)
            if hasattr(self.bot_manager, "registered_handlers"):
                self.bot_manager.registered_handlers["otp"].discard(handler_key)
        except Exception as e:
            logger.error(f"Error unregistering handler for {user_id}:{account_name}: {e}")

    def _is_login_code(self, message_text: str) -> bool:
        patterns = [r"Login code", r"login code", r"verification code", r"Verification code"]
        return any(re.search(pattern, message_text, re.IGNORECASE) for pattern in patterns)

    def _extract_otp_code(self, message_text: str) -> Optional[str]:
        patterns = [r"/?\b(\d{5,7})\b", r"/?\b(\d{2,3}[-\s]\d{2,4})\b"]
        for pattern in patterns:
            match = re.search(pattern, message_text)
            if match:
                code = re.sub(r"[^0-9]", "", match.group(1).lstrip("/"))
                if 5 <= len(code) <= 7:
                    return code
        return None

    @staticmethod
    def _normalize_phone(phone: Any) -> str:
        return re.sub(r"\D", "", str(phone or ""))

    def _has_active_otp_auth_flow(self, user_id: int, phone: Any) -> bool:
        normalized_phone = self._normalize_phone(phone)
        if not normalized_phone:
            return False

        pending_actions = getattr(self.bot_manager, "pending_actions", {})
        action = pending_actions.get(user_id) or pending_actions.get(str(user_id))
        if (
            isinstance(action, dict)
            and action.get("action")
            in {
                "verify_otp",
                "phone_login",
                "2fa_password",
                "session_creation",
                "session_creation_2fa_password",
            }
            and self._normalize_phone(action.get("phone")) == normalized_phone
        ):
            return True

        pending_sessions = getattr(self.bot_manager, "pending_fresh_sessions", {})
        session = pending_sessions.get(user_id) or pending_sessions.get(str(user_id))
        return (
            isinstance(session, dict)
            and self._normalize_phone(session.get("phone")) == normalized_phone
        )

    def _has_pending_fresh_session(self, user_id: int, phone: Any) -> bool:
        pending_sessions = getattr(self.bot_manager, "pending_fresh_sessions", {})
        session = pending_sessions.get(user_id) or pending_sessions.get(str(user_id))
        return (
            isinstance(session, dict)
            and self._normalize_phone(session.get("phone"))
            == self._normalize_phone(phone)
            and bool(self._normalize_phone(phone))
        )

    async def _find_account_for_message(self, event) -> Optional[tuple]:
        """
        Find which account received this OTP message by matching the Telethon client.
        Returns (user_id, account_name, account_dict) or None.
        """
        try:
            from ..utils.crypto_utils import DataEncryption
            client = event.client

            # Use the cached telegram_id (stored at connect time) to avoid
            # a live get_me() API call on every OTP message.
            client_tg_id = None
            tg_id_cache = getattr(self.bot_manager, "_client_tg_ids", {})
            for (uid, aname), tg_id in tg_id_cache.items():
                if self.bot_manager.user_clients.get(uid, {}).get(aname) is client:
                    client_tg_id = tg_id
                    break

            # Fallback: call get_me() only when the cache misses
            if client_tg_id is None:
                try:
                    me = await client.get_me()
                    client_tg_id = me.id if me else None
                    # Populate cache for next time
                    if client_tg_id:
                        for user_id, clients in self.user_clients.items():
                            for account_name, user_client in clients.items():
                                if user_client is client:
                                    tg_id_cache[(user_id, account_name)] = client_tg_id
                except Exception:
                    pass

            for user_id, clients in self.user_clients.items():
                for account_name, user_client in clients.items():
                    if user_client != client:
                        continue

                    account = None

                    # 1. Try by telegram_id (plain, most reliable)
                    if client_tg_id:
                        account = await mongodb.db.accounts.find_one({
                            "user_id": int(user_id),
                            "telegram_id": client_tg_id,
                        })

                    # 2. Fallback — plain name / phone / display_name
                    if not account:
                        account = await mongodb.db.accounts.find_one({
                            "user_id": int(user_id),
                            "$or": [
                                {"name": str(account_name)},
                                {"phone": str(account_name)},
                                {"display_name": str(account_name)},
                            ]
                        })

                    if account:
                        decrypted = DataEncryption.decrypt_account_data(dict(account))
                        decrypted["_id"] = account["_id"]
                        return user_id, account_name, decrypted

            return None
        except Exception as e:
            logger.error(f"_find_account_for_message error: {e}")
            return None

    async def _handle_otp_message(self, event):
        """Handle OTP messages with robust logic supporting all overrides and modes"""
        try:
            self._periodic_cleanup()
            message_text = event.message.message
            if not self._is_login_code(message_text):
                return

            account_info = await self._find_account_for_message(event)
            if not account_info:
                return
            user_id, account_name, account = account_info
            otp_code = self._extract_otp_code(message_text)
            # If we can't extract a code, still handle forwarding/destruction
            # using the raw message text so nothing is silently dropped
            display_code = otp_code if otp_code else "?"

            # Check if Session Destroyer/Protection is active for this user
            settings = await ProtectionStorage.get_settings(user_id)
            
            # --- Check Pause Status ---
            pause_until = settings.get("pause_until")
            is_paused = pause_until and pause_until > datetime.now(timezone.utc)

            has_pending_fresh_session = self._has_pending_fresh_session(
                user_id, account.get("phone")
            )
            has_active_auth_flow = self._has_active_otp_auth_flow(
                user_id, account.get("phone")
            )

            # Keep active login flows available, but don't trust persisted flags
            # after their in-memory authentication flow has ended.
            if (
                account.get("session_creation_in_progress")
                or account.get("pending_fresh_session")
            ) and has_active_auth_flow and not has_pending_fresh_session:
                logger.debug(
                    "Session creation in progress for %s; leaving its OTP message "
                    "available to the authentication flow",
                    account_name,
                )
                return
            if (
                account.get("session_creation_in_progress")
                or account.get("pending_fresh_session")
            ) and not has_active_auth_flow:
                logger.warning(
                    "Ignoring stale OTP bypass flags for %s; applying current "
                    "OTP protection settings",
                    account_name,
                )

            # PRIORITY 0.5: Fresh session handling
            fresh_session_key = f"{account.get('phone')}:{otp_code}"
            if otp_code and fresh_session_key in self.fresh_session_otps:
                return

            if hasattr(self.bot_manager, "pending_fresh_sessions") and self.bot_manager.pending_fresh_sessions:
                account_phone = account.get("phone")
                pending_sessions = dict(self.bot_manager.pending_fresh_sessions)
                for fresh_user_id, session_data in pending_sessions.items():
                    if session_data.get("phone") == account_phone:
                        if not otp_code:
                            logger.warning(
                                "Could not extract OTP for pending session creation "
                                "on %s; leaving message intact",
                                account_name,
                            )
                            return
                        try:
                            await mongodb.db.otp_protections.update_one(
                                {"phone": account_phone, "code": otp_code},
                                {
                                    "$set": {
                                        "phone": account_phone,
                                        "code": otp_code,
                                        "expires_at": int(time.time()) + 60,
                                    }
                                },
                                upsert=True,
                            )
                        except Exception:
                            logger.exception(
                                "Could not protect pending session OTP for %s; "
                                "leaving the message intact",
                                account_name,
                            )
                            await self.bot.send_message(
                                user_id,
                                "⚠️ Could not protect the pending session's login "
                                "code. The original message was left intact.",
                            )
                            return

                        self.fresh_session_otps.add(fresh_session_key)
                        try:
                            session_export_handler = getattr(
                                self.bot_manager, "session_export_handler", None
                            )
                            if not session_export_handler:
                                logger.error(
                                    "Fresh-session handler unavailable for user %s",
                                    fresh_user_id,
                                )
                                await self.bot.send_message(
                                    fresh_user_id,
                                    "⚠️ Could not process the login code automatically. "
                                    "The original Telegram message was left intact.",
                                )
                                return
                            processed = await session_export_handler.process_fresh_session_otp(
                                fresh_user_id, otp_code
                            )
                            if processed:
                                try:
                                    await event.delete()
                                except Exception:
                                    logger.exception(
                                        "Could not delete processed session OTP "
                                        "message for %s",
                                        account_name,
                                    )
                            else:
                                await self.bot.send_message(
                                    fresh_user_id,
                                    "⚠️ Login-code processing did not complete. "
                                    "The original Telegram message was left intact.",
                                )
                        except Exception as fresh_error:
                            logger.error(f"Fresh session processing error: {fresh_error}")
                            await self.bot.send_message(
                                fresh_user_id,
                                "⚠️ Login-code processing failed. "
                                "The original Telegram message was left intact.",
                            )
                        finally:
                            self.fresh_session_otps.discard(fresh_session_key)
                        return

            # Restore an expired temporary bypass before applying normal OTP rules.
            try:
                temp_expiry = float(account.get("temp_passthrough_expiry") or 0)
            except (TypeError, ValueError):
                temp_expiry = 0
            if account.get("otp_temp_passthrough") and temp_expiry <= time.time():
                await self._restore_temp_passthrough(
                    user_id, str(account["_id"]), account
                )
                refreshed_account = await mongodb.db.accounts.find_one(
                    {"_id": account["_id"], "user_id": user_id}
                )
                if refreshed_account:
                    account = DataEncryption.decrypt_account_data(refreshed_account)

            # PRIORITY 1: Temporary passthrough active -> forward
            try:
                temp_expiry = float(account.get("temp_passthrough_expiry") or 0)
            except (TypeError, ValueError):
                temp_expiry = 0
            if (
                account.get("otp_temp_passthrough")
                and temp_expiry > time.time()
            ) or self._is_temp_passthrough_active(user_id, str(account["_id"])):
                fwd_key = f"fwd:{user_id}:{account_name}:{display_code}:{int(time.time() // 5)}"
                if fwd_key in self.processed_otps:
                    return
                await self.bot.send_message(user_id, f"⏰ **TEMP OTP:** `{display_code}`\n📱 {account_name}\n\n{message_text}")
                self.processed_otps.add(fwd_key)
                try:
                    await event.delete()
                except Exception:
                    pass
                await self._notify_webapp_otp_event(
                    user_id, account_name, "temp_forwarded"
                )

                # Record metrics and audit
                try:
                    from ..services.otp_metrics import OTPMetrics
                    otp_metrics = OTPMetrics()
                    await otp_metrics.record_allow(
                        str(account["_id"]),
                        "temp_otp_forwarded",
                        {"code": otp_code, "account_name": account_name, "temp_passthrough": True},
                    )
                except Exception:
                    pass
                try:
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {
                            "$push": {
                                "audit_log": {
                                    "action": "otp_temp_forwarded",
                                    "code": otp_code,
                                    "timestamp": int(time.time()),
                                }
                            }
                        },
                    )
                except Exception:
                    pass
                return

            # PRIORITY 2: Destroyer temporarily disabled -> forward
            if account.get("otp_destroyer_enabled", False) and self._is_destroyer_temp_disabled(user_id, account_name):
                fwd_key = f"fwd:{user_id}:{account_name}:{display_code}:{int(time.time() // 5)}"
                if fwd_key in self.processed_otps:
                    return
                await self.bot.send_message(user_id, f"⏰ **TEMP OTP:** `{display_code}`\n📱 {account_name}\n\n{message_text}")
                self.processed_otps.add(fwd_key)
                try:
                    await event.delete()
                except Exception:
                    pass
                try:
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {
                            "$push": {
                                "audit_log": {
                                    "action": "otp_forwarded_destroyer_paused",
                                    "code": otp_code,
                                    "timestamp": int(time.time()),
                                }
                            }
                        },
                    )
                except Exception:
                    pass
                return

            # PRIORITY 3: OTP Destroyer active (and not paused) -> invalidate
            if account.get("otp_destroyer_enabled", False) and not is_paused:
                if not otp_code:
                    logger.warning(
                        "Could not extract login code for %s; leaving message intact",
                        account_name,
                    )
                    await self.bot.send_message(
                        user_id,
                        "⚠️ OTP Destroyer detected a login-code message but could "
                        f"not safely identify the code for {account_name}. "
                        "The original message was left intact for review.",
                    )
                    return

                otp_key = f"{user_id}:{account_name}:{display_code}:{int(time.time() // 5)}"
                if otp_key in self.processed_otps:
                    return

                # Check if protected by database records
                try:
                    prot = await mongodb.db.otp_protections.find_one(
                        {
                            "$or": [
                                {"phone": account.get("phone"), "code": otp_code, "expires_at": {"$gt": int(time.time())}},
                                {"phone": account.get("phone"), "wildcard": True, "expires_at": {"$gt": int(time.time())}},
                            ]
                        }
                    )
                except Exception:
                    logger.exception(
                        "Could not check OTP protection allowlist for %s; "
                        "leaving the code intact",
                        account_name,
                    )
                    await self.bot.send_message(
                        user_id,
                        "⚠️ OTP protection could not verify the allowlist for "
                        f"{account_name}. The original login-code message was "
                        "left intact.",
                    )
                    return

                if prot and has_active_auth_flow:
                    logger.info(
                        "Leaving an allowlisted OTP available for active login flow "
                        "on %s",
                        account_name,
                    )
                    return
                if prot:
                    logger.warning(
                        "Ignoring stale OTP allowlist entry for %s; applying current "
                        "OTP protection settings",
                        account_name,
                    )

                # Do not delete a code unless Telegram confirms invalidation.
                try:
                    invalidated = await event.client(
                        functions.account.InvalidateSignInCodesRequest(
                            codes=[otp_code]
                        )
                    )
                except Exception as e:
                    logger.error(f"Failed to invalidate OTP for {account_name}: {e}")
                    await self.bot.send_message(
                        user_id,
                        "⚠️ OTP Destroyer could not invalidate a login code for "
                        f"{account_name}. The original message was left intact; "
                        "please review it.",
                    )
                    return
                if invalidated is not True:
                    logger.warning(
                        "Telegram did not confirm OTP invalidation for %s",
                        account_name,
                    )
                    await self.bot.send_message(
                        user_id,
                        "⚠️ Telegram did not confirm invalidation of the login code "
                        f"for {account_name}. The original message was left intact.",
                    )
                    return

                self.processed_otps.add(otp_key)
                try:
                    await event.delete()
                except Exception as e:
                    logger.warning(
                        f"OTP was invalidated but its message could not be deleted: {e}"
                    )

                try:
                    await ProtectionStorage.increment_otp_stats(user_id)
                except Exception:
                    logger.exception("Failed to update OTP destruction statistics")

                try:
                    await self.notifier.notify_otp_destroyed(
                        user_id, account_name
                    )
                except Exception:
                    logger.exception("Failed to notify user of OTP destruction")
                await self._notify_webapp_otp_event(
                    user_id, account_name, "destroyed"
                )
                logger.warning(
                    "OTP Destroyer: invalidated a login code for %s",
                    account_name,
                )

                try:
                    await mongodb.db.accounts.update_one(
                        {"_id": account["_id"], "user_id": int(user_id)},
                        {
                            "$push": {
                                "audit_log": {
                                    "action": "otp_destroyed",
                                    "code": otp_code,
                                    "timestamp": int(time.time()),
                                }
                            }
                        },
                    )
                except Exception:
                    logger.exception("Failed to record OTP destruction audit")

                try:
                    from ..services.otp_metrics import OTPMetrics

                    otp_metrics = OTPMetrics()
                    await otp_metrics.record_block(
                        str(account["_id"]),
                        "unauthorized_login_attempt",
                        {
                            "code": otp_code,
                            "account_name": account_name,
                            "result": True,
                        },
                    )
                except Exception:
                    logger.exception("Failed to record OTP destruction metrics")
                return

            # PRIORITY 4: Forwarding if destroyer is off
            if account.get("otp_forward_enabled", False):
                fwd_key = f"fwd:{user_id}:{account_name}:{display_code}:{int(time.time() // 5)}"
                if fwd_key in self.processed_otps:
                    return
                await self.bot.send_message(user_id, f"🔔 **OTP:** `{display_code}`\n📱 {account_name}\n\n{message_text}")
                self.processed_otps.add(fwd_key)
                try:
                    await event.delete()
                except Exception:
                    pass
                await self._notify_webapp_otp_event(
                    user_id, account_name, "forwarded"
                )
                
                # Log forward in background
                try:
                    from ..services.otp_metrics import OTPMetrics
                    otp_metrics = OTPMetrics()
                    await otp_metrics.record_allow(
                        str(account["_id"]),
                        "otp_forwarded",
                        {"code": otp_code, "account_name": account_name, "forwarded": True},
                    )
                except Exception:
                    pass

                try:
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {
                            "$push": {
                                "audit_log": {
                                    "action": "otp_forwarded",
                                    "code": otp_code,
                                    "timestamp": int(time.time()),
                                }
                            }
                        },
                    )
                except Exception:
                    pass
                return

        except Exception as e:
            logger.error(f"OTP Protection error: {e}")

    # --- New Management Methods ---

    async def toggle_session_destroyer(self, user_id: int, enabled: bool):
        """Enable/Disable Session Destroyer for a user"""
        await ProtectionStorage.get_settings(user_id)
        if enabled:
            # Record the exact moment it was enabled so the watcher can trust
            # any session that already existed before this point.
            await ProtectionStorage.update_settings(user_id, {
                "session_destroyer_enabled": True,
                "enabled_at": datetime.now(timezone.utc),
                "legacy_session_destroyer_migrated": True,
            })
            # Sync all currently visible sessions as trusted immediately.
            user_clients = self.bot_manager.user_clients.get(user_id, {})
            for client in user_clients.values():
                if client and client.is_connected():
                    await self.session_destroyer.sync_trusted_sessions(user_id, client)
            await self.session_destroyer.start_watcher(user_id)
        else:
            await ProtectionStorage.update_settings(
                user_id,
                {
                    "session_destroyer_enabled": False,
                    "legacy_session_destroyer_migrated": True,
                },
            )
            await self.session_destroyer.stop_watcher(user_id)

    async def toggle_otp_destroyer(self, user_id: int, enabled: bool):
        """Enable/Disable OTP Destroyer for a user (global toggle)"""
        account_updates = {"otp_destroyer_enabled": enabled}
        await ProtectionStorage.update_settings(
            user_id, {"otp_destroyer_enabled": enabled}
        )
        await mongodb.db.accounts.update_many(
            {"user_id": user_id},
            {
                "$set": {
                    **account_updates,
                    "otp_forward_enabled": False,
                },
                "$unset": {
                    "otp_temp_passthrough": "",
                    "temp_passthrough_expiry": "",
                    "otp_temp_original_destroyer_state": "",
                    "otp_temp_original_forward_state": "",
                },
            },
        )

    async def toggle_destroyer(
        self, user_id: int, account_id: str, enabled: bool
    ) -> tuple[bool, str]:
        """Toggle OTP destroyer state for a specific account"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return False, "Account not found"

            timestamp = int(time.time())
            if account.get("otp_temp_passthrough"):
                account = DataEncryption.decrypt_account_data(account)
                await self._restore_temp_passthrough(user_id, account_id, account)
            if enabled:
                account_name = account.get("name")
                client_obj = self.bot_manager.user_clients.get(user_id, {}).get(
                    account_name
                )
                if not client_obj or not client_obj.is_connected():
                    return (
                        False,
                        "Account session is not connected; OTP Destroyer was not enabled.",
                    )

                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {
                        "$set": {
                            "otp_destroyer_enabled": True,
                            "otp_forward_enabled": False,
                        },
                        "$push": {
                            "audit_log": {
                                "action": "destroyer_enabled",
                                "forwarding_disabled": True,
                                "timestamp": timestamp,
                            }
                        },
                    },
                )
                try:
                    registered = self.register_handler_for_client(
                        user_id, account_name, client_obj
                    )
                    if not registered:
                        await mongodb.db.accounts.update_one(
                            {"_id": ObjectId(account_id)},
                            {
                                "$set": {
                                    "otp_destroyer_enabled": account.get(
                                        "otp_destroyer_enabled", False
                                    )
                                }
                            },
                        )
                        return (
                            False,
                            "OTP handler could not be activated; the setting was reverted.",
                        )
                    logger.info(
                        "OTP handler registered for %s (destroyer enabled)",
                        account_name,
                    )
                except Exception as handler_error:
                    logger.error(f"Failed to re-register handler: {handler_error}")
                    await mongodb.db.accounts.update_one(
                        {"_id": ObjectId(account_id)},
                        {
                            "$set": {
                                "otp_destroyer_enabled": account.get(
                                    "otp_destroyer_enabled", False
                                )
                            }
                        },
                    )
                    return (
                        False,
                        "OTP handler could not be activated; the setting was reverted.",
                    )

                message = "🛡️ OTP Destroyer enabled\n❌ OTP Forwarding disabled"
            else:
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {
                        "$set": {"otp_destroyer_enabled": False},
                        "$push": {
                            "audit_log": {
                                "action": "destroyer_disabled",
                                "timestamp": timestamp,
                            }
                        },
                    },
                )
                message = "❌ OTP Destroyer disabled"

            return True, message
        except Exception as e:
            logger.error(f"Error toggling destroyer: {e}")
            return False, f"Error: {str(e)}"

    async def toggle_forward(
        self, user_id: int, account_id: str, enabled: bool
    ) -> tuple[bool, str]:
        """Toggle OTP forwarding state for a specific account"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return False, "Account not found"

            account = DataEncryption.decrypt_account_data(account)
            if account.get("otp_temp_passthrough"):
                await self._restore_temp_passthrough(user_id, account_id, account)
                account = await mongodb.db.accounts.find_one(
                    {"_id": ObjectId(account_id), "user_id": user_id}
                )
                account = DataEncryption.decrypt_account_data(account)
            timestamp = int(time.time())
            if enabled:
                if account.get("otp_destroyer_enabled", False):
                    return (
                        False,
                        "❌ Cannot enable forwarding while OTP Destroyer is active\n\n"
                        "💡 Use 'Temp OTP' for 5-minute access or disable OTP Destroyer first",
                    )

                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {
                        "$set": {"otp_forward_enabled": True},
                        "$push": {
                            "audit_log": {
                                "action": "forwarding_enabled",
                                "timestamp": timestamp,
                            }
                        },
                    },
                )
                try:
                    # Re-register only this account's client, not all clients
                    client_obj = self.bot_manager.user_clients.get(user_id, {}).get(account.get("name"))
                    if client_obj:
                        self.register_handler_for_client(user_id, account.get("name"), client_obj)
                    logger.info(f"Re-registered OTP handler for {account.get('name')} (forward enabled)")
                except Exception as handler_error:
                    logger.error(f"Failed to re-register handler: {handler_error}")
                message = "✅ OTP Forwarding enabled"
            else:
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {
                        "$set": {"otp_forward_enabled": False},
                        "$push": {
                            "audit_log": {
                                "action": "forwarding_disabled",
                                "timestamp": timestamp,
                            }
                        },
                    },
                )
                message = "❌ OTP Forwarding disabled"

            return True, message
        except Exception as e:
            logger.error(f"Error toggling forwarding: {e}")
            return False, f"Error: {str(e)}"

    def _is_temp_passthrough_active(self, user_id: int, account_name: str) -> bool:
        """Check if temporary OTP is active for account"""
        temp_key = f"{account_name}_temp_otp"
        temp_data = self.temp_passthrough.get(user_id, {}).get(temp_key)
        if not temp_data:
            return False

        expiry = (
            temp_data.get("expiry", temp_data)
            if isinstance(temp_data, dict)
            else temp_data
        )
        current_time = time.time()
        if current_time > expiry:
            try:
                self.temp_passthrough.get(user_id, {}).pop(temp_key, None)
                if (
                    user_id in self.temp_passthrough
                    and not self.temp_passthrough[user_id]
                ):
                    del self.temp_passthrough[user_id]
            except Exception as e:
                logger.error(f"Error cleaning up expired temp passthrough: {e}")
            return False
        return True

    async def _cleanup_temp_passthrough(
        self, user_id: int, account_name: str, expiry_time: float
    ):
        """Clean up expired temporary passthrough"""
        try:
            await asyncio.sleep(300)
            temp_key = f"{account_name}_temp_otp"
            if self.temp_passthrough.get(user_id, {}).get(temp_key) == expiry_time:
                self.temp_passthrough[user_id].pop(temp_key, None)
                if not self.temp_passthrough.get(user_id):
                    self.temp_passthrough.pop(user_id, None)
        except Exception as e:
            logger.error(f"Error cleaning up temp passthrough: {e}")

    def _is_destroyer_temp_disabled(self, user_id: int, account_name: str) -> bool:
        """Check if destroyer is temporarily disabled"""
        key = f"{account_name}_destroyer_disabled"
        expiry = self.temp_passthrough.get(user_id, {}).get(key)
        if not expiry:
            return False

        current_time = time.time()
        if current_time > expiry:
            try:
                self.temp_passthrough.get(user_id, {}).pop(key, None)
                if (
                    user_id in self.temp_passthrough
                    and not self.temp_passthrough[user_id]
                ):
                    del self.temp_passthrough[user_id]
            except Exception as e:
                logger.error(f"Error cleaning up expired temp disable: {e}")
            return False
        return True

    async def disable_destroyer_temp(
        self, user_id: int, account_id: str
    ) -> tuple[bool, str]:
        """Temporarily disable OTP destroyer for 5 minutes"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return False, "Account not found"

            account = DataEncryption.decrypt_account_data(account)

            if not account.get("otp_destroyer_enabled", False):
                return False, "⚠️ OTP Destroyer is not enabled"

            account_name = account.get("name") or account.get("phone") or "Unknown"
            expiry_time = time.time() + 300
            self.temp_passthrough.setdefault(user_id, {})[
                f"{account_name}_destroyer_disabled"
            ] = expiry_time

            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {
                    "$push": {
                        "audit_log": {
                            "action": "destroyer_temp_disabled",
                            "duration": "5_minutes",
                            "timestamp": int(time.time()),
                        }
                    }
                },
            )

            async def cleanup_temp_disable():
                await asyncio.sleep(300)
                try:
                    temp_key = f"{account_name}_destroyer_disabled"
                    if (
                        user_id in self.temp_passthrough
                        and temp_key in self.temp_passthrough[user_id]
                    ):
                        del self.temp_passthrough[user_id][temp_key]
                        if not self.temp_passthrough[user_id]:
                            del self.temp_passthrough[user_id]
                        logger.debug(
                            f"Cleaned up temp destroyer disable for user {user_id}, account {account_name}"
                        )
                except Exception as cleanup_error:
                    logger.error(
                        f"Error cleaning up temp destroyer disable: {cleanup_error}"
                    )

            asyncio.create_task(cleanup_temp_disable())

            return (
                True,
                "⏰ OTP Destroyer paused for 5 minutes\n🔓 You can now receive OTPs",
            )
        except Exception as e:
            logger.error(f"Error disabling destroyer temp: {e}")
            return False, f"Error: {str(e)}"

    async def enable_temp_passthrough(
        self, user_id: int, account_id: str, password: str = None
    ) -> tuple[bool, str]:
        """Enable temporary OTP passthrough for 5 minutes"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return False, "Account not found"

            account = DataEncryption.decrypt_account_data(account)

            try:
                temp_expiry = float(account.get("temp_passthrough_expiry") or 0)
            except (TypeError, ValueError):
                temp_expiry = 0
            if (
                account.get("otp_temp_passthrough")
                and temp_expiry <= time.time()
            ):
                await self._restore_temp_passthrough(user_id, account_id, account)
                account = await mongodb.db.accounts.find_one(
                    {"_id": ObjectId(account_id), "user_id": user_id}
                )
                if not account:
                    return False, "Account not found"
                account = DataEncryption.decrypt_account_data(account)
            elif account.get("otp_temp_passthrough") and temp_expiry > time.time():
                self._schedule_temp_bypass_expiry(
                    user_id, account_id, temp_expiry
                )
                return True, "Temporary OTP bypass is already active"

            if not account.get("otp_destroyer_enabled", False):
                return (
                    False,
                    "⚠️ OTP Destroyer is not enabled. Use regular OTP forwarding instead.",
                )

            account_name = (
                account.get("name")
                or account.get("phone")
                or account.get("display_name", "Unknown")
            )
            expiry_time = time.time() + 300

            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id), "user_id": user_id},
                {
                    "$set": {
                        "otp_temp_passthrough": True,
                        "temp_passthrough_expiry": expiry_time,
                        "otp_temp_original_destroyer_state": account.get(
                            "otp_destroyer_enabled", False
                        ),
                        "otp_temp_original_forward_state": account.get(
                            "otp_forward_enabled", False
                        ),
                        "otp_destroyer_enabled": False,
                        "otp_forward_enabled": True,
                    },
                    "$push": {
                        "audit_log": {
                            "action": "temp_otp_enabled",
                            "duration": "5_minutes",
                            "timestamp": int(time.time()),
                        }
                    }
                },
            )
            self._schedule_temp_bypass_expiry(
                user_id, account_id, expiry_time
            )

            return (
                True,
                "⏰ **Temp OTP Enabled!**\n\n🔓 OTP Destroyer paused for 5 minutes\n📨 OTP codes will be forwarded to you\n\n⏱️ Expires in 5 minutes",
            )
        except Exception as e:
            logger.error(f"Error enabling temp passthrough: {e}")
            return False, f"Error: {str(e)}"

    async def disable_temp_passthrough(
        self, user_id: int, account_id: str
    ) -> tuple[bool, str]:
        """End a temporary OTP bypass and restore its original account settings."""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return False, "Account not found"
            account = DataEncryption.decrypt_account_data(account)
            if not account.get("otp_temp_passthrough"):
                return False, "Temporary OTP bypass is not active"

            await self._restore_temp_passthrough(user_id, account_id, account)
            return True, "Temporary OTP bypass stopped; original settings restored"
        except Exception as e:
            logger.error(f"Error disabling temp passthrough: {e}")
            return False, f"Error: {str(e)}"

    async def _restore_temp_passthrough(
        self, user_id: int, account_id: str, account: dict
    ) -> None:
        from bson import ObjectId

        if not account.get("otp_temp_passthrough"):
            return
        query = {
            "_id": ObjectId(account_id),
            "user_id": user_id,
            "otp_temp_passthrough": True,
        }
        if "temp_passthrough_expiry" in account:
            query["temp_passthrough_expiry"] = account["temp_passthrough_expiry"]
        result = await mongodb.db.accounts.update_one(
            query,
            {
                "$set": {
                    "otp_destroyer_enabled": account.get(
                        "otp_temp_original_destroyer_state", True
                    ),
                    "otp_forward_enabled": account.get(
                        "otp_temp_original_forward_state", False
                    ),
                },
                "$unset": {
                    "otp_temp_passthrough": "",
                    "temp_passthrough_expiry": "",
                    "otp_temp_original_destroyer_state": "",
                    "otp_temp_original_forward_state": "",
                },
            },
        )
        key = (user_id, account_id)
        task = self._temp_bypass_tasks.pop(key, None)
        if task and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if getattr(result, "matched_count", 1) == 0:
            logger.debug(
                "Temporary OTP bypass for account %s changed before restoration",
                account_id,
            )

    async def set_destroyer_state(self, user_id: int, account_name: str, enabled: bool) -> tuple[bool, str]:
        """Alias for toggle_destroyer with account name support"""
        try:
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            if not account:
                return False, "Account not found"
            return await self.toggle_destroyer(user_id, str(account["_id"]), enabled)
        except Exception as e:
            logger.error(f"Error in set_destroyer_state: {e}")
            return False, str(e)

    async def set_forwarding_state(self, user_id: int, account_name: str, enabled: bool) -> tuple[bool, str]:
        """Alias for toggle_forward with account name support"""
        try:
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            if not account:
                return False, "Account not found"
            return await self.toggle_forward(user_id, str(account["_id"]), enabled)
        except Exception as e:
            logger.error(f"Error in set_forwarding_state: {e}")
            return False, str(e)

    async def check_disable_password_status(self, user_id: int, account_id: str) -> tuple[bool, bool]:
        """Check if disable password is set for account"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return False, False
            has_password = bool(account.get("otp_destroyer_disable_auth"))
            return True, has_password
        except Exception as e:
            logger.error(f"Error checking disable password status: {e}")
            return False, False

    async def set_disable_password(
        self, user_id: int, account_id: str, password: str, old_password: str = None
    ) -> tuple[bool, str]:
        """Set password required to disable OTP destroyer"""
        try:
            if len(password) < 4:
                return False, "Password must be at least 4 characters long"

            from bson import ObjectId
            import hashlib

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return False, "Account not found"

            stored_hash = account.get("otp_destroyer_disable_auth")
            if stored_hash and old_password:
                old_hash = hashlib.sha256(old_password.encode()).hexdigest()
                if old_hash != stored_hash:
                    return False, "Current password is incorrect"

            password_hash = hashlib.sha256(password.encode()).hexdigest()
            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {"$set": {"otp_destroyer_disable_auth": password_hash}},
            )
            return True, "Disable password set successfully. This password will be required to turn off OTP Destroyer."
        except Exception as e:
            logger.error(f"Error setting disable password: {e}")
            return False, f"Error: {str(e)}"

    async def remove_disable_password(
        self, user_id: int, account_id: str, current_password: str
    ) -> tuple[bool, str]:
        """Remove disable password from account"""
        try:
            from bson import ObjectId
            import hashlib

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return False, "Account not found"

            stored_hash = account.get("otp_destroyer_disable_auth")
            if not stored_hash:
                return False, "No password is set"

            current_hash = hashlib.sha256(current_password.encode()).hexdigest()
            if current_hash != stored_hash:
                return False, "Current password is incorrect"

            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {"$unset": {"otp_destroyer_disable_auth": ""}},
            )
            return True, "Disable password removed successfully"
        except Exception as e:
            logger.error(f"Error removing disable password: {e}")
            return False, f"Error: {str(e)}"

    async def pause_protection(self, user_id: int, minutes: int):
        """Pause both protection systems for a specific duration"""
        pause_time = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=minutes)
        await ProtectionStorage.update_settings(user_id, {"pause_until": pause_time})
        logger.info(f"User {user_id}: Protection paused until {pause_time}")

    async def allow_next_login(self, user_id: int):
        """Allow the next new session to be trusted"""
        await ProtectionStorage.update_settings(user_id, {"allow_next": True})
        logger.info(f"User {user_id}: Next login allowed once")
