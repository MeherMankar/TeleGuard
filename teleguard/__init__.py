from .core.constants import AppConstants

__version__ = AppConstants.APP_VERSION
__author__ = "Meher Mankar & Gutkesh"
__email__ = "support@teleguard.dev"

# Core imports
from .core.bot_manager import BotManager as AccountManager
from .core.client_manager import get_client_manager
from .core.config import (
    ADMIN_IDS,
    API_HASH,
    API_ID,
    BOT_TOKEN,
    ENCRYPTION_KEY,
    MAX_ACCOUNTS,
    MONGODB_URI,
    REDIS_URL,
    SESSION_BACKUP_ENABLED,
    ConfigManager,
    config,
)

# Exception imports
from .core.exceptions import (
    AccountError,
    APIError,
    AuthenticationError,
    ConfigurationError,
    DatabaseError,
    OTPError,
    RateLimitError,
    SecurityError,
    SessionError,
    TelegramClientError,
    TeleGuardError,
    ValidationError,
)
from .core.task_queue import task_queue
from .utils.health_server import health_checker
from .utils.rate_limiter import rate_limiter
from .utils.session_manager import SessionManager
from .utils.validators import Validators

__all__ = [
    "AccountManager",
    "Validators",
    "SessionManager",
    "rate_limiter",
    "get_client_manager",
    "task_queue",
    "health_checker",
    "config",
    "ConfigManager",
    "API_ID",
    "API_HASH",
    "BOT_TOKEN",
    "ADMIN_IDS",
    "MAX_ACCOUNTS",
    "MONGODB_URI",
    "REDIS_URL",
    "SESSION_BACKUP_ENABLED",
    "ENCRYPTION_KEY",
    "TeleGuardError",
    "DatabaseError",
    "AuthenticationError",
    "ValidationError",
    "ConfigurationError",
    "TelegramClientError",
    "OTPError",
    "SessionError",
    "APIError",
    "RateLimitError",
    "SecurityError",
    "AccountError",
]
