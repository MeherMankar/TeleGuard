"""Protection Manager - Orchestrates OTP Destroyer and Session Destroyer systems"""

import asyncio
import hashlib
import logging
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

    async def start(self):
        """Start the protection manager and its background workers"""
        await self.session_destroyer.start_all()
        logger.info("🛡️ Protection Manager started (OTP & Session systems active)")

    async def stop(self):
        """Stop all background workers"""
        await self.session_destroyer.stop_all()

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

    def register_handler_for_client(self, user_id: int, account_name: str, client):
        """Register OTP handler for a specific client"""
        if not client or not client.is_connected():
            return
        handler_key = f"{user_id}:{account_name}"
        if handler_key in self.registered_handlers:
            return
        
        try:
            client.add_event_handler(
                self._handle_otp_message, events.NewMessage(chats=[777000, 42777])
            )
            self._client_handlers[(int(user_id), str(account_name))] = self._handle_otp_message
            self.registered_handlers.add(handler_key)
            if hasattr(self.bot_manager, "registered_handlers"):
                self.bot_manager.registered_handlers["otp"].add(handler_key)
            logger.debug(f"Registered OTP handler for {handler_key}")
        except Exception as e:
            logger.error(f"Failed to register OTP handler for {handler_key}: {e}")

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
        return "Unknown"

    async def _find_account_for_message(self, event) -> Optional[tuple]:
        """
        Find which account received this OTP message by matching the Telethon client.
        Returns (user_id, account_name, decrypted_account_dict) or None.
        """
        try:
            from ..utils.crypto_utils import DataEncryption
            client = event.client
            for user_id, clients in self.user_clients.items():
                for account_name, user_client in clients.items():
                    if user_client != client:
                        continue
                    # Try plain name first
                    account = await mongodb.db.accounts.find_one({
                        "user_id": int(user_id),
                        "$or": [
                            {"name": str(account_name)},
                            {"phone": str(account_name)},
                            {"display_name": str(account_name)},
                        ]
                    })
                    if not account:
                        # Try encrypted name
                        try:
                            enc_name = DataEncryption.encrypt_field(str(account_name))
                            account = await mongodb.db.accounts.find_one({
                                "user_id": int(user_id),
                                "name_enc": enc_name
                            })
                        except Exception:
                            pass
                    if account:
                        # Decrypt account data so callers get plain fields
                        try:
                            decrypted = DataEncryption.decrypt_account_data(dict(account))
                            decrypted["_id"] = account["_id"]
                            return user_id, account_name, decrypted
                        except Exception:
                            return user_id, account_name, account
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

            # Check if Session Destroyer/Protection is active for this user
            settings = await ProtectionStorage.get_settings(user_id)
            
            # --- Check Pause Status ---
            pause_until = settings.get("pause_until")
            is_paused = pause_until and pause_until > datetime.now(timezone.utc)

            # PRIORITY 0: Session creation in progress -> allow
            if account.get("session_creation_in_progress") or account.get("pending_fresh_session"):
                logger.debug(f"Session creation in progress for {account_name}, allowing OTP: {otp_code}")
                try:
                    await event.delete()
                except Exception:
                    pass
                return

            # PRIORITY 0.5: Fresh session handling
            fresh_session_key = f"{account.get('phone')}:{otp_code}"
            if fresh_session_key in self.fresh_session_otps:
                try:
                    await event.delete()
                except Exception:
                    pass
                return

            if hasattr(self.bot_manager, "pending_fresh_sessions") and self.bot_manager.pending_fresh_sessions:
                account_phone = account.get("phone")
                pending_sessions = dict(self.bot_manager.pending_fresh_sessions)
                for fresh_user_id, session_data in pending_sessions.items():
                    if session_data.get("phone") == account_phone:
                        self.fresh_session_otps.add(fresh_session_key)
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
                            pass
                        
                        try:
                            if hasattr(self.bot_manager, "session_export_handler"):
                                await self.bot_manager.session_export_handler.process_fresh_session_otp(
                                    fresh_user_id, otp_code
                                )
                            try:
                                await event.delete()
                            except Exception:
                                pass
                        except Exception as fresh_error:
                            logger.error(f"Fresh session processing error: {fresh_error}")
                            try:
                                await event.delete()
                            except Exception:
                                pass
                        finally:
                            self.fresh_session_otps.discard(fresh_session_key)
                        return

            # PRIORITY 1: Temporary passthrough active -> forward
            if self._is_temp_passthrough_active(user_id, account_name):
                await self.bot.send_message(user_id, f"⏰ **TEMP OTP:** `{otp_code}`\n📱 {account_name}\n\n{message_text}")
                try:
                    await event.delete()
                except Exception:
                    pass

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
                await self.bot.send_message(user_id, f"⏰ **TEMP OTP:** `{otp_code}`\n📱 {account_name}\n\n{message_text}")
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
                otp_key = f"{user_id}:{account_name}:{otp_code}:{int(time.time() // 5)}"
                if otp_key in self.processed_otps:
                    try:
                        await event.delete()
                    except Exception:
                        pass
                    return
                self.processed_otps.add(otp_key)

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
                    prot = None

                if prot:
                    logger.info(f"Skipping protected code for {account_name}: {otp_code}")
                    try:
                        await event.delete()
                    except Exception:
                        pass
                    return

                # Invalidate codes
                try:
                    await event.client(functions.account.InvalidateSignInCodesRequest(codes=[otp_code]))
                    await event.delete()
                    
                    # Update Stats, audit, and Notify
                    await ProtectionStorage.increment_otp_stats(user_id)
                    await self.notifier.notify_otp_destroyed(user_id, account_name, otp_code)
                    logger.warning(f"🛡️ OTP Destroyer: Invalidated code {otp_code} for {account_name}")

                    # Log to audit
                    try:
                        await mongodb.db.accounts.update_one(
                            {"user_id": int(user_id), "name": str(account_name)},
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
                        pass

                    # Record metrics
                    try:
                        from ..services.otp_metrics import OTPMetrics
                        otp_metrics = OTPMetrics()
                        await otp_metrics.record_block(
                            str(account["_id"]),
                            "unauthorized_login_attempt",
                            {"code": otp_code, "account_name": account_name, "result": True},
                        )
                    except Exception:
                        pass

                except Exception as e:
                    logger.error(f"Failed to invalidate OTP: {e}")
                    try:
                        await event.delete()
                    except Exception:
                        pass
                return

            # PRIORITY 4: Forwarding if destroyer is off
            if account.get("otp_forward_enabled", False):
                await self.bot.send_message(user_id, f"🔔 **OTP:** `{otp_code}`\n📱 {account_name}\n\n{message_text}")
                try:
                    await event.delete()
                except Exception:
                    pass
                
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
        if enabled:
            # Record the exact moment it was enabled so the watcher can trust
            # any session that already existed before this point.
            await ProtectionStorage.update_settings(user_id, {
                "session_destroyer_enabled": True,
                "enabled_at": datetime.now(timezone.utc),
            })
            # Sync all currently visible sessions as trusted immediately.
            user_clients = self.bot_manager.user_clients.get(user_id, {})
            for client in user_clients.values():
                if client and client.is_connected():
                    await self.session_destroyer.sync_trusted_sessions(user_id, client)
                    break
            await self.session_destroyer.start_watcher(user_id)
        else:
            await ProtectionStorage.update_settings(user_id, {"session_destroyer_enabled": False})
            await self.session_destroyer.stop_watcher(user_id)

    async def toggle_otp_destroyer(self, user_id: int, enabled: bool):
        """Enable/Disable OTP Destroyer for a user (global toggle)"""
        await ProtectionStorage.update_settings(user_id, {"otp_destroyer_enabled": enabled})
        await mongodb.db.accounts.update_many(
            {"user_id": user_id},
            {"$set": {"otp_destroyer_enabled": enabled}}
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
            if enabled:
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
                    self.register_handlers()
                    logger.info(f"Re-registered OTP handlers after enabling destroyer for {account.get('name')}")
                except Exception as handler_error:
                    logger.error(f"Failed to re-register handlers: {handler_error}")

                message = "🛡️ OTP Destroyer enabled\n❌ OTP Forwarding disabled\n✅ Handlers re-registered"
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
                    self.register_handlers()
                    logger.info(f"Re-registered OTP handlers after enabling forwarding for {account.get('name')}")
                except Exception as handler_error:
                    logger.error(f"Failed to re-register handlers: {handler_error}")
                message = "✅ OTP Forwarding enabled\n✅ Handlers re-registered"
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

            temp_key = f"{account_name}_temp_otp"
            self.temp_passthrough.setdefault(user_id, {})[temp_key] = {
                "expiry": expiry_time
            }

            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {
                    "$push": {
                        "audit_log": {
                            "action": "temp_otp_enabled",
                            "duration": "5_minutes",
                            "timestamp": int(time.time()),
                        }
                    }
                },
            )

            async def cleanup_temp_otp():
                await asyncio.sleep(300)
                try:
                    if (
                        user_id in self.temp_passthrough
                        and temp_key in self.temp_passthrough[user_id]
                    ):
                        del self.temp_passthrough[user_id][temp_key]
                        if not self.temp_passthrough[user_id]:
                            del self.temp_passthrough[user_id]
                        logger.debug(
                            f"Cleaned up temp OTP for user {user_id}, account {account_name}"
                        )
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up temp OTP: {cleanup_error}")

            asyncio.create_task(cleanup_temp_otp())

            return (
                True,
                "⏰ **Temp OTP Enabled!**\n\n🔓 OTP Destroyer paused for 5 minutes\n📨 OTP codes will be forwarded to you\n\n⏱️ Expires in 5 minutes",
            )
        except Exception as e:
            logger.error(f"Error enabling temp passthrough: {e}")
            return False, f"Error: {str(e)}"

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
