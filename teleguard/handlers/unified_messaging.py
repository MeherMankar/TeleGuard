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
            topic_title = self._get_topic_title(sender)
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
        try:
            sender_name = self._get_topic_title(sender)
            account_name = getattr(managed_account, 'username', None)
            if account_name:
                account_name = f"@{account_name}"
            else:
                account_name = getattr(managed_account, 'first_name', f"ID: {managed_account.id}")
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
            await self.bot.send_message(
                admin_group_id,
                forward_text,
                reply_to=topic_id,
                parse_mode='md'
            )
        except Exception as e:
            logger.error(f"Failed to forward to topic: {e}")
    async def _get_topic_mapping(self, admin_group_id: int, topic_id: int) -> Optional[dict]:
        """Get user and account mapping from database"""
        try:
            if not isinstance(admin_group_id, int) or not isinstance(topic_id, int):
                logger.error("Invalid input types for topic mapping lookup")
                return None
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
            # Find the managed client
            managed_client = await self._get_client_by_id(managed_account_id)
            if managed_client:
                await managed_client.send_message(target_user_id, message_text)
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
            await self.bot.send_message(
                user_id,
                direct_message,
                parse_mode='md'
            )
        except Exception as e:
            logger.error(f"Failed to send bot message directly: {e}")
    async def _get_user_admin_group(self, user_id: int) -> Optional[int]:
        """Get admin group ID for user"""
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if not user:
                return None
            admin_group_id = user.get("dm_reply_group_id")
            if not admin_group_id:
                return None
            try:
                await self.bot.get_entity(admin_group_id)
                return admin_group_id
            except Exception as access_error:
                return None
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
            resolved_target = await self._resolve_target(client, target)
            if resolved_target is None:
                return False
            await client.send_message(resolved_target, message)
            return True
        except Exception as e:
            error_msg = str(e)
            if "authorization key" in error_msg and "simultaneously" in error_msg:
                logger.warning(f"Session conflict detected for {account_name}")
                # Mark account as having session conflict
                await mongodb.db.accounts.update_one(
                    {"user_id": user_id, "name": account_name},
                    {"$set": {"session_conflict": True}}
                )
                return False
            logger.error(f"Failed to send message from {account_name} to {target}: {e}")
            return False
    async def _resolve_target(self, client, target: str):
        """Resolve target to proper entity"""
        try:
            # If it's a numeric string, treat as user ID
            if target.isdigit():
                user_id = int(target)
                # Try multiple approaches for user ID resolution
                try:
                    # First try to get entity normally
                    entity = await client.get_entity(user_id)
                    return entity
                except Exception as e1:
                    # Try using InputPeerUser with access_hash=0
                    try:
                        from telethon.tl.types import InputPeerUser
                        input_peer = InputPeerUser(user_id=user_id, access_hash=0)
                        return input_peer
                    except Exception as e2:
                        return None
            # If it starts with @, it's a username
            if target.startswith('@'):
                username = target[1:]
                return username
            # If it starts with +, it's a phone number
            if target.startswith('+'):
                return target
            # If it starts with -, it's likely a group/channel ID
            if target.startswith('-'):
                chat_id = int(target)
                return chat_id
            # Try to resolve as entity directly
            entity = await client.get_entity(target)
            return entity
        except ValueError as e:
            logger.error(f"Invalid target format: {target} - {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to resolve target {target}: {e}")
            return None
    async def get_messaging_statistics(self, user_id: int) -> dict:
        """Get messaging statistics for user"""
        try:
            stats = {
                'total_messages_sent': 0,
                'auto_replies_sent': 0,
                'active_accounts': 0,
                'dm_topics_created': 0
            }
            
            # Count active accounts
            user_clients = self.user_clients.get(user_id, {})
            stats['active_accounts'] = len([c for c in user_clients.values() if c and c.is_connected()])
            
            # Get auto-reply stats if available
            if hasattr(self.bot_manager, 'auto_reply_handler'):
                auto_reply_stats = self.bot_manager.auto_reply_handler.analytics
                stats['auto_replies_sent'] = auto_reply_stats.get('auto_replies_sent', 0)
                stats['total_messages_sent'] = auto_reply_stats.get('total_messages', 0)
            
            # Count DM topics
            try:
                topic_count = await mongodb.db.topic_mappings.count_documents({
                    "admin_group_id": {"$exists": True}
                })
                stats['dm_topics_created'] = topic_count
            except Exception:
                pass
                
            return stats
        except Exception as e:
            logger.error(f"Error getting messaging statistics: {e}")
            return {'error': str(e)}

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
            return True
        except Exception as e:
            logger.error(f"Failed to disable auto-reply: {e}")
            return False
    async def setup_new_client_handler(self, user_id: int, account_name: str, client):
        """Set up handlers for newly added client"""
        if client and client.is_connected():
            self._setup_client_handlers(user_id, account_name, client)
    def cleanup_handlers(self):
        """Clean up all registered handlers"""
        self.handled_clients.clear()
        self.registered_client_objects.clear()
        if hasattr(self.bot_manager, 'registered_handlers'):
            self.bot_manager.registered_handlers["messaging"].clear()
