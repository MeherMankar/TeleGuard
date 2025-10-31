"""OTP Manager - Handles OTP forwarding, destroying, and temporary passthrough"""
import asyncio
import logging
import re
import time
from typing import Dict, Optional
from telethon import events
from .mongo_database import mongodb
from ..utils.bot_logger import BotLogger
logger = logging.getLogger(__name__)
class OTPManager:
    """Manages OTP forwarding, destroying, and temporary passthrough"""
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        # Temporary passthrough state: {user_id: {account_name: expiry_timestamp}}
        self.temp_passthrough: Dict[int, Dict[str, float]] = {}
        # Track registered handlers to prevent duplicates
        self.registered_handlers = set()
        # Track processed OTP codes to prevent duplicate destruction messages
        self.processed_otps = set()
        # Track fresh session OTPs to prevent destruction
        self.fresh_session_otps = set()
        # Track sent notifications to prevent duplicates (with timestamp-based keys)
        self.sent_notifications = set()
        # Track last cleanup time for periodic cleanup
        self.last_cleanup = time.time()
        # Track processed message IDs to prevent duplicate handling
        self._processed_messages = set()
    
    def _periodic_cleanup(self):
        """Periodically clean up tracking sets to prevent memory buildup"""
        current_time = time.time()
        # Clean up every 5 minutes
        if current_time - self.last_cleanup > 300:
            # Keep only recent entries
            if len(self.processed_otps) > 100:
                self.processed_otps = set(list(self.processed_otps)[-50:])
            if len(self.sent_notifications) > 100:
                self.sent_notifications = set(list(self.sent_notifications)[-50:])
            if len(self.fresh_session_otps) > 50:
                self.fresh_session_otps = set(list(self.fresh_session_otps)[-25:])
            self.last_cleanup = current_time
            logger.debug("Performed periodic cleanup of OTP tracking sets")
    def register_handlers(self):
        """Register OTP message handler for all user clients"""
        logger.info("🛡️ Starting OTP handler registration...")
        
        if hasattr(self.bot_manager, 'registered_handlers'):
            self.bot_manager.registered_handlers["otp"].clear()
        
        self.registered_handlers.clear()
        
        logger.info(f"Current user_clients: {len(self.user_clients)} users")
        
        async def otp_handler(event):
            """Handle OTP messages from Telegram official account"""
            try:
                # Periodic cleanup
                self._periodic_cleanup()
                
                message_text = event.message.message
                if not self._is_login_code(message_text):
                    return
                
                # Early deduplication check based on message ID and timestamp
                message_key = f"{event.message.id}:{int(time.time()//2)}"
                if hasattr(self, '_processed_messages'):
                    if message_key in self._processed_messages:
                        return
                else:
                    self._processed_messages = set()
                self._processed_messages.add(message_key)
                
                # Keep only recent message keys
                if len(self._processed_messages) > 50:
                    self._processed_messages = set(list(self._processed_messages)[-25:])
                # Find which account received this OTP
                account_info = await self._find_account_for_message(event)
                if not account_info:
                    return
                user_id, account_name, account = account_info
                # Extract the OTP code first
                otp_code = self._extract_otp_code(message_text)
                # PRIORITY 0: Check if this OTP is for fresh session creation
                fresh_session_key = f"{account.get('phone')}:{otp_code}"
                if fresh_session_key in self.fresh_session_otps:
                    await event.delete()
                    return
                if hasattr(self.bot_manager, 'pending_fresh_sessions') and self.bot_manager.pending_fresh_sessions:
                    account_phone = account.get('phone')
                    pending_sessions = dict(self.bot_manager.pending_fresh_sessions)
                    for fresh_user_id, session_data in pending_sessions.items():
                        if session_data.get('phone') == account_phone:
                            # Mark this OTP as being processed for fresh session
                            self.fresh_session_otps.add(fresh_session_key)
                            try:
                                await mongodb.db.otp_protections.update_one(
                                    {"phone": account_phone, "code": otp_code},
                                    {"$set": {"phone": account_phone, "code": otp_code, "expires_at": int(time.time()) + 60}},
                                    upsert=True,
                                )
                            except Exception:
                                pass
                            try:
                                success = await self.bot_manager.session_export_handler.process_fresh_session_otp(fresh_user_id, otp_code)
                                await event.delete()
                            except Exception as fresh_error:
                                logger.error(f"Fresh session processing error: {fresh_error}")
                                await event.delete()
                            finally:
                                self.fresh_session_otps.discard(fresh_session_key)
                            return
                # Priority 1: Check if temp OTP is active
                if self._is_temp_passthrough_active(user_id, account_name):
                    await self._forward_otp(
                        user_id, account_name, otp_code, message_text, temp=True
                    )
                    try:
                        await event.delete()
                    except:
                        pass
                    
                    # Record OTP metrics for temp forwarding
                    try:
                        from ..services.otp_metrics import OTPMetrics
                        otp_metrics = OTPMetrics()
                        account_id = str(account["_id"])
                        await otp_metrics.record_allow(
                            account_id,
                            "temp_otp_forwarded",
                            {
                                "code": otp_code,
                                "account_name": account_name,
                                "temp_passthrough": True
                            }
                        )
                    except Exception as metrics_error:
                        logger.error(f"Failed to record temp OTP metrics: {metrics_error}")
                    
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {"$push": {"audit_log": {
                            "action": "otp_temp_forwarded",
                            "code": otp_code,
                            "message": message_text[:50],
                            "timestamp": int(time.time())
                        }}}
                    )
                    return
                # Priority 2: Check if destroyer is temp disabled
                if account.get("otp_destroyer_enabled", False) and self._is_destroyer_temp_disabled(
                    user_id, account_name
                ):
                    await self._forward_otp(
                        user_id, account_name, otp_code, message_text, temp=True
                    )
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {"$push": {"audit_log": {
                            "action": "otp_forwarded_destroyer_paused",
                            "code": otp_code,
                            "timestamp": int(time.time())
                        }}}
                    )
                    return
                # Priority 3: Check destroyer setting (only if no temp overrides)
                if account.get("otp_destroyer_enabled", False):
                    fresh_check_key = f"{account.get('phone')}:{otp_code}"
                    if fresh_check_key in self.fresh_session_otps:
                        await event.delete()
                        return
                    # Enhanced OTP deduplication with timestamp window
                    otp_key = f"{user_id}:{account_name}:{otp_code}:{int(time.time()//5)}"
                    if otp_key in self.processed_otps:
                        logger.debug(f"Duplicate OTP processing prevented for {otp_key}")
                        await event.delete()
                        return
                    self.processed_otps.add(otp_key)
                    # Keep only recent OTP keys (last 200)
                    if len(self.processed_otps) > 200:
                        self.processed_otps = set(list(self.processed_otps)[-100:])
                    try:
                        try:
                            # Check for exact code protection or a phone-level wildcard protection
                            prot = await mongodb.db.otp_protections.find_one({
                                "$or": [
                                    {"phone": account.get("phone"), "code": otp_code, "expires_at": {"$gt": int(time.time())}},
                                    {"phone": account.get("phone"), "wildcard": True, "expires_at": {"$gt": int(time.time())}},
                                ]
                            })
                            if prot:
                                try:
                                    await event.delete()
                                except:
                                    pass
                                return
                        except Exception:
                            pass
                        from telethon import functions
                        result = await event.client(functions.account.InvalidateSignInCodesRequest(codes=[otp_code]))
                        try:
                            await event.delete()
                        except:
                            pass
                        
                        # Record OTP metrics for destruction
                        try:
                            from ..services.otp_metrics import OTPMetrics
                            otp_metrics = OTPMetrics()
                            account_id = str(account["_id"])
                            await otp_metrics.record_block(
                                account_id,
                                "unauthorized_login_attempt",
                                {
                                    "code": otp_code,
                                    "account_name": account_name,
                                    "result": bool(result)
                                }
                            )
                        except Exception as metrics_error:
                            logger.error(f"Failed to record OTP destruction metrics: {metrics_error}")
                        
                        await mongodb.db.accounts.update_one(
                            {"user_id": int(user_id), "name": str(account_name)},
                            {"$push": {"audit_log": {
                                "action": "otp_destroyed",
                                "code": otp_code,
                                "message": message_text[:50],
                                "timestamp": int(time.time())
                            }}}
                        )
                        # Enhanced notification deduplication with timestamp
                        notification_key = f"{user_id}:{account_name}:{otp_code}:{int(time.time()//10)}"
                        if notification_key not in self.sent_notifications:
                            self.sent_notifications.add(notification_key)
                            # Keep only recent notifications (last 100)
                            if len(self.sent_notifications) > 100:
                                self.sent_notifications = set(list(self.sent_notifications)[-50:])
                            await self.bot.send_message(
                                user_id,
                                f"🛡️ **OTP DESTROYER ACTIVATED**\n\n"
                                f"🔒 **Account Protected:** {account_name}\n"
                                f"🚫 **Login Code Destroyed:** {otp_code}\n"
                                f"⚡ **Unauthorized Access Blocked**\n\n"
                                f"✅ **Security Status:** Login codes permanently invalidated\n"
                                f"❌ **Attacker Impact:** Will receive 'Invalid/Expired Code' error\n"
                                f"🛡️ **Your Account:** Remains fully secure",
                            )
                        else:
                            logger.debug(f"Duplicate OTP notification prevented for {notification_key}")
                    except Exception as destroy_error:
                        logger.error(f"Failed to invalidate OTP: {destroy_error}")
                        try:
                            await event.delete()
                        except:
                            pass
                    return
                # Priority 4: Check forwarding setting (only if destroyer is off)
                if account.get("otp_forward_enabled", False):
                    await self._forward_otp(
                        user_id, account_name, otp_code, message_text
                    )
                    try:
                        await event.delete()
                    except:
                        pass
                    
                    # Record OTP metrics for forwarding
                    try:
                        from ..services.otp_metrics import OTPMetrics
                        otp_metrics = OTPMetrics()
                        account_id = str(account["_id"])
                        await otp_metrics.record_allow(
                            account_id,
                            "otp_forwarded",
                            {
                                "code": otp_code,
                                "account_name": account_name,
                                "forwarded": True
                            }
                        )
                    except Exception as metrics_error:
                        logger.error(f"Failed to record OTP forward metrics: {metrics_error}")
                    
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {"$push": {"audit_log": {
                            "action": "otp_forwarded",
                            "code": otp_code,
                            "timestamp": int(time.time())
                        }}}
                    )
            except Exception as e:
                logger.error(f"OTP handler error: {e}")
        handler_count = 0
        for user_id, clients in self.user_clients.items():
            logger.debug(f"Processing user {user_id} with {len(clients)} clients")
            for account_name, client in clients.items():
                handler_key = f"{user_id}:{account_name}"
                
                # Check if client is valid and connected
                if not client:
                    logger.warning(f"⚠️ Client is None for {handler_key}")
                    continue
                
                if not hasattr(client, 'is_connected'):
                    logger.warning(f"⚠️ Client has no is_connected method for {handler_key}")
                    continue
                
                try:
                    is_connected = client.is_connected()
                except Exception as e:
                    logger.warning(f"⚠️ Error checking connection for {handler_key}: {e}")
                    continue
                
                if not is_connected:
                    logger.warning(f"⚠️ Client not connected for {handler_key}")
                    continue
                
                try:
                    # Always register handler (cleared at start)
                    client.add_event_handler(
                        otp_handler, events.NewMessage(chats=[777000, 42777])
                    )
                    self.registered_handlers.add(handler_key)
                    handler_count += 1
                    logger.info(f"✅ Registered OTP handler for {handler_key}")
                except Exception as e:
                    logger.error(f"❌ Failed to register OTP handler for {handler_key}: {e}")
        if handler_count > 0:
            logger.info(f"🛡️ OTP Manager registered handlers for {handler_count} clients")
            print(f"  OTP handlers registered for {handler_count} accounts")
        else:
            logger.warning("⚠️ No OTP handlers registered - no active clients found")
            print("  No active accounts found for OTP protection")
        
        if hasattr(self.bot_manager, 'registered_handlers'):
            for handler_key in self.registered_handlers:
                self.bot_manager.registered_handlers["otp"].add(handler_key)
    def register_handler_for_client(self, user_id: int, account_name: str, client):
        """Register OTP handler for a specific client (uses main handler logic to prevent duplicates)"""
        if not client or not client.is_connected():
            logger.warning("Cannot register OTP handler - client not connected")
            return
        handler_key = f"{user_id}:{account_name}"
        if handler_key in self.registered_handlers:
            logger.debug(f"OTP handler already registered for {handler_key}")
            return
        
        # Use the same handler logic as register_handlers to prevent duplicates
        # The main otp_handler function already handles all the logic properly
        logger.info(f"Registering OTP handler for new client: {account_name}")
        self.registered_handlers.add(handler_key)
        
        # Add to bot manager registry if available
        if hasattr(self.bot_manager, 'registered_handlers'):
            self.bot_manager.registered_handlers["otp"].add(handler_key)
    def _is_login_code(self, message_text: str) -> bool:
        """Check if message contains login code"""
        patterns = [
            r"Login code",
            r"login code",
            r"verification code",
            r"Verification code",
        ]
        return any(
            re.search(pattern, message_text, re.IGNORECASE) for pattern in patterns
        )
    def _extract_otp_code(self, message_text: str) -> Optional[str]:
        """Extract OTP code from message"""
        patterns = [
            r"\b(\d{5,7})\b",
            r"\b(\d{2,3}[-\s]\d{2,4})\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, message_text)
            if match:
                code = re.sub(r"[^0-9]", "", match.group(1))
                if 5 <= len(code) <= 7:
                    return code
        return "Unknown"
    async def _find_account_for_message(self, event) -> Optional[tuple]:
        """Find which account received the OTP message"""
        try:
            client = event.client
            for user_id, clients in self.user_clients.items():
                for account_name, user_client in clients.items():
                    if user_client == client:
                        # Single optimized query with $or operator
                        account = await mongodb.db.accounts.find_one({
                            "user_id": int(user_id),
                            "$or": [{"name": str(account_name)}, {"phone": str(account_name)}]
                        })
                        if account:
                            return user_id, account_name, account
            # Fallback: find any account with destroyer enabled
            account = await mongodb.db.accounts.find_one({"otp_destroyer_enabled": True})
            if account:
                return account.get('user_id'), account.get('name'), account
            return None
        except Exception as e:
            logger.error(f"Error finding account for message: {e}")
            return None
    async def _forward_otp(
        self,
        user_id: int,
        account_name: str,
        otp_code: str,
        full_text: str,
        temp: bool = False,
    ):
        """Forward OTP to user via bot"""
        try:
            if temp:
                header = "⏰🔓 **Temp OTP Received!**"
                footer = "\n\n⚠️ Temp access - expires soon"
            else:
                header = "🔔🔢 **OTP Received!**"
                footer = ""
            formatted_message = (
                f"{header}\n\n"
                f"📱 **Account:** {account_name}\n"
                f"🔢 **Code:** `{otp_code}`\n\n"
                f"📝 **Full Message:**\n{full_text}{footer}"
            )
            await self.bot.send_message(user_id, formatted_message)
            logger.info(f"OTP forwarded to user {user_id} for account {account_name}: {otp_code}")
        except Exception as e:
            logger.error(f"Error forwarding OTP: {e}")
    def _is_temp_passthrough_active(self, user_id: int, account_name: str) -> bool:
        """Check if temporary OTP is active for account"""
        temp_key = f"{account_name}_temp_otp"
        temp_data = self.temp_passthrough.get(user_id, {}).get(temp_key)
        if not temp_data:
            return False
        
        expiry = temp_data.get("expiry", temp_data) if isinstance(temp_data, dict) else temp_data
        if time.time() > expiry:
            self.temp_passthrough.get(user_id, {}).pop(temp_key, None)
            if user_id in self.temp_passthrough and not self.temp_passthrough[user_id]:
                del self.temp_passthrough[user_id]
            return False
        return True
    async def _cleanup_temp_passthrough(
        self, user_id: int, account_name: str, expiry_time: float
    ):
        """Clean up expired temporary passthrough"""
        try:
            await asyncio.sleep(300)
            if self.temp_passthrough.get(user_id, {}).get(account_name) == expiry_time:
                self.temp_passthrough[user_id].pop(account_name, None)
                if not self.temp_passthrough.get(user_id):
                    self.temp_passthrough.pop(user_id, None)
        except Exception as e:
            logger.error(f"Error cleaning up temp passthrough: {e}")

    async def setup_handler_for_new_client(self, user_id: int, account_name: str, client):
        """Setup OTP handler for newly added client"""
        if not client or not client.is_connected():
            logger.warning(f"Cannot setup OTP handler - client not connected for {account_name}")
            return
        
        handler_key = f"{user_id}:{account_name}"
        
        # Skip if already registered
        if handler_key in self.registered_handlers:
            logger.debug(f"OTP handler already registered for {handler_key}")
            return
        
        logger.info(f"Setting up OTP handler for new client: {handler_key}")
        
        # Define the handler inline to avoid scope issues
        async def otp_handler(event):
            """Handle OTP messages from Telegram official account"""
            try:
                self._periodic_cleanup()
                
                message_text = event.message.message
                if not self._is_login_code(message_text):
                    return
                
                message_key = f"{event.message.id}:{int(time.time()//2)}"
                if hasattr(self, '_processed_messages'):
                    if message_key in self._processed_messages:
                        return
                else:
                    self._processed_messages = set()
                self._processed_messages.add(message_key)
                
                if len(self._processed_messages) > 50:
                    self._processed_messages = set(list(self._processed_messages)[-25:])
                
                account_info = await self._find_account_for_message(event)
                if not account_info:
                    return
                
                msg_user_id, msg_account_name, account = account_info
                otp_code = self._extract_otp_code(message_text)
                
                # Check fresh session
                fresh_session_key = f"{account.get('phone')}:{otp_code}"
                if fresh_session_key in self.fresh_session_otps:
                    await event.delete()
                    return
                
                # Check temp passthrough
                if self._is_temp_passthrough_active(msg_user_id, msg_account_name):
                    await self._forward_otp(msg_user_id, msg_account_name, otp_code, message_text, temp=True)
                    await event.delete()
                    return
                
                # Check destroyer
                if account.get("otp_destroyer_enabled", False):
                    otp_key = f"{msg_user_id}:{msg_account_name}:{otp_code}:{int(time.time()//5)}"
                    if otp_key in self.processed_otps:
                        await event.delete()
                        return
                    self.processed_otps.add(otp_key)
                    
                    if len(self.processed_otps) > 200:
                        self.processed_otps = set(list(self.processed_otps)[-100:])
                    
                    try:
                        from telethon import functions
                        result = await event.client(functions.account.InvalidateSignInCodesRequest(codes=[otp_code]))
                        try:
                            await event.delete()
                        except:
                            pass
                        
                        await mongodb.db.accounts.update_one(
                            {"user_id": int(msg_user_id), "name": str(msg_account_name)},
                            {"$push": {"audit_log": {
                                "action": "otp_destroyed",
                                "code": otp_code,
                                "message": message_text[:50],
                                "timestamp": int(time.time())
                            }}}
                        )
                        
                        notification_key = f"{msg_user_id}:{msg_account_name}:{otp_code}:{int(time.time()//10)}"
                        if notification_key not in self.sent_notifications:
                            self.sent_notifications.add(notification_key)
                            if len(self.sent_notifications) > 100:
                                self.sent_notifications = set(list(self.sent_notifications)[-50:])
                            
                            await self.bot.send_message(
                                msg_user_id,
                                f"🛡️ **OTP DESTROYER ACTIVATED**\n\n"
                                f"🔒 **Account Protected:** {msg_account_name}\n"
                                f"🚫 **Login Code Destroyed:** {otp_code}\n"
                                f"⚡ **Unauthorized Access Blocked**\n\n"
                                f"✅ **Security Status:** Login codes permanently invalidated\n"
                                f"❌ **Attacker Impact:** Will receive 'Invalid/Expired Code' error\n"
                                f"🛡️ **Your Account:** Remains fully secure",
                            )
                    except Exception as destroy_error:
                        logger.error(f"Failed to invalidate OTP: {destroy_error}")
                        try:
                            await event.delete()
                        except:
                            pass
                    return
                
                # Check forwarding
                if account.get("otp_forward_enabled", False):
                    await self._forward_otp(msg_user_id, msg_account_name, otp_code, message_text)
                    try:
                        await event.delete()
                    except:
                        pass
                    return
                    
            except Exception as e:
                logger.error(f"OTP handler error: {e}")
        
        # Register the handler
        try:
            client.add_event_handler(otp_handler, events.NewMessage(chats=[777000, 42777]))
            self.registered_handlers.add(handler_key)
            
            if hasattr(self.bot_manager, 'registered_handlers'):
                self.bot_manager.registered_handlers["otp"].add(handler_key)
            
            logger.info(f"✅ OTP handler registered for new client: {handler_key}")
        except Exception as e:
            logger.error(f"❌ Failed to register OTP handler for {handler_key}: {e}")

    async def toggle_destroyer(
        self, user_id: int, account_id: str, enabled: bool, disable_password: str = None
    ) -> tuple[bool, str]:
        """Toggle OTP destroyer state"""
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
                        "$set": {"otp_destroyer_enabled": True, "otp_forward_enabled": False},
                        "$push": {"audit_log": {
                            "action": "destroyer_enabled",
                            "forwarding_disabled": True,
                            "timestamp": timestamp
                        }}
                    }
                )
                self.register_handlers()
                logger.info(f"Re-registered OTP handlers after enabling destroyer for {account.get('name')}")
                # Log to logs bot
                try:
                    phone = account.get('phone', 'Unknown')
                    try:
                        user = await self.bot.get_entity(user_id)
                        username = user.username if hasattr(user, 'username') else None
                    except:
                        username = None
                    await BotLogger.log_otp_enabled(user_id, phone, username)
                except Exception as log_error:
                    logger.error(f"Failed to log OTP enable: {log_error}")
                message = "🛡️ OTP Destroyer enabled\n❌ OTP Forwarding disabled\n✅ Handlers re-registered"
            else:
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {
                        "$set": {"otp_destroyer_enabled": False},
                        "$push": {"audit_log": {"action": "destroyer_disabled", "timestamp": timestamp}}
                    }
                )
                # Log to logs bot
                try:
                    phone = account.get('phone', 'Unknown')
                    try:
                        user = await self.bot.get_entity(user_id)
                        username = user.username if hasattr(user, 'username') else None
                    except:
                        username = None
                    await BotLogger.log_otp_disabled(user_id, phone, username)
                except Exception as log_error:
                    logger.error(f"Failed to log OTP disable: {log_error}")
                message = "❌ OTP Destroyer disabled"
            
            return True, message
        except Exception as e:
            logger.error(f"Error toggling destroyer: {e}")
            return False, f"Error: {str(e)}"
    async def toggle_forward(
        self, user_id: int, account_id: str, enabled: bool
    ) -> tuple[bool, str]:
        """Toggle OTP forwarding state"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return False, "Account not found"
            
            timestamp = int(time.time())
            if enabled:
                if account.get("otp_destroyer_enabled", False):
                    return (
                        False,
                        "❌ Cannot enable forwarding while OTP Destroyer is active\n\n💡 Use 'Temp OTP' for 5-minute access or disable OTP Destroyer first",
                    )
                
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {
                        "$set": {"otp_forward_enabled": True},
                        "$push": {"audit_log": {"action": "forwarding_enabled", "timestamp": timestamp}}
                    }
                )
                self.register_handlers()
                logger.info(f"Re-registered OTP handlers after enabling forwarding for {account.get('name')}")
                message = "✅ OTP Forwarding enabled\n✅ Handlers re-registered"
            else:
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {
                        "$set": {"otp_forward_enabled": False},
                        "$push": {"audit_log": {"action": "forwarding_disabled", "timestamp": timestamp}}
                    }
                )
                message = "❌ OTP Forwarding disabled"
            
            return True, message
        except Exception as e:
            logger.error(f"Error toggling forwarding: {e}")
            return False, f"Error: {str(e)}"
    async def disable_destroyer_temp(
        self, user_id: int, account_id: str, disable_password: str = None
    ) -> tuple[bool, str]:
        """Temporarily disable OTP destroyer for 5 minutes"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return False, "Account not found"
            if not account.get("otp_destroyer_enabled", False):
                return False, "⚠️ OTP Destroyer is not enabled"
            
            expiry_time = time.time() + 300
            self.temp_passthrough.setdefault(user_id, {})[f"{account['name']}_destroyer_disabled"] = expiry_time
            
            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {"$push": {"audit_log": {
                    "action": "destroyer_temp_disabled",
                    "duration": "5_minutes",
                    "timestamp": int(time.time())
                }}}
            )
            return True, "⏰ OTP Destroyer paused for 5 minutes\n🔓 You can now receive OTPs"
        except Exception as e:
            logger.error(f"Error disabling destroyer temp: {e}")
            return False, f"Error: {str(e)}"
    def _is_destroyer_temp_disabled(self, user_id: int, account_name: str) -> bool:
        """Check if destroyer is temporarily disabled"""
        key = f"{account_name}_destroyer_disabled"
        expiry = self.temp_passthrough.get(user_id, {}).get(key)
        if not expiry:
            return False
        
        if time.time() > expiry:
            self.temp_passthrough.get(user_id, {}).pop(key, None)
            if user_id in self.temp_passthrough and not self.temp_passthrough[user_id]:
                del self.temp_passthrough[user_id]
            return False
        return True
    
    async def enable_temp_passthrough(self, user_id: int, account_id: str, password: str = None) -> tuple[bool, str]:
        """Enable temporary OTP passthrough for 5 minutes (disables destroyer, enables forwarding)"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                return False, "Account not found"
            
            if not account.get("otp_destroyer_enabled", False):
                return False, "⚠️ OTP Destroyer is not enabled. Use regular OTP forwarding instead."
            
            account_name = account.get('name') or account.get('phone') or account.get('display_name', 'Unknown')
            expiry_time = time.time() + 300  # 5 minutes
            
            # Set temp passthrough key
            temp_key = f"{account_name}_temp_otp"
            self.temp_passthrough.setdefault(user_id, {})[temp_key] = {"expiry": expiry_time}
            
            # Log the action
            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {"$push": {"audit_log": {
                    "action": "temp_otp_enabled",
                    "duration": "5_minutes",
                    "timestamp": int(time.time())
                }}}
            )
            
            return True, f"⏰ **Temp OTP Enabled!**\n\n🔓 OTP Destroyer paused for 5 minutes\n📨 OTP codes will be forwarded to you\n\n⏱️ Expires in 5 minutes"
        except Exception as e:
            logger.error(f"Error enabling temp passthrough: {e}")
            return False, f"Error: {str(e)}"


