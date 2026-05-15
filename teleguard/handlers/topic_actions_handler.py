"""Advanced Topic Actions Handler - Close to block, Clear to delete history, General topic broadcast"""

import logging

from telethon import events

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

        # Monitor forum topic edits (close/open)
        @self.bot.on(events.Raw())
        async def handle_raw_events(event):
            try:
                from telethon.tl.types import UpdateEditChannelMessage

                if isinstance(event, UpdateEditChannelMessage):
                    msg = event.message
                    if hasattr(msg, "action"):
                        from telethon.tl.types import MessageActionTopicEdit

                        if isinstance(msg.action, MessageActionTopicEdit):
                            if msg.action.closed:
                                await self._handle_topic_closed(
                                    event.message.peer_id.channel_id, msg.id
                                )
            except Exception as e:
                logger.debug(f"Raw event handler: {e}")

        # Monitor general topic (ID=1) for broadcasts
        @self.bot.on(events.NewMessage())
        async def handle_general_topic(event):
            try:
                if not event.is_group:
                    return

                reply_to = getattr(event.message, "reply_to", None)
                if reply_to:
                    topic_id = getattr(reply_to, "reply_to_top_id", None)
                    if topic_id == 1:  # General topic
                        await self._handle_general_topic_broadcast(event)
            except Exception as e:
                logger.error(f"General topic handler error: {e}")

        # Command to manually block user from topic
        @self.bot.on(events.NewMessage(pattern=r"^/block$"))
        async def block_from_topic(event):
            try:
                if not event.is_group:
                    return

                reply_to = getattr(event.message, "reply_to", None)
                if reply_to:
                    topic_id = getattr(reply_to, "reply_to_top_id", None)
                    if topic_id:
                        await self._block_user_from_topic(
                            event.chat_id, topic_id, event.sender_id
                        )
                        await event.reply("✅ User blocked")
            except Exception as e:
                logger.error(f"Block command error: {e}")

        # Command to clear chat history from topic
        @self.bot.on(events.NewMessage(pattern=r"^/clear_history$"))
        async def clear_from_topic(event):
            try:
                if not event.is_group:
                    return

                reply_to = getattr(event.message, "reply_to", None)
                if reply_to:
                    topic_id = getattr(reply_to, "reply_to_top_id", None)
                    if topic_id:
                        result = await self._clear_history_from_topic(
                            event.chat_id, topic_id, event.sender_id
                        )
                        if result:
                            await event.reply(
                                "✅ Chat history cleared and topic renamed"
                            )
                        else:
                            await event.reply("❌ Failed to clear history")
            except Exception as e:
                logger.error(f"Clear history command error: {e}")

    async def _handle_topic_closed(self, channel_id: int, topic_id: int):
        """Handle topic closed - block user"""
        try:
            chat_id = -1000000000000 - channel_id
            await self._block_user_from_topic(chat_id, topic_id)
            logger.info(f"Topic {topic_id} closed, user blocked")
        except Exception as e:
            logger.error(f"Handle topic closed error: {e}")

    async def _block_user_from_topic(
        self, chat_id: int, topic_id: int, sender_id: int = None
    ):
        """Block user associated with topic"""
        try:
            # Find topic mapping
            topic_mapping = await mongodb.db.dm_topics.find_one(
                {"group_id": chat_id, "topic_id": topic_id}
            )

            if not topic_mapping:
                logger.warning(f"No topic mapping found for topic {topic_id}")
                return

            user_id = topic_mapping.get("user_id")
            account_id = topic_mapping.get("account_id")
            target_sender_id = topic_mapping.get("sender_id")

            if not user_id or not account_id or not target_sender_id:
                logger.error("Missing data in topic mapping")
                return

            # Get client by account_id
            client = None
            for uid, clients in self.user_clients.items():
                for acc_name, c in clients.items():
                    if c and c.is_connected():
                        try:
                            me = await c.get_me()
                            if me.id == account_id:
                                client = c
                                user_id = uid
                                break
                        except BaseException:
                            continue
                if client:
                    break

            if not client:
                logger.error(f"Client not found for account_id {account_id}")
                return

            # Block the user
            from telethon.tl.functions.contacts import BlockRequest

            await client(BlockRequest(id=target_sender_id))

            logger.info(f"✅ Blocked user {target_sender_id} on account {account_id}")

            # Notify in bot
            await self.bot.send_message(
                user_id,
                f"🚫 **User Blocked**\n\nUser ID: {target_sender_id}\n\nTopic closed = User blocked",
            )

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

    async def _clear_history_from_topic(
        self, chat_id: int, topic_id: int, sender_id: int
    ):
        """Clear chat history for user in topic"""
        try:
            # Find topic mapping
            topic_mapping = await mongodb.db.dm_topics.find_one(
                {"group_id": chat_id, "topic_id": topic_id}
            )

            if not topic_mapping:
                logger.warning(f"No topic mapping found for topic {topic_id}")
                return False

            topic_mapping.get("user_id")
            account_id = topic_mapping.get("account_id")
            target_user_id = topic_mapping.get("sender_id")
            account_name = topic_mapping.get("account_name", "Unknown")

            if not account_id or not target_user_id:
                return False

            # Get client by account_id
            client = None
            for uid, clients in self.user_clients.items():
                for acc_name, c in clients.items():
                    if c and c.is_connected():
                        try:
                            me = await c.get_me()
                            if me.id == account_id:
                                client = c
                                account_name = acc_name
                                break
                        except BaseException:
                            continue
                if client:
                    break

            if not client:
                logger.error(f"Client not found for account_id {account_id}")
                return False

            # Delete chat history
            from telethon.tl.functions.messages import DeleteHistoryRequest

            await client(
                DeleteHistoryRequest(
                    peer=target_user_id, max_id=0, just_clear=False, revoke=True
                )
            )

            # Rename topic to indicate cleared
            try:
                from telethon.tl.functions.channels import EditForumTopicRequest

                sender = await client.get_entity(target_user_id)
                sender_name = getattr(sender, "first_name", "User")
                new_title = f"🗑️ {sender_name} → {account_name} (Cleared)"

                await self.bot(
                    EditForumTopicRequest(
                        channel=chat_id, topic_id=topic_id, title=new_title
                    )
                )
            except Exception as e:
                logger.error(f"Failed to rename topic: {e}")

            logger.info(
                f"✅ Cleared chat history with user {target_user_id} on account {account_name}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to clear history: {e}")
            return False

    async def _handle_general_topic_broadcast(self, event):
        """Broadcast message from general topic to all users from all accounts"""
        try:
            # Check if sender is the group owner
            user = await mongodb.db.users.find_one(
                {"manager_forum_chat_id": event.chat_id}
            )
            if not user or event.sender_id != user["telegram_id"]:
                return

            message_text = event.text
            if not message_text:
                return

            # Get all topics for this user
            topics = await mongodb.db.dm_topics.find(
                {"user_id": user["telegram_id"]}
            ).to_list(None)

            # Group by account
            accounts_users = {}
            for topic in topics:
                account_name = topic["account_name"]
                sender_id = topic["sender_id"]

                if account_name not in accounts_users:
                    accounts_users[account_name] = set()
                accounts_users[account_name].add(sender_id)

            # Send from each account to its users
            sent_count = 0
            for account_name, user_ids in accounts_users.items():
                client = self.user_clients.get(user["telegram_id"], {}).get(
                    account_name
                )
                if not client or not client.is_connected():
                    continue

                for uid in user_ids:
                    try:
                        await client.send_message(uid, message_text)
                        sent_count += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to send to {uid} from {account_name}: {e}"
                        )

            # Confirm broadcast
            await event.reply(
                f"📢 Broadcast sent to {sent_count} users from {
                    len(accounts_users)} accounts"
            )

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
