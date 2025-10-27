"""
Application Constants
Centralized constants for TeleGuard application.
Provides consistent values across all modules and components.
Authors: @Meher_Mankar, @Gutkesh
Repository: https://github.com/mehermankar/teleguard
"""
from enum import Enum
from typing import Dict, Any
class AppConstants:
    """Core application constants"""
    # Application metadata
    APP_NAME = "TeleGuard"
    APP_VERSION = "2.0.0"
    API_VERSION = "v1"
    # Database constants
    MAX_ACCOUNTS_PER_USER = 10
    SESSION_TIMEOUT = 300  # 5 minutes
    AUDIT_LOG_RETENTION_DAYS = 30
    # Security constants
    PASSWORD_MIN_LENGTH = 8
    API_KEY_LENGTH = 32
    RATE_LIMIT_WINDOW = 3600  # 1 hour
    MAX_API_REQUESTS_PER_HOUR = 1000
    # Telegram constants
    MAX_MESSAGE_LENGTH = 4096
    MAX_CAPTION_LENGTH = 1024
    OTP_CODE_LENGTH = 5
    # File and session constants
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    SESSION_FILE_EXTENSION = ".session"
    BACKUP_RETENTION_COUNT = 5
class MessageTemplates:
    """Standard message templates"""
    # Success messages
    SUCCESS_ACCOUNT_ADDED = "✅ **Account Added Successfully**\n\nAccount: {name}\nPhone: {phone}"
    SUCCESS_OTP_ENABLED = "🛡️ **OTP Destroyer Enabled**\n\nProtection is now active for {account}"
    SUCCESS_2FA_SET = "🔑 **2FA Password Set**\n\nTwo-factor authentication enabled for {account}"
    # Error messages
    ERROR_ACCOUNT_NOT_FOUND = "❌ **Account Not Found**\n\nThe specified account could not be found."
    ERROR_SERVICE_UNAVAILABLE = "❌ **Service Unavailable**\n\nThe requested service is temporarily unavailable."
    ERROR_INVALID_INPUT = "❌ **Invalid Input**\n\nPlease check your input and try again."
    ERROR_PERMISSION_DENIED = "❌ **Permission Denied**\n\nYou don't have permission to perform this action."
    # Info messages
    INFO_PROCESSING = "⚙️ **Processing...**\n\nPlease wait while we process your request."
    INFO_SESSION_EXPIRED = "⏰ **Session Expired**\n\nPlease start the process again."
class DatabaseCollections:
    """Database collection names"""
    USERS = "users"
    ACCOUNTS = "accounts"
    AUDIT_LOGS = "audit_logs"
    SECURITY_EVENTS = "security_events"
    API_KEYS = "api_keys"
    SESSIONS = "sessions"
    TEMPLATES = "templates"
    SETTINGS = "settings"
class LogLevels:
    """Logging level constants"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
class EventTypes(Enum):
    """Event type enumeration"""
    # Account events
    ACCOUNT_ADDED = "account_added"
    ACCOUNT_REMOVED = "account_removed"
    ACCOUNT_UPDATED = "account_updated"
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    # OTP events
    OTP_ENABLED = "otp_enabled"
    OTP_DISABLED = "otp_disabled"
    OTP_DESTROYED = "otp_destroyed"
    # 2FA events
    TWO_FA_SET = "2fa_set"
    TWO_FA_CHANGED = "2fa_changed"
    TWO_FA_REMOVED = "2fa_removed"
    # Security events
    API_ACCESS_GRANTED = "api_access_granted"
    API_ACCESS_DENIED = "api_access_denied"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
class StatusCodes:
    """HTTP status codes"""
    # Success codes
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    # Client error codes
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429
    # Server error codes
    INTERNAL_SERVER_ERROR = 500
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504
class ConfigKeys:
    """Configuration key constants"""
    # Telegram API
    API_ID = "API_ID"
    API_HASH = "API_HASH"
    BOT_TOKEN = "BOT_TOKEN"
    # Database
    MONGO_URI = "MONGO_URI"
    REDIS_URL = "REDIS_URL"
    # Security - Load from environment only
    ENCRYPTION_KEY = "ENCRYPTION_KEY"  # Must be set in environment
    ADMIN_IDS = "ADMIN_IDS"  # Must be set in environment
    # Features
    MAX_ACCOUNTS = "MAX_ACCOUNTS"
    RATE_LIMIT_ENABLED = "RATE_LIMIT_ENABLED"
    SESSION_BACKUP_ENABLED = "SESSION_BACKUP_ENABLED"
class Emojis:
    """Emoji constants for consistent UI"""
    # Status emojis
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    PROCESSING = "⚙️"
    # Feature emojis
    SHIELD = "🛡️"
    KEY = "🔑"
    PHONE = "📱"
    MESSAGE = "💬"
    SETTINGS = "⚙️"
    BACK = "🔙"
    # Action emojis
    ADD = "➕"
    REMOVE = "❌"
    EDIT = "✏️"
    REFRESH = "🔄"
    DOWNLOAD = "📥"
    UPLOAD = "📤"
# Default configuration values
DEFAULT_CONFIG: Dict[str, Any] = {
    ConfigKeys.MAX_ACCOUNTS: AppConstants.MAX_ACCOUNTS_PER_USER,
    ConfigKeys.RATE_LIMIT_ENABLED: True,
    ConfigKeys.SESSION_BACKUP_ENABLED: False,
    "LOG_LEVEL": LogLevels.INFO,
    "SESSION_TIMEOUT": AppConstants.SESSION_TIMEOUT,
    "AUDIT_RETENTION_DAYS": AppConstants.AUDIT_LOG_RETENTION_DAYS,
}
