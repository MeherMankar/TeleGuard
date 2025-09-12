"""Enhanced Activity Simulator with Comprehensive Audit Logging

Simulates natural user behavior with complete transparency.
All actions are logged and can be viewed by users.
"""

import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional

from telethon import errors, functions, types
from telethon.tl.types import InputPeerEmpty, MessageMediaPoll

from ..core.comprehensive_audit import AuditEventType, ComprehensiveAudit
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class ActivitySimulator:
    """Activity simulator with comprehensive audit logging"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.user_clients = bot_manager.user_clients
        self.running = False
        self.simulation_tasks: Dict[int, asyncio.Task] = {}
        self.audit = ComprehensiveAudit()
        self._lock = asyncio.Lock()

        # Activity weights (higher = more likely)
        self.activity_weights = {
            "view_random_entity": 35,
            "react_to_random_post": 25,
            "browse_profiles": 20,
            "vote_in_random_poll": 10,
            "join_or_leave_public_channel": 5,
            "send_message": 3,  # New: Send messages occasionally
            "post_comment": 2,  # New: Post comments rarely
        }

    async def start(self):
        """Start activity simulator for all enabled accounts"""
        self.running = True
        await self._load_enabled_accounts()
        logger.info("Activity Simulator started")

    async def stop(self):
        """Stop all simulation tasks"""
        self.running = False
        async with self._lock:
            for task in self.simulation_tasks.values():
                task.cancel()
            self.simulation_tasks.clear()
        logger.info("🎭 Activity Simulator stopped")

    async def enable_simulation(
        self, user_id: int, account_id: int
    ) -> tuple[bool, str]:
        """Enable simulation for specific account"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                return False, "Account not found"

            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)}, {"$set": {"simulation_enabled": True}}
            )

            # Start simulation task
            await self._start_account_simulation(user_id, account_id, account["name"])

            return True, "Human-like activity simulation enabled"
        except Exception as e:
            logger.error(f"Failed to enable simulation: {e}")
            return False, f"Error: {str(e)}"

    async def disable_simulation(
        self, user_id: int, account_id: int
    ) -> tuple[bool, str]:
        """Disable simulation for specific account"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                return False, "Account not found"

            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)}, {"$set": {"simulation_enabled": False}}
            )

            # Stop simulation task
            task_key = f"{user_id}_{account_id}"
            async with self._lock:
                if task_key in self.simulation_tasks:
                    self.simulation_tasks[task_key].cancel()
                    del self.simulation_tasks[task_key]

            return True, "Human-like activity simulation disabled"
        except Exception as e:
            logger.error(f"Failed to disable simulation: {e}")
            return False, f"Error: {str(e)}"

    async def _load_enabled_accounts(self):
        """Load and start simulation for all enabled accounts"""
        try:
            accounts = await mongodb.db.accounts.find(
                {"simulation_enabled": True, "is_active": True}
            ).to_list(length=None)

            for account in accounts:
                await self._start_account_simulation(
                    account["user_id"], account["_id"], account["name"]
                )

        except Exception as e:
            logger.error(f"Failed to load enabled accounts: {e}")

    async def _start_account_simulation(
        self, user_id: int, account_id: int, account_name: str
    ):
        """Start simulation task for specific account"""
        task_key = f"{user_id}_{account_id}"

        async with self._lock:
            if task_key in self.simulation_tasks:
                return

            task = asyncio.create_task(
                self._simulation_loop(user_id, account_id, account_name)
            )
            self.simulation_tasks[task_key] = task
        logger.info(f"🎭 Started simulation for {account_name}")

    async def _simulation_loop(self, user_id: int, account_id: int, account_name: str):
        """Main simulation loop for an account"""
        while self.running:
            try:
                # Random sleep between sessions (2-6 hours for genuine behavior)
                sleep_time = random.uniform(7200, 21600)
                await asyncio.sleep(sleep_time)

                if not self.running:
                    break

                await self._perform_activity_burst(user_id, account_id, account_name)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Simulation error for {account_name}: {e}")
                await asyncio.sleep(300)

    async def _perform_activity_burst(
        self, user_id: int, account_id: int, account_name: str
    ):
        """Perform a burst of 2-5 random activities"""
        try:
            client = self._get_client(user_id, account_name)
            if not client or not client.is_connected():
                return

            num_actions = random.randint(2, 5)

            # Log session start
            await self.audit.log_sim_session(account_id, user_id, "start", num_actions)

            logger.info(
                f"🎭 Starting activity burst for {account_name} ({num_actions} actions)"
            )

            for i in range(num_actions):
                try:
                    # Select random activity based on weights
                    activity = random.choices(
                        list(self.activity_weights.keys()),
                        weights=list(self.activity_weights.values()),
                    )[0]

                    # Execute activity with audit logging
                    await self._execute_activity_with_audit(
                        client, activity, account_id, user_id, account_name
                    )

                    # Random delay between actions (30-180 seconds for natural behavior)
                    if i < num_actions - 1:
                        delay = random.uniform(30, 180)
                        await asyncio.sleep(delay)

                except Exception as e:
                    logger.error(f"Activity execution error for {account_name}: {e}")
                    await asyncio.sleep(30)

            # Log session end
            await self.audit.log_sim_session(account_id, user_id, "end", num_actions)

            logger.info(f"🎭 Completed activity burst for {account_name}")

        except Exception as e:
            logger.error(f"Activity burst error for {account_name}: {e}")

    async def _execute_activity_with_audit(
        self, client, activity: str, account_id: int, user_id: int, account_name: str
    ):
        """Execute activity with comprehensive audit logging"""
        try:
            if activity == "view_random_entity":
                await self._view_random_entity_with_audit(
                    client, account_id, user_id, account_name
                )
            elif activity == "react_to_random_post":
                await self._react_to_random_post_with_audit(
                    client, account_id, user_id, account_name
                )
            elif activity == "browse_profiles":
                await self._browse_profiles_with_audit(
                    client, account_id, user_id, account_name
                )
            elif activity == "vote_in_random_poll":
                await self._vote_in_random_poll_with_audit(
                    client, account_id, user_id, account_name
                )
            elif activity == "join_or_leave_public_channel":
                await self._join_or_leave_channel_with_audit(
                    client, account_id, user_id, account_name
                )
            elif activity == "send_message":
                await self._send_message_with_audit(
                    client, account_id, user_id, account_name
                )
            elif activity == "post_comment":
                await self._post_comment_with_audit(
                    client, account_id, user_id, account_name
                )

        except errors.FloodWaitError as e:
            logger.warning(f"Rate limited for {account_name}, waiting {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Activity {activity} failed for {account_name}: {e}")

    async def _view_random_entity_with_audit(
        self, client, account_id: int, user_id: int, account_name: str
    ):
        """View random entity with audit logging"""
        try:
            dialogs = await client.get_dialogs(limit=50)
            entities = [d for d in dialogs if d.is_channel or d.is_group]
            if not entities:
                return

            entity = random.choice(entities)
            message_count = random.randint(5, 10)
            messages = await client.get_messages(entity, limit=message_count)
            read_time = random.uniform(5, 25)
            await asyncio.sleep(read_time)

            # Log the activity
            await self.audit.log_sim_entity_viewed(
                account_id, user_id, entity.name, message_count, read_time
            )

            logger.debug(f"👀 {account_name} viewed {entity.name}")

        except Exception as e:
            logger.error(f"View entity error for {account_name}: {e}")

    async def _react_to_random_post_with_audit(
        self, client, account_id: int, user_id: int, account_name: str
    ):
        """React to random post with audit logging"""
        try:
            dialogs = await client.get_dialogs(limit=30)
            entities = [d for d in dialogs if d.is_channel or d.is_group]
            if not entities:
                return

            entity = random.choice(entities)
            messages = await client.get_messages(entity, limit=20)
            reactable_messages = [m for m in messages if m.id and not m.out]
            if not reactable_messages:
                return

            message = random.choice(reactable_messages)
            reactions = ["👍", "❤️", "🔥", "🎉", "😊", "👏", "💯"]
            emoji = random.choice(reactions)

            await client(
                functions.messages.SendReactionRequest(
                    peer=entity,
                    msg_id=message.id,
                    reaction=[types.ReactionEmoji(emoticon=emoji)],
                )
            )

            # Log the reaction
            await self.audit.log_sim_reaction(
                account_id, user_id, entity.name, emoji, message.id
            )

            logger.debug(
                f"👍 {account_name} reacted {emoji} to message in {entity.name}"
            )

        except Exception as e:
            logger.error(f"React error for {account_name}: {e}")

    async def _browse_profiles_with_audit(
        self, client, account_id: int, user_id: int, account_name: str
    ):
        """Browse profiles with audit logging"""
        try:
            dialogs = await client.get_dialogs(limit=20)
            entities = [d for d in dialogs if d.is_group]
            if not entities:
                return

            entity = random.choice(entities)
            messages = await client.get_messages(entity, limit=30)
            users = [m.sender for m in messages if m.sender and not m.sender.bot]
            if not users:
                return

            user = random.choice(users)
            full_user = await client(functions.users.GetFullUserRequest(user))
            view_time = random.uniform(3, 8)
            await asyncio.sleep(view_time)

            # Log profile view
            profile_name = user.first_name or "Unknown User"
            await self.audit.log_sim_profile_viewed(
                account_id, user_id, profile_name, view_time
            )

            logger.debug(f"👤 {account_name} viewed profile of {profile_name}")

        except Exception as e:
            logger.error(f"Profile browse error for {account_name}: {e}")

    async def _vote_in_random_poll_with_audit(
        self, client, account_id: int, user_id: int, account_name: str
    ):
        """Vote in poll with audit logging"""
        try:
            dialogs = await client.get_dialogs(limit=30)
            entities = [d for d in dialogs if d.is_channel or d.is_group]
            if not entities:
                return

            for entity in random.sample(entities, min(5, len(entities))):
                messages = await client.get_messages(entity, limit=50)

                for message in messages:
                    if (
                        message.media
                        and isinstance(message.media, MessageMediaPoll)
                        and not message.media.poll.closed
                    ):
                        poll = message.media.poll
                        if poll.answers:
                            answer = random.choice(poll.answers)

                            await client(
                                functions.messages.SendVoteRequest(
                                    peer=entity,
                                    msg_id=message.id,
                                    options=[answer.option],
                                )
                            )

                            # Log poll vote
                            await self.audit.log_sim_poll_voted(
                                account_id,
                                user_id,
                                entity.name,
                                poll.question,
                                answer.text,
                            )

                            logger.debug(
                                f"🗳️ {account_name} voted in poll in {entity.name}"
                            )
                            return

        except Exception as e:
            logger.error(f"Poll vote error for {account_name}: {e}")

    async def _join_or_leave_channel_with_audit(
        self, client, account_id: int, user_id: int, account_name: str
    ):
        """Join or leave channel with audit logging"""
        try:
            # Only 5% chance to execute this action
            if random.random() > 0.05:
                return

            action = random.choice(["join", "leave"])

            if action == "join":
                search_terms = ["news", "tech", "music", "movies", "books"]
                term = random.choice(search_terms)

                results = await client(
                    functions.contacts.SearchRequest(q=term, limit=10)
                )

                channels = [c for c in results.chats if c.broadcast and not c.megagroup]
                if channels:
                    channel = random.choice(channels)
                    await client(functions.channels.JoinChannelRequest(channel))

                    # Log channel join
                    await self.audit.log_sim_join_channel(
                        account_id, user_id, channel.title, channel.id
                    )

                    logger.debug(f"➕ {account_name} joined channel {channel.title}")

            else:  # leave
                dialogs = await client.get_dialogs(limit=100)
                old_channels = [d for d in dialogs if d.is_channel and not d.is_group]

                if old_channels:
                    channel = random.choice(old_channels)
                    await client(functions.channels.LeaveChannelRequest(channel))

                    # Log channel leave
                    await self.audit.log_sim_leave_channel(
                        account_id, user_id, channel.name, channel.id
                    )

                    logger.debug(f"➖ {account_name} left channel {channel.name}")

        except Exception as e:
            logger.error(f"Join/leave error for {account_name}: {e}")

    async def _send_message_with_audit(
        self, client, account_id: int, user_id: int, account_name: str
    ):
        """Send message with audit logging (very rare)"""
        try:
            # Only 1% chance to actually send a message
            if random.random() > 0.01:
                return

            dialogs = await client.get_dialogs(limit=20)
            groups = [d for d in dialogs if d.is_group and not d.is_channel]
            if not groups:
                return

            group = random.choice(groups)

            # Simple, safe messages
            messages = [
                "👍",
                "Thanks!",
                "Great!",
                "Nice",
                "Cool",
                "Awesome",
                "Good point",
                "Interesting",
                "I agree",
                "👏",
            ]
            message_text = random.choice(messages)

            sent_message = await client.send_message(group, message_text)

            # Log message sent
            await self.audit.log_sim_message_sent(
                account_id, user_id, group.name, message_text
            )

            logger.debug(f"💬 {account_name} sent message to {group.name}")

        except Exception as e:
            logger.error(f"Send message error for {account_name}: {e}")

    async def _post_comment_with_audit(
        self, client, account_id: int, user_id: int, account_name: str
    ):
        """Post comment with audit logging (very rare)"""
        try:
            # Only 0.5% chance to post a comment
            if random.random() > 0.005:
                return

            dialogs = await client.get_dialogs(limit=30)
            channels = [d for d in dialogs if d.is_channel and not d.is_group]
            if not channels:
                return

            channel = random.choice(channels)
            messages = await client.get_messages(channel, limit=10)

            # Find a message to comment on
            for message in messages:
                if message.id and not message.out:
                    comments = [
                        "👍",
                        "Great post!",
                        "Thanks for sharing",
                        "Interesting",
                        "Nice!",
                    ]
                    comment_text = random.choice(comments)

                    # Try to comment (this might not work on all channels)
                    try:
                        await client.send_message(
                            channel, comment_text, reply_to=message.id
                        )

                        # Log comment posted
                        await self.audit.log_sim_comment_posted(
                            account_id, user_id, channel.name, comment_text
                        )

                        logger.debug(f"💬 {account_name} commented on {channel.name}")
                        break
                    except Exception as e:
                        logger.warning(f"Could not post comment on {channel.name}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Post comment error for {account_name}: {e}")

    def _get_client(self, user_id: int, account_name: str):
        """Get Telethon client for account"""
        user_clients = self.user_clients.get(user_id, {})
        return user_clients.get(account_name)
