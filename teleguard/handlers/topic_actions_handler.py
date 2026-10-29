"""Handle forum topic lifecycle actions for unified DM topics."""

import logging

from telethon import events
from telethon.tl.types import (
    MessageActionTopicEdit,
    UpdateDeleteChannelMessages,
    UpdateEditChannelMessage,
    UpdateNewChannelMessage,
)

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class TopicActionsHandler:
    """Block or unblock mapped DM senders as their forum topics change."""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients

    def register_handlers(self):
        """Register topic lifecycle and existing topic commands."""

        @self.bot.on(events.Raw())
        async def handle_topic_updates(event):
            try:
                if isinstance(event, UpdateDeleteChannelMessages):
                    await self._handle_deleted_topic_messages(
                        event.channel_id, event.messages
                    )
                    return

                if not isinstance(
                    event, (UpdateEditChannelMessage, UpdateNewChannelMessage)
                ):
                    return

                message = event.message
                action = getattr(message, "action", None)
                if not isinstance(action, MessageActionTopicEdit):
                    return

                closed = getattr(action, "closed", None)
                if closed is None:
                    return

                channel_id = getattr(message.peer_id, "channel_id", None)
                if channel_id is not None:
                    await self._handle_topic_closed(
                        channel_id, message.id, closed=closed
                    )
            except Exception:
                logger.exception("Failed to process forum topic update")

        @self.bot.on(events.NewMessage())
        async def handle_general_topic(event):
            try:
                if not event.is_group:
                    return
                reply_to = getattr(event.message, "reply_to", None)
                if reply_to and getattr(reply_to, "reply_to_top_id", None) == 1:
                    await self._handle_general_topic_broadcast(event)
            except Exception:
                logger.exception("General topic handler error")

        @self.bot.on(events.NewMessage(pattern=r"^/block$"))
        async def block_from_topic(event):
            try:
                if not event.is_group:
                    return
                reply_to = getattr(event.message, "reply_to", None)
                topic_id = getattr(reply_to, "reply_to_top_id", None)
                if topic_id:
                    blocked = await self._block_user_from_topic(
                        event.chat_id, topic_id, event.sender_id
                    )
                    await event.reply(
                        "✅ User blocked" if blocked else "❌ Could not block user"
                    )
            except Exception:
                logger.exception("Block command error")

        @self.bot.on(events.NewMessage(pattern=r"^/clear_history$"))
        async def clear_from_topic(event):
            try:
                if not event.is_group:
                    return
                reply_to = getattr(event.message, "reply_to", None)
                topic_id = getattr(reply_to, "reply_to_top_id", None)
                if topic_id:
                    result = await self._clear_history_from_topic(
                        event.chat_id, topic_id
                    )
                    await event.reply(
                        "✅ Chat history cleared"
                        if result
                        else "❌ Failed to clear history"
                    )
            except Exception:
                logger.exception("Clear history command error")

    async def _handle_topic_closed(
        self, channel_id: int, topic_id: int, closed: bool = True
    ) -> bool:
        """Persist a topic's state and apply it to its mapped Telegram account."""
        chat_id = -1000000000000 - channel_id
        query = {"admin_group_id": chat_id, "topic_id": topic_id}
        mapping = await mongodb.db.topic_mappings.find_one(query)
        if not mapping:
            logger.warning(
                "No topic mapping found for group %s topic %s", chat_id, topic_id
            )
            return False

        await mongodb.db.topic_mappings.update_one(
            query,
            {"$set": {"is_closed": closed, "block_sync_pending": True}},
        )
        return await self._apply_topic_state(mapping, closed)

    async def _block_user_from_topic(
        self, chat_id: int, topic_id: int, sender_id: int = None
    ) -> bool:
        """Block the sender associated with a topic."""
        return await self._set_topic_state(chat_id, topic_id, True)

    async def _set_topic_state(
        self, chat_id: int, topic_id: int, closed: bool
    ) -> bool:
        query = {"admin_group_id": chat_id, "topic_id": topic_id}
        mapping = await mongodb.db.topic_mappings.find_one(query)
        if not mapping:
            logger.warning(
                "No topic mapping found for group %s topic %s", chat_id, topic_id
            )
            return False
        await mongodb.db.topic_mappings.update_one(
            query,
            {"$set": {"is_closed": closed, "block_sync_pending": True}},
        )
        return await self._apply_topic_state(mapping, closed)

    async def _apply_topic_state(
        self, mapping: dict, closed: bool, client=None
    ) -> bool:
        success = await self._set_sender_blocked(mapping, closed, client)
        await mongodb.db.topic_mappings.update_one(
            {
                "admin_group_id": mapping["admin_group_id"],
                "topic_id": mapping["topic_id"],
            },
            {"$set": {"block_sync_pending": not success}},
        )
        return success

    async def _set_sender_blocked(
        self, mapping: dict, blocked: bool, client=None
    ) -> bool:
        account_id = mapping.get("account_id")
        target_sender_id = mapping.get("sender_id")
        if not account_id or not target_sender_id:
            logger.error("Topic mapping is missing account or sender ID")
            return False

        if client is None:
            client = await self.bot_manager.get_client_by_telegram_id(account_id)
        if not client:
            logger.error(
                "Cannot %s sender %s: mapped account %s is unavailable",
                "block" if blocked else "unblock",
                target_sender_id,
                account_id,
            )
            return False

        try:
            from telethon.tl.functions.contacts import BlockRequest, UnblockRequest

            sender = await client.get_input_entity(target_sender_id)
            request = (
                BlockRequest(id=sender)
                if blocked
                else UnblockRequest(id=sender)
            )
            await client(request)
            logger.info(
                "%s sender %s on account %s",
                "Blocked" if blocked else "Unblocked",
                target_sender_id,
                account_id,
            )
            return True
        except Exception:
            logger.exception(
                "Failed to %s sender %s on account %s",
                "block" if blocked else "unblock",
                target_sender_id,
                account_id,
            )
            return False

    async def _handle_deleted_topic_messages(
        self, channel_id: int, deleted_message_ids: list[int]
    ):
        """Clear mapped DM history when Telegram deletes a topic and its root.

        Telegram removes the forum topic's own messages with the deleted topic.
        """
        chat_id = -1000000000000 - channel_id
        for topic_id in set(deleted_message_ids):
            mapping = await mongodb.db.topic_mappings.find_one(
                {"admin_group_id": chat_id, "topic_id": topic_id}
            )
            if not mapping:
                continue
            query = {"admin_group_id": chat_id, "topic_id": topic_id}
            await mongodb.db.topic_mappings.update_one(
                query,
                {"$set": {"topic_deleted": True, "history_clear_pending": True}},
            )
            if not await self._clear_sender_history(mapping):
                continue

            await mongodb.db.topic_mappings.delete_one(query)

    async def _clear_sender_history(self, mapping: dict, client=None) -> bool:
        account_id = mapping.get("account_id")
        target_sender_id = mapping.get("sender_id")
        if not account_id or not target_sender_id:
            logger.error("Topic mapping is missing account or sender ID")
            return False

        if client is None:
            client = await self.bot_manager.get_client_by_telegram_id(account_id)
        if not client:
            logger.error(
                "Cannot clear DM history for sender %s: mapped account %s is unavailable",
                target_sender_id,
                account_id,
            )
            return False

        try:
            from telethon.tl.functions.messages import DeleteHistoryRequest

            sender = await client.get_input_entity(target_sender_id)
            await client(
                DeleteHistoryRequest(
                    peer=sender, max_id=0, just_clear=False, revoke=True
                )
            )
            logger.info(
                "Cleared DM history for sender %s on account %s",
                target_sender_id,
                account_id,
            )
            return True
        except Exception:
            logger.exception(
                "Failed to clear DM history for sender %s on account %s",
                target_sender_id,
                account_id,
            )
            return False

    async def _clear_history_from_topic(self, chat_id: int, topic_id: int) -> bool:
        mapping = await mongodb.db.topic_mappings.find_one(
            {"admin_group_id": chat_id, "topic_id": topic_id}
        )
        if not mapping:
            logger.warning("No topic mapping found for topic %s", topic_id)
            return False
        return await self._clear_sender_history(mapping)

    async def sync_account_topic_states(self, account_id: int, client):
        """Retry topic actions that could not run while an account was offline."""
        deleted_topics = await mongodb.db.topic_mappings.find(
            {"account_id": account_id, "history_clear_pending": True}
        ).to_list(None)
        for mapping in deleted_topics:
            if await self._clear_sender_history(mapping, client):
                await mongodb.db.topic_mappings.delete_one(
                    {
                        "admin_group_id": mapping["admin_group_id"],
                        "topic_id": mapping["topic_id"],
                    }
                )

        pending_states = await mongodb.db.topic_mappings.find(
            {"account_id": account_id, "block_sync_pending": True}
        ).to_list(None)
        for mapping in pending_states:
            await self._apply_topic_state(
                mapping, bool(mapping.get("is_closed")), client
            )

    async def sync_connected_account_states(self):
        """Reconcile pending topic actions for clients already loaded at startup."""
        for clients in self.user_clients.values():
            for client in clients.values():
                if not client or not client.is_connected():
                    continue
                try:
                    me = await client.get_me()
                    await self.sync_account_topic_states(me.id, client)
                except Exception:
                    logger.exception(
                        "Failed to sync topic state for a connected account"
                    )

    async def _handle_general_topic_broadcast(self, event):
        """Broadcast a general-topic message to the user's mapped DM senders."""
        try:
            user = await mongodb.db.users.find_one(
                {"manager_forum_chat_id": event.chat_id}
            )
            if not user or event.sender_id != user["telegram_id"] or not event.text:
                return

            topics = await mongodb.db.dm_topics.find(
                {"user_id": user["telegram_id"]}
            ).to_list(None)
            accounts_users = {}
            for topic in topics:
                account_name = topic["account_name"]
                accounts_users.setdefault(account_name, set()).add(topic["sender_id"])

            sent_count = 0
            for account_name, user_ids in accounts_users.items():
                client = self.user_clients.get(user["telegram_id"], {}).get(
                    account_name
                )
                if not client or not client.is_connected():
                    continue
                for target_id in user_ids:
                    try:
                        await client.send_message(target_id, event.text)
                        sent_count += 1
                    except Exception:
                        logger.exception(
                            "Failed to broadcast to %s from %s",
                            target_id,
                            account_name,
                        )

            await event.reply(
                f"📢 Broadcast sent to {sent_count} users from "
                f"{len(accounts_users)} accounts"
            )
        except Exception:
            logger.exception("Failed to handle general topic broadcast")
