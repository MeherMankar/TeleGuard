"""Automation Engine for scheduled tasks and online maker
Developed by:
- @Meher_Mankar
- @Gutkesh
GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""
import asyncio
import json
import logging
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from .mongo_database import mongodb
from telethon import events

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    from .config import config
    if hasattr(config, 'ai') and hasattr(config.ai, 'gemini_api_key') and config.ai.gemini_api_key:
        genai.configure(api_key=config.ai.gemini_api_key)
        AI_AVAILABLE = True
    else:
        AI_AVAILABLE = False
except ImportError:
    AI_AVAILABLE = False
class AutomationEngine:
    """Handles automated tasks for accounts with AI-powered human-like behavior"""
    def __init__(self, user_clients: Dict, fullclient_manager):
        self.user_clients = user_clients
        self.fullclient_manager = fullclient_manager
        self.running = False
        self.tasks = {}
        self.ai_model = None
        self.group_handlers = {}
        self.last_activity = {}
        
        if AI_AVAILABLE:
            try:
                self.ai_model = genai.GenerativeModel('gemini-pro')
                logger.info("AI-powered automation enabled")
            except Exception as e:
                logger.warning(f"AI initialization failed: {e}")
    async def start(self):
        """Start automation engine"""
        self.running = True
        asyncio.create_task(self._automation_loop())
        asyncio.create_task(self._setup_ai_handlers())
        logger.info("Automation engine started")
    async def stop(self):
        """Stop automation engine"""
        self.running = False
        for task in self.tasks.values():
            task.cancel()
    async def _automation_loop(self):
        """Main automation loop"""
        while self.running:
            try:
                await self._process_scheduled_jobs()
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Automation loop error: {e}")
                await asyncio.sleep(60)
    async def _process_scheduled_jobs(self):
        """Process scheduled automation jobs"""
        try:
            jobs = await mongodb.db.automation_jobs.find({"enabled": True}).to_list(length=None)
            for job in jobs:
                await self._execute_job(job)
            
            # Process AI-powered human-like activities
            await self._process_ai_activities()
        except Exception as e:
            logger.error(f"Process scheduled jobs error: {e}")
    async def _execute_job(self, job):
        """Execute a specific automation job"""
        try:
            config = json.loads(job.get("job_config", "{}"))
            account_id = job.get("account_id")
            if job.get("job_type") == "auto_reply":
                await self._execute_auto_reply(account_id, config)
            elif job.get("job_type") == "scheduled_post":
                await self._execute_scheduled_post(account_id, config)
            elif job.get("job_type") == "auto_join":
                await self._execute_auto_join(account_id, config)
            elif job.get("job_type") == "ai_group_interaction":
                await self._execute_ai_group_interaction(account_id, config)
            elif job.get("job_type") == "human_activity_simulation":
                await self._execute_human_activity(account_id, config)
        except Exception as e:
            logger.error(f"Execute job error: {e}")
    def _calculate_next_run(self, job) -> str:
        """Calculate next run time for job"""
        try:
            config = json.loads(job.job_config)
            interval = config.get("interval", 3600)  # Default 1 hour
            next_time = time.time() + interval
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(next_time))
        except Exception as e:
            logger.error(f"Error calculating next run time: {e}")
            # Default to 1 hour from now
            next_time = time.time() + 3600
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(next_time))
    async def _execute_auto_reply(self, account_id: int, config: Dict):
        """Execute auto-reply job"""
        try:
            message_text = config.get("message")
            if not message_text:
                logger.error(
                    f"No message configured for auto-reply job for account {account_id}"
                )
                return
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id)})
            if not account:
                logger.error(f"Account {account_id} not found for auto-reply job")
                return
            client = await self.fullclient_manager._get_account_client(
                account["user_id"], str(account_id)
            )
            if not client:
                logger.error(f"Client not found for account {account_id}")
                return
            dialogs = await client.get_dialogs()
            for dialog in dialogs:
                if dialog.unread_count > 0 and dialog.is_user:
                    messages = await client.get_messages(
                        dialog, limit=dialog.unread_count
                    )
                    for message in messages:
                        if not message.out:
                            await message.reply(message_text)
        except Exception as e:
            logger.error(
                f"Error executing auto-reply job for account {account_id}: {e}"
            )
    async def _execute_scheduled_post(self, account_id: int, config: Dict):
        """Execute scheduled post job"""
        try:
            channel = config.get("channel")
            message = config.get("message")
            if not channel or not message:
                logger.error(
                    f"No channel or message configured for scheduled-post job for account {account_id}"
                )
                return
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id)})
            if not account:
                logger.error(f"Account {account_id} not found for scheduled-post job")
                return
            client = await self.fullclient_manager._get_account_client(
                account["user_id"], str(account_id)
            )
            if not client:
                logger.error(f"Client not found for account {account_id}")
                return
            await client.send_message(channel, message)
        except Exception as e:
            logger.error(
                f"Error executing scheduled-post job for account {account_id}: {e}"
            )
    async def _execute_auto_join(self, account_id: int, config: Dict):
        """Execute auto-join job"""
        try:
            channel_link = config.get("channel_link")
            if not channel_link:
                logger.error(
                    f"No channel_link configured for auto-join job for account {account_id}"
                )
                return
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id)})
            if not account:
                logger.error(f"Account {account_id} not found for auto-join job")
                return
            client = await self.fullclient_manager._get_account_client(
                account["user_id"], str(account_id)
            )
            if not client:
                logger.error(f"Client not found for account {account_id}")
                return
            from telethon.tl.functions.channels import JoinChannelRequest
            await client(JoinChannelRequest(channel_link))
        except Exception as e:
            logger.error(f"Error executing auto-join job for account {account_id}: {e}")
    
    async def setup_new_client_ai_handler(self, user_id: int, account_name: str, client):
        """Setup AI handler for newly added client"""
        if client and client.is_connected():
            await self._setup_client_ai_handler(user_id, account_name, client)
    
    async def _setup_ai_handlers(self):
        """Setup AI-powered message handlers for human-like interactions"""
        if not self.ai_model:
            return
        
        for user_id, clients in self.user_clients.items():
            for account_name, client in clients.items():
                if client and client.is_connected():
                    await self._setup_client_ai_handler(user_id, account_name, client)
    
    async def _setup_client_ai_handler(self, user_id: int, account_name: str, client):
        """Setup AI handler for a specific client"""
        try:
            me = await client.get_me()
            handler_key = f"{user_id}:{me.id}"
            
            if handler_key in self.group_handlers:
                return
            
            self.group_handlers[handler_key] = True
            
            @client.on(events.NewMessage(incoming=True))
            async def ai_message_handler(event):
                try:
                    if event.is_private or not event.text:
                        return
                    
                    # Check if account should respond based on AI analysis
                    should_respond = await self._ai_should_respond(event, me)
                    if should_respond:
                        response = await self._ai_generate_response(event)
                        if response:
                            # Add human-like delay
                            delay = random.uniform(2, 8)
                            await asyncio.sleep(delay)
                            await event.reply(response)
                            
                            # Update activity tracking
                            self.last_activity[handler_key] = datetime.now()
                            
                except Exception as e:
                    logger.error(f"AI handler error: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to setup AI handler: {e}")
    
    async def _ai_should_respond(self, event, me) -> bool:
        """AI determines if account should respond to message"""
        if not self.ai_model:
            return False
        
        try:
            # Get recent message context
            messages = await event.client.get_messages(event.chat_id, limit=5)
            context = "\n".join([f"{msg.sender_id}: {msg.text or '[media]'}" for msg in messages if msg.text])
            
            # Check if mentioned or replied to
            is_mentioned = me.username and f"@{me.username}" in event.text.lower()
            is_replied = event.reply_to_msg_id and messages and messages[0].sender_id == me.id
            
            # AI analysis prompt
            prompt = f"""Analyze if this Telegram account should respond naturally to this group message:

Account: {me.first_name or 'User'} (@{me.username or 'no_username'})
Message: "{event.text}"
Sender: {event.sender_id}
Mentioned: {is_mentioned}
Replied to me: {is_replied}
Recent context: {context[:200]}

Respond with only 'yes' or 'no' based on:
1. Natural conversation flow
2. If directly mentioned/replied
3. If message asks question or needs response
4. Avoid spam-like behavior
5. Human-like engagement patterns"""
            
            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            return response.text.strip().lower() == 'yes'
            
        except Exception as e:
            logger.error(f"AI response decision error: {e}")
            return False
    
    async def _ai_generate_response(self, event) -> Optional[str]:
        """AI generates human-like response to message"""
        if not self.ai_model:
            return None
        
        try:
            # Get chat context
            messages = await event.client.get_messages(event.chat_id, limit=10)
            context = "\n".join([f"{msg.sender_id}: {msg.text or '[media]'}" for msg in messages[-5:] if msg.text])
            
            prompt = f"""Generate a natural, human-like response to this Telegram group message:

Message: "{event.text}"
Context: {context}

Guidelines:
1. Keep response short and natural (1-2 sentences max)
2. Match the conversation tone
3. Be helpful but not overly eager
4. Use casual language appropriate for groups
5. Avoid repetitive patterns
6. Don't always agree - be authentic
7. Use emojis sparingly and naturally

Response:"""
            
            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            generated_text = response.text.strip()
            
            # Filter out inappropriate responses
            if len(generated_text) > 200 or any(word in generated_text.lower() for word in ['ai', 'artificial', 'bot', 'generated']):
                return None
            
            return generated_text
            
        except Exception as e:
            logger.error(f"AI response generation error: {e}")
            return None
    
    def _calculate_human_break_time(self) -> float:
        """Calculate realistic human break time between activities"""
        # Simulate different types of breaks
        break_type = random.choices(
            ['short', 'medium', 'long', 'very_long'],
            weights=[40, 35, 20, 5]
        )[0]
        
        if break_type == 'short':
            return random.uniform(180, 600)  # 3-10 minutes
        elif break_type == 'medium':
            return random.uniform(600, 1800)  # 10-30 minutes
        elif break_type == 'long':
            return random.uniform(1800, 7200)  # 30 minutes - 2 hours
        else:  # very_long
            return random.uniform(7200, 21600)  # 2-6 hours
    
    async def _simulate_human_ai_response(self, client, group_id, response: str):
        """Simulate extremely realistic AI response behavior"""
        # Read the message that triggered the response
        reading_time = random.uniform(2.0, 5.0)
        await asyncio.sleep(reading_time)
        
        # Think about the response (AI processing time simulation)
        thinking_time = len(response) * 0.15 + random.uniform(3.0, 8.0)
        await asyncio.sleep(thinking_time)
        
        # Start typing
        await client.send_typing(group_id)
        
        # Realistic typing with human-like patterns
        words = response.split()
        typing_speed = random.uniform(35, 65)  # Slightly slower for thoughtful responses
        chars_per_second = (typing_speed * 5) / 60
        
        base_typing_time = len(response) / chars_per_second
        
        # Add pauses for complex responses
        if len(words) > 8:
            base_typing_time += random.uniform(2.0, 5.0)
        
        # Break into natural segments
        segments = max(1, len(words) // 6)
        segment_time = base_typing_time / segments
        
        for i in range(segments):
            await asyncio.sleep(segment_time * random.uniform(0.6, 1.5))
            
            # Natural pauses (thinking, rephrasing)
            if random.random() < 0.4:
                pause_time = random.uniform(1.0, 3.5)
                await asyncio.sleep(pause_time)
            
            # Refresh typing indicator
            if i < segments - 1 and random.random() < 0.5:
                await client.send_typing(group_id)
        
        # Final review pause
        await asyncio.sleep(random.uniform(1.0, 3.0))
    
    async def _process_ai_activities(self):
        """Process AI-powered human-like activities"""
        if not self.ai_model:
            return
        
        try:
            # Get accounts with AI automation enabled
            ai_jobs = await mongodb.db.automation_jobs.find({
                "job_type": "human_activity_simulation",
                "enabled": True
            }).to_list(length=50)
            
            for job in ai_jobs:
                await self._execute_human_activity(job["account_id"], json.loads(job["job_config"]))
                
        except Exception as e:
            logger.error(f"AI activities processing error: {e}")
    
    async def _execute_ai_group_interaction(self, account_id: str, config: Dict):
        """Execute AI-powered group interaction"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id)})
            if not account:
                return
            
            client = await self.fullclient_manager._get_account_client(
                account["user_id"], str(account_id)
            )
            if not client:
                return
            
            # Get target groups from config
            target_groups = config.get("groups", [])
            interaction_type = config.get("type", "reply_mentions")
            
            for group_id in target_groups:
                try:
                    if interaction_type == "reply_mentions":
                        await self._ai_reply_to_mentions(client, group_id)
                    elif interaction_type == "engage_discussions":
                        await self._ai_engage_discussions(client, group_id)
                    elif interaction_type == "react_to_messages":
                        await self._ai_react_to_messages(client, group_id)
                        
                except Exception as e:
                    logger.error(f"Group interaction error for {group_id}: {e}")
                    
        except Exception as e:
            logger.error(f"AI group interaction error: {e}")
    
    async def _execute_human_activity(self, account_id: str, config: Dict):
        """Execute human-like activity simulation"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id)})
            if not account:
                return
            
            client = await self.fullclient_manager._get_account_client(
                account["user_id"], str(account_id)
            )
            if not client:
                return
            
            activities = config.get("activities", ["read_messages", "typing_simulation"])
            
            for activity in activities:
                try:
                    if activity == "read_messages":
                        await self._simulate_reading(client)
                    elif activity == "typing_simulation":
                        await self._simulate_typing(client)
                    elif activity == "online_presence":
                        await self._maintain_online_presence(client)
                    elif activity == "random_interactions":
                        await self._random_interactions(client)
                        
                    # Extremely realistic delays between activities (like real human breaks)
                    break_duration = self._calculate_human_break_time()
                    await asyncio.sleep(break_duration)
                    
                except Exception as e:
                    logger.error(f"Activity simulation error: {e}")
                    
        except Exception as e:
            logger.error(f"Human activity simulation error: {e}")
    
    async def _ai_reply_to_mentions(self, client, group_id):
        """AI replies to mentions in group"""
        try:
            me = await client.get_me()
            if not me.username:
                return
            
            # Get recent messages mentioning the account
            messages = await client.get_messages(group_id, limit=50)
            mention_pattern = f"@{me.username}"
            
            for message in messages:
                if (message.text and mention_pattern in message.text.lower() and 
                    message.sender_id != me.id and 
                    (datetime.now() - message.date).total_seconds() < 3600):  # Last hour
                    
                    # Check if already replied
                    replies = await client.get_messages(group_id, reply_to=message.id, limit=10)
                    if any(reply.sender_id == me.id for reply in replies):
                        continue
                    
                    # Generate AI response
                    response = await self._ai_generate_response(message)
                    if response:
                        # Extremely realistic AI response behavior
                        await self._simulate_human_ai_response(client, group_id, response)
                        await message.reply(response)
                        break  # Only reply to one mention per cycle
                        
        except Exception as e:
            logger.error(f"AI mention reply error: {e}")
    
    async def _simulate_reading(self, client):
        """Simulate reading messages in dialogs"""
        try:
            dialogs = await client.get_dialogs(limit=10)
            for dialog in dialogs[:3]:  # Read from top 3 chats
                if dialog.unread_count > 0:
                    await client.send_read_acknowledge(dialog.entity)
                    await asyncio.sleep(random.uniform(1, 3))
                    
        except Exception as e:
            logger.error(f"Reading simulation error: {e}")
    
    async def _simulate_typing(self, client):
        """Simulate typing in active chats"""
        try:
            dialogs = await client.get_dialogs(limit=5)
            active_dialog = random.choice(dialogs)
            
            # Start typing
            await client.send_typing(active_dialog.entity)
            await asyncio.sleep(random.uniform(2, 5))
            
            # Realistic human behavior: sometimes send, sometimes just stop typing
            if random.random() < 0.25:  # 25% chance to actually send (more realistic)
                casual_messages = ["👍", "ok", "got it", "thanks", "sure", "nice", "cool"]
                
                # Human-like decision pause
                await asyncio.sleep(random.uniform(1.0, 3.5))
                
                # Brief typing before sending
                await client.send_typing(active_dialog.entity)
                await asyncio.sleep(random.uniform(0.8, 2.2))
                
                await client.send_message(active_dialog.entity, random.choice(casual_messages))
                
        except Exception as e:
            logger.error(f"Typing simulation error: {e}")
