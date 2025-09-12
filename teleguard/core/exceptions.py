"""Custom exceptions for TeleGuard"""


class TeleGuardError(Exception):
    """Base exception for TeleGuard"""

    pass


class AuthenticationError(TeleGuardError):
    """Authentication related errors"""

    pass


class ValidationError(TeleGuardError):
    """Input validation errors"""

    pass


class AccountError(TeleGuardError):
    """Account management errors"""

    pass


class SessionError(TeleGuardError):
    """Session handling errors"""

    pass


class RateLimitError(TeleGuardError):
    """Rate limiting errors"""

    pass


class DatabaseError(TeleGuardError):
    """Database operation errors"""

    pass
