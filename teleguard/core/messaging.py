"""Messaging Manager for TeleGuard

Handles message sending, auto-reply, and message templates.

Developed by:
- @Meher_Mankar
- @Gutkesh
"""

import logging
from typing import Dict, List, Optional

from telethon import events, TelegramClient

from .mongo_database import mongodb

logger = logging.getLogger(__name__)


class MessagingManager:
    """Manages messaging features for accounts"""

    def __init__(self, user_clients: Dict[int, Dict[str, TelegramClient]]):
        self.user_clients = user_clients
        self.auto_reply_handlers = {}

    async def send_message(
        self, user_id: int, account_name: str, target: str, message: str
    ) -> bool:
        """Send message from specific account"""
        try:
            client = self.user_clients.get(user_id, {}).get(account_name)
            if not client:
                return False

            await client.send_message(target, message)
            logger.info(f"Message sent from {account_name} to {target}")
            return True

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def setup_auto_reply(
        self, user_id: int, account_name: str, reply_message: str
    ):
        """Setup auto-reply for an account"""
        try:
            client = self.user_clients.get(user_id, {}).get(account_name)
            if not client:
                return False

            # Remove existing handler if any
            handler_key = f"{user_id}_{account_name}"
            if handler_key in self.auto_reply_handlers:
                client.remove_event_handler(self.auto_reply_handlers[handler_key])

            # Create new auto-reply handler
            @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
            async def auto_reply_handler(event):
                try:
                    # Don't reply to self or bots
                    if event.sender_id == (await client.get_me()).id:
                        return

                    sender = await event.get_sender()
                    if getattr(sender, "bot", False):
                        return

                    await event.reply(reply_message)
                    logger.info(f"Auto-reply sent from {account_name}")

                except Exception as e:
                    logger.error(f"Auto-reply error: {e}")

            self.auto_reply_handlers[handler_key] = auto_reply_handler
            logger.info(f"Auto-reply enabled for {account_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to setup auto-reply: {e}")
            return False

    async def disable_auto_reply(self, user_id: int, account_name: str):
        """Disable auto-reply for an account"""
        try:
            client = self.user_clients.get(user_id, {}).get(account_name)
            handler_key = f"{user_id}_{account_name}"

            if handler_key in self.auto_reply_handlers and client:
                client.remove_event_handler(self.auto_reply_handlers[handler_key])
                del self.auto_reply_handlers[handler_key]
                logger.info(f"Auto-reply disabled for {account_name}")
                return True

        except Exception as e:
            logger.error(f"Failed to disable auto-reply: {e}")

        return False

    async def forward_message(
        self,
        user_id: int,
        account_name: str,
        from_chat: str,
        to_chat: str,
        message_id: int,
    ) -> bool:
        """Forward message between chats"""
        try:
            client = self.user_clients.get(user_id, {}).get(account_name)
            if not client:
                return False

            await client.forward_messages(to_chat, message_id, from_chat)
            logger.info(f"Message forwarded from {from_chat} to {to_chat}")
            return True

        except Exception as e:
            logger.error(f"Failed to forward message: {e}")
            return False

    async def create_template(self, user_id: int, name: str, content: str) -> bool:
        """Create message template"""
        try:
            import time

            # Get user's first account for template storage
            account = await mongodb.db.accounts.find_one({"user_id": user_id})

            if not account:
                return False

            template = {
                "account_id": account["_id"],
                "user_id": user_id,
                "name": name,
                "content": content,
                "created_at": int(time.time()),
            }

            await mongodb.db.message_templates.insert_one(template)

            logger.info(f"Template '{name}' created for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to create template: {e}")
            return False

    async def get_templates(self, user_id: int) -> list:
        """Get user's message templates"""
        try:
            templates = await mongodb.db.message_templates.find(
                {"user_id": user_id}
            ).to_list(length=None)
            return [(str(t["_id"]), t["name"], t["content"]) for t in templates]

        except Exception as e:
            logger.error(f"Failed to get templates: {e}")
            return []

    async def delete_template(self, user_id: int, template_id: str) -> bool:
        """Delete message template"""
        try:
            from bson import ObjectId

            result = await mongodb.db.message_templates.delete_one(
                {"_id": ObjectId(template_id), "user_id": user_id}
            )

            return result.deleted_count > 0

        except Exception as e:
            logger.error(f"Failed to delete template: {e}")
            return False
