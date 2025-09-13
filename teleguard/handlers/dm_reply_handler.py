"""DM Reply Handler - Forward DMs to admin group and handle replies"""

import logging
from telethon import events, Button
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class DMReplyHandler:
    """Handles DM forwarding to admin group and reply management"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        self.handled_clients = set()
        self.reply_states = {}  # {admin_id: (target_user_id, via_account_id)}
        
        # Admin configuration
        from ..core.config import ADMIN_IDS
        self.admin_ids = ADMIN_IDS
        
    def setup_dm_handlers(self):
        """Set up DM handlers for all user clients"""
        for user_id, clients in self.user_clients.items():
            for account_name, client in clients.items():
                if client and client.is_connected():
                    self._setup_client_dm_handler(user_id, account_name, client)
        
        # Set up bot handlers for admin replies
        self._setup_bot_handlers()
    
    async def set_admin_group(self, user_id: int, group_id: int = None) -> tuple[bool, str]:
        """Set admin group for user's DM replies"""
        try:
            if group_id is None:
                await mongodb.db.users.update_one(
                    {"telegram_id": user_id},
                    {"$unset": {"dm_reply_group_id": ""}}
                )
                return True, "DM reply disabled"
            else:
                await mongodb.db.users.update_one(
                    {"telegram_id": user_id},
                    {"$set": {"dm_reply_group_id": group_id}}
                )
                return True, f"DM reply group set to {group_id}"
        except Exception as e:
            logger.error(f"Failed to set admin group: {e}")
            return False, f"Error: {str(e)}"
    
    async def get_admin_group(self, user_id: int) -> int:
        """Get admin group ID for user"""
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            return user.get("dm_reply_group_id") if user else None
        except Exception as e:
            logger.error(f"Failed to get admin group: {e}")
            return None
    
    def _setup_client_dm_handler(self, user_id: int, account_name: str, client):
        """Set up DM handler for a specific client"""
        
        client_key = f"{user_id}:{account_name}"
        if client_key in self.handled_clients:
            return
            
        self.handled_clients.add(client_key)
        
        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def dm_handler(event):
            try:
                # Skip if message is from self
                if event.out:
                    return
                
                sender = await event.get_sender()
                me = await client.get_me()
                
                # Create formatted message for admin group
                sender_mention = f"[{sender.first_name or 'Unknown'}](tg://user?id={sender.id})"
                account_identifier = me.username or f"ID: {me.id}"
                
                forward_message = (
                    f"🔔 **New Message**\n\n"
                    f"**To Account:** `@{account_identifier}`\n"
                    f"**From:** {sender_mention}\n\n"
                    f"**Message:**\n```{event.text or '[Media/Sticker]'}```"
                )
                
                # Create reply button
                reply_button = [
                    Button.inline("✍️ Reply", data=f"reply_to:{sender.id}:{me.id}")
                ]
                
                # Get user's admin group and send if configured
                admin_group_id = await self.get_admin_group(user_id)
                if admin_group_id:
                    await self.bot.send_message(
                        admin_group_id,
                        forward_message,
                        buttons=reply_button,
                        parse_mode='md'
                    )
                    logger.info(f"DM forwarded from {account_name} to user's admin group")
                
            except Exception as e:
                logger.error(f"DM handler error for {account_name}: {e}")
    
    def _setup_bot_handlers(self):
        """Set up bot handlers for admin replies"""
        
        @self.bot.on(events.CallbackQuery(pattern=b"reply_to:(\\d+):(\\d+)"))
        async def handle_reply_button(event):
            # Check if this is a valid admin group for any user
            user = await mongodb.db.users.find_one({"dm_reply_group_id": event.chat_id})
            if not user:
                return
            
            # Check if sender is the group owner or admin
            if event.sender_id != user["telegram_id"]:
                await event.answer("❌ Unauthorized", alert=True)
                return
            
            target_user_id = int(event.pattern_match.group(1))
            via_account_id = int(event.pattern_match.group(2))
            
            # Store reply state
            self.reply_states[event.sender_id] = (target_user_id, via_account_id)
            
            await event.answer("✅ Acknowledged. Send your reply now.", alert=True)
        
        @self.bot.on(events.NewMessage())
        async def handle_admin_reply(event):
            # Check if this is a valid admin group for any user
            user = await mongodb.db.users.find_one({"dm_reply_group_id": event.chat_id})
            if not user:
                return
                
            admin_id = event.sender_id
            
            # Check if admin is in reply state
            if admin_id not in self.reply_states:
                return
            
            # Check if sender is the group owner
            if admin_id != user["telegram_id"]:
                return
            
            target_user_id, via_account_id = self.reply_states.pop(admin_id)
            
            # Find the correct managed client
            managed_client = await self._get_client_by_id(via_account_id)
            
            if managed_client:
                try:
                    await managed_client.send_message(target_user_id, event.text)
                    await event.reply("✔️ Message sent successfully!")
                    logger.info(f"Reply sent from account {via_account_id} to user {target_user_id}")
                except Exception as e:
                    await event.reply(f"❌ Failed to send message: {e}")
                    logger.error(f"Failed to send reply: {e}")
            else:
                await event.reply("❌ Error: Could not find the managed account client.")
    
    async def _get_client_by_id(self, account_id: int):
        """Get client by account user ID"""
        for user_id, clients in self.user_clients.items():
            for account_name, client in clients.items():
                if client and client.is_connected():
                    try:
                        me = await client.get_me()
                        if hasattr(me, 'id') and me.id == account_id:
                            return client
                    except Exception as e:
                        logger.debug(f"Error checking client {account_name}: {e}")
                        continue
        return None
    
    async def setup_new_client_handler(self, user_id: int, account_name: str, client):
        """Set up DM handler for a newly added client"""
        if client and client.is_connected():
            self._setup_client_dm_handler(user_id, account_name, client)