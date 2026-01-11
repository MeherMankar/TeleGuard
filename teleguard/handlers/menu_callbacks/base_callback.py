"""Base callback handler"""

import logging

logger = logging.getLogger(__name__)


class BaseCallback:
    def __init__(self, bot, account_manager, menu_system):
        self.bot = bot
        self.account_manager = account_manager
        self.menu_system = menu_system
