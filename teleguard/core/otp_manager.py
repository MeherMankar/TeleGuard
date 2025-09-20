"""OTP Manager - Handles OTP forwarding, destroying, and temporary passthrough"""

import asyncio
import logging
import re
import time
from typing import Dict, Optional

from telethon import events

from .mongo_database import mongodb

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

    def register_handlers(self):
        """Register OTP message handler for all user clients"""
        
        # Clear existing registrations to prevent duplicates
        self.registered_handlers.clear()
        
        # Clear bot manager OTP registry if available
        if hasattr(self.bot_manager, 'registered_handlers'):
            self.bot_manager.registered_handlers["otp"].clear()
            logger.info("Cleared OTP handler registry to prevent duplicates")

        async def otp_handler(event):
            """Handle OTP messages from Telegram official account"""
            try:
                message_text = event.message.message

                # Check if this is a login code message
                if not self._is_login_code(message_text):
                    return

                # Find which account received this OTP
                account_info = await self._find_account_for_message(event)
                if not account_info:
                    return

                user_id, account_name, account = account_info

                # Extract the OTP code
                otp_code = self._extract_otp_code(message_text)

                # Priority 1: Check if temp OTP is active (destroyer disabled, forwarding enabled)
                if self._is_temp_passthrough_active(user_id, account_name):
                    # Temp OTP means destroyer is disabled and forwarding is enabled
                    await self._forward_otp(
                        user_id, account_name, otp_code, message_text, temp=True
                    )
                    await event.delete()  # Delete the original message
                    # Update audit in MongoDB
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {"$push": {"audit_log": {
                            "action": "otp_temp_forwarded",
                            "code": otp_code,
                            "message": message_text[:50],
                            "timestamp": int(time.time())
                        }}}
                    )
                    logger.info(
                        f"OTP forwarded via temp OTP (destroyer disabled) for {account_name}"
                    )
                    return  # CRITICAL: Exit here, don't continue to destroyer

                # Priority 2: Check if destroyer is temp disabled
                if account.get("otp_destroyer_enabled", False) and self._is_destroyer_temp_disabled(
                    user_id, account_name
                ):
                    await self._forward_otp(
                        user_id, account_name, otp_code, message_text, temp=True
                    )
                    # Update audit in MongoDB
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {"$push": {"audit_log": {
                            "action": "otp_forwarded_destroyer_paused",
                            "code": otp_code,
                            "timestamp": int(time.time())
                        }}}
                    )
                    logger.info(
                        f"OTP forwarded (destroyer temp disabled) for {account_name}"
                    )
                    return  # CRITICAL: Exit here, don't continue to destroyer

                # Priority 3: Check destroyer setting (only if no temp overrides)
                if account.get("otp_destroyer_enabled", False):
                    # Destroy the OTP by invalidating it
                    try:
                        from telethon import functions

                        await event.client(
                            functions.account.InvalidateSignInCodesRequest([otp_code])
                        )
                        await event.delete()

                        # Update audit in MongoDB with encrypted fields
                        await mongodb.db.accounts.update_one(
                            {"user_id": int(user_id), "name_enc": DataEncryption.encrypt_field(str(account_name))},
                            {"$push": {"audit_log_enc": DataEncryption.encrypt_field({
                                "action": "otp_destroyed",
                                "code": otp_code,
                                "message": message_text[:50],
                                "timestamp": int(time.time())
                            })}}
                        )

                        # Notify user about destruction
                        await self.bot.send_message(
                            user_id,
                            f"🛡️ **OTP DESTROYER ACTIVATED**\n"
                            f"📱 **Account:** {account_name}\n"
                            f"🎯 **Status:** ✅ DESTROYED\n"
                            f"🔢 **Codes:** {otp_code}\n\n"
                            f"✅ **Login codes permanently invalidated!**\n"
                            f"🔒 Nobody can use these codes to sign in.\n\n"
                            f"🕒 **Time:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
                        )

                        logger.info(f"OTP destroyed and invalidated for {account_name}: {otp_code}")
                    except Exception as destroy_error:
                        logger.error(f"Failed to invalidate OTP: {destroy_error}")
                        await event.delete()  # Still delete the message
                    return

                # Priority 4: Check forwarding setting (only if destroyer is off)
                if account.get("otp_forward_enabled", False):
                    await self._forward_otp(
                        user_id, account_name, otp_code, message_text
                    )
                    await event.delete()
                    # Update audit in MongoDB
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {"$push": {"audit_log": {
                            "action": "otp_forwarded",
                            "code": otp_code,
                            "timestamp": int(time.time())
                        }}}
                    )
                    logger.info(f"OTP forwarded and deleted for {account_name}")

            except Exception as e:
                logger.error(f"OTP handler error: {e}")

        # Register handler on all user clients
        handler_count = 0
        for user_id, clients in self.user_clients.items():
            for account_name, client in clients.items():
                if client and client.is_connected():
                    handler_key = f"{user_id}:{account_name}"
                    if handler_key not in self.registered_handlers:
                        try:
                            client.add_event_handler(
                                otp_handler, events.NewMessage(chats=[777000, 42777])
                            )
                            self.registered_handlers.add(handler_key)
                            handler_count += 1
                            logger.info(f"🛡️ OTP handler registered for {account_name}")
                        except Exception as e:
                            logger.error(f"Failed to register OTP handler for {account_name}: {e}")
                    else:
                        logger.info(f"OTP handler already registered for {account_name}, skipping")
                else:
                    logger.warning(f"Client {account_name} not connected, skipping OTP handler")
        
        logger.info(f"🛡️ OTP Manager registered handlers for {handler_count} clients")
        
        # Update bot manager registry
        if hasattr(self.bot_manager, 'registered_handlers'):
            for handler_key in self.registered_handlers:
                self.bot_manager.registered_handlers["otp"].add(handler_key)
    
    def register_handler_for_client(self, user_id: int, account_name: str, client):
        """Register OTP handler for a specific client"""
        if not client or not client.is_connected():
            logger.warning(f"Cannot register OTP handler for {account_name} - client not connected")
            return
        
        # Check if handler already registered for this client
        handler_key = f"{user_id}:{account_name}"
        if handler_key in self.registered_handlers:
            logger.info(f"OTP handler already registered for {account_name}, skipping")
            return
        
        self.registered_handlers.add(handler_key)
        
        async def otp_handler(event):
            """Handle OTP messages from Telegram official account"""
            try:
                message_text = event.message.message

                # Check if this is a login code message
                if not self._is_login_code(message_text):
                    return

                # Find which account received this OTP
                account_info = await self._find_account_for_message(event)
                if not account_info:
                    return

                found_user_id, found_account_name, account = account_info
                otp_code = self._extract_otp_code(message_text)

                # Check destroyer setting
                if account.get("otp_destroyer_enabled", False):
                    try:
                        from telethon import functions
                        await event.client(functions.account.InvalidateSignInCodesRequest([otp_code]))
                        await event.delete()

                        await mongodb.db.accounts.update_one(
                            {"user_id": int(found_user_id), "name": str(found_account_name)},
                            {"$push": {"audit_log": {
                                "action": "otp_destroyed",
                                "code": otp_code,
                                "message": message_text[:50],
                                "timestamp": int(time.time())
                            }}}
                        )

                        await self.bot.send_message(
                            found_user_id,
                            f"🛡️ **OTP DESTROYER ACTIVATED**\n"
                            f"📱 **Account:** {found_account_name}\n"
                            f"🎯 **Status:** ✅ DESTROYED\n"
                            f"🔢 **Codes:** {otp_code}\n\n"
                            f"✅ **Login codes permanently invalidated!**\n"
                            f"🔒 Nobody can use these codes to sign in.\n\n"
                            f"🕒 **Time:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
                        )
                        logger.info(f"OTP destroyed and invalidated for {found_account_name}: {otp_code}")
                    except Exception as destroy_error:
                        logger.error(f"Failed to invalidate OTP: {destroy_error}")
                        await event.delete()

            except Exception as e:
                logger.error(f"OTP handler error: {e}")
        
        try:
            client.add_event_handler(otp_handler, events.NewMessage(chats=[777000, 42777]))
            logger.info(f"🛡️ OTP handler registered for new client {account_name}")
        except Exception as e:
            logger.error(f"Failed to register OTP handler for {account_name}: {e}")

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
        # Look for 5-7 digit codes with optional hyphens/spaces
        patterns = [
            r"\b(\d{5,7})\b",  # Simple 5-7 digits
            r"\b(\d{2,3}[-\s]\d{2,4})\b",  # With hyphens/spaces like "12-345" or "123 45"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message_text)
            if match:
                # Remove hyphens and spaces
                code = re.sub(r"[^0-9]", "", match.group(1))
                if 5 <= len(code) <= 7:
                    return code
        
        return "Unknown"

    async def _find_account_for_message(self, event) -> Optional[tuple]:
        """Find which account received the OTP message"""
        try:
            # Get the client that received this message
            client = event.client

            # Find matching account in user_clients
            for user_id, clients in self.user_clients.items():
                for account_name, user_client in clients.items():
                    if user_client == client:
                        # Try multiple lookup strategies for account
                        account = None
                        
                        # 1. Try by name (unencrypted)
                        account = await mongodb.db.accounts.find_one({
                            "user_id": int(user_id),
                            "name": str(account_name)
                        })
                        
                        # 2. Try by phone (unencrypted)
                        if not account:
                            account = await mongodb.db.accounts.find_one({
                                "user_id": int(user_id),
                                "phone": str(account_name)
                            })
                        
                        # 3. Try encrypted fields if available
                        if not account:
                            try:
                                from ..utils.data_encryption import DataEncryption
                                encrypted_account = await mongodb.db.accounts.find_one({
                                    "user_id": int(user_id),
                                    "name_enc": DataEncryption.encrypt_field(str(account_name))
                                })
                                if encrypted_account:
                                    account = DataEncryption.decrypt_account_data(encrypted_account)
                            except Exception as enc_error:
                                logger.debug(f"Encryption lookup failed: {enc_error}")
                        
                        if account:
                            return user_id, account_name, account

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

        except Exception as e:
            logger.error(f"Error forwarding OTP: {e}")

    def _is_temp_passthrough_active(self, user_id: int, account_name: str) -> bool:
        """Check if temporary OTP is active for account"""
        if user_id not in self.temp_passthrough:
            return False

        temp_key = f"{account_name}_temp_otp"
        if temp_key not in self.temp_passthrough[user_id]:
            return False

        temp_data = self.temp_passthrough[user_id][temp_key]
        if isinstance(temp_data, dict):
            expiry = temp_data.get("expiry", 0)
        else:
            # Handle old format
            expiry = temp_data

        if time.time() > expiry:
            # Clean up expired entry
            del self.temp_passthrough[user_id][temp_key]
            if not self.temp_passthrough[user_id]:
                del self.temp_passthrough[user_id]
            return False

        return True

    async def _cleanup_temp_passthrough(
        self, user_id: int, account_name: str, expiry_time: float
    ):
        """Clean up expired temporary passthrough"""
        try:
            await asyncio.sleep(300)  # Wait 5 minutes

            # Check if this is still the same entry (not replaced)
            if (
                user_id in self.temp_passthrough
                and account_name in self.temp_passthrough[user_id]
                and self.temp_passthrough[user_id][account_name] == expiry_time
            ):
                del self.temp_passthrough[user_id][account_name]
                if not self.temp_passthrough[user_id]:
                    del self.temp_passthrough[user_id]

                logger.info(f"Temp passthrough expired for {account_name}")

        except Exception as e:
            logger.error(f"Error cleaning up temp passthrough: {e}")

    async def _update_account_audit(self, account):
        """Update account audit log in database - deprecated, using direct MongoDB updates"""
        # This method is no longer used - audit updates are done directly in MongoDB
        pass

    async def setup_handler_for_new_client(self, user_id: int, account_name: str, client):
        """Setup OTP handler for newly added client"""
        self.register_handler_for_client(user_id, account_name, client)
    
    async def check_disable_password_status(
        self, user_id: int, account_id: str
    ) -> tuple[bool, bool]:
        """Check if disable password is set for an account"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if account:
                return True, bool(account.get("otp_destroyer_disable_auth"))
            return False, False
        except Exception as e:
            logger.error(f"Error checking disable password status: {e}")
            return False, False

    async def toggle_destroyer(
        self, user_id: int, account_id: str, enabled: bool, disable_password: str = None
    ) -> tuple[bool, str]:
        """Toggle OTP destroyer state with password protection for disabling"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                return False, "Account not found"

            if enabled:
                # Enable destroyer, disable forwarding
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {
                        "otp_destroyer_enabled": True,
                        "otp_forward_enabled": False
                    },
                    "$push": {"audit_log": {
                        "action": "destroyer_enabled",
                        "forwarding_disabled": True,
                        "timestamp": int(time.time())
                    }}}
                )
                message = "🛡️ OTP Destroyer enabled\n❌ OTP Forwarding disabled"
            else:
                # Check if disable password is required
                if account.get("otp_destroyer_disable_auth"):
                    if not disable_password:
                        return False, "🔒 Disable password required"

                    import hashlib
                    password_hash = hashlib.sha256(disable_password.encode()).hexdigest()
                    if password_hash != account["otp_destroyer_disable_auth"]:
                        return False, "❌ Invalid disable password"

                # Disable destroyer only
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {"otp_destroyer_enabled": False},
                    "$push": {"audit_log": {
                        "action": "destroyer_disabled",
                        "auth_verified": bool(account.get("otp_destroyer_disable_auth")),
                        "timestamp": int(time.time())
                    }}}
                )
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

            if enabled:
                if account.get("otp_destroyer_enabled", False):
                    return (
                        False,
                        "❌ Cannot enable forwarding while OTP Destroyer is active\n\n💡 Use 'Temp OTP' for 5-minute access or disable OTP Destroyer first",
                    )

                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {"otp_forward_enabled": True},
                    "$push": {"audit_log": {
                        "action": "forwarding_enabled",
                        "timestamp": int(time.time())
                    }}}
                )
                message = "✅ OTP Forwarding enabled"
            else:
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {"otp_forward_enabled": False},
                    "$push": {"audit_log": {
                        "action": "forwarding_disabled",
                        "timestamp": int(time.time())
                    }}}
                )
                message = "❌ OTP Forwarding disabled"

            return True, message

        except Exception as e:
            logger.error(f"Error toggling forwarding: {e}")
            return False, f"Error: {str(e)}"

    async def disable_destroyer_temp(
        self, user_id: int, account_id: str, disable_password: str = None
    ) -> tuple[bool, str]:
        """Temporarily disable OTP destroyer for 5 minutes with password protection"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                return False, "Account not found"

            if not account.get("otp_destroyer_enabled", False):
                return False, "⚠️ OTP Destroyer is not enabled"

            # Check if disable password is required
            if account.get("otp_destroyer_disable_auth"):
                if not disable_password:
                    return False, "🔒 Disable password required"

                import hashlib
                password_hash = hashlib.sha256(disable_password.encode()).hexdigest()
                if password_hash != account["otp_destroyer_disable_auth"]:
                    return False, "❌ Invalid disable password"

            # Temporarily disable destroyer
            expiry_time = time.time() + 300  # 5 minutes
            if user_id not in self.temp_passthrough:
                self.temp_passthrough[user_id] = {}
            self.temp_passthrough[user_id][
                f"{account['name']}_destroyer_disabled"
            ] = expiry_time

            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {"$push": {"audit_log": {
                    "action": "destroyer_temp_disabled",
                    "duration": "5_minutes",
                    "auth_verified": bool(account.get("otp_destroyer_disable_auth")),
                    "timestamp": int(time.time())
                }}}
            )

            return (
                True,
                "⏰ OTP Destroyer paused for 5 minutes\n🔓 You can now receive OTPs",
            )

        except Exception as e:
            logger.error(f"Error disabling destroyer temp: {e}")
            return False, f"Error: {str(e)}"



    def _is_destroyer_temp_disabled(self, user_id: int, account_name: str) -> bool:
        """Check if destroyer is temporarily disabled"""
        if user_id not in self.temp_passthrough:
            return False

        key = f"{account_name}_destroyer_disabled"
        if key not in self.temp_passthrough[user_id]:
            return False

        expiry = self.temp_passthrough[user_id][key]
        if time.time() > expiry:
            del self.temp_passthrough[user_id][key]
            if not self.temp_passthrough[user_id]:
                del self.temp_passthrough[user_id]
            return False

        return True





    async def set_disable_password(
        self, user_id: int, account_id: str, new_password: str, old_password: str = None
    ) -> tuple[bool, str]:
        """Set or change the disable password for OTP Destroyer"""
        try:
            from bson import ObjectId
            import hashlib
            
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                return False, "Account not found"

            # If password already exists, verify old password
            if account.get("otp_destroyer_disable_auth"):
                if not old_password:
                    return False, "🔐 Current password required to change"

                old_password_hash = hashlib.sha256(old_password.encode()).hexdigest()
                if old_password_hash != account["otp_destroyer_disable_auth"]:
                    return False, "❌ Current password is incorrect"

            # Set new password
            new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
            
            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {"$set": {"otp_destroyer_disable_auth": new_password_hash},
                "$push": {"audit_log": {
                    "action": "disable_password_set",
                    "timestamp": int(time.time())
                }}}
            )

            return True, "🔐 Disable password set\n🛡️ Required for disabling OTP Destroyer"

        except Exception as e:
            logger.error(f"Error setting disable password: {e}")
            return False, f"Error: {str(e)}"

    async def remove_disable_password(
        self, user_id: int, account_id: str, current_password: str
    ) -> tuple[bool, str]:
        """Remove the disable password for OTP Destroyer"""
        try:
            from bson import ObjectId
            import hashlib
            
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                return False, "Account not found"

            if not account.get("otp_destroyer_disable_auth"):
                return False, "⚠️ No disable password is set"

            # Verify current password
            password_hash = hashlib.sha256(current_password.encode()).hexdigest()
            if password_hash != account["otp_destroyer_disable_auth"]:
                return False, "❌ Current password is incorrect"

            # Remove password
            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {"$unset": {"otp_destroyer_disable_auth": ""},
                "$push": {"audit_log": {
                    "action": "disable_password_removed",
                    "timestamp": int(time.time())
                }}}
            )

            return (
                True,
                "🔓 Disable password removed\n⚠️ OTP Destroyer can now be disabled without password",
            )

        except Exception as e:
            logger.error(f"Error removing disable password: {e}")
            return False, f"Error: {str(e)}"
