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
        logger.info("SETTING UP UNIFIED MESSAGING HANDLERS - Total user_clients: {}".format(len(self.user_clients)))
        
        # Don't clear existing handlers - just check for duplicates
        logger.info(f"Current handled clients: {len(self.handled_clients)}")
        logger.info(f"Current registered client objects: {len(self.registered_client_objects)}")
        
        # Set up handlers for existing clients
        client_count = 0
        for user_id, clients in self.user_clients.items():
            logger.info(f"Setting up handlers for user {user_id} with {len(clients)} clients")
            for account_name, client in clients.items():
                if client and client.is_connected():
                    logger.info(f"Setting up handler for {account_name}")
                    self._setup_client_handlers(user_id, account_name, client)
                    client_count += 1
                else:
                    logger.warning(f"Client {account_name} is not connected")
        
        logger.info(f"COMPLETED HANDLER SETUP - {client_count} clients processed, {len(self.handled_clients)} handlers active")
        
        # Set up admin reply handler
        self._setup_admin_reply_handler()
        logger.info("Admin reply handler set up")
    
    def _setup_client_handlers(self, user_id: int, account_name: str, client):
        """Set up handlers for managed account"""
        client_key = f"{user_id}:{account_name}"
        
        # Check if handlers already exist for this client
        if client_key in self.handled_clients:
            logger.info(f"Handlers already exist for {client_key}, skipping")
            return
            
        # Check if this exact client object already has handlers
        client_obj_id = id(client)
        if client_obj_id in self.registered_client_objects:
            logger.info(f"Client object {client_obj_id} already has handlers, skipping {client_key}")
            self.handled_clients.add(client_key)
            return
            
        # Check if client already has event handlers registered
        if hasattr(client, '_event_builders') and client._event_builders:
            logger.info(f"Client {client_key} already has {len(client._event_builders)} event handlers, checking for duplicates")
            # Check if any handler is for private messages
            for builder in client._event_builders:
                if hasattr(builder, 'func') and 'private' in str(builder.func):
                    logger.warning(f"Found existing private message handler for {client_key}, skipping to prevent duplicates")
                    self.handled_clients.add(client_key)
                    self.registered_client_objects.add(client_obj_id)
                    return
            
        # Mark as handled before registering to prevent race conditions
        self.handled_clients.add(client_key)
        self.registered_client_objects.add(id(client))
        
        # Update global registry
        if hasattr(self.bot_manager, 'registered_handlers'):
            self.bot_manager.registered_handlers["messaging"].add(client_key)
            
        logger.info(f"Registering NEW unified messaging handler for {client_key} (object ID: {id(client)})")
        
        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def private_message_handler(event):
            try:
                if event.out:
                    return
                
                # Create unique message ID for deduplication
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
                
                logger.info(f"📨 NEW DM RECEIVED [{client_key}]: {sender.id} -> {me.id} ({account_name}) - Text: {event.text[:50] if event.text else '[No text]'}")
                
                # Check if sender is bot or Telegram official
                is_bot = getattr(sender, 'bot', False)
                is_telegram_official = sender.id in [777000, 42777]  # Telegram and Telegram Notifications
                
                if is_telegram_official:
                    logger.info(f"Telegram official message detected ({sender.id}), skipping unified messaging (OTP manager will handle)")
                    return  # Let OTP manager handle Telegram messages
                elif is_bot:
                    logger.info(f"Bot message detected ({sender.id}), sending directly via bot")
                    # Send bot messages directly via bot instead of topics
                    await self._send_bot_message_directly(user_id, sender, me, event)
                else:
                    # Get user's admin group for regular user messages
                    admin_group_id = await self._get_user_admin_group(user_id)
                    if admin_group_id:
                        logger.info(f"Admin group found: {admin_group_id}, handling DM...")
                        # Auto-create topic and forward message
                        await self._handle_incoming_dm(
                            admin_group_id, event, sender, me, user_id
                        )
                    else:
                        logger.warning(f"No admin group configured for user {user_id}")
                
                # Handle auto-reply if enabled (only for non-bot messages)
                if not is_bot and not is_telegram_official:
                    logger.info(f"🤖 Checking auto-reply for {account_name} (user {user_id})")
                    await self._handle_auto_reply(client, event, user_id, account_name)
                    
            except Exception as e:
                logger.error(f"Private message handler error for {account_name}: {e}", exc_info=True)
    
    def _setup_admin_reply_handler(self):
        """Set up handler for admin replies in topics"""
        
        @self.bot.on(events.NewMessage())
        async def admin_group_handler(event):
            try:
                # Check if this is in an admin group
                user = await mongodb.db.users.find_one({"dm_reply_group_id": event.chat_id})
                if not user:
                    return
                
                logger.info(f"💬 ADMIN GROUP MESSAGE: chat={event.chat_id}, sender={event.sender_id}, text={event.text[:50] if event.text else '[No text]'}")
                logger.info(f"Message object: {type(event.message)}, reply_to: {event.message.reply_to}")
                
                # Skip if not from the admin user
                if event.sender_id != user["telegram_id"]:
                    logger.info(f"Message not from admin user {user['telegram_id']}")
                    return
                
                # Check if replying to a message (topic)
                if not event.message.reply_to:
                    logger.info("Message is not a reply")
                    return
                
                # Get the message being replied to
                replied_msg_id = event.message.reply_to.reply_to_msg_id
                logger.info(f"Replying to message ID: {replied_msg_id}")
                
                # Try to find mapping by topic ID (the message being replied to could be the topic starter)
                mapping = await mongodb.db.topic_mappings.find_one({
                    "admin_group_id": event.chat_id,
                    "topic_id": replied_msg_id
                })
                
                # If not found, try to find any mapping for this admin group and check recent messages
                if not mapping:
                    all_mappings = await mongodb.db.topic_mappings.find({
                        "admin_group_id": event.chat_id
                    }).to_list(length=None)
                    logger.info(f"Found {len(all_mappings)} total mappings for group {event.chat_id}")
                    for m in all_mappings:
                        logger.info(f"Mapping: topic_id={m['topic_id']}, sender={m['sender_id']}, account={m['account_id']}")
                
                if mapping:
                    logger.info(f"✅ Found mapping for reply: {mapping}")
                    await self._send_topic_reply({
                        'user_id': mapping['sender_id'],
                        'account_id': mapping['account_id']
                    }, event.text)
                else:
                    logger.error(f"❌ No mapping found for message ID {replied_msg_id} in group {event.chat_id}")
                
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
            logger.info(f"🤖 _handle_auto_reply called for {account_name}")
            
            # Check if auto-reply is enabled for this account
            account = await mongodb.db.accounts.find_one({
                "user_id": user_id,
                "name": account_name
            })
            
            logger.info(f"🤖 Account found: {account is not None}, auto_reply_enabled: {account.get('auto_reply_enabled', 'NOT_SET') if account else 'NO_ACCOUNT'}")
            
            if not account or not account.get("auto_reply_enabled", False):
                logger.info(f"🤖 Auto-reply not enabled for {account_name}")
                return
            
            # Don't reply to bots, self, or Telegram official
            sender = await event.get_sender()
            if getattr(sender, "bot", False):
                logger.debug(f"Skipping auto-reply to bot: {sender.id}")
                return
                
            if sender.id in [777000, 42777]:  # Telegram official
                logger.debug(f"Skipping auto-reply to Telegram official: {sender.id}")
                return
            
            # Get auto-reply settings
            settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
            message_text = event.message.text.lower() if event.message.text else ""
            
            logger.info(f"🤖 Settings found: {settings}")
            logger.info(f"🤖 Message text: '{message_text}'")
            
            response = None
            
            # Check for keyword matches first
            if settings.get('keyword_replies_enabled', False):
                user_keywords = settings.get('keywords', {})
                for keyword, reply_msg in user_keywords.items():
                    if keyword.lower() in message_text:
                        response = reply_msg
                        logger.info(f"Keyword '{keyword}' matched for auto-reply")
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
                logger.info(f"✅ AUTO-REPLY SENT from {account_name} to {sender.id}: {response[:50]}...")
            else:
                logger.info(f"❌ No auto-reply response generated for {account_name}")
            
        except Exception as e:
            logger.error(f"Auto-reply error for {account_name}: {e}")
    
    async def _find_or_create_topic(self, admin_group_id: int, sender_id: int, 
                                   account_id: int, sender, user_id: int) -> Optional[int]:
        """Find existing topic or create new one"""
        try:
            # Check for existing topic
            existing_topic = await self._find_existing_topic(admin_group_id, sender_id, account_id)
            if existing_topic:
                logger.info(f"Found existing topic {existing_topic} for {sender_id} -> {account_id}")
                return existing_topic
            
            # Verify admin group is a forum group
            try:
                chat_info = await self.bot.get_entity(admin_group_id)
                logger.info(f"Admin group info: {type(chat_info).__name__}, forum={getattr(chat_info, 'forum', False)}")
                
                if not getattr(chat_info, 'forum', False):
                    logger.error(f"Admin group {admin_group_id} is not a forum group - cannot create topics")
                    return None
                    
            except Exception as e:
                logger.error(f"Failed to get admin group info: {e}")
                return None
            
            # Create new topic
            topic_title = self._get_topic_title(sender)
            logger.info(f"Creating topic '{topic_title}' for {sender_id} -> {account_id}")
            
            result = await self.bot(functions.channels.CreateForumTopicRequest(
                channel=admin_group_id,
                title=topic_title,
                random_id=hash(f"{sender_id}_{account_id}_{user_id}")
            ))
            
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
                logger.error(f"Failed to extract topic ID from result: {result}")
                return None
            
            logger.info(f"Extracted topic ID: {topic_id}")
            
            # Store mapping in database for persistence
            await self._store_topic_mapping(admin_group_id, topic_id, sender_id, account_id)
            
            # Create system message with mapping
            await self._create_system_message(admin_group_id, topic_id, sender_id, account_id)
            
            logger.info(f"✅ Created topic {topic_id} for {sender_id} -> {account_id}")
            return topic_id
            
        except Exception as e:
            logger.error(f"Failed to create topic for {sender_id} -> {account_id}: {e}")
            return None
    
    async def _find_existing_topic(self, admin_group_id: int, sender_id: int, account_id: int) -> Optional[int]:
        """Find existing topic for sender and account combination"""
        try:
            # First check database for existing mapping
            mapping = await mongodb.db.topic_mappings.find_one({
                "admin_group_id": admin_group_id,
                "sender_id": sender_id,
                "account_id": account_id
            })
            
            if mapping:
                topic_id = mapping["topic_id"]
                logger.info(f"FOUND EXISTING TOPIC {topic_id} in database for {sender_id} -> {account_id}")
                return topic_id
            
            logger.info(f"NO EXISTING TOPIC found for {sender_id} -> {account_id}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to find existing topic: {e}")
            return None
    
    def _get_topic_title(self, sender) -> str:
        """Generate topic title from sender info"""
        if hasattr(sender, 'first_name') and sender.first_name:
            title = sender.first_name
            if hasattr(sender, 'last_name') and sender.last_name:
                title += f" {sender.last_name}"
        elif hasattr(sender, 'username') and sender.username:
            title = f"@{sender.username}"
        else:
            title = f"User {sender.id}"
        
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
            
            result = await mongodb.db.topic_mappings.insert_one(mapping)
            logger.info(f"✅ STORED topic mapping: {sender_id} -> {account_id} = topic {topic_id}, DB ID: {result.inserted_id}")
            
            # Verify the mapping was stored
            verify = await mongodb.db.topic_mappings.find_one({"_id": result.inserted_id})
            if verify:
                logger.info(f"✅ Mapping verified in database: {verify}")
            else:
                logger.error(f"❌ Failed to verify mapping in database")
            
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
            
            logger.info(f"✅ System message created for topic {topic_id}")
            
        except Exception as e:
            logger.error(f"Failed to create system message: {e}")
    
    async def _forward_to_topic(self, admin_group_id: int, topic_id: int, 
                              event, sender, managed_account):
        """Forward DM to topic"""
        try:
            sender_name = self._get_topic_title(sender)
            account_name = getattr(managed_account, 'username', None)
            if account_name:
                account_name = f"@{account_name}"
            else:
                account_name = getattr(managed_account, 'first_name', f"ID: {managed_account.id}")
            
            # Handle different message types
            if event.text:
                content = event.text
            elif event.media:
                content = "[Media/File]"
            else:
                content = "[Message]"
            
            forward_text = (
                f"📨 **From:** {sender_name}\n"
                f"📱 **To:** {account_name}\n\n"
                f"{content}"
            )
            
            logger.info(f"Forwarding message to topic {topic_id}: {sender_name} -> {account_name}")
            
            await self.bot.send_message(
                admin_group_id,
                forward_text,
                reply_to=topic_id,
                parse_mode='md'
            )
            
            logger.info(f"✅ Message forwarded to topic {topic_id}")
            
        except Exception as e:
            logger.error(f"Failed to forward to topic {topic_id}: {e}")
    
    async def _get_topic_mapping(self, admin_group_id: int, topic_id: int) -> Optional[dict]:
        """Get user and account mapping from database"""
        try:
            mapping = await mongodb.db.topic_mappings.find_one({
                "admin_group_id": admin_group_id,
                "topic_id": topic_id
            })
            
            if mapping:
                return {
                    'user_id': mapping['sender_id'],
                    'account_id': mapping['account_id']
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get topic mapping: {e}")
            return None
    
    async def _send_topic_reply(self, mapping: dict, message_text: str):
        """Send reply from topic to original sender"""
        try:
            target_user_id = mapping['user_id']
            managed_account_id = mapping['account_id']
            
            logger.info(f"Sending reply: {managed_account_id} -> {target_user_id}, text: {message_text[:50] if message_text else '[No text]'}")
            
            # Find the managed client
            managed_client = await self._get_client_by_id(managed_account_id)
            if managed_client:
                await managed_client.send_message(target_user_id, message_text)
                logger.info(f"✅ Reply sent via topic from {managed_account_id} to {target_user_id}")
            else:
                logger.error(f"No managed client found for account ID {managed_account_id}")
        except Exception as e:
            logger.error(f"Failed to send topic reply: {e}", exc_info=True)
    
    async def _get_client_by_id(self, account_id: int):
        """Get managed client by account ID"""
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
    

    
    async def _send_bot_message_directly(self, user_id: int, sender, managed_account, event):
        """Send bot messages directly via bot instead of topics"""
        try:
            sender_name = self._get_topic_title(sender)
            account_name = getattr(managed_account, 'username', None)
            if account_name:
                account_name = f"@{account_name}"
            else:
                account_name = getattr(managed_account, 'first_name', f"ID: {managed_account.id}")
            
            # Handle different message types
            if event.text:
                content = event.text
            elif event.media:
                content = "[Media/File]"
            else:
                content = "[Message]"
            
            direct_message = (
                f"🤖 **Bot Message**\n"
                f"📨 **From:** {sender_name} (Bot)\n"
                f"📱 **To:** {account_name}\n\n"
                f"{content}"
            )
            
            logger.info(f"Sending bot message directly to user {user_id}: {sender_name} -> {account_name}")
            
            await self.bot.send_message(
                user_id,
                direct_message,
                parse_mode='md'
            )
            
            logger.info(f"✅ Bot message sent directly to user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to send bot message directly: {e}")
    
    async def _get_user_admin_group(self, user_id: int) -> Optional[int]:
        """Get admin group ID for user"""
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            return user.get("dm_reply_group_id") if user else None
        except Exception as e:
            logger.error(f"Failed to get admin group: {e}")
            return None
    
    # Messaging functionality
    async def send_message(self, user_id: int, account_name: str, target: str, message: str) -> bool:
        """Send message from specific account with proper target handling"""
        try:
            client = self.user_clients.get(user_id, {}).get(account_name)
            if not client:
                logger.error(f"Client not found for {account_name}")
                return False

            # Handle different target formats
            resolved_target = await self._resolve_target(client, target)
            if resolved_target is None:
                logger.error(f"Could not resolve target: {target}")
                return False

            await client.send_message(resolved_target, message)
            logger.info(f"Message sent from {account_name} to {target}")
            return True

        except Exception as e:
            logger.error(f"Failed to send message from {account_name} to {target}: {e}")
            return False
    
    async def _resolve_target(self, client, target: str):
        """Resolve target to proper entity"""
        try:
            # If it's a numeric string, treat as user ID
            if target.isdigit():
                user_id = int(target)
                logger.info(f"Resolving numeric target as user ID: {user_id}")
                
                # Try multiple approaches for user ID resolution
                try:
                    # First try to get entity normally
                    entity = await client.get_entity(user_id)
                    logger.info(f"Successfully resolved user ID {user_id} via get_entity")
                    return entity
                except Exception as e1:
                    logger.warning(f"get_entity failed for {user_id}: {e1}")
                    
                    # Try using InputPeerUser with access_hash=0
                    try:
                        from telethon.tl.types import InputPeerUser
                        input_peer = InputPeerUser(user_id=user_id, access_hash=0)
                        logger.info(f"Using InputPeerUser with access_hash=0 for {user_id}")
                        return input_peer
                    except Exception as e2:
                        logger.error(f"InputPeerUser also failed for {user_id}: {e2}")
                        return None
            
            # If it starts with @, it's a username
            if target.startswith('@'):
                username = target[1:]  # Remove @
                logger.info(f"Resolving username: {username}")
                return username
            
            # If it starts with +, it's a phone number
            if target.startswith('+'):
                logger.info(f"Resolving phone number: {target}")
                return target
            
            # If it starts with -, it's likely a group/channel ID
            if target.startswith('-'):
                chat_id = int(target)
                logger.info(f"Resolving chat ID: {chat_id}")
                return chat_id
            
            # Try to resolve as entity directly
            logger.info(f"Attempting to resolve as entity: {target}")
            entity = await client.get_entity(target)
            return entity
            
        except ValueError as e:
            logger.error(f"Invalid target format: {target} - {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to resolve target {target}: {e}")
            return None
    
    async def setup_auto_reply(self, user_id: int, account_name: str, reply_message: str) -> bool:
        """Setup auto-reply for an account"""
        try:
            # Enable auto-reply for account
            await mongodb.db.accounts.update_one(
                {"user_id": user_id, "name": account_name},
                {"$set": {"auto_reply_enabled": True}}
            )
            
            # Store default message in settings
            await mongodb.db.auto_reply_settings.update_one(
                {"user_id": user_id},
                {"$set": {
                    "time_based_replies_enabled": True,
                    "available_message": reply_message
                }},
                upsert=True
            )
            
            logger.info(f"Auto-reply enabled for {account_name} with message: {reply_message[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to setup auto-reply: {e}")
            return False
    
    async def disable_auto_reply(self, user_id: int, account_name: str) -> bool:
        """Disable auto-reply for an account"""
        try:
            await mongodb.db.accounts.update_one(
                {"user_id": user_id, "name": account_name},
                {"$set": {"auto_reply_enabled": False}}
            )
            
            logger.info(f"Auto-reply disabled for {account_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to disable auto-reply: {e}")
            return False
    

    
    async def setup_new_client_handler(self, user_id: int, account_name: str, client):
        """Set up handlers for newly added client"""
        if client and client.is_connected():
            logger.info(f"Setting up unified messaging for new client: {account_name} (user {user_id})")
            self._setup_client_handlers(user_id, account_name, client)
        else:
            logger.error(f"Cannot setup handlers for {account_name} - client not connected")
    
    def cleanup_handlers(self):
        """Clean up all registered handlers"""
        logger.info(f"Cleaning up {len(self.handled_clients)} unified messaging handlers")
        self.handled_clients.clear()
        self.registered_client_objects.clear()
        if hasattr(self.bot_manager, 'registered_handlers'):
            self.bot_manager.registered_handlers["messaging"].clear()