"""Unified Messaging System - Handles all messaging, DM forwarding, and topic management"""

import logging
from typing import Optional

from telethon import events, functions

from ..core.mongo_database import mongodb
from ..core.config import config

logger = logging.getLogger(__name__)


class UnifiedMessagingSystem:
    """Unified system for messaging, DM forwarding, and topic management"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        self.handled_clients = set()
        self.registered_client_objects = set()
        self.auto_reply_handlers = {}
        self.processed_messages = set()

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
        if hasattr(client, "_event_builders") and client._event_builders:
            for builder in client._event_builders:
                if hasattr(builder, "func") and "private" in str(builder.func):
                    self.handled_clients.add(client_key)
                    self.registered_client_objects.add(client_obj_id)
                    return
        self.handled_clients.add(client_key)
        self.registered_client_objects.add(id(client))
        if hasattr(self.bot_manager, "registered_handlers"):
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
                if len(self.processed_messages) > 1000:
                    self.processed_messages = set(list(self.processed_messages)[-500:])
                sender = await event.get_sender()
                me = await client.get_me()
                is_bot = getattr(sender, "bot", False)
                is_telegram_official = sender.id in [777000, 42777]

                logger.info(f"📨 Private message received on {account_name}: from={sender.id}, is_bot={is_bot}, is_official={is_telegram_official}")

                if is_telegram_official:
                    await self._send_bot_message_directly(user_id, sender, me, event)
                    return
                elif is_bot:
                    logger.info(f"Skipping bot message from {sender.id}")
                    return

                admin_group_id = await self._get_user_admin_group(user_id, account_name)
                logger.info(f"Admin group for {account_name}: {admin_group_id}")
                if admin_group_id:
                    await self._handle_incoming_dm(
                        admin_group_id, event, sender, me, user_id
                    )
                else:
                    logger.info(f"No admin group configured for {account_name}, skipping topic creation")
                if not is_bot and not is_telegram_official:
                    await self._handle_auto_reply(client, event, user_id, account_name)
            except Exception as e:
                logger.error(
                    f"Private message handler error for {account_name}: {e}",
                    exc_info=True,
                )

    def _setup_admin_reply_handler(self):
        """Set up handler for admin replies in topics"""

        @self.bot.on(events.NewMessage())
        async def admin_group_handler(event):
            try:
                if not event.message.reply_to:
                    return
                
                # Check if message is in a topic (forum thread)
                reply_to = event.message.reply_to
                topic_id = getattr(reply_to, "reply_to_top_id", None)
                
                if not topic_id:
                    return
                
                # Find which account this group belongs to
                account = await mongodb.db.accounts.find_one(
                    {"dm_reply_group_id": event.chat_id}
                )
                if not account:
                    return
                
                # Verify sender is the account owner
                if event.sender_id != account["user_id"]:
                    return
                
                # Get topic mapping
                mapping = await mongodb.db.topic_mappings.find_one(
                    {"admin_group_id": event.chat_id, "topic_id": topic_id}
                )
                
                if mapping:
                    logger.info(f"Sending topic reply: has_media={event.message.media is not None}, has_text={event.text is not None}")
                    await self._send_topic_reply(
                        {
                            "user_id": mapping["sender_id"],
                            "account_id": mapping["account_id"],
                        },
                        message_text=event.text,
                        message_obj=event.message
                    )
                else:
                    logger.warning(f"No mapping found for topic {topic_id} in group {event.chat_id}")
            except Exception as e:
                logger.error(f"Admin group handler error: {e}", exc_info=True)

    async def _handle_incoming_dm(
        self, admin_group_id: int, event, sender, me, user_id: int
    ):
        """Handle incoming DM with automatic topic creation"""
        try:
            logger.info(f"📨 Handling incoming DM: sender={sender.id}, account={me.id}, group={admin_group_id}")
            topic_id = await self._find_or_create_topic(
                admin_group_id, sender.id, me.id, sender, user_id
            )
            if topic_id:
                logger.info(f"✅ Forwarding to topic {topic_id}")
                await self._forward_to_topic(
                    admin_group_id, topic_id, event, sender, me
                )
            else:
                logger.error(f"❌ No topic_id returned, cannot forward message")
        except Exception as e:
            logger.error(f"Failed to handle incoming DM: {e}", exc_info=True)

    async def _handle_auto_reply(self, client, event, user_id: int, account_name: str):
        """Handle auto-reply if enabled for account"""
        try:
            account = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "name": account_name}
            )
            if not account or not account.get("auto_reply_enabled", False):
                return
            sender = await event.get_sender()
            if getattr(sender, "bot", False):
                logger.debug(f"Skipping auto-reply to bot: {sender.id}")
                return
            if sender.id in [777000, 42777]:
                logger.debug(f"Skipping auto-reply to Telegram official: {sender.id}")
                return
            settings = (
                await mongodb.db.auto_reply_settings.find_one({"user_id": user_id})
                or {}
            )
            message_text = event.message.text.lower() if event.message.text else ""
            response = None
            if settings.get("keyword_replies_enabled", False):
                user_keywords = settings.get("keywords", {})
                for keyword, reply_msg in user_keywords.items():
                    if keyword.lower() in message_text:
                        response = reply_msg
                        break
            if not response and settings.get("time_based_replies_enabled", False):
                from datetime import datetime, time

                now = datetime.now()
                business_hours = {
                    "start": time(9, 0),
                    "end": time(17, 0),
                    "days": [0, 1, 2, 3, 4],
                }
                is_business_hours = (
                    now.weekday() in business_hours["days"]
                    and business_hours["start"] <= now.time() <= business_hours["end"]
                )
                if is_business_hours:
                    response = settings.get(
                        "available_message",
                        "I'm currently available and will respond soon.",
                    )
                else:
                    response = settings.get(
                        "unavailable_message",
                        "I'm not available right now. I'll get back to you later.",
                    )
            if response:
                await event.reply(response)
        except Exception as e:
            logger.error(f"Auto-reply error for {account_name}: {e}")

    async def _find_or_create_topic(self, admin_group_id: int, sender_id: int, account_id: int, sender, user_id: int) -> Optional[int]:
        """Find existing topic or create new one"""
        try:
            logger.info(f"🔍 Looking for topic: sender={sender_id}, account={account_id}, group={admin_group_id}")
            
            existing_topic = await self._find_existing_topic(admin_group_id, sender_id, account_id)
            if existing_topic:
                logger.info(f"✅ Found existing topic {existing_topic} for sender {sender_id}")
                return existing_topic
            
            logger.info(f"🆕 No existing topic found, creating new one...")
            
            forum_enabled = await self._verify_forum_enabled(admin_group_id)
            logger.info(f"📋 Forum enabled check result: {forum_enabled}")
            if not forum_enabled:
                logger.error(f"❌ Forum not enabled for group {admin_group_id}")
                return None
            
            logger.info(f"👤 Getting account info for {account_id}...")
            account_info = await self._get_account_info(account_id)
            logger.info(f"👤 Account info retrieved: {account_info is not None}")
            
            topic_title = self._get_topic_title(sender, account_info)
            logger.info(f"📝 Topic title generated: '{topic_title}'")
            
            logger.info(f"🔨 Calling _create_new_topic...")
            topic_id = await self._create_new_topic(admin_group_id, topic_title, sender_id, account_id, user_id)
            logger.info(f"🔨 _create_new_topic returned: {topic_id}")
            
            if topic_id:
                logger.info(f"✅ Topic created successfully with ID {topic_id}")
                await self._store_topic_mapping(admin_group_id, topic_id, sender_id, account_id)
                await self._create_system_message(admin_group_id, topic_id, sender_id, account_id)
            else:
                logger.error(f"❌ Failed to create topic for sender {sender_id}")
            
            return topic_id
        except Exception as e:
            logger.error(f"❌ Failed in find_or_create_topic: {e}", exc_info=True)
            return None

    async def _find_existing_topic(
        self, admin_group_id: int, sender_id: int, account_id: int
    ) -> Optional[int]:
        """Find existing topic for sender (one topic per user)"""
        try:
            if not all(
                isinstance(x, int) for x in [admin_group_id, sender_id, account_id]
            ):
                logger.error("Invalid input types for topic mapping")
                return None
            mapping = await mongodb.db.topic_mappings.find_one(
                {
                    "admin_group_id": admin_group_id,
                    "sender_id": sender_id,
                }
            )
            if mapping:
                topic_id = mapping["topic_id"]
                return topic_id
            return None
        except Exception as e:
            logger.error(f"Failed to find existing topic: {e}")
            return None

    def _get_topic_title(self, sender, account_info=None) -> str:
        """Generate topic title from sender and account info"""
        if hasattr(sender, "first_name") and sender.first_name:
            sender_name = sender.first_name
            if hasattr(sender, "last_name") and sender.last_name:
                sender_name += f" {sender.last_name}"
        elif hasattr(sender, "username") and sender.username:
            sender_name = f"@{sender.username}"
        else:
            sender_name = f"User {sender.id}"

        if account_info:
            if hasattr(account_info, "username") and account_info.username:
                account_name = f"@{account_info.username}"
            elif hasattr(account_info, "first_name") and account_info.first_name:
                account_name = account_info.first_name
            else:
                account_name = f"Account {account_info.id}"
        else:
            account_name = "Account"

        title = f"{sender_name} → {account_name}"
        return title[:100]

    async def _store_topic_mapping(
        self, admin_group_id: int, topic_id: int, sender_id: int, account_id: int
    ):
        """Store topic mapping in database"""
        try:
            import time

            mapping = {
                "admin_group_id": admin_group_id,
                "topic_id": topic_id,
                "sender_id": sender_id,
                "account_id": account_id,
                "created_at": int(time.time()),
            }
            await mongodb.db.topic_mappings.update_one(
                {
                    "admin_group_id": admin_group_id,
                    "sender_id": sender_id,
                    "account_id": account_id,
                },
                {"$set": mapping},
                upsert=True,
            )
        except Exception as e:
            logger.error(f"Failed to store topic mapping: {e}")

    async def _create_system_message(
        self, admin_group_id: int, topic_id: int, sender_id: int, account_id: int
    ):
        """Create system message with mapping info"""
        try:
            system_text = (
                f"🔗 **Topic Mapping**\n"
                f"User ID: `{sender_id}`\n"
                f"Account ID: `{account_id}`\n"
                f"Topic ID: `{topic_id}`"
            )
            await self.bot.send_message(
                admin_group_id, system_text, reply_to=topic_id, parse_mode="md"
            )
        except Exception as e:
            logger.error(f"Failed to create system message: {e}")

    async def _forward_to_topic(
        self, admin_group_id: int, topic_id: int, event, sender, managed_account
    ):
        """Forward DM to topic using copy (no download) - supports up to 4GB files"""
        media_id = None
        try:
            sender_name = self._get_topic_title(sender)
            account_name = getattr(managed_account, "username", None)
            if account_name:
                account_name = f"@{account_name}"
            else:
                account_name = getattr(
                    managed_account, "first_name", f"ID: {managed_account.id}"
                )
            
            caption = f"📨 **From:** {sender_name}\n📱 **To:** {account_name}"
            
            # Handle media - copy without downloading
            if event.message.media:
                try:
                    # Store metadata temporarily
                    media_id = await self._save_temp_media(event.message)
                    
                    if event.text:
                        caption += f"\n\n{event.text}"
                    
                    # Send caption first
                    await self.bot.send_message(
                        admin_group_id, caption, reply_to=topic_id, parse_mode="md"
                    )
                    
                    # Forward message to topic (no download) - supports 2-4GB files
                    from telethon.tl.functions.messages import ForwardMessagesRequest
                    from telethon.tl.types import InputReplyToMessage
                    await self.bot(ForwardMessagesRequest(
                        from_peer=event.chat_id,
                        id=[event.message.id],
                        to_peer=admin_group_id,
                        top_msg_id=topic_id
                    ))
                finally:
                    # Clean up temp storage
                    if media_id:
                        await self._delete_temp_media(media_id)
                return
            
            # Text-only message
            if event.text:
                forward_text = f"{caption}\n\n{event.text}"
            else:
                forward_text = f"{caption}\n\n[Empty Message]"
            
            await self.bot.send_message(
                admin_group_id, forward_text, reply_to=topic_id, parse_mode="md"
            )
        except Exception as e:
            logger.error(f"Failed to forward to topic: {e}", exc_info=True)

    async def _get_topic_mapping(
        self, admin_group_id: int, topic_id: int
    ) -> Optional[dict]:
        """Get user and account mapping from database"""
        try:
            if not isinstance(admin_group_id, int) or not isinstance(topic_id, int):
                logger.error("Invalid input types for topic mapping lookup")
                return None
            mapping = await mongodb.db.topic_mappings.find_one(
                {"admin_group_id": admin_group_id, "topic_id": topic_id}
            )
            if mapping:
                return {
                    "user_id": mapping["sender_id"],
                    "account_id": mapping["account_id"],
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get topic mapping: {e}")
            return None

    async def _send_topic_reply(self, mapping: dict, message_text: str = None, message_obj=None):
        """Send reply from topic to original sender using copy (no download)"""
        media_id = None
        try:
            target_user_id = mapping["user_id"]
            managed_account_id = mapping["account_id"]
            managed_client = await self._get_client_by_id(managed_account_id)
            
            if not managed_client:
                logger.error(f"No client found for account {managed_account_id}")
                return
            
            logger.info(f"Sending reply to user {target_user_id} from account {managed_account_id}")
            
            # If message object provided (media/sticker), forward without downloading
            if message_obj and message_obj.media:
                logger.info(f"Forwarding media: type={type(message_obj.media)}")
                
                try:
                    # Store metadata temporarily
                    media_id = await self._save_temp_media(message_obj)
                    
                    # Forward media directly (no download) - supports 2-4GB files
                    await managed_client.forward_messages(
                        target_user_id,
                        message_obj.id,
                        message_obj.chat_id
                    )
                    logger.info("Media forwarded successfully")
                finally:
                    # Clean up temp storage
                    if media_id:
                        await self._delete_temp_media(media_id)
            # Text message
            elif message_text:
                logger.info(f"Sending text message: {message_text[:50]}...")
                await managed_client.send_message(target_user_id, message_text)
                logger.info("Text sent successfully")
            else:
                logger.warning("No message text or media to send")
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

    async def _send_bot_message_directly(
        self, user_id: int, sender, managed_account, event
    ):
        """Send bot messages directly via bot instead of topics"""
        import tempfile
        import os
        temp_file = None
        try:
            sender_name = self._get_topic_title(sender)
            account_name = getattr(managed_account, "username", None)
            if account_name:
                account_name = f"@{account_name}"
            else:
                account_name = getattr(
                    managed_account, "first_name", f"ID: {managed_account.id}"
                )
            
            caption = f"🤖 **Bot Message**\n📨 **From:** {sender_name} (Bot)\n📱 **To:** {account_name}"
            
            # Handle media
            if event.message.media:
                if event.text:
                    caption += f"\n\n{event.text}"
                
                # Check file size
                file_size = getattr(event.message.media, 'document', None)
                if file_size:
                    file_size = getattr(file_size, 'size', 0)
                else:
                    file_size = 0
                
                # For large files (>100MB), use temp file; otherwise use bytes
                if file_size > 100 * 1024 * 1024:  # 100MB
                    temp_file = tempfile.NamedTemporaryFile(delete=False)
                    temp_file.close()
                    await event.client.download_media(event.message, file=temp_file.name)
                    await self.bot.send_file(
                        user_id,
                        temp_file.name,
                        caption=caption,
                        parse_mode="md",
                        force_document=False
                    )
                else:
                    media_bytes = await event.client.download_media(event.message, file=bytes)
                    await self.bot.send_file(
                        user_id,
                        media_bytes,
                        caption=caption,
                        parse_mode="md",
                        force_document=False
                    )
                return
            
            # Text-only message
            if event.text:
                direct_message = f"{caption}\n\n{event.text}"
            else:
                direct_message = f"{caption}\n\n[Empty Message]"
            
            await self.bot.send_message(user_id, direct_message, parse_mode="md")
        except Exception as e:
            logger.error(f"Failed to send bot message directly: {e}", exc_info=True)
        finally:
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except:
                    pass

    async def _get_user_admin_group(self, user_id: int, account_name: str = None) -> Optional[int]:
        """Get admin group ID for specific account"""
        try:
            if account_name:
                account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
                if account and account.get("dm_reply_group_id"):
                    admin_group_id = account["dm_reply_group_id"]
                    try:
                        chat_info = await self.bot.get_entity(admin_group_id)
                        is_forum = getattr(chat_info, "forum", False)
                        if not is_forum:
                            logger.warning(f"Group {admin_group_id} for account {account_name} does not have Topics enabled")
                            return None
                        return admin_group_id
                    except Exception as e:
                        logger.error(f"Failed to access group {admin_group_id}: {e}")
                        return None
            return None
        except Exception as e:
            logger.error(f"Failed to get admin group: {e}")
            return None

    async def send_message(
        self, user_id: int, account_name: str, target: str, message: str
    ) -> bool:
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
                await mongodb.db.accounts.update_one(
                    {"user_id": user_id, "name": account_name},
                    {"$set": {"session_conflict": True}},
                )
                return False
            logger.error(f"Failed to send message from {account_name} to {target}: {e}")
            return False

    async def _resolve_target(self, client, target: str):
        """Resolve target to proper entity"""
        try:
            if target.isdigit():
                user_id = int(target)
                try:
                    entity = await client.get_entity(user_id)
                    return entity
                except Exception as e1:
                    try:
                        from telethon.tl.types import InputPeerUser

                        input_peer = InputPeerUser(user_id=user_id, access_hash=0)
                        return input_peer
                    except Exception as e2:
                        return None
            if target.startswith("@"):
                username = target[1:]
                return username
            if target.startswith("+"):
                return target
            if target.startswith("-"):
                chat_id = int(target)
                return chat_id
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
                "total_messages_sent": 0,
                "auto_replies_sent": 0,
                "active_accounts": 0,
                "dm_topics_created": 0,
            }

            user_clients = self.user_clients.get(user_id, {})
            stats["active_accounts"] = len(
                [c for c in user_clients.values() if c and c.is_connected()]
            )

            if hasattr(self.bot_manager, "auto_reply_handler"):
                auto_reply_stats = self.bot_manager.auto_reply_handler.analytics
                stats["auto_replies_sent"] = auto_reply_stats.get(
                    "auto_replies_sent", 0
                )
                stats["total_messages_sent"] = auto_reply_stats.get("total_messages", 0)

            try:
                topic_count = await mongodb.db.topic_mappings.count_documents(
                    {"admin_group_id": {"$exists": True}}
                )
                stats["dm_topics_created"] = topic_count
            except Exception:
                pass

            return stats
        except Exception as e:
            logger.error(f"Error getting messaging statistics: {e}")
            return {"error": str(e)}

    async def setup_auto_reply(
        self, user_id: int, account_name: str, reply_message: str
    ) -> bool:
        """Setup auto-reply for an account"""
        try:
            await mongodb.db.accounts.update_one(
                {"user_id": user_id, "name": account_name},
                {"$set": {"auto_reply_enabled": True}},
            )
            await mongodb.db.auto_reply_settings.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "time_based_replies_enabled": True,
                        "available_message": reply_message,
                    }
                },
                upsert=True,
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
                {"$set": {"auto_reply_enabled": False}},
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
        if hasattr(self.bot_manager, "registered_handlers"):
            self.bot_manager.registered_handlers["messaging"].clear()

    async def _verify_forum_enabled(self, admin_group_id: int) -> bool:
        """Verify forum is enabled for group"""
        try:
            chat_info = await self.bot.get_entity(admin_group_id)
            is_forum = getattr(chat_info, "forum", False)
            if not is_forum:
                logger.error(f"Group {admin_group_id} does not have Topics/Forum enabled")
            return is_forum
        except Exception as e:
            logger.error(f"Failed to verify forum for {admin_group_id}: {e}")
            return False

    async def _get_account_info(self, account_id: int):
        """Get account info for topic title"""
        account_client = await self._get_client_by_id(account_id)
        if account_client:
            try:
                return await account_client.get_me()
            except Exception:
                pass
        return None

    async def _should_filter_media(self, message) -> bool:
        """Check if message should be filtered (media filter for free tier optimization)"""
        if not hasattr(message, 'media') or not message.media:
            return False
        # Filter photos and videos to save MongoDB storage
        from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
        if isinstance(message.media, MessageMediaPhoto):
            return True
        if isinstance(message.media, MessageMediaDocument):
            if message.media.document:
                mime = getattr(message.media.document, 'mime_type', '')
                if mime.startswith(('video/', 'image/')):
                    return True
        return False

    async def _save_temp_media(self, message) -> str:
        """Save media temporarily to DB"""
        try:
            from bson import ObjectId
            import time
            
            media_doc = {
                "_id": ObjectId(),
                "message_id": message.id,
                "created_at": int(time.time())
            }
            
            await mongodb.db.temp_media.insert_one(media_doc)
            return str(media_doc["_id"])
        except Exception as e:
            logger.error(f"Failed to save temp media: {e}")
            return None
    
    async def _delete_temp_media(self, media_id: str):
        """Delete temp media from DB"""
        try:
            from bson import ObjectId
            await mongodb.db.temp_media.delete_one({"_id": ObjectId(media_id)})
        except Exception as e:
            logger.error(f"Failed to delete temp media: {e}")

    async def _create_new_topic(self, admin_group_id: int, topic_title: str, sender_id: int, account_id: int, user_id: int) -> Optional[int]:
        """Create new forum topic"""
        try:
            import random
            from telethon.tl import functions
            
            logger.info(f"🔨 Creating topic '{topic_title}' in group {admin_group_id}")
            result = await self.bot(functions.channels.CreateForumTopicRequest(
                channel=admin_group_id,
                title=topic_title,
                icon_color=0x6FB9F0,
                random_id=random.randint(1, 2**63 - 1),
            ))
            logger.debug(f"Topic creation result type: {type(result)}, has updates: {hasattr(result, 'updates')}")
            if hasattr(result, "updates") and result.updates:
                logger.debug(f"Updates count: {len(result.updates)}")
                for i, update in enumerate(result.updates):
                    logger.debug(f"Update {i}: type={type(update)}, has message={hasattr(update, 'message')}, has id={hasattr(update, 'id')}")
                    if hasattr(update, "message") and update.message:
                        topic_id = update.message.id
                        logger.info(f"✅ Created topic '{topic_title}' with ID {topic_id} (from message.id)")
                        return topic_id
                    elif hasattr(update, "id"):
                        topic_id = update.id
                        logger.info(f"✅ Created topic '{topic_title}' with ID {topic_id} (from update.id)")
                        return topic_id
            logger.error(f"❌ Failed to extract topic ID from result: {result}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to create topic '{topic_title}' in {admin_group_id}: {e}", exc_info=True)
            return None
