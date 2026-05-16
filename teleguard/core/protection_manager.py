"""Protection Manager - Orchestrates OTP Destroyer and Session Destroyer systems"""

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Set, Any

from telethon import events, functions

from .mongo_database import mongodb
from .session_destroyer import SessionDestroyer
from ..services.protection_storage import ProtectionStorage
from ..services.protection_notifier import ProtectionNotifier

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
        self.registered_handlers.add(handler_key)
        if hasattr(self.bot_manager, "registered_handlers"):
            self.bot_manager.registered_handlers["otp"].add(handler_key)

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
        try:
            client = event.client
            for user_id, clients in self.user_clients.items():
                for account_name, user_client in clients.items():
                    if user_client == client:
                        account = await mongodb.db.accounts.find_one({
                            "user_id": int(user_id),
                            "$or": [{"name": str(account_name)}, {"phone": str(account_name)}]
                        })
                        if account: return user_id, account_name, account
            return None
        except Exception: return None

    async def _handle_otp_message(self, event):
        """Handle OTP messages with ported legacy logic"""
        try:
            self._periodic_cleanup()
            message_text = event.message.message
            if not self._is_login_code(message_text): return

            account_info = await self._find_account_for_message(event)
            if not account_info: return
            user_id, account_name, account = account_info
            otp_code = self._extract_otp_code(message_text)

            # Check if Session Destroyer is active for this user
            settings = await ProtectionStorage.get_settings(user_id)
            
            # --- Check Pause Status ---
            pause_until = settings.get("pause_until")
            is_paused = pause_until and pause_until > datetime.now(timezone.utc)

            # OTP DESTROYER LOGIC
            if account.get("otp_destroyer_enabled", False) and not is_paused:
                # Invalidate codes
                try:
                    await event.client(functions.account.InvalidateSignInCodesRequest(codes=[otp_code]))
                    await event.delete()
                    
                    # Update Stats & Notify
                    await ProtectionStorage.increment_otp_stats(user_id)
                    await self.notifier.notify_otp_destroyed(user_id, account_name, otp_code)
                    logger.warning(f"🛡️ OTP Destroyer: Invalidated code {otp_code} for {account_name}")
                except Exception as e:
                    logger.error(f"Failed to invalidate OTP: {e}")
                return

            # If forwarding enabled and not destroyed
            if account.get("otp_forward_enabled", False):
                await self.bot.send_message(user_id, f"🔔 **OTP:** `{otp_code}`\n📱 {account_name}\n\n{message_text}")
                await event.delete()

        except Exception as e:
            logger.error(f"OTP Protection error: {e}")

    # --- New Management Methods ---

    async def toggle_session_destroyer(self, user_id: int, enabled: bool):
        """Enable/Disable Session Destroyer for a user"""
        await ProtectionStorage.update_settings(user_id, {"session_destroyer_enabled": enabled})
        if enabled:
            # Sync existing sessions as trusted first time
            user_clients = self.bot_manager.user_clients.get(user_id, {})
            for client in user_clients.values():
                if client and client.is_connected():
                    await self.session_destroyer.sync_trusted_sessions(user_id, client)
                    break
            await self.session_destroyer.start_watcher(user_id)
        else:
            await self.session_destroyer.stop_watcher(user_id)

    async def toggle_otp_destroyer(self, user_id: int, enabled: bool):
        """Enable/Disable OTP Destroyer for a user (global toggle)"""
        await ProtectionStorage.update_settings(user_id, {"otp_destroyer_enabled": enabled})
        # Note: Individual account settings might still exist, this acts as a master switch 
        # in the new UI, but we'll maintain backward compatibility where possible.
        await mongodb.db.accounts.update_many(
            {"user_id": user_id},
            {"$set": {"otp_destroyer_enabled": enabled}}
        )

    async def pause_protection(self, user_id: int, minutes: int):
        """Pause both protection systems for a specific duration"""
        pause_time = datetime.now(timezone.utc).replace(microsecond=0) + asyncio.timedelta(minutes=minutes)
        await ProtectionStorage.update_settings(user_id, {"pause_until": pause_time})
        logger.info(f"User {user_id}: Protection paused until {pause_time}")

    async def allow_next_login(self, user_id: int):
        """Allow the next new session to be trusted"""
        await ProtectionStorage.update_settings(user_id, {"allow_next": True})
        logger.info(f"User {user_id}: Next login allowed once")
