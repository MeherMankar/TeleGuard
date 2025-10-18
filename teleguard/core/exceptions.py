"""
Custom Exception Classes for TeleGuard
Professional exception hierarchy for better error handling and debugging.
Provides specific exceptions for different components and operations.
Authors: @Meher_Mankar, @Gutkesh
Repository: https://github.com/mehermankar/teleguard
"""
from typing import Optional, Dict, Any
class TeleGuardError(Exception):
    """Base exception class for all TeleGuard errors"""
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
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
    pass
class AuthenticationError(TeleGuardError):
    """Authentication and authorization errors"""
    pass
class ValidationError(TeleGuardError):
    """Input validation errors"""
    pass
class ConfigurationError(TeleGuardError):
    """Configuration and setup errors"""
    pass
class TelegramClientError(TeleGuardError):
    """Telegram client operation errors"""
    pass
class OTPError(TeleGuardError):
    """OTP management errors"""
    pass
class SessionError(TeleGuardError):
    """Session management errors"""
    pass
class APIError(TeleGuardError):
    """API operation errors"""
    pass
class RateLimitError(TeleGuardError):
    """Rate limiting errors"""
    pass
class SecurityError(TeleGuardError):
    """Security-related errors"""
    pass

class AccountError(TeleGuardError):
    """Account management errors"""
    pass
