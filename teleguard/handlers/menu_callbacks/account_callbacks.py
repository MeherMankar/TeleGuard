"""Account management callbacks"""

from .base_callback import BaseCallback


class AccountCallbacks(BaseCallback):
    async def handle_add_account(self, event, user_id):
        """Delegate to menu_system"""
        await self.menu_system._handle_add_account(event, user_id)

    async def handle_remove_account(self, event, user_id):
        """Delegate to menu_system"""
        await self.menu_system._handle_remove_account(event, user_id)

    async def handle_account_manage(self, event, user_id, account_id):
        """Delegate to menu_system"""
        await self.menu_system.send_account_management(
            user_id, account_id, event.message_id
        )
