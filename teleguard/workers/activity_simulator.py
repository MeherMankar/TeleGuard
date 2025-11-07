"""Activity simulator
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
from ..core.mongo_database import mongodb
logger = logging.getLogger(__name__)
class ActivitySimulator:
    """Activity simulator"""
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.user_clients = bot_manager.user_clients
        self.running = False
        self.simulation_tasks: Dict[int, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        # activity weights with new behaviors
        self.activity_weights = {
            "view_random_entity": 30,
            "react_to_random_post": 20,
            "browse_profiles": 15,
            "scroll_and_read": 12,  # New: Realistic scrolling
            "vote_in_random_poll": 8,
            "typing_simulation": 6,  # New: Show typing indicators
            "join_or_leave_public_channel": 4,
            "send_message": 3,
            "post_comment": 2,
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
    async def _simulation_loop(self, user_id: int, account_id: int, account_name: str):
        """Main simulation loop for an account"""
        while self.running:
            try:
                # Extremely realistic human activity patterns
                sleep_time = self._calculate_realistic_activity_interval()
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
            # More varied activity bursts
            num_actions = random.choices(
                [1, 2, 3, 4, 5, 6, 7],
                weights=[5, 15, 25, 25, 15, 10, 5]
            )[0]
            # Log session start
                        for i in range(num_actions):
                try:
                    # Select random activity based on weights
                    activity = random.choices(
                        list(self.activity_weights.keys()),
                        weights=list(self.activity_weights.values()),
                    )[0]
                    await self._execute_activity(
                        client, activity, account_id, user_id, account_name
                    )
                    # Extremely realistic delays between actions (like real human behavior)
                    if i < num_actions - 1:
                        delay = self._calculate_realistic_action_delay(i, num_actions)
                        await asyncio.sleep(delay)
                except Exception as e:
                    logger.error(f"Activity execution error for {account_name}: {e}")
                    await asyncio.sleep(30)
            # Log session end
                    except Exception as e:
            logger.error(f"Activity burst error for {account_name}: {e}")
    async def _execute_activity(
        self, client, activity: str, account_id: int, user_id: int, account_name: str
    ):
        """Execute activity with comprehensive audit logging"""
        try:
            if activity == "view_random_entity":
                await self._view_random_entity(
                    client, account_id, user_id, account_name
                )
            elif activity == "react_to_random_post":
                await self._react_to_random_post(
                    client, account_id, user_id, account_name
                )
            elif activity == "browse_profiles":
                await self._browse_profiles(
                    client, account_id, user_id, account_name
                )
            elif activity == "vote_in_random_poll":
                await self._vote_in_random_poll(
                    client, account_id, user_id, account_name
                )
            elif activity == "join_or_leave_public_channel":
                await self._join_or_leave_channel(
                    client, account_id, user_id, account_name
                )
            elif activity == "send_message":
                await self._send_message(
                    client, account_id, user_id, account_name
                )
            elif activity == "post_comment":
                await self._post_comment(
                    client, account_id, user_id, account_name
                )
            elif activity == "scroll_and_read":
                await self._scroll_and_read(
                    client, account_id, user_id, account_name
                )
            elif activity == "typing_simulation":
                await self._typing_simulation(
                    client, account_id, user_id, account_name
                )
        except errors.FloodWaitError as e:
            logger.warning(f"Rate limited for {account_name}, waiting {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Activity {activity} failed for {account_name}: {e}")
    async def _view_random_entity(
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
                            account_id, user_id, entity.name, message_count, read_time
            )
        except Exception as e:
            logger.error(f"View entity error for {account_name}: {e}")
    async def _react_to_random_post(
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
                            account_id, user_id, entity.name, emoji, message.id
            )
        except Exception as e:
            logger.error(f"React error for {account_name}: {e}")
    async def _browse_profiles(
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
                            account_id, user_id, profile_name, view_time
            )
        except Exception as e:
            logger.error(f"Profile browse error for {account_name}: {e}")
    async def _vote_in_random_poll(
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
                                                            account_id,
                                user_id,
                                entity.name,
                                poll.question,
                                answer.text,
                            )
                            return
        except Exception as e:
            logger.error(f"Poll vote error for {account_name}: {e}")
    async def _join_or_leave_channel(
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
                                            account_id, user_id, channel.title, channel.id
                    )
            else:  # leave
                dialogs = await client.get_dialogs(limit=100)
                old_channels = [d for d in dialogs if d.is_channel and not d.is_group]
                if old_channels:
                    channel = random.choice(old_channels)
                    await client(functions.channels.LeaveChannelRequest(channel))
                    # Log channel leave
                                            account_id, user_id, channel.name, channel.id
                    )
        except Exception as e:
            logger.error(f"Join/leave error for {account_name}: {e}")
    async def _send_message(
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
                            account_id, user_id, group.name, message_text
            )
        except Exception as e:
            logger.error(f"Send message error for {account_name}: {e}")
    async def _post_comment(
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
                                                    account_id, user_id, channel.name, comment_text
                        )
                        break
                    except Exception as e:
                        logger.warning(f"Could not post comment on {channel.name}: {e}")
                        continue
        except Exception as e:
            logger.error(f"Post comment error for {account_name}: {e}")
    async def _scroll_and_read(
        self, client, account_id: int, user_id: int, account_name: str
    ):
        """Simulate realistic scrolling and reading behavior"""
        try:
            dialogs = await client.get_dialogs(limit=30)
            entities = [d for d in dialogs if d.is_channel or d.is_group]
            if not entities:
                return
            entity = random.choice(entities)
            # Simulate scrolling through messages
            total_messages = random.randint(20, 50)
            messages = await client.get_messages(entity, limit=total_messages)
            # Simulate reading with realistic pauses
            read_count = 0
            for i, message in enumerate(messages):
                if message.text:
                    # Extremely realistic reading time (like actual human reading)
                    read_time = self._calculate_realistic_reading_time(message.text)
                    await asyncio.sleep(read_time)
                    read_count += 1
                    # Realistic scrolling behavior with natural pauses
                    if i % random.randint(4, 8) == 0:
                        pause_type = random.choices(
                            ['quick_pause', 'thinking_pause', 'distraction'],
                            weights=[60, 30, 10]
                        )[0]
                        
                        if pause_type == 'quick_pause':
                            pause_time = random.uniform(1.5, 4.0)
                        elif pause_type == 'thinking_pause':
                            pause_time = random.uniform(4.0, 12.0)
                        else:  # distraction
                            pause_time = random.uniform(15.0, 60.0)
                        
                        await asyncio.sleep(pause_time)
            # Log scrolling activity
                            account_id, user_id, entity.name, read_count, sum([1, 2, 3])  # Approximate total time
            )
        except Exception as e:
            logger.error(f"Scroll and read error for {account_name}: {e}")
    async def _typing_simulation(
        self, client, account_id: int, user_id: int, account_name: str
    ):
        """Simulate typing indicators without sending messages"""
        try:
            dialogs = await client.get_dialogs(limit=20)
            entities = [d for d in dialogs if d.is_group and not d.is_channel]
            if not entities:
                return
            entity = random.choice(entities)
            # Show typing indicator
            await client(
                functions.messages.SetTypingRequest(
                    peer=entity,
                    action=types.SendMessageTypingAction()
                )
            )
            # Extremely realistic typing simulation
            typing_time = self._calculate_realistic_typing_time()
            await asyncio.sleep(typing_time)
            
            # Cancel typing (by sending empty typing action)
            await client(
                functions.messages.SetTypingRequest(
                    peer=entity,
                    action=types.SendMessageCancelAction()
                )
            )
            # Log typing simulation
                            account_id, user_id, f"Typing in {entity.name}", 1, typing_time
            )
        except Exception as e:
            logger.error(f"Typing simulation error for {account_name}: {e}")
    
    def _calculate_realistic_reading_time(self, text: str) -> float:
        """Calculate extremely realistic reading time based on text complexity"""
        if not text:
            return random.uniform(0.5, 1.5)
        
        # Average human reading speed: 200-300 words per minute
        words = len(text.split())
        reading_speed = random.uniform(200, 300)  # WPM
        
        base_time = (words / reading_speed) * 60  # Convert to seconds
        
        # Add comprehension time for complex content
        if any(word in text.lower() for word in ['http', '@', '#', 'telegram.org']):
            base_time *= 1.4  # Links and mentions take longer
        
        # Add natural variation
        reading_time = base_time * random.uniform(0.8, 1.6)
        
        # Realistic bounds
        return max(1.0, min(reading_time, 20.0))
    
    def _calculate_realistic_typing_time(self) -> float:
        """Calculate realistic typing/thinking time for typing simulation"""
        # Simulate different typing scenarios
        typing_scenario = random.choices(
            ['quick_thought', 'composing', 'hesitating', 'distracted'],
            weights=[40, 35, 20, 5]
        )[0]
        
        if typing_scenario == 'quick_thought':
            return random.uniform(2.0, 6.0)
        elif typing_scenario == 'composing':
            return random.uniform(6.0, 15.0)
        elif typing_scenario == 'hesitating':
            return random.uniform(8.0, 25.0)
        else:  # distracted
            return random.uniform(20.0, 60.0)
    async def get_simulation_stats(self, user_id: int) -> Dict[str, Any]:
        """Get simulation statistics for user"""
        try:
            accounts = await mongodb.db.accounts.find({
                "user_id": user_id,
                "simulation_enabled": True
            }).to_list(length=None)
            stats = {
                "total_accounts": len(accounts),
                "active_simulations": 0,
                "accounts": []
            }
            for account in accounts:
                task_key = f"{user_id}_{account['_id']}"
                is_active = task_key in self.simulation_tasks
                if is_active:
                    stats["active_simulations"] += 1
                stats["accounts"].append({
                    "name": account["name"],
                    "active": is_active,
                    "enabled": account.get("simulation_enabled", False)
                })
            return stats
        except Exception as e:
            logger.error(f"Failed to get simulation stats: {e}")
            return {"error": str(e)}
    def _get_client(self, user_id: int, account_name: str):
        """Get Telethon client for account"""
        user_clients = self.user_clients.get(user_id, {})
        return user_clients.get(account_name)
    
    def _calculate_realistic_activity_interval(self) -> float:
        """Calculate extremely realistic intervals between activity sessions"""
        # Simulate different user behavior patterns
        activity_pattern = random.choices(
            ['very_active', 'active', 'moderate', 'casual', 'inactive'],
            weights=[5, 15, 35, 35, 10]
        )[0]
        
        if activity_pattern == 'very_active':
            return random.uniform(1800, 7200)  # 30 minutes - 2 hours
        elif activity_pattern == 'active':
            return random.uniform(3600, 14400)  # 1-4 hours
        elif activity_pattern == 'moderate':
            return random.uniform(7200, 28800)  # 2-8 hours
        elif activity_pattern == 'casual':
            return random.uniform(14400, 86400)  # 4-24 hours
        else:  # inactive
            return random.uniform(43200, 172800)  # 12-48 hours
    
    def _calculate_realistic_action_delay(self, current_action: int, total_actions: int) -> float:
        """Calculate realistic delays between individual actions"""
        # Shorter delays at the beginning (more focused)
        # Longer delays towards the end (getting distracted/tired)
        progress = current_action / total_actions
        
        base_delay = 45 + (progress * 180)  # 45 seconds to 3.75 minutes
        
        # Add random variation
        variation = random.uniform(0.5, 2.0)
        delay = base_delay * variation
        
        # Occasional longer pauses (like real humans getting distracted)
        if random.random() < 0.2:  # 20% chance
            distraction_time = random.uniform(120, 600)  # 2-10 minutes
            delay += distraction_time
        
        return delay
