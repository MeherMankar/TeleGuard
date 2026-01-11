"""
Custom Exception Classes for TeleGuard
Professional exception hierarchy for better error handling and debugging.
Provides specific exceptions for different components and operations.
Authors: @Meher_Mankar, @Gutkesh
Repository: https://github.com/mehermankar/teleguard
"""

from typing import Any, Dict, Optional


class TeleGuardError(Exception):
    """Base exception class for all TeleGuard errors"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)

    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class DatabaseError(TeleGuardError):
    """Database operation errors"""



class AuthenticationError(TeleGuardError):
    """Authentication and authorization errors"""



class ValidationError(TeleGuardError):
    """Input validation errors"""



class ConfigurationError(TeleGuardError):
    """Configuration and setup errors"""



class TelegramClientError(TeleGuardError):
    """Telegram client operation errors"""



class OTPError(TeleGuardError):
    """OTP management errors"""



class SessionError(TeleGuardError):
    """Session management errors"""



class APIError(TeleGuardError):
    """API operation errors"""



class RateLimitError(TeleGuardError):
    """Rate limiting errors"""



class SecurityError(TeleGuardError):
    """Security-related errors"""



class AccountError(TeleGuardError):
    """Account management errors"""

