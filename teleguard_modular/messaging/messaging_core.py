"""Split from smart_messaging.py - messaging_core"""
"""Unified Messaging System - Handles all messaging, DM forwarding, and topic management"""
import logging
import re
from typing import Dict, Optional
from telethon import events, functions, TelegramClient
from ..core.mongo_database import mongodb
logger = logging.getLogger(__name__)
class UnifiedMessagingSystem:
    """Unified system for messaging, DM forwarding, and topic management"""
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        self.handled_clients = set()
        self.registered_client_objects = set()  # Track actual client objects
        self.auto_reply_handlers = {}
        self.processed_messages = set()  # Track processed messages to prevent duplicates
    def setup_handlers(self):
        """Set up all messaging handlers"""
        client_count = 0
        for user_id, clients in self.user_clients.items():
            for account_name, client in clients.items():
                if client and client.is_connected():
                    self._setup_client_handlers(user_id, account_name, client)
                    client_count += 1
        self._setup_admin_reply_handler()
    def _setup_client_handlers(self, user_id: int, account_name: str, client):
        """Set up handlers for managed account"""
        client_key = f"{user_id}:{account_name}"
        if client_key in self.handled_clients:
            return
        client_obj_id = id(client)
        if client_obj_id in self.registered_client_objects:
            self.handled_clients.add(client_key)
            return
        if hasattr(client, '_event_builders') and client._event_builders:
            for builder in client._event_builders:
                if hasattr(builder, 'func') and 'private' in str(builder.func):
                    self.handled_clients.add(client_key)
                    self.registered_client_objects.add(client_obj_id)
                    return
        # Mark as handled before registering to prevent race conditions
        self.handled_clients.add(client_key)
        self.registered_client_objects.add(id(client))
        if hasattr(self.bot_manager, 'registered_handlers'):
            self.bot_manager.registered_handlers["messaging"].add(client_key)
        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def private_message_handler(event):
            try:
                if event.out:
                    return
                message_id = f"{event.chat_id}_{event.id}_{client_key}"
                if message_id in self.processed_messages:
                    logger.debug(f"Message {message_id} already processed, skipping")
                    return
                self.processed_messages.add(message_id)
                # Keep only last 1000 processed messages to prevent memory leak
                if len(self.processed_messages) > 1000:
                    self.processed_messages = set(list(self.processed_messages)[-500:])
                sender = await event.get_sender()
                me = await client.get_me()
                is_bot = getattr(sender, 'bot', False)
                is_telegram_official = sender.id in [777000, 42777]  # Telegram and Telegram Notifications
                if is_telegram_official:
                    return  # Let OTP manager handle Telegram messages
                elif is_bot:
                    # Send bot messages directly via bot instead of topics
                    await self._send_bot_message_directly(user_id, sender, me, event)
                else:
                    admin_group_id = await self._get_user_admin_group(user_id)
                    if admin_group_id:
                        # Auto-create topic and forward message
                        await self._handle_incoming_dm(
                            admin_group_id, event, sender, me, user_id
                        )
                if not is_bot and not is_telegram_official:
                    await self._handle_auto_reply(client, event, user_id, account_name)
            except Exception as e:
                logger.error(f"Private message handler error for {account_name}: {e}", exc_info=True)
    def _setup_admin_reply_handler(self):
        """Set up handler for admin replies in topics"""
        @self.bot.on(events.NewMessage())
        async def admin_group_handler(event):
            try:
                user = await mongodb.db.users.find_one({"dm_reply_group_id": event.chat_id})
                if not user:
                    return
                # Skip if not from the admin user
                if event.sender_id != user["telegram_id"]:
                    return
                if not event.message.reply_to:
                    return
                replied_msg_id = event.message.reply_to.reply_to_msg_id
                # Try to find mapping by topic ID (the message being replied to could be the topic starter)
                mapping = await mongodb.db.topic_mappings.find_one({
                    "admin_group_id": event.chat_id,
                    "topic_id": replied_msg_id
                })
                if mapping:
                    await self._send_topic_reply({
                        'user_id': mapping['sender_id'],
                        'account_id': mapping['account_id']
                    }, event.text)
            except Exception as e:
                logger.error(f"Admin group handler error: {e}", exc_info=True)
    async def _handle_incoming_dm(self, admin_group_id: int, event, sender, me, user_id: int):
        """Handle incoming DM with automatic topic creation"""
        try:
            # Find or create topic for this conversation
            topic_id = await self._find_or_create_topic(
                admin_group_id, sender.id, me.id, sender, user_id
            )
            if topic_id:
                # Forward message to topic
                await self._forward_to_topic(
                    admin_group_id, topic_id, event, sender, me
                )
        except Exception as e:
            logger.error(f"Failed to handle incoming DM: {e}", exc_info=True)
    async def _handle_auto_reply(self, client, event, user_id: int, account_name: str):
        """Handle auto-reply if enabled for account"""
        try:
            account = await mongodb.db.accounts.find_one({
                "user_id": user_id,
                "name": account_name
            })
            if not account or not account.get("auto_reply_enabled", False):
                return
            # Don't reply to bots, self, or Telegram official
            sender = await event.get_sender()
            if getattr(sender, "bot", False):
                logger.debug(f"Skipping auto-reply to bot: {sender.id}")
                return
            if sender.id in [777000, 42777]:  # Telegram official
                logger.debug(f"Skipping auto-reply to Telegram official: {sender.id}")
                return
            settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
            message_text = event.message.text.lower() if event.message.text else ""
            response = None
            if settings.get('keyword_replies_enabled', False):
                user_keywords = settings.get('keywords', {})
                for keyword, reply_msg in user_keywords.items():
                    if keyword.lower() in message_text:
                        response = reply_msg
                        break
            # If no keyword match, check time-based replies
            if not response and settings.get('time_based_replies_enabled', False):
                from datetime import datetime, time
                now = datetime.now()
                business_hours = {'start': time(9, 0), 'end': time(17, 0), 'days': [0, 1, 2, 3, 4]}
                is_business_hours = (
                    now.weekday() in business_hours['days'] and
                    business_hours['start'] <= now.time() <= business_hours['end']
                )
                if is_business_hours:
                    response = settings.get('available_message', "I'm currently available and will respond soon.")
                else:
                    response = settings.get('unavailable_message', "I'm not available right now. I'll get back to you later.")
            # Send auto-reply if we have a response
            if response:
                await event.reply(response)
        except Exception as e:
            logger.error(f"Auto-reply error for {account_name}: {e}")
    async def _find_or_create_topic(self, admin_group_id: int, sender_id: int, 
                                   account_id: int, sender, user_id: int) -> Optional[int]:
        """Find existing topic or create new one"""
        try:
            existing_topic = await self._find_existing_topic(admin_group_id, sender_id, account_id)
            if existing_topic:
                return existing_topic
            try:
                chat_info = await self.bot.get_entity(admin_group_id)
                if not getattr(chat_info, 'forum', False):
                    return None
            except Exception as e:
                return None
            # Get account info for topic title
            account_client = await self._get_client_by_id(account_id)
            account_info = None
            if account_client:
                try:
                    account_info = await account_client.get_me()
                except Exception:
                    pass
            topic_title = self._get_topic_title(sender, account_info)
            try:
                result = await self.bot(functions.channels.CreateForumTopicRequest(
                    channel=admin_group_id,
                    title=topic_title,
                    random_id=hash(f"{sender_id}_{account_id}_{user_id}")
                ))
            except Exception as create_error:
                return None
            # Extract topic ID from result
            topic_id = None
            if hasattr(result, 'updates') and result.updates:
                for update in result.updates:
                    if hasattr(update, 'message') and update.message:
                        topic_id = update.message.id
                        break
                    elif hasattr(update, 'id'):
                        topic_id = update.id
                        break
            if not topic_id:
                return None
            # Store mapping in database for persistence
            await self._store_topic_mapping(admin_group_id, topic_id, sender_id, account_id)
            await self._create_system_message(admin_group_id, topic_id, sender_id, account_id)
            return topic_id
        except Exception as e:
            logger.error(f"Failed to create topic: {e}")
            return None
    async def _find_existing_topic(self, admin_group_id: int, sender_id: int, account_id: int) -> Optional[int]:
        """Find existing topic for sender and account combination"""
        try:
            if not all(isinstance(x, int) for x in [admin_group_id, sender_id, account_id]):
                logger.error("Invalid input types for topic mapping")
                return None
            # First check database for existing mapping
            mapping = await mongodb.db.topic_mappings.find_one({
                "admin_group_id": admin_group_id,
                "sender_id": sender_id,
                "account_id": account_id
            })
            if mapping:
                topic_id = mapping["topic_id"]
                return topic_id
            return None
        except Exception as e:
            logger.error(f"Failed to find existing topic: {e}")
            return None
    def _get_topic_title(self, sender, account_info=None) -> str:
        """Generate topic title from sender and account info"""
        # Get sender name
        if hasattr(sender, 'first_name') and sender.first_name:
            sender_name = sender.first_name
            if hasattr(sender, 'last_name') and sender.last_name:
                sender_name += f" {sender.last_name}"
        elif hasattr(sender, 'username') and sender.username:
            sender_name = f"@{sender.username}"
        else:
            sender_name = f"User {sender.id}"
        
        # Get account name
        if account_info:
            if hasattr(account_info, 'username') and account_info.username:
                account_name = f"@{account_info.username}"
            elif hasattr(account_info, 'first_name') and account_info.first_name:
                account_name = account_info.first_name
            else:
                account_name = f"Account {account_info.id}"
        else:
            account_name = "Account"
        
        title = f"{sender_name} → {account_name}"
        return title[:100]  # Telegram limit
    async def _store_topic_mapping(self, admin_group_id: int, topic_id: int, sender_id: int, account_id: int):
        """Store topic mapping in database"""
        try:
            import time
            mapping = {
                "admin_group_id": admin_group_id,
                "topic_id": topic_id,
                "sender_id": sender_id,
                "account_id": account_id,
                "created_at": int(time.time())
            }
            # Use upsert to prevent duplicates
            await mongodb.db.topic_mappings.update_one(
                {
                    "admin_group_id": admin_group_id,
                    "sender_id": sender_id,
                    "account_id": account_id
                },
                {"$set": mapping},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to store topic mapping: {e}")
    async def _create_system_message(self, admin_group_id: int, topic_id: int, 
                                   sender_id: int, account_id: int):
        """Create system message with mapping info"""
        try:
            system_text = (
                f"🔗 **Topic Mapping**\n"
                f"User ID: `{sender_id}`\n"
                f"Account ID: `{account_id}`\n"
                f"Topic ID: `{topic_id}`"
            )
            await self.bot.send_message(
                admin_group_id,
                system_text,
                reply_to=topic_id,
                parse_mode='md'
            )
        except Exception as e:
            logger.error(f"Failed to create system message: {e}")
    async def _forward_to_topic(self, admin_group_id: int, topic_id: int, 
                              event, sender, managed_account):
        """Forward DM to topic"""
