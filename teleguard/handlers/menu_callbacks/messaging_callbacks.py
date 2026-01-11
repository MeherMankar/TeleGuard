"""Messaging callbacks"""

from .base_callback import BaseCallback


class MessagingCallbacks(BaseCallback):
    async def handle_messaging(self, event, user_id, data):
        """Delegate to menu_system"""
        await self.menu_system._handle_messaging_callback(event, user_id, data)

    async def handle_autoreply(self, event, user_id, data):
        """Delegate to menu_system"""
        await self.menu_system._handle_autoreply_callback(event, user_id, data)

    async def handle_bulk(self, event, user_id, data):
        """Delegate to menu_system"""
        await self.menu_system._handle_bulk_callback(event, user_id, data)
