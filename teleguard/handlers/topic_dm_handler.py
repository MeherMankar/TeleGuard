"""Topic-based DM Reply Handler - Uses Telegram Group Topics for conversation management"""

import logging
from datetime import datetime, timezone

from telethon import events, functions

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class TopicDMHandler:
    """Handles DM forwarding using Telegram Group Topics"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        self.handled_clients = set()
        self.mapping_cache = {}  # Cache: (user_id, account_id) -> topic_id

    def setup_topic_handlers(self):
        """Set up topic-based DM handlers"""
        for user_id, clients in self.user_clients.items():
            for account_name, client in clients.items():
                if client and client.is_connected():
                    self._setup_client_dm_handler(user_id, account_name, client)
        self._setup_admin_reply_handler()

    def _setup_client_dm_handler(self, user_id: int, account_name: str, client):
        """Set up DM handler for managed account"""
        client_key = f"{user_id}:{account_name}"
        if client_key in self.handled_clients:
            return
        self.handled_clients.add(client_key)

        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def dm_handler(event):
            try:
                if event.out:
                    return
                sender = await event.get_sender()
                me = await client.get_me()
                admin_group_id = await self._get_user_admin_group(user_id)
                if not admin_group_id:
                    return
                # Find or create topic for this sender
                topic_id = await self._find_or_create_topic(
                    admin_group_id, sender.id, me.id, sender
                )
                if topic_id:
                    # Forward message to topic
                    await self._forward_to_topic(
                        admin_group_id, topic_id, event, sender, me
                    )
            except Exception as e:
                logger.error(f"DM handler error: {e}")

    def _setup_admin_reply_handler(self):
        """Set up handler for admin replies in topics"""

        @self.bot.on(events.NewMessage())
        async def topic_reply_handler(event):
            try:
                if not hasattr(event.message, "reply_to") or not event.message.reply_to:
                    return
                if not hasattr(event.message.reply_to, "forum_topic_id"):
                    return
                topic_id = event.message.reply_to.forum_topic_id
                if not topic_id:
                    return
                user = await mongodb.db.users.find_one(
                    {"dm_reply_group_id": event.chat_id}
                )
                if not user:
                    return
                # Skip if sender is not the group owner
                if event.sender_id != user["telegram_id"]:
                    return
                mapping = await self._get_topic_mapping(event.chat_id, topic_id)
                if not mapping:
                    return
                target_user_id = mapping["user_id"]
                managed_account_id = mapping["account_id"]
                # Find the managed client
                managed_client = await self._get_client_by_id(managed_account_id)
                if managed_client:
                    await managed_client.send_message(target_user_id, event.text)
            except Exception as e:
                logger.error(f"Reply handler error: {e}")

    async def _get_user_admin_group(self, user_id: int) -> int:
        """Get admin group ID for user"""
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            return user.get("dm_reply_group_id") if user else None
        except Exception as e:
            logger.error(f"Failed to get admin group: {e}")
            return None

    async def _find_or_create_topic(
        self, admin_group_id: int, sender_id: int, account_id: int, sender
    ) -> int:
        """Find existing topic or create new one for sender + account combination"""
        try:
            # Check cache first
            cache_key = (sender_id, account_id)
            if cache_key in self.mapping_cache:
                return self.mapping_cache[cache_key]

            # Check database
            mapping = await mongodb.db.topic_mappings.find_one(
                {"user_id": sender_id, "account_id": account_id}
            )
            if mapping:
                topic_id = mapping["topic_id"]
                self.mapping_cache[cache_key] = topic_id
                return topic_id

            # Create new topic
            topic_title = self._get_topic_title(sender, account_id)
            result = await self.bot(
                functions.channels.CreateForumTopicRequest(
                    channel=admin_group_id,
                    title=topic_title,
                    random_id=hash(f"{sender_id}_{account_id}"),
                )
            )
            topic_id = result.updates[0].message.id

            # Store mapping atomically (prevents duplicates during race conditions)
            await mongodb.db.topic_mappings.update_one(
                {"user_id": sender_id, "account_id": account_id},
                {
                    "$setOnInsert": {
                        "user_id": sender_id,
                        "account_id": account_id,
                        "topic_id": topic_id,
                        "admin_group_id": admin_group_id,
                        "created_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )

            # Update cache
            self.mapping_cache[cache_key] = topic_id
            return topic_id
        except Exception as e:
            logger.error(f"Failed to create topic: {e}")
            return None



    def _get_topic_title(self, sender, account_id: int) -> str:
        """Generate topic title from sender info + account"""
        if hasattr(sender, "first_name") and sender.first_name:
            user_name = sender.first_name
            if hasattr(sender, "last_name") and sender.last_name:
                user_name += f" {sender.last_name}"
        elif hasattr(sender, "username") and sender.username:
            user_name = f"@{sender.username}"
        else:
            user_name = f"User {sender.id}"
        
        # Add account identifier
        account_short = str(account_id)[-4:]  # Last 4 digits
        title = f"{user_name} | {account_short}"
        return title[:100]  # Telegram topic title limit



    async def _forward_to_topic(
        self, admin_group_id: int, topic_id: int, event, sender, managed_account
    ):
        """Forward DM to topic"""
        try:
            sender_name = self._get_topic_title(sender)
            account_name = managed_account.username or f"ID: {managed_account.id}"
            forward_text = (
                f"📨 **From:** {sender_name}\n"
                f"📱 **To:** @{account_name}\n\n"
                f"{event.text or '[Media/File]'}"
            )
            await self.bot.send_message(
                admin_group_id, forward_text, reply_to=topic_id, parse_mode="md"
            )
        except Exception as e:
            logger.error(f"Failed to forward to topic: {e}")

    async def _get_topic_mapping(self, admin_group_id: int, topic_id: int) -> dict:
        """Get user and account mapping from database using topic_id"""
        try:
            mapping = await mongodb.db.topic_mappings.find_one({"topic_id": topic_id})
            if mapping:
                return {
                    "user_id": mapping["user_id"],
                    "account_id": mapping["account_id"],
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get topic mapping: {e}")
            return None

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

    async def setup_new_client_handler(self, user_id: int, account_name: str, client):
        """Set up topic handler for newly added client"""
        if client and client.is_connected():
            self._setup_client_dm_handler(user_id, account_name, client)
