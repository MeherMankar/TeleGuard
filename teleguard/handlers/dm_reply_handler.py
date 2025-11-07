"""DM Reply Handler - Forward DMs to admin group and handle replies with AI enhancement"""
import logging
import random
import asyncio
from datetime import datetime
import json
from telethon import events, Button
from ..core.mongo_database import mongodb
from ..utils.logger import BotLogger

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    from ..core.config import config
    if hasattr(config, 'ai') and hasattr(config.ai, 'gemini_api_key') and config.ai.gemini_api_key:
        genai.configure(api_key=config.ai.gemini_api_key)
        AI_AVAILABLE = True
    else:
        AI_AVAILABLE = False
except ImportError:
    AI_AVAILABLE = False

class DMReplyHandler:
    """Handles DM forwarding to admin group and reply management with AI enhancement"""
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        self.handled_clients = set()
        self.processed_messages = set()  # Track processed messages to prevent duplicates
        self.ai_model = None
        self.auto_reply_enabled = {}
        
        if AI_AVAILABLE:
            try:
                self.ai_model = genai.GenerativeModel('gemini-pro')
                logger.info("AI-powered DM handling enabled")
            except Exception as e:
                logger.warning(f"AI initialization failed: {e}")
        
    async def setup_dm_handlers(self):
        """Set up DM handlers for all user clients"""
        for user_id, clients in self.user_clients.items():
            for account_name, client in clients.items():
                if client and client.is_connected():
                    await self._setup_client_dm_handler(user_id, account_name, client)
        self._setup_bot_handlers()

    async def get_admin_group(self, user_id: int) -> int:
        """Get admin group ID for user"""
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            return user.get("dm_reply_group_id") if user else None
        except Exception as e:
            logger.error(f"Failed to get admin group: {e}")
            return None

    async def _setup_client_dm_handler(self, user_id: int, account_name: str, client):
        """Set up DM handler for a specific client"""
        try:
            if not client or not client.is_connected():
                logger.warning(f"Client {account_name} is not connected, skipping DM handler setup")
                return
                
            me = await client.get_me()
            if not me or not hasattr(me, 'id') or me.id is None:
                logger.error(f"Failed to get valid user info for {account_name}")
                return
                
            client_key = f"{user_id}:{me.id}"
            if client_key in self.handled_clients:
                logger.info(f"DM handler already exists for {account_name}, removing old handler")
                self.handled_clients.discard(client_key)
            
            self.handled_clients.add(client_key)
            logger.info(f"Setting up DM handler for {account_name} (ID: {me.id})")
            
            @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
            async def dm_handler(event):
                try:
                    # Create unique message ID to prevent duplicates
                    message_key = f"{event.chat_id}:{event.id}"
                    if message_key in self.processed_messages:
                        return
                    self.processed_messages.add(message_key)
                    
                    if event.out:
                        return
                        
                    sender = await event.get_sender()
                    sender_name = sender.first_name or 'Unknown'
                    
                    # Get proper account identifier
                    account_identifier = me.username if me.username else f"ID: {me.id}"
                    account_display_name = account_name if account_name != f"ID: {me.id}" else me.first_name or f"ID: {me.id}"
                    
                    # Check for AI auto-reply before forwarding
                    await self._handle_ai_auto_reply(event, me, user_id)
                    
                    admin_group_id = await self.get_admin_group(user_id)
                    if admin_group_id:
                        # Create unique topic for each sender-account pair
                        topic_title = f"{sender_name} → {account_display_name}"
                        topic_id = await self._get_or_create_topic(admin_group_id, topic_title, sender.id, me.id)
                        
                        try:
                            if topic_id:
                                if event.media:
                                    await self.bot.send_file(admin_group_id, event.media, caption=event.text, reply_to=topic_id)
                                else:
                                    await self.bot.send_message(admin_group_id, event.text or '[Empty]', reply_to=topic_id)
                            else:
                                if event.media:
                                    await self.bot.send_file(admin_group_id, event.media, caption=event.text)
                                else:
                                    await self.bot.send_message(admin_group_id, event.text or '[Empty]')
                        except ValueError as ve:
                            if "Could not find the input entity" in str(ve):
                                logger.warning(f"Cannot access admin group {admin_group_id}, removing from user settings")
                                await mongodb.db.users.update_one(
                                    {"telegram_id": user_id},
                                    {"$unset": {"dm_reply_group_id": ""}}
                                )
                            else:
                                raise ve
                        except Exception as send_error:
                            error_msg = str(send_error)
                            # Check if topic was deleted
                            if "topic was deleted" in error_msg.lower() or "TOPIC_DELETED" in error_msg:
                                logger.info(f"Topic {topic_id} was deleted, recreating...")
                                # Remove old mapping
                                await mongodb.db.dm_topics.delete_one({"topic_id": topic_id})
                                # Create new topic
                                new_topic_id = await self._get_or_create_topic(admin_group_id, topic_title, sender.id, me.id)
                                if new_topic_id:
                                    # Retry sending
                                    if event.media:
                                        await self.bot.send_file(admin_group_id, event.media, caption=event.text, reply_to=new_topic_id)
                                    else:
                                        await self.bot.send_message(admin_group_id, event.text or '[Empty]', reply_to=new_topic_id)
                                    logger.info(f"✅ Recreated topic and sent message")
                            else:
                                logger.error(f"Failed to send DM to admin group: {send_error}")
                            
                except Exception as e:
                    logger.error(f"DM handler error: {e}", exc_info=True)
                    try:
                        await BotLogger.log_error("DM Handler Error", str(e)[:500], user_id, f"Account: {account_name}")
                    except:
                        pass
                    
        except Exception as e:
            logger.error(f"Failed to set up DM handler for {account_name}: {e}")
            try:
                await BotLogger.log_error("DM Setup Error", str(e)[:500], user_id, f"Account: {account_name}")
            except:
                pass
            
        # Setup AI automation if enabled
        if self.ai_model:
            try:
                await self.setup_ai_automation_job(user_id, str(me.id), {
                    'targets': ['private_chats'],
                    'reply_probability': 0.3,
                    'enhancement_enabled': True
                })
            except Exception as e:
                logger.error(f"Failed to setup AI automation: {e}")
    
    async def enable_ai_features(self, user_id: int, features: dict):
        """Enable AI features for user"""
        try:
            await mongodb.db.users.update_one(
                {"telegram_id": user_id},
                {"$set": {
                    "ai_auto_reply_enabled": features.get('auto_reply', False),
                    "ai_enhancement_enabled": features.get('enhancement', False),
                    "ai_analysis_enabled": features.get('analysis', False)
                }}
            )
            logger.info(f"AI features updated for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to update AI features: {e}")

    def _setup_bot_handlers(self):
        """Set up bot handlers for topic replies"""
        @self.bot.on(events.NewMessage())
        async def handle_topic_reply(event):
            try:
                # Only process group messages
                if not event.is_group:
                    return
                
                # Check if this is from a user with DM reply enabled
                user = await mongodb.db.users.find_one({"dm_reply_group_id": event.chat_id})
                if not user or event.sender_id != user["telegram_id"]:
                    return
                
                # Skip if no text or media
                if not event.text and not event.media:
                    return
                
                # Get topic ID - check multiple attributes
                topic_id = None
                reply_to = getattr(event.message, 'reply_to', None)
                
                if reply_to:
                    # Forum topics use reply_to_top_id
                    topic_id = getattr(reply_to, 'reply_to_top_id', None)
                    if not topic_id:
                        topic_id = getattr(reply_to, 'reply_to_msg_id', None)
                
                # If no reply_to, check if message is directly in a topic
                if not topic_id and hasattr(event.message, 'reply_to_msg_id'):
                    topic_id = event.message.reply_to_msg_id
                
                logger.info(f"Topic reply detected: topic_id={topic_id}, chat={event.chat_id}, text={event.text[:50]}")
                
                if not topic_id:
                    logger.debug("No topic_id found, skipping")
                    return
                
                # Find topic mapping
                topic_mapping = await mongodb.db.dm_topics.find_one({
                    "group_id": event.chat_id,
                    "topic_id": topic_id
                })
                
                if not topic_mapping:
                    logger.warning(f"No mapping found for topic {topic_id} in group {event.chat_id}")
                    # List all mappings for debugging
                    all_mappings = await mongodb.db.dm_topics.find({"group_id": event.chat_id}).to_list(None)
                    logger.info(f"Available mappings: {[(m['topic_id'], m.get('topic_title')) for m in all_mappings]}")
                    return
                
                sender_id = topic_mapping["sender_id"]
                account_id = topic_mapping["account_id"]
                
                managed_client = await self._get_client_by_account_id(account_id)
                if not managed_client:
                    # Account not loaded - try to load it now
                    logger.info(f"Account {account_id} not loaded, attempting to load...")
                    await event.reply("⚠️ Account not loaded. Loading now...")
                    
                    # Find account in database
                    accounts = await mongodb.db.accounts.find({"is_active": True}).to_list(None)
                    target_account = None
                    
                    for acc in accounts:
                        # Match by account's telegram_id stored in DB or by checking session
                        if acc.get('session_string'):
                            # We need to check if this account matches the account_id
                            # The account_id in topic mapping is the Telegram user ID of the account
                            # We can try to load and check
                            try:
                                from telethon import TelegramClient
                                from telethon.sessions import StringSession
                                from ..core.config import config
                                
                                temp_client = TelegramClient(
                                    StringSession(acc['session_string']),
                                    config.telegram.api_id,
                                    config.telegram.api_hash
                                )
                                await temp_client.connect()
                                me = await temp_client.get_me()
                                await temp_client.disconnect()
                                
                                if me.id == account_id:
                                    target_account = acc
                                    break
                            except:
                                continue
                    
                    if target_account:
                        try:
                            # Load the account
                            await self.bot_manager.start_user_client(
                                target_account['user_id'],
                                target_account['name'],
                                target_account['session_string']
                            )
                            
                            # Setup DM handler for newly loaded account
                            managed_client = await self._get_client_by_account_id(account_id)
                            if managed_client:
                                await self.setup_new_client_handler(
                                    target_account['user_id'],
                                    target_account['name'],
                                    managed_client
                                )
                                await event.reply("✅ Account loaded successfully!")
                            else:
                                await event.reply("❌ Failed to load account. Please try again.")
                                return
                        except Exception as load_error:
                            logger.error(f"Failed to load account: {load_error}")
                            await event.reply(f"❌ Failed to load account: {str(load_error)[:100]}")
                            return
                    else:
                        await event.reply("❌ Account not found. Please re-add the account.")
                        return
                
                logger.info(f"Sending reply from account {account_id} to user {sender_id}")
                
                # Resolve entity first to ensure we can send to this user
                try:
                    target_entity = await managed_client.get_entity(sender_id)
                except Exception as entity_error:
                    error_msg = f"❌ Cannot send message - user not found. They may have blocked the account or deleted their profile."
                    await event.reply(error_msg)
                    logger.error(f"Entity resolution failed for user {sender_id}: {entity_error}")
                    return
                
                # Simulate human typing if text
                if event.text:
                    await self._simulate_human_reply_behavior(managed_client, sender_id, event.text)
                
                # Send the message with media support
                if event.media:
                    await managed_client.send_file(sender_id, event.media, caption=event.text)
                    logger.info(f"✅ Media sent")
                else:
                    reply_text = event.text
                    # AI-enhance reply if enabled
                    if self.ai_model and await self._is_ai_enhancement_enabled(user["telegram_id"]):
                        try:
                            enhanced_reply = await self._ai_enhance_reply(reply_text, sender_id, managed_client)
                            if enhanced_reply:
                                reply_text = enhanced_reply
                        except Exception as ai_error:
                            logger.debug(f"AI enhancement failed: {ai_error}")
                    
                    await managed_client.send_message(sender_id, reply_text)
                    logger.info(f"✅ Reply sent: {reply_text[:50]}")
                
            except Exception as e:
                logger.error(f"Failed to handle topic reply: {e}")
                try:
                    await BotLogger.log_error("Topic Reply Error", str(e)[:500], event.sender_id, "Topic reply handler")
                except:
                    pass

    async def _get_client_by_account_id(self, account_id: int):
        """Get managed client by account Telegram ID"""
        for user_id, clients in self.user_clients.items():
            for account_name, client in clients.items():
                if client and client.is_connected():
                    try:
                        me = await client.get_me()
                        if me.id == account_id:
                            return client
                    except Exception as e:
                        continue
        return None

    async def _get_or_create_topic(self, group_id: int, topic_title: str, sender_id: int, account_id: int):
        """Get existing topic or create new one"""
        try:
            topic_key = f"{sender_id}_{account_id}"
            
            existing_topic = await mongodb.db.dm_topics.find_one({
                "group_id": group_id,
                "topic_key": topic_key
            })
            
            if existing_topic:
                # Update topic title if names changed
                if existing_topic.get('topic_title') != topic_title:
                    try:
                        from telethon.tl.functions.channels import EditForumTopicRequest
                        await self.bot(EditForumTopicRequest(
                            channel=group_id,
                            topic_id=existing_topic['topic_id'],
                            title=topic_title
                        ))
                        await mongodb.db.dm_topics.update_one(
                            {"_id": existing_topic["_id"]},
                            {"$set": {"topic_title": topic_title}}
                        )
                    except Exception:
                        pass
                return existing_topic["topic_id"]
            
            logger.info(f"Creating new topic: '{topic_title}' in group {group_id}")
            
            from telethon.tl.functions.channels import CreateForumTopicRequest
            result = await self.bot(CreateForumTopicRequest(
                channel=group_id,
                title=topic_title,
                icon_color=0x6FB9F0,
                random_id=hash(topic_key) % (2**63)
            ))
            
            logger.debug(f"Topic creation result: {result}")
            
            topic_id = None
            if hasattr(result, 'updates') and result.updates:
                for update in result.updates:
                    if hasattr(update, 'message'):
                        if hasattr(update.message, 'id'):
                            topic_id = update.message.id
                            logger.info(f"Extracted topic_id from message.id: {topic_id}")
                            break
                        elif hasattr(update.message, 'reply_to') and hasattr(update.message.reply_to, 'reply_to_top_id'):
                            topic_id = update.message.reply_to.reply_to_top_id
                            logger.info(f"Extracted topic_id from reply_to_top_id: {topic_id}")
                            break
            
            if not topic_id and hasattr(result, 'updates'):
                for update in result.updates:
                    if hasattr(update, 'id'):
                        topic_id = update.id
                        logger.info(f"Extracted topic_id from update.id: {topic_id}")
                        break
            
            if not topic_id:
                logger.error(f"Failed to extract topic_id from result: {result}")
                return None
            
            # Save to database
            await mongodb.db.dm_topics.insert_one({
                "group_id": group_id,
                "topic_key": topic_key,
                "topic_id": topic_id,
                "topic_title": topic_title,
                "sender_id": sender_id,
                "account_id": account_id,
                "created_at": datetime.utcnow()
            })
            
            logger.info(f"✅ Created and saved topic: {topic_id} - '{topic_title}'")
            return topic_id
            
        except Exception as e:
            logger.error(f"Failed to create/get topic: {e}", exc_info=True)
            try:
                await BotLogger.log_error("Topic Creation Error", str(e)[:500], context=f"Group: {group_id}, Title: {topic_title}")
            except:
                pass
        return None
    
    async def setup_ai_automation_job(self, user_id: int, account_id: str, config: dict):
        """Setup AI automation job for account"""
        try:
            job_data = {
                "user_id": user_id,
                "account_id": account_id,
                "job_type": "ai_smart_reply",
                "job_config": json.dumps(config),
                "enabled": True,
                "created_at": datetime.utcnow(),
                "next_run": datetime.utcnow()
            }
            
            await mongodb.db.automation_jobs.insert_one(job_data)
            logger.info(f"AI automation job created for account {account_id}")
            
        except Exception as e:
            logger.error(f"Failed to create AI automation job: {e}")

    async def setup_new_client_handler(self, user_id: int, account_name: str, client):
        """Set up DM handler for a newly added client"""
        if client and client.is_connected():
            await self._setup_client_dm_handler(user_id, account_name, client)
            logger.info(f"✅ DM handler registered for new account: {account_name}")
    
    async def refresh_all_handlers(self):
        """Refresh all DM handlers - automatically called on startup and when adding accounts"""
        try:
            self.handled_clients.clear()
            await self.setup_dm_handlers()
            handler_count = len(self.handled_clients)
            logger.info(f"✅ Refreshed DM handlers: {handler_count} accounts registered")
        except Exception as e:
            logger.error(f"Failed to refresh DM handlers: {e}")
    
    async def _handle_ai_auto_reply(self, event, me, user_id: int):
        """Handle AI-powered auto-reply to DMs"""
        try:
            # Check if auto-reply is enabled for this user
            if not await self._is_auto_reply_enabled(user_id):
                return
            
            if not self.ai_model or not event.text:
                return
            
            # Generate AI response
            response = await self._ai_generate_dm_reply(event, me)
            if response:
                # Extremely realistic auto-reply behavior
                await self._simulate_human_auto_reply_behavior(event.client, event.chat_id, response)
                await event.reply(response)
                
                # Log auto-reply
                logger.info(f"AI auto-reply sent for account {me.id}")
                
        except Exception as e:
            logger.error(f"AI auto-reply error: {e}")
    
    async def _ai_analyze_message(self, message_text: str) -> dict:
        """AI analyzes incoming message for priority and context"""
        if not self.ai_model or not message_text:
            return {'priority': 'normal', 'summary': ''}
        
        try:
            prompt = f"""Analyze this Telegram DM for priority and context:

Message: "{message_text}"

Provide analysis in this format:
Priority: [urgent/high/normal/low]
Summary: [brief 1-line summary]
Category: [question/complaint/spam/business/personal/other]

Analysis:"""
            
            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            analysis_text = response.text.strip()
            
            # Parse response
            analysis = {'priority': 'normal', 'summary': '', 'category': 'other'}
            for line in analysis_text.split('\n'):
                if line.startswith('Priority:'):
                    analysis['priority'] = line.split(':', 1)[1].strip().lower()
                elif line.startswith('Summary:'):
                    analysis['summary'] = f"📋 {line.split(':', 1)[1].strip()}\n"
                elif line.startswith('Category:'):
                    analysis['category'] = line.split(':', 1)[1].strip().lower()
            
            return analysis
            
        except Exception as e:
            logger.error(f"Message analysis error: {e}")
            return {'priority': 'normal', 'summary': ''}
    
    def _get_priority_indicator(self, analysis: dict) -> str:
        """Get priority indicator emoji based on analysis"""
        priority = analysis.get('priority', 'normal')
        if priority == 'urgent':
            return '🚨'
        elif priority == 'high':
            return '⚡'
        elif priority == 'low':
            return '📝'
        else:
            return '📨'
    
    async def _ai_generate_dm_reply(self, event, me) -> str:
        """Generate AI-powered DM reply"""
        if not self.ai_model:
            return None
        
        try:
            sender = await event.get_sender()
            sender_name = sender.first_name or 'User'
            
            prompt = f"""Generate a natural, helpful auto-reply to this DM:

From: {sender_name}
To: {me.first_name or 'User'}
Message: "{event.text}"

Guidelines:
1. Be friendly and professional
2. Acknowledge their message
3. Keep it concise (1-2 sentences)
4. Sound natural, not robotic
5. Offer help if appropriate

Auto-reply:"""
            
            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            reply_text = response.text.strip()
            
            # Validate response
            if len(reply_text) > 300 or any(word in reply_text.lower() for word in ['ai', 'artificial', 'bot']):
                return None
            
            return reply_text
            
        except Exception as e:
            logger.error(f"AI DM reply generation error: {e}")
            return None
    
    async def _ai_enhance_reply(self, reply_text: str, sender_id: int, client) -> str:
        """AI-enhance manual reply for better communication"""
        if not self.ai_model:
            return None
        
        try:
            # Get conversation context
            messages = await client.get_messages(sender_id, limit=5)
            context = "\n".join([f"{msg.sender_id}: {msg.text or '[media]'}" for msg in messages if msg.text])
            
            prompt = f"""Enhance this reply to be more natural and effective:

Original reply: "{reply_text}"
Conversation context: {context[-200:]}

Guidelines:
1. Keep the core message intact
2. Make it sound more natural
3. Add appropriate tone
4. Maintain professionalism
5. Don't change the meaning

Enhanced reply:"""
            
            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            enhanced = response.text.strip()
            
            # Validate enhancement
            if len(enhanced) > len(reply_text) * 2:
                return None
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Reply enhancement error: {e}")
            return None
    
    async def _is_auto_reply_enabled(self, user_id: int) -> bool:
        """Check if auto-reply is enabled for user"""
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            return user and user.get("ai_auto_reply_enabled", False)
        except Exception as e:
            logger.error(f"Auto-reply check error: {e}")
            return False
    
    async def _is_ai_enhancement_enabled(self, user_id: int) -> bool:
        """Check if AI enhancement is enabled for user"""
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            return user and user.get("ai_enhancement_enabled", False)
        except Exception as e:
            logger.error(f"AI enhancement check error: {e}")
            return False
    
    async def _simulate_human_reply_behavior(self, client, target, message: str):
        """Simulate extremely realistic human reply behavior"""
        try:
            # Brief thinking time
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Start typing
            async with client.action(target, 'typing'):
                typing_time = len(message) * random.uniform(0.05, 0.1)
                typing_time = max(1.0, min(typing_time, 5.0))
                await asyncio.sleep(typing_time)
            
            # Brief pause before sending
            await asyncio.sleep(random.uniform(0.3, 0.8))
        except Exception as e:
            logger.debug(f"Typing simulation error: {e}")
            await asyncio.sleep(random.uniform(0.5, 1.5))
    
    async def _simulate_human_auto_reply_behavior(self, client, chat_id, message: str):
        """Simulate realistic auto-reply behavior (more immediate but still human)"""
        try:
            # Brief moment to "see" the message
            await asyncio.sleep(random.uniform(0.3, 1.5))
            
            # Start typing
            async with client.action(chat_id, 'typing'):
                # Faster typing for auto-replies but still realistic
                typing_time = len(message) * random.uniform(0.04, 0.08)
                typing_time = max(2.0, min(typing_time, 8.0))
                
                # Add some natural variation
                if random.random() < 0.3:  # 30% chance for brief pause
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                
                await asyncio.sleep(typing_time)
            
            # Small pause before sending
            await asyncio.sleep(random.uniform(0.2, 1.0))
        except Exception as e:
            logger.debug(f"Auto-reply typing simulation error: {e}")
            # Fallback to simple delay
            await asyncio.sleep(random.uniform(1.0, 3.0))
