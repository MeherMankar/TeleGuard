"""Cleanup callbacks"""
from .base_callback import BaseCallback

class CleanupCallbacks(BaseCallback):
    async def handle_cleanup(self, event, user_id, data):
        """Delegate to menu_system"""
        await self.menu_system._handle_cleanup_callback(event, user_id, data)
