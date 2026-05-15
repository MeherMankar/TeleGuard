"""Automation Worker for scheduled tasks with AI-powered human behavior"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai

    from ..core.config import config

    if (
        hasattr(config, "ai")
        and hasattr(config.ai, "gemini_api_key")
        and config.ai.gemini_api_key
    ):
        genai.configure(api_key=config.ai.gemini_api_key)
        AI_AVAILABLE = True
    else:
        AI_AVAILABLE = False
except ImportError:
    AI_AVAILABLE = False


class AutomationWorker:
    """Background worker for automation tasks with AI-powered human behavior"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.running = False
        self.tasks = {}
        self.ai_model = None
        self.interaction_history = {}

        if AI_AVAILABLE:
            try:
                self.ai_model = genai.GenerativeModel("gemini-pro")
                logger.info("AI-powered automation worker enabled")
            except Exception as e:
                logger.warning(f"AI initialization failed: {e}")

    async def start(self):
        """Start automation worker"""
        self.running = True
        logger.info("Automation worker started")
        while self.running:
            try:
                await self._process_jobs()
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Automation worker error: {e}")
                await asyncio.sleep(60)

    async def stop(self):
        """Stop automation worker"""
        self.running = False
        for task in self.tasks.values():
            task.cancel()
        logger.info("Automation worker stopped")

    async def _process_jobs(self):
        """Process pending automation jobs"""
        try:
            current_time = datetime.utcnow().isoformat()
            if not isinstance(current_time, str):
                logger.error("Invalid current_time format")
                return
            jobs = await mongodb.db.automation_jobs.find(
                {"enabled": True, "next_run": {"$lte": current_time}}
            ).to_list(
                length=100
            )  # Limit results
            for job in jobs:
                await self._execute_job(job)
        except Exception as e:
            logger.error(f"Failed to process automation jobs: {e}")

    async def _execute_job(self, job: dict):
        """Execute a single automation job"""
        try:
            config = self._parse_job_config(job)
            if not config:
                return
            job_handlers = {
                "auto_reply": self._handle_auto_reply,
                "scheduled_message": self._handle_scheduled_message,
                "online_maker": self._handle_online_maker,
                "ai_smart_reply": self._handle_ai_smart_reply,
                "group_engagement": self._handle_group_engagement,
                "natural_activity": self._handle_natural_activity,
            }
            handler = job_handlers.get(job["job_type"])
            if handler:
                await handler(job["account_id"], config)
            await self._update_job_schedule(job, config)
        except Exception as e:
            logger.error(f"Failed to execute job {job['_id']}: {e}")

    async def _handle_auto_reply(self, account_id: str, config: Dict[str, Any]):
        """Handle auto-reply job with AI enhancement"""
        try:
            client = await self._get_client(account_id)
            if not client:
                return

            # Get unread messages
            dialogs = await client.get_dialogs()
            for dialog in dialogs:
                if dialog.unread_count > 0 and dialog.is_user:
                    messages = await client.get_messages(
                        dialog, limit=dialog.unread_count
                    )
                    for message in messages:
                        if not message.out and message.text:
                            # AI-powered smart reply
                            reply = await self._ai_generate_smart_reply(message, config)
                            if reply:
                                # Human-like delay
                                await asyncio.sleep(random.uniform(3, 10))
                                await message.reply(reply)

        except Exception as e:
            logger.error(f"Auto-reply error: {e}")

    async def _handle_scheduled_message(self, account_id: str, config: Dict[str, Any]):
        """Handle scheduled message job with AI content generation"""
        try:
            client = await self._get_client(account_id)
            if not client:
                return

            target = config.get("target")
            message_template = config.get("message", "")

            if target and message_template:
                # AI-enhance message if enabled
                if config.get("ai_enhance", False) and self.ai_model:
                    enhanced_message = await self._ai_enhance_message(
                        message_template, target
                    )
                    message_to_send = enhanced_message or message_template
                else:
                    message_to_send = message_template

                await client.send_message(target, message_to_send)
                logger.info(f"Scheduled message sent for account {account_id}")

        except Exception as e:
            logger.error(f"Scheduled message error: {e}")

    async def _handle_online_maker(self, account_id: str, config: Dict[str, Any]):
        """Handle online maker job"""
        if hasattr(self.bot_manager, "fullclient_manager"):
            from bson import ObjectId
            from bson.errors import InvalidId

            try:
                if not ObjectId.is_valid(account_id):
                    logger.error(f"Invalid account_id format: {account_id}")
                    return
                account = await mongodb.db.accounts.find_one(
                    {"_id": ObjectId(account_id)}
                )
            except InvalidId as e:
                logger.error(f"Invalid ObjectId: {account_id} - {e}")
                return
            if account:
                await self.bot_manager.fullclient_manager.update_online_status(
                    account["user_id"], account_id
                )

                # Add natural activity simulation
                if random.random() < 0.3:  # 30% chance for additional activity
                    await self._simulate_natural_online_activity(
                        account["user_id"], account_id
                    )

    async def _get_client(self, account_id: str):
        """Get client for account"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id)})
            if account and hasattr(self.bot_manager, "fullclient_manager"):
                return await self.bot_manager.fullclient_manager._get_account_client(
                    account["user_id"], account_id
                )
        except Exception as e:
            logger.error(f"Failed to get client: {e}")
        return None

    async def _ai_generate_smart_reply(self, message, config: Dict) -> Optional[str]:
        """Generate AI-powered smart reply"""
        if not self.ai_model:
            return config.get("default_reply", "Thanks for your message!")

        try:
            sender = await message.get_sender()
            sender_name = sender.first_name or "User"

            prompt = f"""Generate a natural, helpful reply to this message:

From: {sender_name}
Message: "{message.text}"

Guidelines:
1. Be friendly and helpful
2. Keep it concise (1-2 sentences)
3. Match the tone of the original message
4. Provide value when possible
5. Sound human and natural

Reply:"""

            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            reply_text = response.text.strip()

            # Validate response
            if len(reply_text) > 300 or "ai" in reply_text.lower():
                return config.get("default_reply", "Thanks for your message!")

            return reply_text

        except Exception as e:
            logger.error(f"AI reply generation error: {e}")
            return config.get("default_reply", "Thanks for your message!")

    async def _ai_enhance_message(self, template: str, target: str) -> Optional[str]:
        """AI-enhance scheduled message"""
        if not self.ai_model:
            return None

        try:
            prompt = f"""Enhance this message template to be more natural and engaging:

Original: "{template}"
Target: {target}

Guidelines:
1. Keep the core message intact
2. Make it sound more natural and human
3. Add appropriate emojis if suitable
4. Maintain professional tone if business context
5. Keep length similar to original

Enhanced message:"""

            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            enhanced = response.text.strip()

            # Validate enhancement
            if len(enhanced) > len(template) * 2:
                return None

            return enhanced

        except Exception as e:
            logger.error(f"Message enhancement error: {e}")
            return None

    async def _handle_ai_smart_reply(self, account_id: str, config: Dict[str, Any]):
        """Handle AI-powered smart reply system"""
        try:
            client = await self._get_client(account_id)
            if not client or not self.ai_model:
                return

            # Get target groups/chats
            targets = config.get("targets", [])
            reply_probability = config.get("reply_probability", 0.3)

            for target in targets:
                try:
                    # Get recent messages
                    messages = await client.get_messages(target, limit=20)
                    me = await client.get_me()

                    for message in messages:
                        if (
                            message.sender_id != me.id
                            and message.text
                            and random.random() < reply_probability
                        ):

                            # Check if should reply based on AI analysis
                            should_reply = await self._ai_should_reply(message, me)
                            if should_reply:
                                reply = await self._ai_generate_contextual_reply(
                                    message, target
                                )
                                if reply:
                                    await asyncio.sleep(random.uniform(5, 15))
                                    await message.reply(reply)
                                    break  # Only one reply per target per cycle

                except Exception as e:
                    logger.error(f"Smart reply error for target {target}: {e}")

        except Exception as e:
            logger.error(f"AI smart reply error: {e}")

    async def _handle_group_engagement(self, account_id: str, config: Dict[str, Any]):
        """Handle intelligent group engagement"""
        try:
            client = await self._get_client(account_id)
            if not client or not self.ai_model:
                return
            groups = config.get("groups", [])
            engagement_types = config.get("types", ["react", "reply", "mention_response"])
            for group_id in groups:
                try:
                    await self._process_group_engagement(client, group_id, engagement_types)
                except Exception as e:
                    logger.error(f"Group engagement error for {group_id}: {e}")
        except Exception as e:
            logger.error(f"Group engagement error: {e}")

    async def _handle_natural_activity(self, account_id: str, config: Dict[str, Any]):
        """Handle natural human-like activity simulation"""
        try:
            client = await self._get_client(account_id)
            if not client:
                return

            activities = config.get("activities", ["read", "typing", "online"])

            for activity in activities:
                try:
                    if activity == "read":
                        await self._simulate_reading_activity(client)
                    elif activity == "typing":
                        await self._simulate_typing_activity(client)
                    elif activity == "online":
                        await self._maintain_natural_online_presence(client)

                    # Natural delay between activities
                    await asyncio.sleep(random.uniform(30, 180))

                except Exception as e:
                    logger.error(f"Natural activity error: {e}")

        except Exception as e:
            logger.error(f"Natural activity error: {e}")

    async def _ai_should_reply(self, message, me) -> bool:
        """AI determines if should reply to message"""
        if not self.ai_model:
            return random.random() < 0.2

        try:
            prompt = f"""Should this Telegram account reply to this message naturally?

Message: "{message.text}"
Account: {me.first_name or 'User'}

Consider:
1. Is it a question or needs response?
2. Is it directed at the account?
3. Would a human naturally respond?
4. Avoid spam-like behavior

Respond with only 'yes' or 'no':"""

            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            return response.text.strip().lower() == "yes"

        except Exception as e:
            logger.error(f"AI reply decision error: {e}")
            return False

    async def _ai_generate_contextual_reply(self, message, chat_id) -> Optional[str]:
        """Generate contextual AI reply"""
        if not self.ai_model:
            return None

        try:
            # Get chat context
            client = message.client
            recent_messages = await client.get_messages(chat_id, limit=5)
            context = "\n".join(
                [
                    f"{msg.sender_id}: {msg.text or '[media]'}"
                    for msg in recent_messages
                    if msg.text
                ]
            )

            prompt = f"""Generate a natural reply to this message in context:

Message: "{message.text}"
Context: {context[-300:]}

Guidelines:
1. Be natural and conversational
2. Keep it short (1-2 sentences)
3. Add value to the conversation
4. Match the group's tone
5. Use emojis sparingly

Reply:"""

            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            reply_text = response.text.strip()

            # Validate reply
            if len(reply_text) > 200 or any(
                word in reply_text.lower() for word in ["ai", "artificial", "bot"]
            ):
                return None

            return reply_text

        except Exception as e:
            logger.error(f"Contextual reply error: {e}")
            return None

    async def _ai_generate_mention_reply(self, message) -> Optional[str]:
        """Generate reply to mention"""
        if not self.ai_model:
            return "Thanks for mentioning me!"

        try:
            prompt = f"""Generate a natural reply to this mention:

Message: "{message.text}"

Guidelines:
1. Acknowledge the mention naturally
2. Be helpful if they asked something
3. Keep it friendly and brief
4. Sound human, not robotic

Reply:"""

            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            return response.text.strip()

        except Exception as e:
            logger.error(f"Mention reply error: {e}")
            return "Thanks for mentioning me!"

    async def _simulate_reading_activity(self, client):
        """Simulate natural reading patterns"""
        try:
            dialogs = await client.get_dialogs(limit=8)
            for dialog in random.sample(dialogs, min(3, len(dialogs))):
                if dialog.unread_count > 0:
                    await client.send_read_acknowledge(dialog.entity)
                    await asyncio.sleep(random.uniform(1, 4))

        except Exception as e:
            logger.error(f"Reading simulation error: {e}")

    async def _simulate_typing_activity(self, client):
        """Simulate natural typing behavior"""
        try:
            dialogs = await client.get_dialogs(limit=5)
            if dialogs:
                dialog = random.choice(dialogs)

                # Start typing
                from telethon import functions
                from telethon.tl import types

                await client(
                    functions.messages.SetTypingRequest(
                        peer=dialog.entity, action=types.SendMessageTypingAction()
                    )
                )
                typing_duration = random.uniform(3, 8)
                await asyncio.sleep(typing_duration)

                # Sometimes send a message, sometimes just stop
                if random.random() < 0.4:  # 40% chance to send
                    casual_responses = [
                        "👍",
                        "ok",
                        "got it",
                        "thanks",
                        "sure",
                        "alright",
                        "sounds good",
                        "will do",
                        "understood",
                        "✅",
                    ]
                    await client.send_message(
                        dialog.entity, random.choice(casual_responses)
                    )

        except Exception as e:
            logger.error(f"Typing simulation error: {e}")

    async def _maintain_natural_online_presence(self, client):
        """Maintain natural online presence patterns"""
        try:
            # Simulate natural online/offline patterns
            online_duration = random.uniform(300, 1800)  # 5-30 minutes
            await asyncio.sleep(online_duration)

            # Update last seen to maintain presence
            await client.get_me()

        except Exception as e:
            logger.error(f"Online presence error: {e}")

    async def _simulate_natural_online_activity(self, user_id: int, account_id: str):
        """Simulate natural online activity"""
        try:
            client = await self._get_client(account_id)
            if client:
                await client.get_me()
                if random.random() < 0.5:
                    dialogs = await client.get_dialogs(limit=3)
                    for dialog in dialogs:
                        if dialog.unread_count > 0:
                            await client.send_read_acknowledge(dialog.entity)
                            await asyncio.sleep(random.uniform(1, 3))
        except Exception as e:
            logger.error(f"Natural activity simulation error: {e}")

    def _parse_job_config(self, job: dict):
        """Parse and validate job config"""
        import json
        try:
            config = json.loads(job["job_config"])
            if not isinstance(config, dict):
                logger.error(f"Invalid job config format for job {job['_id']}")
                return None
            return config
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in job config for job {job['_id']}: {e}")
            return None

    async def _update_job_schedule(self, job: dict, config: dict):
        """Update job schedule after execution"""
        update_data = {"last_run": datetime.utcnow().isoformat()}
        if config.get("interval"):
            next_run = datetime.utcnow() + timedelta(seconds=config["interval"])
            update_data["next_run"] = next_run.isoformat()
        else:
            update_data["enabled"] = False
        await mongodb.db.automation_jobs.update_one({"_id": job["_id"]}, {"$set": update_data})

    async def _process_group_engagement(self, client, group_id, engagement_types):
        """Process engagement for a single group"""
        messages = await client.get_messages(group_id, limit=30)
        me = await client.get_me()
        for message in messages:
            if message.sender_id == me.id:
                continue
            if await self._handle_mention_response(message, me, engagement_types):
                break
            if await self._handle_random_engagement(message, group_id, engagement_types):
                break

    async def _handle_mention_response(self, message, me, engagement_types) -> bool:
        """Handle mention responses"""
        if "mention_response" in engagement_types and me.username and f"@{me.username}" in (message.text or "").lower():
            reply = await self._ai_generate_mention_reply(message)
            if reply:
                await asyncio.sleep(random.uniform(3, 8))
                await message.reply(reply)
                return True
        return False

    async def _handle_random_engagement(self, message, group_id, engagement_types) -> bool:
        """Handle random engagement"""
        if random.random() < 0.1:
            if "react" in engagement_types and random.random() < 0.5:
                reactions = ["👍", "❤️", "😄", "🔥", "👏"]
                await message.react(random.choice(reactions))
                return False
            elif "reply" in engagement_types:
                reply = await self._ai_generate_contextual_reply(message, group_id)
                if reply:
                    await asyncio.sleep(random.uniform(5, 12))
                    await message.reply(reply)
                    return True
        return False
