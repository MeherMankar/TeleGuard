"""Enhanced error handling utilities"""
import logging
import asyncio
import traceback
from typing import Optional, Dict, Any
from telethon.errors import (
    PhoneNumberInvalidError, 
    FloodWaitError, 
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    AuthKeyUnregisteredError,
    UserDeactivatedError
)

logger = logging.getLogger(__name__)

class ErrorHandler:
    """Enhanced error handling for TeleGuard operations"""
    
    @staticmethod
    def get_user_friendly_error(error: Exception) -> str:
        """Convert technical errors to user-friendly messages"""
        error_str = str(error)
        error_type = type(error).__name__
        
        # Phone number errors
        if isinstance(error, PhoneNumberInvalidError) or "phone number is invalid" in error_str.lower():
            return (
                "❌ **Invalid Phone Number**\n\n"
                "Please check:\n"
                "• Correct country code (e.g., +1 for US)\n"
                "• Valid phone number format\n"
                "• No extra characters or spaces\n\n"
                "Example: +1234567890"
            )
        
        # Rate limiting errors
        if isinstance(error, FloodWaitError) or "flood" in error_str.lower():
            wait_time = getattr(error, 'seconds', 0)
            if wait_time > 0:
                hours = wait_time // 3600
                minutes = (wait_time % 3600) // 60
                if hours > 0:
                    time_str = f"{hours}h {minutes}m"
                elif minutes > 0:
                    time_str = f"{minutes}m"
                else:
                    time_str = f"{wait_time}s"
                return (
                    f"⏰ **Rate Limited**\n\n"
                    f"Please wait {time_str} before trying again.\n\n"
                    "This is a Telegram limitation to prevent spam."
                )
            else:
                return (
                    "⏰ **Rate Limited**\n\n"
                    "Too many requests. Please wait before trying again."
                )
        
        # 2FA errors
        if isinstance(error, SessionPasswordNeededError) or "password" in error_str.lower():
            return (
                "🔐 **Two-Factor Authentication Required**\n\n"
                "Please enter your 2FA password.\n"
                "Your message will be deleted for security."
            )
        
        # OTP errors
        if isinstance(error, PhoneCodeExpiredError) or "expired" in error_str.lower():
            return (
                "⏰ **Verification Code Expired**\n\n"
                "Please request a new code:\n"
                "1. Go to Account Settings\n"
                "2. Add Account again\n"
                "3. Enter the new code quickly"
            )
        
        if isinstance(error, PhoneCodeInvalidError) or "invalid" in error_str.lower():
            return (
                "❌ **Invalid Verification Code**\n\n"
                "Please check the code and try again.\n"
                "Make sure all digits are correct."
            )
        
        # Session errors
        if isinstance(error, AuthKeyUnregisteredError) or "authorization key" in error_str.lower():
            return (
                "🔑 **Session Invalid**\n\n"
                "Your session has expired or was used elsewhere.\n"
                "Please re-add this account to continue."
            )
        
        # Account deactivated
        if isinstance(error, UserDeactivatedError) or "deactivated" in error_str.lower():
            return (
                "🚫 **Account Deactivated**\n\n"
                "This Telegram account has been deactivated.\n"
                "Please contact Telegram support."
            )
        
        # Network errors
        if "network" in error_str.lower() or "connection" in error_str.lower():
            return (
                "🌐 **Network Error**\n\n"
                "Connection issue detected. Please:\n"
                "• Check your internet connection\n"
                "• Try again in a few moments"
            )
        
        # Generic timeout
        if "timeout" in error_str.lower():
            return (
                "⏱️ **Operation Timed Out**\n\n"
                "The operation took too long. Please try again."
            )
        
        # Account-related errors
        if "account" in error_str.lower() or "client" in error_str.lower():
            if "authorization" in error_str.lower() or "auth" in error_str.lower():
                return (
                    "🔑 **Account Authorization Error**\n\n"
                    "Your account session has expired or is invalid.\n"
                    "Please re-add this account to continue using it."
                )
            elif "connection" in error_str.lower() or "network" in error_str.lower():
                return (
                    "🌐 **Account Connection Error**\n\n"
                    "Unable to connect your account. This could be due to:\n"
                    "• Network connectivity issues\n"
                    "• Telegram server problems\n"
                    "• Account restrictions\n\n"
                    "Please try again in a few minutes."
                )
            elif "banned" in error_str.lower() or "restricted" in error_str.lower():
                return (
                    "🚫 **Account Restricted**\n\n"
                    "This account appears to be restricted or banned.\n"
                    "Please check your account status in the official Telegram app."
                )
            else:
                return (
                    "⚠️ **Account Error**\n\n"
                    "There was an issue with your account.\n"
                    "Please try again or contact support if the problem persists."
                )
        
        # Default error message for account-related issues
        if any(keyword in error_str.lower() for keyword in ['account', 'session', 'client', 'login', 'auth']):
            return (
                "⚠️ **Account Issue**\n\n"
                "An error occurred with your account. Please try again.\n"
                "If the problem persists, you may need to re-add the account."
            )
        
        # Default error message
        return f"❌ **Error**: {error_str}"
    
    @staticmethod
    async def handle_client_error(client, error: Exception, context: str = "", user_id: Optional[int] = None, bot = None) -> bool:
        """Handle client-specific errors and return whether to retry"""
        error_str = str(error)
        
        logger.error(f"Client error in {context}: {error_str}")
        
        # Send user-friendly error to user if bot and user_id provided
        if bot and user_id:
            await ErrorHandler.notify_user_of_error(bot, user_id, error, context)
        
        # IP address conflicts - don't retry
        if "ip address" in error_str.lower() and "simultaneously" in error_str.lower():
            logger.warning(f"IP conflict detected: {error_str}")
            return False
        
        # Authorization errors - don't retry
        if isinstance(error, AuthKeyUnregisteredError):
            logger.warning(f"Auth key unregistered: {error_str}")
            return False
        
        # Rate limiting - don't retry immediately
        if isinstance(error, FloodWaitError):
            logger.warning(f"Rate limited: {error_str}")
            return False
        
        # Network errors - can retry
        if "network" in error_str.lower() or "connection" in error_str.lower():
            logger.info(f"Network error, can retry: {error_str}")
            return True
        
        # Timeout errors - can retry
        if "timeout" in error_str.lower():
            logger.info(f"Timeout error, can retry: {error_str}")
            return True
        
        # Default: don't retry unknown errors
        return False
    
    @staticmethod
    def log_error_details(error: Exception, context: str = "", user_id: Optional[int] = None):
        """Log detailed error information for debugging"""
        error_details = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "user_id": user_id,
            "traceback": traceback.format_exc()
        }
        
        logger.error(f"Detailed error log: {error_details}")
    
    @staticmethod
    async def handle_account_error(bot, user_id: int, error: Exception, account_name: str = "", context: str = ""):
        """Handle account-specific errors and notify user"""
        try:
            # Log the error for debugging
            ErrorHandler.log_error_details(error, f"Account error - {context}", user_id)
            
            # Send user-friendly message
            await ErrorHandler.notify_user_of_error(bot, user_id, error, context)
            
            # If it's a critical account error, also notify admin
            if ErrorHandler.is_critical_error(error):
                await ErrorHandler.notify_admin_if_critical(bot, error, f"Account: {account_name}, User: {user_id}")
                
        except Exception as e:
            logger.error(f"Failed to handle account error for user {user_id}: {e}")
    
    @staticmethod
    async def safe_operation(operation, *args, max_retries: int = 3, **kwargs):
        """Safely execute an operation with retries"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_error = e
                
                # Check if we should retry
                should_retry = ErrorHandler.handle_client_error(None, e, f"attempt {attempt + 1}")
                
                if not should_retry or attempt == max_retries - 1:
                    break
                
                # Wait before retry (exponential backoff)
                wait_time = min(2 ** attempt, 10)  # Max 10 seconds
                await asyncio.sleep(wait_time)
                
                logger.info(f"Retrying operation after {wait_time}s (attempt {attempt + 2}/{max_retries})")
        
        # If we get here, all retries failed
        raise last_error
    
    @staticmethod
    def is_critical_error(error: Exception) -> bool:
        """Determine if an error is critical and requires immediate attention"""
        error_str = str(error).lower()
        
        critical_patterns = [
            "database",
            "mongodb",
            "connection pool",
            "out of memory",
            "disk space",
            "permission denied"
        ]
        
        return any(pattern in error_str for pattern in critical_patterns)
    
    @staticmethod
    async def notify_user_of_error(bot, user_id: int, error: Exception, context: str = ""):
        """Send user-friendly error message to user"""
        try:
            user_friendly_msg = ErrorHandler.get_user_friendly_error(error)
            await bot.send_message(user_id, user_friendly_msg)
        except Exception as e:
            logger.error(f"Failed to notify user {user_id} of error: {e}")
    
    @staticmethod
    async def notify_admin_if_critical(bot, error: Exception, context: str = ""):
        """Notify admin if error is critical"""
        if not ErrorHandler.is_critical_error(error):
            return
        
        try:
            from ..core.config import ADMIN_IDS
            
            error_msg = (
                f"🚨 **Critical Error Detected**\n\n"
                f"**Context**: {context}\n"
                f"**Error**: {str(error)}\n"
                f"**Type**: {type(error).__name__}\n\n"
                f"Please check the logs immediately."
            )
            
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, error_msg)
                except Exception as notify_error:
                    logger.error(f"Failed to notify admin {admin_id}: {notify_error}")
                    
        except Exception as e:
            logger.error(f"Failed to send critical error notification: {e}")