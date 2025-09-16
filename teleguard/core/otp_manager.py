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

                        # Update audit in MongoDB
                        await mongodb.db.accounts.update_one(
                            {"user_id": user_id, "name": account_name},
                            {"$push": {"audit_log": {
                                "action": "otp_destroyed",
                                "code": otp_code,
                                "message": message_text[:50],
                                "timestamp": int(time.time())
                            }}}
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
                            {"user_id": found_user_id, "name": found_account_name},
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
        # Look for 5-6 digit codes
        match = re.search(r"\b(\d{5,6})\b", message_text)
        return match.group(1) if match else "Unknown"

    async def _find_account_for_message(self, event) -> Optional[tuple]:
        """Find which account received the OTP message"""
        try:
            # Get the client that received this message
            client = event.client

            # Find matching account in user_clients
            for user_id, clients in self.user_clients.items():
                for account_name, user_client in clients.items():
                    if user_client == client:
                        # Get account from MongoDB
                        account = await mongodb.db.accounts.find_one({
                            "user_id": user_id,
                            "name": account_name
                        })
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
        self, user_id: int, account_id: int
    ) -> tuple[bool, bool]:
        """Check if disable password is set for an account"""
        try:
            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account.otp_destroyer_disable_auth)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                password_hash = result.scalar_one_or_none()
                return True, bool(password_hash)
        except Exception as e:
            logger.error(f"Error checking disable password status: {e}")
            return False, False

    async def toggle_destroyer(
        self, user_id: int, account_id: int, enabled: bool, disable_password: str = None
    ) -> tuple[bool, str]:
        """Toggle OTP destroyer state with password protection for disabling"""
        try:
            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()

                if not account:
                    return False, "Account not found"

                if enabled:
                    # Enable destroyer, disable forwarding
                    account.otp_destroyer_enabled = True
                    account.otp_forward_enabled = False
                    account.add_audit_entry(
                        {"action": "destroyer_enabled", "forwarding_disabled": True}
                    )
                    message = "🛡️ OTP Destroyer enabled\n❌ OTP Forwarding disabled"
                else:
                    # Check if disable password is required
                    if account.otp_destroyer_disable_auth:
                        if not disable_password:
                            return False, "🔒 Disable password required"

                        import hashlib

                        password_hash = hashlib.sha256(
                            disable_password.encode()
                        ).hexdigest()
                        if password_hash != account.otp_destroyer_disable_auth:
                            return False, "❌ Invalid disable password"

                    # Disable destroyer only
                    account.otp_destroyer_enabled = False
                    account.add_audit_entry(
                        {
                            "action": "destroyer_disabled",
                            "auth_verified": bool(account.otp_destroyer_disable_auth),
                        }
                    )
                    message = "❌ OTP Destroyer disabled"

                await session.commit()
                return True, message

        except Exception as e:
            logger.error(f"Error toggling destroyer: {e}")
            return False, f"Error: {str(e)}"

    async def toggle_forward(
        self, user_id: int, account_id: int, enabled: bool
    ) -> tuple[bool, str]:
        """Toggle OTP forwarding state"""
        try:
            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()

                if not account:
                    return False, "Account not found"

                if enabled:
                    if account.otp_destroyer_enabled:
                        return (
                            False,
                            "❌ Cannot enable forwarding while OTP Destroyer is active\n\n💡 Use 'Temp OTP' for 5-minute access or disable OTP Destroyer first",
                        )

                    account.otp_forward_enabled = True
                    account.add_audit_entry({"action": "forwarding_enabled"})
                    message = "✅ OTP Forwarding enabled"
                else:
                    account.otp_forward_enabled = False
                    account.add_audit_entry({"action": "forwarding_disabled"})
                    message = "❌ OTP Forwarding disabled"

                await session.commit()
                return True, message

        except Exception as e:
            logger.error(f"Error toggling forwarding: {e}")
            return False, f"Error: {str(e)}"

    async def disable_destroyer_temp(
        self, user_id: int, account_id: int, disable_password: str = None
    ) -> tuple[bool, str]:
        """Temporarily disable OTP destroyer for 5 minutes with password protection"""
        try:
            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()

                if not account:
                    return False, "Account not found"

                if not account.otp_destroyer_enabled:
                    return False, "⚠️ OTP Destroyer is not enabled"

                # Check if disable password is required
                if account.otp_destroyer_disable_auth:
                    if not disable_password:
                        return False, "🔒 Disable password required"

                    import hashlib

                    password_hash = hashlib.sha256(
                        disable_password.encode()
                    ).hexdigest()
                    if password_hash != account.otp_destroyer_disable_auth:
                        return False, "❌ Invalid disable password"

                # Temporarily disable destroyer
                expiry_time = time.time() + 300  # 5 minutes
                if user_id not in self.temp_passthrough:
                    self.temp_passthrough[user_id] = {}
                self.temp_passthrough[user_id][
                    f"{account.name}_destroyer_disabled"
                ] = expiry_time

                account.add_audit_entry(
                    {
                        "action": "destroyer_temp_disabled",
                        "duration": "5_minutes",
                        "auth_verified": bool(account.otp_destroyer_disable_auth),
                        "timestamp": int(time.time()),
                    }
                )
                await session.commit()

                # Schedule re-enable
                asyncio.create_task(
                    self._reenable_destroyer(user_id, account_id, expiry_time)
                )

                await self.bot.send_message(
                    user_id,
                    f"⏰ **OTP Destroyer Paused: {account.name}**\n\n"
                    f"❌ Destroyer disabled for 5 minutes\n"
                    f"🔓 You can now receive OTPs normally\n\n"
                    f"⚠️ Will auto-reactivate in 5 minutes",
                )

                return (
                    True,
                    "⏰ OTP Destroyer paused for 5 minutes\n🔓 You can now receive OTPs",
                )

        except Exception as e:
            logger.error(f"Error disabling destroyer temp: {e}")
            return False, f"Error: {str(e)}"

    async def _reenable_destroyer(
        self, user_id: int, account_id: int, expiry_time: float
    ):
        """Re-enable OTP destroyer after temp disable"""
        try:
            await asyncio.sleep(300)  # Wait 5 minutes

            # Clean up temp disable flag
            if user_id in self.temp_passthrough:
                for key in list(self.temp_passthrough[user_id].keys()):
                    if key.endswith("_destroyer_disabled"):
                        del self.temp_passthrough[user_id][key]
                if not self.temp_passthrough[user_id]:
                    del self.temp_passthrough[user_id]

            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()

                if account:
                    account.add_audit_entry(
                        {
                            "action": "destroyer_temp_reenabled",
                            "timestamp": int(time.time()),
                        }
                    )
                    await session.commit()

                    await self.bot.send_message(
                        user_id,
                        f"🛡️ **OTP Destroyer Reactivated: {account.name}**\n\n"
                        f"✅ 5-minute pause period ended\n"
                        f"🛡️ Full protection restored\n\n"
                        f"💡 Use 'Temp Disable' again if needed",
                    )

                    logger.info(f"OTP Destroyer re-enabled for {account.name}")

        except Exception as e:
            logger.error(f"Error re-enabling destroyer: {e}")

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

    async def enable_temp_passthrough(
        self, user_id: int, account_id: int, disable_password: str = None
    ) -> tuple[bool, str]:
        """Temporarily disable OTP destroyer and enable OTP forwarding for 5 minutes with password protection"""
        try:
            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()

                if not account:
                    return False, "Account not found"

                if not account.otp_destroyer_enabled:
                    return False, "⚠️ Temp OTP only works when OTP Destroyer is enabled"

                # Check if disable password is required
                if account.otp_destroyer_disable_auth:
                    if not disable_password:
                        return False, "🔒 Disable password required"

                    import hashlib

                    password_hash = hashlib.sha256(
                        disable_password.encode()
                    ).hexdigest()
                    if password_hash != account.otp_destroyer_disable_auth:
                        return False, "❌ Invalid disable password"

                # Store original states
                original_destroyer = account.otp_destroyer_enabled
                original_forward = account.otp_forward_enabled

                # Temporarily disable destroyer and enable forwarding
                account.otp_destroyer_enabled = False
                account.otp_forward_enabled = True
                account.otp_temp_passthrough = True

                account.add_audit_entry(
                    {
                        "action": "temp_otp_enabled",
                        "destroyer_disabled": True,
                        "forwarding_enabled": True,
                        "duration": "5_minutes",
                        "auth_verified": bool(account.otp_destroyer_disable_auth),
                        "timestamp": int(time.time()),
                    }
                )
                await session.commit()

                # Set in memory with expiry and original states
                expiry_time = time.time() + 300  # 5 minutes
                if user_id not in self.temp_passthrough:
                    self.temp_passthrough[user_id] = {}
                self.temp_passthrough[user_id][f"{account.name}_temp_otp"] = {
                    "expiry": expiry_time,
                    "original_destroyer": original_destroyer,
                    "original_forward": original_forward,
                }

                # Schedule restoration
                asyncio.create_task(
                    self._restore_temp_otp(user_id, account_id, expiry_time)
                )

                # Notify user about temporary access
                await self.bot.send_message(
                    user_id,
                    f"⏰ **Temp OTP Enabled: {account.name}**\n\n"
                    f"❌ OTP Destroyer temporarily disabled\n"
                    f"✅ OTP Forwarding temporarily enabled\n\n"
                    f"🔓 You'll receive OTPs for 5 minutes\n"
                    f"⚠️ Will auto-restore in 5 minutes",
                )

                return (
                    True,
                    "⏰ Temp OTP enabled for 5 minutes\n❌ Destroyer disabled\n✅ Forwarding enabled",
                )

        except Exception as e:
            logger.error(f"Error enabling temp OTP: {e}")
            return False, f"Error: {str(e)}"

    async def _restore_temp_otp(
        self, user_id: int, account_id: int, expiry_time: float
    ):
        """Restore original OTP settings after temp period expires"""
        try:
            await asyncio.sleep(300)  # Wait 5 minutes

            # Get original states from memory
            temp_key = None
            original_states = None
            if user_id in self.temp_passthrough:
                for key, value in self.temp_passthrough[user_id].items():
                    if (
                        key.endswith("_temp_otp")
                        and isinstance(value, dict)
                        and value.get("expiry") == expiry_time
                    ):
                        temp_key = key
                        original_states = value
                        break

            if not original_states:
                logger.warning(
                    f"Could not find original states for temp OTP restoration"
                )
                return

            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()

                if account and account.otp_temp_passthrough:
                    # Restore original settings
                    account.otp_destroyer_enabled = original_states[
                        "original_destroyer"
                    ]
                    account.otp_forward_enabled = original_states["original_forward"]
                    account.otp_temp_passthrough = False

                    account.add_audit_entry(
                        {
                            "action": "temp_otp_expired",
                            "destroyer_restored": original_states["original_destroyer"],
                            "forwarding_restored": original_states["original_forward"],
                            "timestamp": int(time.time()),
                        }
                    )
                    await session.commit()

                    # Clean up memory
                    if temp_key and user_id in self.temp_passthrough:
                        del self.temp_passthrough[user_id][temp_key]
                        if not self.temp_passthrough[user_id]:
                            del self.temp_passthrough[user_id]

                    # Notify user about restoration
                    destroyer_status = (
                        "✅ Enabled"
                        if original_states["original_destroyer"]
                        else "❌ Disabled"
                    )
                    forward_status = (
                        "✅ Enabled"
                        if original_states["original_forward"]
                        else "❌ Disabled"
                    )

                    await self.bot.send_message(
                        user_id,
                        f"⏰ **Temp OTP Expired: {account.name}**\n\n"
                        f"🔒 5-minute period ended\n"
                        f"🛡️ OTP Destroyer: {destroyer_status}\n"
                        f"📤 OTP Forwarding: {forward_status}\n\n"
                        f"💡 Settings restored to original state",
                    )

                    logger.info(
                        f"Temp OTP expired and settings restored for {account.name}"
                    )

        except Exception as e:
            logger.error(f"Error restoring temp OTP: {e}")

    async def set_disable_password(
        self, user_id: int, account_id: int, new_password: str, old_password: str = None
    ) -> tuple[bool, str]:
        """Set or change the disable password for OTP Destroyer"""
        try:
            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()

                if not account:
                    return False, "Account not found"

                # If password already exists, verify old password
                if account.otp_destroyer_disable_auth:
                    if not old_password:
                        return False, "🔐 Current password required to change"

                    import hashlib

                    old_password_hash = hashlib.sha256(
                        old_password.encode()
                    ).hexdigest()
                    if old_password_hash != account.otp_destroyer_disable_auth:
                        return False, "❌ Current password is incorrect"

                # Set new password
                import hashlib

                new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                account.otp_destroyer_disable_auth = new_password_hash

                action = (
                    "disable_password_changed"
                    if account.otp_destroyer_disable_auth
                    else "disable_password_set"
                )
                account.add_audit_entry(
                    {"action": action, "timestamp": int(time.time())}
                )
                await session.commit()

                message = (
                    "🔐 Disable password updated"
                    if old_password
                    else "🔐 Disable password set"
                )
                return True, f"{message}\n🛡️ Required for disabling OTP Destroyer"

        except Exception as e:
            logger.error(f"Error setting disable password: {e}")
            return False, f"Error: {str(e)}"

    async def remove_disable_password(
        self, user_id: int, account_id: int, current_password: str
    ) -> tuple[bool, str]:
        """Remove the disable password for OTP Destroyer"""
        try:
            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()

                if not account:
                    return False, "Account not found"

                if not account.otp_destroyer_disable_auth:
                    return False, "⚠️ No disable password is set"

                # Verify current password
                import hashlib

                password_hash = hashlib.sha256(current_password.encode()).hexdigest()
                if password_hash != account.otp_destroyer_disable_auth:
                    return False, "❌ Current password is incorrect"

                # Remove password
                account.otp_destroyer_disable_auth = None
                account.add_audit_entry(
                    {
                        "action": "disable_password_removed",
                        "timestamp": int(time.time()),
                    }
                )
                await session.commit()

                return (
                    True,
                    "🔓 Disable password removed\n⚠️ OTP Destroyer can now be disabled without password",
                )

        except Exception as e:
            logger.error(f"Error removing disable password: {e}")
            return False, f"Error: {str(e)}"
