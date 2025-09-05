"""Enhanced OTP Destroyer with audit logging and security

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import re
import time
import json
import hashlib
import logging
from typing import List, Optional
from telethon import events, functions
from database import get_session
from models import Account, User

logger = logging.getLogger(__name__)

class EnhancedOTPDestroyer:
    """Enhanced OTP destroyer with audit logging and security features"""
    
    CODE_REGEX = re.compile(r'(?<!\d)(\d(?:-?\d){4,6})(?!\d)')
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        
    def normalize_codes(self, raw_codes: List[str]) -> List[str]:
        """Normalize and deduplicate OTP codes"""
        normalized = []
        for code in raw_codes:
            clean_code = re.sub(r'[^0-9]', '', code)
            if len(clean_code) >= 5:  # Valid OTP length
                normalized.append(clean_code)
        return list(set(normalized))
    
    def extract_codes_from_message(self, message: str) -> List[str]:
        """Extract OTP codes from service message"""
        found_codes = self.CODE_REGEX.findall(message)
        return self.normalize_codes(found_codes) if found_codes else []
    
    async def setup_otp_listener(self, client, user_id: int, account_name: str):
        """Set up OTP destroyer listener for an account"""
        
        @client.on(events.NewMessage(chats=777000))
        async def otp_destroyer_handler(event):
            try:
                # Check if OTP destroyer is enabled for this account
                async with get_session() as session:
                    from sqlalchemy import select
                    result = await session.execute(
                        select(Account)
                        .join(User)
                        .where(User.telegram_id == user_id, Account.name == account_name)
                    )
                    account = result.scalar_one_or_none()
                    
                    if not account or not account.otp_destroyer_enabled:
                        return
                    
                    message = event.message.message
                    codes = self.extract_codes_from_message(message)
                    
                    if not codes:
                        return
                    
                    logger.info(f"OTP Destroyer: Found codes {codes} for account {account_name}")
                    
                    # Invalidate codes using Telegram API
                    try:
                        result = await client(functions.account.InvalidateSignInCodesRequest(
                            codes=codes
                        ))
                        
                        # Log the action
                        audit_entry = {
                            "action": "invalidate_codes",
                            "codes": codes,
                            "result": bool(result),
                            "message_id": event.message.id,
                            "raw_message": message[:200]  # First 200 chars
                        }
                        
                        account.add_audit_entry(audit_entry)
                        account.otp_destroyed_at = time.strftime('%Y-%m-%d %H:%M:%S')
                        await session.commit()
                        
                        # Notify owner
                        await self._send_destruction_alert(user_id, account_name, codes, bool(result))
                        
                        logger.info(f"Successfully invalidated codes {codes} for {account_name}")
                        
                    except Exception as e:
                        logger.error(f"Failed to invalidate codes: {e}")
                        
                        # Log the failure
                        audit_entry = {
                            "action": "invalidate_error",
                            "codes": codes,
                            "error": str(e)
                        }
                        account.add_audit_entry(audit_entry)
                        await session.commit()
                        
            except Exception as e:
                logger.error(f"OTP destroyer handler error: {e}")
    
    async def _send_destruction_alert(self, user_id: int, account_name: str, codes: List[str], success: bool):
        """Send alert about OTP code destruction"""
        codes_str = ", ".join(codes)
        status = "✅ SUCCESS" if success else "❌ FAILED"
        
        alert_message = (
            f"🛡️ OTP DESTROYER ACTIVATED\n\n"
            f"Account: {account_name}\n"
            f"Status: {status}\n"
            f"Codes: {codes_str}\n\n"
            f"{'Codes permanently invalidated on Telegram servers.' if success else 'Failed to invalidate codes.'}\n"
            f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        try:
            await self.bot.send_message(user_id, alert_message)
        except Exception as e:
            logger.error(f"Failed to send destruction alert: {e}")
    
    async def enable_otp_destroyer(self, user_id: int, account_id: int) -> bool:
        """Enable OTP destroyer for an account"""
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
                    return False
                
                account.otp_destroyer_enabled = True
                account.add_audit_entry({
                    "action": "enable_otp_destroyer",
                    "user_id": user_id
                })
                await session.commit()
                
                logger.info(f"OTP destroyer enabled for account {account.name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to enable OTP destroyer: {e}")
            return False
    
    async def disable_otp_destroyer(self, user_id: int, account_id: int, auth_password: str = None) -> tuple[bool, str]:
        """Disable OTP destroyer with authentication"""
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
                
                # Check if disable auth is required
                if account.otp_destroyer_disable_auth:
                    if not auth_password:
                        return False, "Password required to disable OTP destroyer"
                    
                    # Verify password hash
                    password_hash = hashlib.sha256(auth_password.encode()).hexdigest()
                    if password_hash != account.otp_destroyer_disable_auth:
                        return False, "Invalid password"
                
                account.otp_destroyer_enabled = False
                account.add_audit_entry({
                    "action": "disable_otp_destroyer",
                    "user_id": user_id,
                    "auth_used": bool(auth_password)
                })
                await session.commit()
                
                logger.info(f"OTP destroyer disabled for account {account.name}")
                return True, "OTP destroyer disabled successfully"
                
        except Exception as e:
            logger.error(f"Failed to disable OTP destroyer: {e}")
            return False, f"Error: {str(e)}"
    
    async def set_disable_password(self, user_id: int, account_id: int, password: str) -> bool:
        """Set password required to disable OTP destroyer"""
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
                    return False
                
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                account.otp_destroyer_disable_auth = password_hash
                account.add_audit_entry({
                    "action": "set_disable_password",
                    "user_id": user_id
                })
                await session.commit()
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to set disable password: {e}")
            return False