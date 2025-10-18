"""TeleGuard - Telegram Account Manager with OTP Destroyer Protection"""
__version__ = "2.0.0"
__author__ = "Meher Mankar & Gutkesh"
__email__ = "support@teleguard.dev"
from .core.client_manager import get_client_manager
# Core imports
from .core.bot_manager import BotManager as AccountManager
from .core.config import *
# components
from .core.exceptions import *
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
]
