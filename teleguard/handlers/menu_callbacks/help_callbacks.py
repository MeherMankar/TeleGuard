"""Help and support callbacks"""
from .base_callback import BaseCallback

class HelpCallbacks(BaseCallback):
    async def handle_help(self, event, user_id, data):
        """Delegate to menu_system"""
        await self.menu_system._handle_help_callback(event, user_id, data)
    
    async def handle_support(self, event, user_id, data):
        """Delegate to menu_system"""
        await self.menu_system._handle_support_callback(event, user_id, data)
    
    async def handle_developer(self, event, user_id, data):
        """Delegate to menu_system"""
        await self.menu_system._handle_developer_callback(event, user_id, data)
