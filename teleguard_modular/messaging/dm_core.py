"""Split from unified_dm.py - dm_core"""
"""DM Reply Handler - Forward DMs to admin group and handle replies with AI enhancement"""
import logging
import random
import asyncio
from datetime import datetime
import json
from telethon import events, Button
from ..core.mongo_database import mongodb
from ..utils.bot_logger import BotLogger

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
