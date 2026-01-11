"""
Professional Configuration Management for TeleGuard
Centralized configuration system with validation, type safety,
and comprehensive error handling for all application settings.
Authors: @Meher_Mankar, @Gutkesh
Repository: https://github.com/mehermankar/teleguard
"""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Set

from cryptography.fernet import Fernet
from dotenv import load_dotenv

from .constants import ConfigKeys
from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Application environment types"""

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


@dataclass
class TelegramConfig:
    """Telegram API configuration"""

    api_id: int
    api_hash: str
    bot_token: str

    def __post_init__(self):
        """Validate Telegram configuration"""
        if not isinstance(self.api_id, int) or self.api_id <= 0:
            raise ConfigurationError("API_ID must be a positive integer")
        if not self.api_hash or len(self.api_hash) != 32:
            raise ConfigurationError(
                "API_HASH must be a 32-character hexadecimal string"
            )
        if not self.bot_token or ":" not in self.bot_token:
            raise ConfigurationError("BOT_TOKEN must be in format 'bot_id:token'")


@dataclass
class DatabaseConfig:
    """Database configuration"""

    mongodb_uri: str
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 20
    redis_retry_on_timeout: bool = True
    redis_health_check_interval: int = 30

    def __post_init__(self):
        """Validate database configuration"""
        if not self.mongodb_uri:
            raise ConfigurationError("MONGODB_URI is required")


@dataclass
class SecurityConfig:
    """Security configuration"""

    encryption_key: Optional[bytes] = None
    fernet_key: Optional[str] = None
    backup_encryption_key: Optional[str] = None
    session_backup_enabled: bool = False
    audit_log_retention_days: int = 30
    admin_ids: Set[int] = field(default_factory=set)

    def __post_init__(self):
        """Validate security configuration"""
        if self.session_backup_enabled and not self.backup_encryption_key:
            logger.warning("Session backup enabled but no encryption key provided")


@dataclass
class PerformanceConfig:
    """Performance and limits configuration"""

    max_accounts: int = 999999
    rate_limit_requests: int = 30
    rate_limit_window: int = 60
    database_pool_size: int = 10
    max_client_idle_time: int = 3600
    health_check_interval: int = 300
    keep_alive_interval: int = 3600

    def __post_init__(self):
        """Validate performance configuration"""
        if self.max_accounts <= 0:
            raise ConfigurationError("MAX_ACCOUNTS must be greater than 0")


@dataclass
class CacheConfig:
    """Cache TTL configuration"""

    session_token_ttl: int = 3600
    otp_code_ttl: int = 300
    temp_data_ttl: int = 1800
    rate_limit_ttl: int = 3600


@dataclass
class BackupConfig:
    """Backup system configuration"""

    telegram_backup_channel: Optional[str] = None
    github_repo: Optional[str] = None
    github_token: Optional[str] = None
    github_backup_branch: str = "backups"
    snapshot_dir: Optional[str] = None


@dataclass
class SessionMasterConfig:
    """SessionMaster configuration settings"""

    max_auth_attempts: int = 3
    auth_timeout: int = 300
    device_rotation_enabled: bool = True
    session_validation_interval: int = 3600
    max_concurrent_sessions: int = 50
    automation_enabled: bool = True
    max_concurrent_tasks: int = 10
    task_retry_limit: int = 3
    bulk_subscribe_delay: tuple = (1, 3)
    bulk_message_delay: tuple = (2, 5)
    bulk_operation_batch_size: int = 50
    analytics_enabled: bool = True
    phone_auth_enabled: bool = True
    session_file_upload: bool = True
    session_string_import: bool = True
    bulk_operations_enabled: bool = True
    member_extraction_enabled: bool = True
    message_scraping_enabled: bool = True
    account_warming_enabled: bool = True


class ConfigManager:
    """
    Professional configuration manager with validation and type safety.
    Handles loading, validation, and access to all application configuration
    with comprehensive error handling and environment-specific settings.
    """

    def __init__(self, env_file: Optional[Path] = None):
        self.env_file = env_file or self._get_default_env_file()
        self.environment = self._detect_environment()
        self._load_environment()
        self.telegram = self._load_telegram_config()
        self.database = self._load_database_config()
        self.security = self._load_security_config()
        self.performance = self._load_performance_config()
        self.cache = self._load_cache_config()
        self.backup = self._load_backup_config()
        self.sessionmaster = self._load_sessionmaster_config()
        self._validate_configuration()
        # Configuration loaded successfully

    def _get_default_env_file(self) -> Path:
        """Get default .env file path"""
        # Try multiple locations for .env file
        possible_paths = [
            Path(".env"),  # Current directory
            Path("config/.env"),  # Config subdirectory
            Path(__file__).parent.parent.parent / ".env",  # Project root
            Path(__file__).parent.parent.parent / "config" / ".env",  # Original path
        ]

        for path in possible_paths:
            if path.exists():
                return path

        # Return the first path as default (will be created if needed)
        return possible_paths[0]

    def _detect_environment(self) -> Environment:
        """Detect current environment"""
        env_name = os.getenv("ENVIRONMENT", "production").lower()
        try:
            return Environment(env_name)
        except ValueError:
            logger.warning(
                f"Unknown environment '{env_name}', defaulting to production"
            )
            return Environment.PRODUCTION

    def _load_environment(self) -> None:
        """Load environment variables from .env file"""
        if self.env_file.exists():
            load_dotenv(self.env_file)
        else:
            # Try to load from environment variables directly
            load_dotenv()

    def _load_telegram_config(self) -> TelegramConfig:
        """Load and validate Telegram configuration"""
        api_id_str = os.getenv(ConfigKeys.API_ID)
        if not api_id_str:
            raise ConfigurationError("API_ID environment variable is required")
        try:
            api_id = int(api_id_str)
        except ValueError:
            raise ConfigurationError("API_ID must be a valid integer")
        api_hash = os.getenv(ConfigKeys.API_HASH)
        if not api_hash:
            raise ConfigurationError("API_HASH environment variable is required")
        bot_token = os.getenv(ConfigKeys.BOT_TOKEN)
        if not bot_token:
            raise ConfigurationError("BOT_TOKEN environment variable is required")
        return TelegramConfig(api_id=api_id, api_hash=api_hash, bot_token=bot_token)

    def _load_database_config(self) -> DatabaseConfig:
        """Load and validate database configuration"""
        mongodb_uri = os.getenv(ConfigKeys.MONGO_URI)
        if not mongodb_uri:
            raise ConfigurationError("MONGO_URI environment variable is required")
        return DatabaseConfig(
            mongodb_uri=mongodb_uri,
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            redis_max_connections=self._get_int_env("REDIS_MAX_CONNECTIONS", 20),
            redis_retry_on_timeout=self._get_bool_env("REDIS_RETRY_ON_TIMEOUT", True),
            redis_health_check_interval=self._get_int_env(
                "REDIS_HEALTH_CHECK_INTERVAL", 30
            ),
        )

    def _load_security_config(self) -> SecurityConfig:
        """Load and validate security configuration"""
        # Parse admin IDs
        admin_ids = self._parse_admin_ids()
        encryption_key = self._get_or_create_encryption_key()
        fernet_key = os.getenv("FERNET_KEY")
        backup_encryption_key = os.getenv(ConfigKeys.ENCRYPTION_KEY)
        return SecurityConfig(
            encryption_key=encryption_key,
            fernet_key=fernet_key,
            backup_encryption_key=backup_encryption_key,
            session_backup_enabled=self._get_bool_env(
                ConfigKeys.SESSION_BACKUP_ENABLED, False
            ),
            audit_log_retention_days=self._get_int_env("AUDIT_LOG_RETENTION_DAYS", 30),
            admin_ids=admin_ids,
        )

    def _load_performance_config(self) -> PerformanceConfig:
        """Load and validate performance configuration"""
        return PerformanceConfig(
            max_accounts=self._get_int_env(ConfigKeys.MAX_ACCOUNTS, 999999),
            rate_limit_requests=self._get_int_env("RATE_LIMIT_REQUESTS", 30),
            rate_limit_window=self._get_int_env("RATE_LIMIT_WINDOW", 60),
            database_pool_size=self._get_int_env("DATABASE_POOL_SIZE", 10),
            max_client_idle_time=self._get_int_env("MAX_CLIENT_IDLE_TIME", 3600),
            health_check_interval=self._get_int_env("HEALTH_CHECK_INTERVAL", 300),
            keep_alive_interval=self._get_int_env("KEEP_ALIVE_INTERVAL", 3600),
        )

    def _load_cache_config(self) -> CacheConfig:
        """Load cache configuration"""
        return CacheConfig(
            session_token_ttl=self._get_int_env("CACHE_TTL_SESSION_TOKEN", 3600),
            otp_code_ttl=self._get_int_env("CACHE_TTL_OTP_CODE", 300),
            temp_data_ttl=self._get_int_env("CACHE_TTL_TEMP_DATA", 1800),
            rate_limit_ttl=self._get_int_env("CACHE_TTL_RATE_LIMIT", 3600),
        )

    def _load_backup_config(self) -> BackupConfig:
        """Load backup system configuration"""
        return BackupConfig(
            telegram_backup_channel=os.getenv("TELEGRAM_BACKUP_CHANNEL"),
            github_repo=os.getenv("GITHUB_REPO"),
            github_token=os.getenv("GITHUB_TOKEN"),
            github_backup_branch=os.getenv("GITHUB_BACKUP_BRANCH", "backups"),
            snapshot_dir=os.getenv("SNAPSHOT_DIR"),
        )

    def _load_sessionmaster_config(self) -> SessionMasterConfig:
        """Load SessionMaster configuration"""
        return SessionMasterConfig(
            max_auth_attempts=self._get_int_env("SM_MAX_AUTH_ATTEMPTS", 3),
            auth_timeout=self._get_int_env("SM_AUTH_TIMEOUT", 300),
            device_rotation_enabled=self._get_bool_env("SM_DEVICE_ROTATION", True),
            session_validation_interval=self._get_int_env(
                "SM_SESSION_VALIDATION_INTERVAL", 3600
            ),
            max_concurrent_sessions=self._get_int_env("SM_MAX_CONCURRENT_SESSIONS", 50),
            automation_enabled=self._get_bool_env("SM_AUTOMATION_ENABLED", True),
            max_concurrent_tasks=self._get_int_env("SM_MAX_CONCURRENT_TASKS", 10),
            task_retry_limit=self._get_int_env("SM_TASK_RETRY_LIMIT", 3),
            bulk_subscribe_delay=tuple(
                map(int, os.getenv("SM_BULK_SUBSCRIBE_DELAY", "1,3").split(","))
            ),
            bulk_message_delay=tuple(
                map(int, os.getenv("SM_BULK_MESSAGE_DELAY", "2,5").split(","))
            ),
            bulk_operation_batch_size=self._get_int_env("SM_BULK_BATCH_SIZE", 50),
            analytics_enabled=self._get_bool_env("SM_ANALYTICS_ENABLED", True),
            phone_auth_enabled=self._get_bool_env("SM_PHONE_AUTH", True),
            session_file_upload=self._get_bool_env("SM_SESSION_FILE_UPLOAD", True),
            session_string_import=self._get_bool_env("SM_SESSION_STRING_IMPORT", True),
            bulk_operations_enabled=self._get_bool_env("SM_BULK_OPERATIONS", True),
            member_extraction_enabled=self._get_bool_env("SM_MEMBER_EXTRACTION", True),
            message_scraping_enabled=self._get_bool_env("SM_MESSAGE_SCRAPING", True),
            account_warming_enabled=self._get_bool_env("SM_ACCOUNT_WARMING", True),
        )

    def _parse_admin_ids(self) -> Set[int]:
        """Parse admin IDs with proper error handling"""
        admin_ids_str = os.getenv(ConfigKeys.ADMIN_IDS, "")
        if not admin_ids_str:
            logger.warning("No admin IDs configured")
            return set()
        admin_ids = set()
        for uid in admin_ids_str.split(","):
            uid = uid.strip()
            if uid:
                try:
                    admin_ids.add(int(uid))
                except ValueError:
                    logger.warning(f"Invalid admin ID: {uid}")
        # Admin IDs loaded
        return admin_ids

    def _get_or_create_encryption_key(self) -> Optional[bytes]:
        """Get existing encryption key or create a new one"""
        key_file = Path(__file__).parent.parent.parent / "config" / "secret.key"
        try:
            if key_file.exists():
                with open(key_file, "rb") as f:
                    key = f.read()
                    Fernet(key)
                    return key
            else:
                # Generate new key
                key = Fernet.generate_key()
                key_file.parent.mkdir(exist_ok=True)
                with open(key_file, "wb") as f:
                    f.write(key)
                # Generated new encryption key
                return key
        except Exception as e:
            logger.error(f"Failed to handle encryption key: {e}")
            return None

    def _get_int_env(self, key: str, default: int) -> int:
        """Get integer environment variable with default"""
        try:
            return int(os.getenv(key, str(default)))
        except (ValueError, TypeError):
            # Using default value for invalid integer
            return default

    def _get_bool_env(self, key: str, default: bool) -> bool:
        """Get boolean environment variable with default"""
        value = os.getenv(key, str(default)).lower()
        return value in ("true", "1", "yes", "on")

    def _validate_configuration(self) -> None:
        """Validate complete configuration"""
        if (
            not self.telegram.api_id
            or not self.telegram.api_hash
            or not self.telegram.bot_token
        ):
            raise ConfigurationError("Telegram API credentials are incomplete")
        if not self.database.mongodb_uri:
            raise ConfigurationError("Database configuration is incomplete")
        if not self.security.admin_ids:
            pass  # No admin users configured
        # Environment-specific validation
        if self.environment == Environment.PRODUCTION:
            if not self.security.encryption_key:
                pass  # No encryption key in production
            if self.performance.max_accounts > 20:
                pass  # High account limit in production

    def get_fernet_cipher(self) -> Optional[Fernet]:
        """Get Fernet cipher instance if available"""
        if self.security.fernet_key:
            try:
                return Fernet(self.security.fernet_key.encode())
            except Exception as e:
                logger.error(f"Failed to create Fernet cipher: {e}")
        return None

    def is_admin(self, user_id: int) -> bool:
        """Check if user is an admin"""
        return user_id in self.security.admin_ids

    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary for logging/debugging"""
        return {
            "environment": self.environment.value,
            "max_accounts": self.performance.max_accounts,
            "admin_count": len(self.security.admin_ids),
            "backup_enabled": self.security.session_backup_enabled,
            "encryption_enabled": bool(self.security.encryption_key),
            "redis_configured": bool(self.database.redis_url),
            "github_backup": bool(self.backup.github_repo),
            "telegram_backup": bool(self.backup.telegram_backup_channel),
        }


# Global configuration instance
config = ConfigManager()
# Legacy compatibility - expose commonly used values
API_ID = config.telegram.api_id
API_HASH = config.telegram.api_hash
BOT_TOKEN = config.telegram.bot_token
ADMIN_IDS = config.security.admin_ids
MAX_ACCOUNTS = config.performance.max_accounts
MONGODB_URI = config.database.mongodb_uri
REDIS_URL = config.database.redis_url
SESSION_BACKUP_ENABLED = config.security.session_backup_enabled
TELEGRAM_BACKUP_CHANNEL = config.backup.telegram_backup_channel
ENCRYPTION_KEY = config.security.encryption_key
FERNET = config.get_fernet_cipher()
# Configuration loaded
