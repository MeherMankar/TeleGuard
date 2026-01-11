"""
Session Guardian Configuration
Loads configuration from environment variables with safe defaults
"""

import os
from typing import Any, Dict


def load_guardian_config() -> Dict[str, Any]:
    """Load session guardian configuration from environment variables"""

    config = {
        # Basic settings
        "log_dir": os.getenv("LOG_DIR", "logs"),
        "summary_interval": int(os.getenv("SUMMARY_INTERVAL", "36000")),  # 10 hours
        # Rate limiting settings
        "rate_limits": {
            "messages_per_minute": int(os.getenv("MAX_MESSAGES_PER_MINUTE", "20")),
            "joins_per_hour": int(os.getenv("MAX_JOINS_PER_HOUR", "10")),
            "forwards_per_minute": int(os.getenv("MAX_FORWARDS_PER_MINUTE", "10")),
            "bulk_per_minute": int(os.getenv("MAX_BULK_PER_MINUTE", "5")),
        },
        # Retry settings
        "retry_settings": {
            "max_attempts": int(os.getenv("MAX_RETRY_ATTEMPTS", "5")),
            "base_delay": float(os.getenv("RETRY_BASE_DELAY", "0.5")),
            "max_delay": float(os.getenv("RETRY_MAX_DELAY", "60.0")),
        },
        # Telegram logging
        "telegram_logging": {
            "bot_token": os.getenv("LOG_BOT_TOKEN"),
            "chat_id": os.getenv("LOG_CHAT_ID"),
            "enabled": os.getenv("TELEGRAM_LOGGING_ENABLED", "true").lower() == "true",
        },
        # Session lock settings
        "session_lock": {
            "enabled": os.getenv("SESSION_LOCK_ENABLED", "true").lower() == "true",
            "timeout": int(os.getenv("SESSION_LOCK_TIMEOUT", "300")),  # 5 minutes
        },
        # Emergency settings
        "emergency": {
            "auto_shutdown_on_auth_error": os.getenv(
                "AUTO_SHUTDOWN_ON_AUTH_ERROR", "true"
            ).lower()
            == "true",
            "delete_session_on_revoke": os.getenv(
                "DELETE_SESSION_ON_REVOKE", "false"
            ).lower()
            == "true",
            "notify_admin_on_error": os.getenv("NOTIFY_ADMIN_ON_ERROR", "true").lower()
            == "true",
        },
        # IP change handling
        "ip_monitoring": {
            "enabled": os.getenv("IP_MONITORING_ENABLED", "true").lower() == "true",
            "check_interval": int(os.getenv("IP_CHECK_INTERVAL", "300")),  # 5 minutes
            "notify_on_change": os.getenv("NOTIFY_ON_IP_CHANGE", "true").lower()
            == "true",
            "session_warmup_delay": int(
                os.getenv("SESSION_WARMUP_DELAY", "30")
            ),  # 30 seconds
        },
    }

    return config


def validate_config(config: Dict[str, Any]) -> bool:
    """Validate configuration and return True if valid"""

    errors = []

    # Check required Telegram logging settings if enabled
    if config["telegram_logging"]["enabled"]:
        if not config["telegram_logging"]["bot_token"]:
            errors.append("LOG_BOT_TOKEN is required when Telegram logging is enabled")

        if not config["telegram_logging"]["chat_id"]:
            errors.append("LOG_CHAT_ID is required when Telegram logging is enabled")

    # Validate rate limits
    rate_limits = config["rate_limits"]
    if rate_limits["messages_per_minute"] < 1:
        errors.append("MAX_MESSAGES_PER_MINUTE must be at least 1")

    if rate_limits["joins_per_hour"] < 1:
        errors.append("MAX_JOINS_PER_HOUR must be at least 1")

    # Validate retry settings
    retry_settings = config["retry_settings"]
    if retry_settings["max_attempts"] < 1:
        errors.append("MAX_RETRY_ATTEMPTS must be at least 1")

    if retry_settings["base_delay"] < 0:
        errors.append("RETRY_BASE_DELAY must be non-negative")

    if errors:
        print("Configuration validation errors:")
        for error in errors:
            print(f"  - {error}")
        return False

    return True


# Default configuration for testing
DEFAULT_TEST_CONFIG = {
    "log_dir": "test_logs",
    "summary_interval": 3600,  # 1 hour for testing
    "rate_limits": {
        "messages_per_minute": 5,  # Lower limits for testing
        "joins_per_hour": 2,
        "forwards_per_minute": 3,
        "bulk_per_minute": 1,
    },
    "retry_settings": {
        "max_attempts": 3,
        "base_delay": 0.1,
        "max_delay": 5.0,
    },
    "telegram_logging": {
        "bot_token": None,
        "chat_id": None,
        "enabled": False,
    },
    "session_lock": {
        "enabled": True,
        "timeout": 60,
    },
    "emergency": {
        "auto_shutdown_on_auth_error": True,
        "delete_session_on_revoke": False,
        "notify_admin_on_error": False,
    },
    "ip_monitoring": {
        "enabled": True,
        "check_interval": 60,
        "notify_on_change": False,
        "session_warmup_delay": 10,
    },
}
