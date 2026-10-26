"""Menu callback handlers - modular structure"""

from .account_callbacks import AccountCallbacks
from .help_callbacks import HelpCallbacks
from .messaging_callbacks import MessagingCallbacks
from .otp_callbacks import OTPCallbacks

__all__ = [
    "AccountCallbacks",
    "OTPCallbacks",
    "MessagingCallbacks",
    "HelpCallbacks",
]
