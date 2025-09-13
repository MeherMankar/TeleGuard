"""Configuration settings for TeleGuard

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from config directory
env_path = Path(__file__).parent.parent.parent / "config" / ".env"
load_dotenv(env_path)

# Telegram API Configuration
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Validate required environment variables
if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError(
        "Missing required environment variables: API_ID, API_HASH, BOT_TOKEN"
    )

# Database Configuration
# Database Configuration
db_path = Path(__file__).parent.parent.parent / "config" / "bot_data.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

# Security Configuration
KEY_FILE = Path(__file__).parent.parent.parent / "config" / "secret.key"


def get_or_create_encryption_key() -> bytes:
    """Get existing encryption key or create a new one"""
    try:
        if KEY_FILE.exists():
            with open(KEY_FILE, "rb") as f:
                key = f.read()
                # Validate key
                Fernet(key)
                return key
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(KEY_FILE, "wb") as f:
                f.write(key)
            logger.info("Generated new encryption key")
            return key
    except Exception as e:
        logger.error(f"Failed to handle encryption key: {e}")
        raise


# Initialize encryption
ENCRYPTION_KEY = get_or_create_encryption_key()
FERNET = Fernet(ENCRYPTION_KEY)

# Session manager will be initialized later to avoid circular imports

# Bot Settings
MAX_ACCOUNTS = int(os.getenv("MAX_ACCOUNTS", "10"))
KEEP_ALIVE_INTERVAL = int(os.getenv("KEEP_ALIVE_INTERVAL", "3600"))
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "/")

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Rate Limiting
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "30"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

# OTP Destroyer Settings
OTP_DESTROY_TIMEOUT = int(os.getenv("OTP_DESTROY_TIMEOUT", "30"))
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))

# Performance Settings
DATABASE_POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", "10"))
MAX_CLIENT_IDLE_TIME = int(os.getenv("MAX_CLIENT_IDLE_TIME", "3600"))
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "300"))

# Security Settings
SESSION_BACKUP_ENABLED = os.getenv("SESSION_BACKUP_ENABLED", "false").lower() == "true"
AUDIT_LOG_RETENTION_DAYS = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "30"))

# Admin Configuration
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = set()
if ADMIN_IDS_STR:
    try:
        ADMIN_IDS = {
            int(uid.strip()) for uid in ADMIN_IDS_STR.split(",") if uid.strip()
        }
        logger.info(f"Loaded {len(ADMIN_IDS)} admin IDs")
    except ValueError as e:
        logger.error(f"Invalid ADMIN_IDS format: {e}")
        ADMIN_IDS = set()


