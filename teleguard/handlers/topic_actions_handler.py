"""Advanced Topic Actions Handler - Close to block, Clear to delete history, General topic broadcast"""
import logging
from telethon import events
from telethon.tl.types import ChannelAdminLogEventActionEditTopic, ChannelAdminLogEventActionDeleteTopic
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class TopicActionsHandler:
    """Handles advanced topic actions"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        
    def register_handlers(self):
        """Register topic action handlers"""
        
        # Monitor channel events for topic changes
        @self.bot.on(events.Raw())
        async def handle_channel_events(event):
            try:
                from telethon.tl.types import UpdateChannelMessageForwards, UpdateEditChannelMessage
                
                # Check for topic edit (close/open)
                if hasattr(event, '__class__') and 'EditTopic' in event.__class__.__name__:
                    await self._check_topic_closed(event)
            except Exception as e:
                logger.debug(f"Channel event handler: {e}")
        
        # Monitor message deletions
        @self.bot.on(events.MessageDeleted())
        async def handle_message_deletion(event):
            try:
                if event.deleted_ids and len(event.deleted_ids) > 5:  # Bulk delete = clear
                    await self._handle_messages_cleared(event)
            except Exception as e:
                logger.error(f"Message deletion handler error: {e}")
        
        # Monitor general topic (ID=1) for broadcasts
        @self.bot.on(events.NewMessage())
        async def handle_general_topic(event):
            try:
                if not event.is_group:
                    return
                
                reply_to = getattr(event.message, 'reply_to', None)
                if reply_to:
                    topic_id = getattr(reply_to, 'reply_to_top_id', None)
                    if topic_id == 1:  # General topic
                        await self._handle_general_topic_broadcast(event)
            except Exception as e:
                logger.error(f"General topic handler error: {e}")
        
        # Command to manually block user from topic
        @self.bot.on(events.NewMessage(pattern=r'^/block$'))
        async def block_from_topic(event):
            try:
                if not event.is_group:
                    return
                
                reply_to = getattr(event.message, 'reply_to', None)
                if reply_to:
                    topic_id = getattr(reply_to, 'reply_to_top_id', None)
                    if topic_id:
                        await self._block_user_from_topic(event.chat_id, topic_id, event.sender_id)
                        await event.reply("✅ User blocked")
            except Exception as e:
                logger.error(f"Block command error: {e}")
        
        # Command to clear chat history from topic
        @self.bot.on(events.NewMessage(pattern=r'^/clear_history$'))
        async def clear_from_topic(event):
            try:
                if not event.is_group:
                    return
                
                reply_to = getattr(event.message, 'reply_to', None)
                if reply_to:
                    topic_id = getattr(reply_to, 'reply_to_top_id', None)
                    if topic_id:
                        await self._clear_history_from_topic(event.chat_id, topic_id, event.sender_id)
                        await event.reply("✅ Chat history cleared")
            except Exception as e:
                logger.error(f"Clear history command error: {e}")
    
    async def _check_topic_closed(self, event):
        """Check if topic was closed and block user"""
        try:
            if hasattr(event, 'closed') and event.closed:
                chat_id = event.channel_id if hasattr(event, 'channel_id') else None
                topic_id = event.id if hasattr(event, 'id') else None
                
                if chat_id and topic_id:
                    await self._block_user_from_topic(-chat_id, topic_id, None)
        except Exception as e:
            logger.error(f"Check topic closed error: {e}")
    
    async def _block_user_from_topic(self, chat_id: int, topic_id: int, sender_id: int):
        """Block user associated with topic"""
        try:
            # Verify sender is group owner
            if sender_id:
                user = await mongodb.db.users.find_one({"dm_reply_group_id": chat_id})
                if not user or sender_id != user["telegram_id"]:
                    return
            
            # Find topic mapping
            topic_mapping = await mongodb.db.dm_topics.find_one({
                "group_id": chat_id,
                "topic_id": topic_id
            })
            
            if not topic_mapping:
                return
            
            target_user_id = topic_mapping['sender_id']
            account_id = topic_mapping['account_id']
            
            # Get managed client
            managed_client = await self._get_client_by_account_id(account_id)
            if not managed_client:
                return
            
            # Block the user
            from telethon.tl.functions.contacts import BlockRequest
            await managed_client(BlockRequest(id=target_user_id))
            
            logger.info(f"Blocked user {target_user_id} on account {account_id}")
            
        except Exception as e:
            logger.error(f"Failed to block user: {e}")
    
    async def _handle_messages_cleared(self, event):
        """When messages are bulk deleted, clear chat history"""
        try:
            chat_id = event.chat_id
            
            user = await mongodb.db.users.find_one({"dm_reply_group_id": chat_id})
            if not user:
                return
            
            # Note: We can't determine which topic, so we notify user
            logger.info(f"Bulk message deletion detected in group {chat_id}")
            
        except Exception as e:
            logger.error(f"Failed to handle messages cleared: {e}")
    
    async def _clear_history_from_topic(self, chat_id: int, topic_id: int, sender_id: int):
        """Clear chat history for user in topic"""
        try:
            # Verify sender is group owner
            user = await mongodb.db.users.find_one({"dm_reply_group_id": chat_id})
            if not user or sender_id != user["telegram_id"]:
                return
            
            # Find topic mapping
            topic_mapping = await mongodb.db.dm_topics.find_one({
                "group_id": chat_id,
                "topic_id": topic_id
            })
            
            if not topic_mapping:
                return
            
            target_user_id = topic_mapping['sender_id']
            account_id = topic_mapping['account_id']
            
            # Get managed client
            managed_client = await self._get_client_by_account_id(account_id)
            if not managed_client:
                return
            
            # Delete chat history
            from telethon.tl.functions.messages import DeleteHistoryRequest
            await managed_client(DeleteHistoryRequest(
                peer=target_user_id,
                max_id=0,
                just_clear=True,
                revoke=True
            ))
            
            logger.info(f"Cleared chat history with user {target_user_id} on account {account_id}")
            
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")
    
    async def _handle_general_topic_broadcast(self, event):
        """Broadcast message from general topic to all users from all accounts"""
        try:
            # Check if sender is the group owner
            user = await mongodb.db.users.find_one({"dm_reply_group_id": event.chat_id})
            if not user or event.sender_id != user["telegram_id"]:
                return
            
            message_text = event.text
            if not message_text:
                return
            
            # Get all unique users from all topics
            topics = await mongodb.db.dm_topics.find({"group_id": event.chat_id}).to_list(None)
            
            # Group by account to send from each account
            accounts_users = {}
            for topic in topics:
                account_id = topic['account_id']
                sender_id = topic['sender_id']
                
                if account_id not in accounts_users:
                    accounts_users[account_id] = set()
                accounts_users[account_id].add(sender_id)
            
            # Send from each account to its users
            sent_count = 0
            for account_id, user_ids in accounts_users.items():
                managed_client = await self._get_client_by_account_id(account_id)
                if not managed_client:
                    continue
                
                for user_id in user_ids:
                    try:
                        await managed_client.send_message(user_id, message_text)
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send to {user_id} from {account_id}: {e}")
            
            # Confirm broadcast
            await event.reply(f"📢 Broadcast sent to {sent_count} users from {len(accounts_users)} accounts")
            
            logger.info(f"Broadcast sent to {sent_count} users from general topic")
            
        except Exception as e:
            logger.error(f"Failed to handle general topic broadcast: {e}")
    
    async def _get_client_by_account_id(self, account_id: int):
        """Get managed client by account Telegram ID"""
        for user_id, clients in self.user_clients.items():
            for account_name, client in clients.items():
                if client and client.is_connected():
                    try:
                        me = await client.get_me()
                        if me.id == account_id:
                            return client
                    except Exception:
                        continue
        return None
