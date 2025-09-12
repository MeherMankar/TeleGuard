"""Auto-reply handler for user accounts"""

import logging
from telethon import events
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class AutoReplyHandler:
    """Handles automatic replies for user accounts"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.user_clients = bot_manager.user_clients
        self.handled_clients = set()  # Track clients with handlers
        
    def setup_auto_reply_handlers(self):
        """Set up auto-reply handlers for all user clients"""
        for user_id, clients in self.user_clients.items():
            for account_name, client in clients.items():
                if client and client.is_connected():
                    self._setup_client_handler(user_id, account_name, client)
    
    def _setup_client_handler(self, user_id: int, account_name: str, client):
        """Set up auto-reply handler for a specific client"""
        
        # Check if handler already exists for this client
        client_key = f"{user_id}:{account_name}"
        if client_key in self.handled_clients:
            return
            
        self.handled_clients.add(client_key)
        
        @client.on(events.NewMessage(incoming=True, func=lambda e: not e.is_group and not e.is_channel))
        async def auto_reply_handler(event):
            try:
                # Get account settings
                account = await mongodb.db.accounts.find_one({
                    "user_id": user_id,
                    "name": account_name
                })
                
                if not account or not account.get("auto_reply_enabled", False):
                    return
                
                auto_reply_message = account.get("auto_reply_message", "")
                if not auto_reply_message:
                    return
                
                # Send auto-reply
                await event.reply(auto_reply_message)
                logger.info(f"Auto-reply sent from {account_name} to {event.sender_id}")
                
            except Exception as e:
                logger.error(f"Auto-reply error for {account_name}: {e}")
    
    async def setup_new_client_handler(self, user_id: int, account_name: str, client):
        """Set up auto-reply handler for a newly added client"""
        if client and client.is_connected():
            self._setup_client_handler(user_id, account_name, client)