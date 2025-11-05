"""Base callback handler"""
import logging
from ...core.mongo_database import mongodb
from ...utils.network_helpers import format_display_name, format_phone_number

logger = logging.getLogger(__name__)

class BaseCallback:
    def __init__(self, bot, account_manager, menu_system):
        self.bot = bot
        self.account_manager = account_manager
        self.menu_system = menu_system
