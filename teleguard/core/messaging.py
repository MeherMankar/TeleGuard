"""Advanced messaging manager with template system
Developed by:
- @Meher_Mankar
- @Gutkesh
GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import Dict, Optional

from .mongo_database import mongodb

logger = logging.getLogger(__name__)


class MessagingManager:
    """Manages message templates and sending"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients

    def _replace_variables(self, content: str, target_info: Dict = None) -> str:
        """Replace template variables with actual values"""
        try:
            now = datetime.now()
            # Sanitize target_info to prevent injection
            import html

            safe_target_info = {}
            if target_info:
                for key, value in target_info.items():
                    if isinstance(value, str):
                        # Use html.escape for proper sanitization
                        safe_value = html.escape(str(value)[:100])
                        safe_target_info[key] = safe_value
                    else:
                        safe_target_info[key] = html.escape(str(value)[:100])
            # Default replacements with safe values
            replacements = {
                "{time}": now.strftime("%H:%M"),
                "{date}": now.strftime("%Y-%m-%d"),
                "{datetime}": now.strftime("%Y-%m-%d %H:%M"),
                "{name}": safe_target_info.get("first_name", "Friend"),
                "{username}": (
                    f"@{safe_target_info.get('username')}"
                    if safe_target_info.get("username")
                    else "Friend"
                ),
                "{full_name}": f"{safe_target_info.get('first_name', '')} {safe_target_info.get('last_name', '')}".strip()
                or "Friend",
            }
            # Replace variables safely using string formatting
            for var, value in replacements.items():
                if var in content:
                    # Use safe string replacement
                    content = content.replace(var, str(value))
            return content
        except Exception as e:
            logger.error(f"Failed to replace variables: {e}")
            return content

    async def _simulate_human_message_behavior(self, client, target, message: str):
        """Simulate extremely realistic human typing behavior"""
        # Random pre-typing delay (thinking/reading)
        thinking_delay = random.uniform(0.5, 4.0)
        await asyncio.sleep(thinking_delay)

        # Start typing
        from telethon import functions
        from telethon.tl import types

        await client(
            functions.messages.SetTypingRequest(
                peer=target, action=types.SendMessageTypingAction()
            )
        )

        # Simulate realistic typing with pauses and corrections
        words = message.split()
        total_chars = len(message)

        # Base typing speed: 40-80 WPM (realistic human range)
        wpm = random.uniform(40, 80)
        chars_per_second = (wpm * 5) / 60  # Average 5 chars per word

        # Calculate realistic typing time with variations
        base_typing_time = total_chars / chars_per_second

        # Add human-like variations
        typing_time = base_typing_time * random.uniform(0.8, 1.5)

        # Add pauses for longer messages (thinking while typing)
        if len(words) > 10:
            typing_time += random.uniform(1, 3)

        # Add correction delays for complex messages
        if any(len(word) > 8 for word in words):
            typing_time += random.uniform(0.5, 2)

        # Simulate typing with realistic pauses
        segments = max(1, len(words) // 5)  # Break into segments
        segment_time = typing_time / segments

        for i in range(segments):
            # Type for a segment
            await asyncio.sleep(segment_time * random.uniform(0.7, 1.3))

            # Random micro-pauses (hesitation, thinking)
            if random.random() < 0.3:  # 30% chance
                await asyncio.sleep(random.uniform(0.2, 1.5))

            # Restart typing indicator occasionally (like real typing)
            if i < segments - 1 and random.random() < 0.4:
                from telethon import functions
                from telethon.tl import types

                await client(
                    functions.messages.SetTypingRequest(
                        peer=target, action=types.SendMessageTypingAction()
                    )
                )

        # Final pause before sending (reviewing message)
        if random.random() < 0.6:  # 60% chance to review
            await asyncio.sleep(random.uniform(0.3, 2.0))

    async def send_message(self, user_id: int, account_name: str, target: str, message: str) -> bool:
        """Send a message with smart routing and human-like behavior"""
        try:
            client = await self._get_best_client(user_id, account_name, target)
            if not client:
                logger.error(f"No connected client found for user {user_id}, account {account_name}")
                return False
            target_entity = await self._resolve_target_entity(client, target)
            if not target_entity:
                return False
            from telethon.tl.types import InputPeerUser
            if not isinstance(target_entity, InputPeerUser):
                await self._simulate_typing(client, target_entity, message)
            await client.send_message(target_entity, message)
            logger.info(f"Message sent from {account_name} to {target}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message from {account_name} to {target}: {e}")
            return False

    async def _get_best_client(self, user_id: int, account_name: str, target: str):
        """Smart routing: get the best client to send message from"""
        try:
            # First try specified account
            if (
                user_id in self.user_clients
                and account_name in self.user_clients[user_id]
            ):
                client = self.user_clients[user_id][account_name]
                if client and client.is_connected():
                    return client

            # Fallback: try any connected account
            if user_id in self.user_clients:
                for name, client in self.user_clients[user_id].items():
                    if client and client.is_connected():
                        logger.info(
                            f"Smart routing: using {name} instead of {account_name}"
                        )
                        return client

            return None
        except Exception as e:
            logger.error(f"Smart routing failed: {e}")
            return None

    async def _get_user_admin_group(self, user_id: int) -> Optional[int]:
        """Get user's admin group for DM replies"""
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if user:
                return user.get("manager_forum_chat_id")
            return None
        except Exception as e:
            logger.error(f"Failed to get user admin group: {e}")
            return None

    async def get_messaging_statistics(self, user_id: int) -> Dict:
        """Get messaging statistics for user"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                None
            )
            active_accounts = sum(1 for acc in accounts if acc.get("is_active", False))
            return {
                "total_messages_sent": 0,
                "auto_replies_sent": 0,
                "active_accounts": active_accounts,
                "dm_topics_created": 0,
            }
        except Exception as e:
            logger.error(f"Failed to get messaging statistics: {e}")
            return {
                "total_messages_sent": 0,
                "auto_replies_sent": 0,
                "active_accounts": 0,
                "dm_topics_created": 0,
            }

    async def _resolve_target_entity(self, client, target: str):
        """Resolve target to entity"""
        try:
            if target.startswith("@"):
                try:
                    return await client.get_entity(target)
                except BaseException:
                    from telethon import functions
                    result = await client(functions.contacts.ResolveUsernameRequest(username=target[1:]))
                    if result.users:
                        return result.users[0]
                    raise ValueError(f"Username {target} not found")
            elif target.startswith("-") or target.isdigit():
                # For user IDs, use get_input_entity which works with IDs directly
                user_id = int(target)
                try:
                    return await client.get_entity(user_id)
                except ValueError:
                    async for dialog in client.iter_dialogs():
                        if dialog.entity.id == user_id:
                            return dialog.entity
                    from telethon.tl.types import User
                    async for participant in client.iter_participants(client.get_dialogs()):
                        if isinstance(participant, User) and participant.id == user_id:
                            return participant
                    raise ValueError(f"User {user_id} not found")
            else:
                return await client.get_entity(target)
        except Exception as e:
            logger.error(f"Failed to resolve target {target}: {e}")
            return None

    async def _simulate_typing(self, client, target_entity, message: str):
        """Simulate human-like typing"""
        from telethon import functions
        from telethon.tl import types
        await client(functions.messages.SetTypingRequest(peer=target_entity, action=types.SendMessageTypingAction()))
        typing_delay = len(message) * random.uniform(0.03, 0.08)
        typing_delay = min(max(typing_delay, 1.0), 8.0)
        await asyncio.sleep(typing_delay)
