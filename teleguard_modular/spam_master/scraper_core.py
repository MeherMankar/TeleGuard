"""Split from contact_scraper.py - scraper_core"""
"""handler for appealing spam restrictions with manual captcha verification"""
import asyncio
import logging
import random
import re
from pathlib import Path
from typing import Dict, Optional
from telethon import events
from telethon.tl.custom import Button
from ..utils.session_protection import session_protection

logger = logging.getLogger(__name__)

class SpamAppealHandler:
    """Handles automated spam appeal process with manual captcha verification"""
    
    def __init__(self, bot_manager):
        self.bot = bot_manager.bot
        self.bot_manager = bot_manager
        self.spam_bot_username = "spambot"
        self.spam_info_bot_username = "SpamBot"  # Alternative spam bot
        self.active_appeals: Dict[int, Dict] = {}  # user_id -> appeal_state
        self.appeal_messages = self._load_appeal_messages()

    def _load_appeal_messages(self) -> list:
        """Load appeal message templates from file"""
        try:
            messages_file = Path(__file__).parent.parent / "data" / "appeal_messages.txt"
            logger.info(f"Attempting to load appeal messages from: {messages_file}")
            
            if messages_file.exists():
                content = messages_file.read_text(encoding='utf-8')
                # Split by double newlines and filter out empty messages
                messages = [msg.strip() for msg in content.split('\n\n') if msg.strip() and len(msg.strip()) > 50]
                logger.info(f"Successfully loaded {len(messages)} appeal messages from file")
                
                # Log first few messages for verification
                for i, msg in enumerate(messages[:3]):
                    logger.debug(f"Appeal message {i+1} preview: {msg[:100]}...")
                
                return messages
            else:
                logger.warning(f"Appeal messages file not found: {messages_file}")
        except Exception as e:
            logger.error(f"Failed to load appeal messages: {e}")
        
        # Return default messages if file loading fails
        default_messages = [
            "Hello, I believe my account has been restricted by mistake. I am a legitimate user and have not violated any terms of service. I use Telegram for personal communication with friends and family. Please review my account and remove any restrictions. Thank you for your time and consideration.",
            "I am writing to appeal the spam restrictions placed on my account. I have been using Telegram responsibly for legitimate purposes only. I believe this restriction was applied in error. I would appreciate if you could review my case and restore my account to normal status.",
            "Dear Telegram Support, my account has been flagged as spam, but I assure you this is a mistake. I only use Telegram to communicate with close contacts and have never engaged in spam activities. Please investigate and lift the restrictions on my account."
        ]
        logger.info(f"Using {len(default_messages)} default appeal messages")
        return default_messages

    def register_handlers(self):
        """Register appeal handlers with smart detection"""

        @self.bot.on(events.NewMessage(pattern=r"^/spam_stats$"))
        async def spam_stats_command(event):
            """Show spam detector statistics"""
            try:
                if hasattr(self.bot_manager, 'spam_detector'):
                    stats = self.bot_manager.spam_detector.get_detection_stats()
                    stats_text = "📊 **Spam Detector Statistics**\n\n"
                    
                    for spam_type, count in stats.items():
                        if spam_type != 'total_messages':
                            type_name = spam_type.replace('_', ' ').title()
                            stats_text += f"• {type_name}: {count} messages\n"
                    
                    stats_text += f"\n📝 Total Messages: {stats.get('total_messages', 0)}"
                    await event.reply(stats_text)
                else:
                    await event.reply("❌ Spam detector not available")
            except Exception as e:
                logger.error(f"Spam stats command error: {e}")
                await event.reply("❌ Error getting spam statistics")
        
        @self.bot.on(events.NewMessage(pattern=r"^/test_appeal_messages$"))
        async def test_appeal_messages_command(event):
            """Test appeal message loading and selection"""
            user_id = event.sender_id
            try:
                # Check if user is admin
                from ..core.config import config
                if user_id not in config.security.admin_ids:
                    await event.reply("❌ Admin access required")
                    return
                
                # Test message loading
                message_count = len(self.appeal_messages)
                
                # Test message selection
                test_message = await self._select_smart_appeal_message("test context")
                
                response = (
                    f"🧪 **Appeal Messages Test**\n\n"
                    f"📁 **Loaded Messages:** {message_count}\n"
                    f"📄 **Test Selection Length:** {len(test_message)} chars\n\n"
                    f"**Sample Message Preview:**\n"
                    f"```\n{test_message[:200]}...\n```\n\n"
                    f"✅ Appeal message system is working!"
                )
                
                await event.reply(response)
                
            except Exception as e:
                logger.error(f"Test appeal messages error: {e}")
                await event.reply(f"❌ Test failed: {str(e)}")
        
        @self.bot.on(events.NewMessage(pattern=r"^/appeal(?:\s+(.+))?$"))
        async def appeal_command(event):
            user_id = event.sender_id
            try:
                # Automatically disable session protection for appeal process
                from ..core.mongo_database import mongodb
                await mongodb.db.accounts.update_many(
                    {"user_id": user_id},
                    {
                        '$set': {
                            'session_protection_disabled': True,
                            'protection_bypass_until': int(asyncio.get_event_loop().time()) + 1800  # 30 minutes
                        },
                        '$unset': {
                            'session_protection_active': '',
                            'protection_cooldown': '',
                            'last_protection_trigger': ''
                        }
                    }
                )
                
                # Get accounts from database to show proper names
                accounts = await mongodb.db.accounts.find({"user_id": user_id, "is_active": True}).to_list(length=None)
                
                if not accounts:
                    await event.reply("❌ No accounts found. Add an account first using /start")
                    return
                
                context = event.pattern_match.group(1) if event.pattern_match.group(1) else ""
                
                # Show account selection if multiple accounts
                if len(accounts) > 1:
                    buttons = []
                    for account in accounts[:10]:  # Limit to 10 accounts
                        # Use display_name or name, fallback to phone
                        display_name = account.get('display_name') or account.get('name') or account.get('phone', 'Unknown')
                        # Use account ID as callback data to avoid confusion
                        buttons.append([Button.inline(f"📱 {display_name}", f"appeal_account_id:{account['_id']}")])
                    
                    buttons.append([Button.inline("❌ Cancel", "appeal_cancel")])
                    
                    await event.reply(
                        f"🧠 **Smart Spam Appeal**\n\n"
                        f"Select account to appeal spam restrictions:\n\n"
                        f"📊 Available accounts: {len(accounts)}",
                        buttons=buttons
                    )
                else:
                    # Single account - proceed directly
                    account = accounts[0]
                    display_name = account.get('display_name') or account.get('name') or account.get('phone', 'Unknown')
                    await self._start_appeal_for_account(user_id, display_name, context, event)
                    
            except Exception as e:
                logger.error(f"Appeal command error: {e}")
                await event.reply("❌ Error sending smart appeal. Please try again.")
        
        @self.bot.on(events.CallbackQuery(pattern=b"appeal_account_id:(.+)"))
        async def appeal_account_callback(event):
            user_id = event.sender_id
            account_id = event.data.decode().split(':', 1)[1]
            try:
                await event.answer()
                await event.delete()
                
                # Get account details from database using ID
                from bson import ObjectId
                from ..core.mongo_database import mongodb
                account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
                
                if not account:
                    await event.respond("❌ Account not found.")
                    return
                
                # Use the correct account name for client lookup
                account_name = account.get('name') or account.get('phone') or account.get('display_name', 'Unknown')
                # Small delay before processing (like human clicking)
                await asyncio.sleep(random.uniform(0.2, 0.8))
                await self._start_appeal_for_account(user_id, account_name, "", event)
                
            except Exception as e:
                logger.error(f"Appeal account callback error: {e}")
                await event.respond("❌ Error starting appeal process.")
        
        @self.bot.on(events.CallbackQuery(pattern=b"appeal_cancel"))
        async def appeal_cancel_callback(event):
            try:
                await event.answer()
                await event.delete()
                await event.respond("❌ Appeal process cancelled.")
            except Exception as e:
                logger.error(f"Appeal cancel callback error: {e}")

        @self.bot.on(events.CallbackQuery(pattern=b"captcha_(done|refresh|cancel)"))
        async def captcha_callback(event):
            user_id = event.sender_id
            action = event.data.decode().split('_')[1]
            try:
                await event.answer()
                await event.delete()
                if user_id not in self.active_appeals:
                    await event.respond("⚠️ No active appeal process found.")
                    return
                
                state = self.active_appeals[user_id]
                
                if action == "cancel":
                    self.active_appeals.pop(user_id, None)
                    await event.respond("❌ Appeal process cancelled.")
                    return
                elif action == "done":
                    state['state'] = 'captcha_solved'
                    await event.respond(
                        "✅ **Captcha Verification Confirmed**\n\n"
                        "Looking for 'Done' button in @spambot...\n"
                        "⏳ Please wait..."
                    )
                    await asyncio.sleep(3)
                    await self._auto_click_done(user_id)
            except Exception as e:
                logger.error(f"Captcha callback error: {e}")
                await event.respond("❌ Error processing captcha verification.")

    async def _start_appeal_process(self, user_id: int):
        """Start the automated appeal process"""
        try:
            # Check if appeal exists
            if user_id not in self.active_appeals:
                logger.error(f"No active appeal found for user {user_id}")
                return
            
            # Prevent duplicate appeals (but allow 'new' state to proceed)
            current_state = self.active_appeals[user_id].get('state')
            if current_state and current_state not in ['new', 'starting']:
                logger.info(f"Appeal already in progress for user {user_id}, state: {current_state}")
                return
            
            account_name = self.active_appeals[user_id].get('account_name', 'Unknown Account')
            logger.info(f"Getting client for account: {account_name}")
            client = await self._get_user_client(user_id, account_name)
            
            if not client:
                await self._notify_user(user_id, f"❌ Account '{account_name}' not connected.")
                self.active_appeals.pop(user_id, None)
                return
            
            if not client.is_connected():
                await self._notify_user(user_id, f"❌ Account '{account_name}' not connected.")
                self.active_appeals.pop(user_id, None)
                return
            
            # Verify we got the correct client
            try:
                me = await client.get_me()
                actual_name = me.first_name or 'Unknown'
                logger.info(f"Using client for: {actual_name} (requested: {account_name})")
            except Exception as e:
                logger.warning(f"Could not verify client identity: {e}")
            
            self.active_appeals[user_id]['state'] = 'starting'
            await self._notify_user(user_id, f"🛡️ **Starting Appeal for {account_name}**\n\n⏳ This may take 30 seconds to 1 minute...")
            
            # Setup handler first
            await self.setup_client_handler(user_id, client)
            logger.info(f"Handler setup complete for {account_name}")
            
            # Short delay then send /start
            await asyncio.sleep(random.uniform(2.0, 5.0))
            
            # Try both bot usernames
            bot_username = "spambot"
            try:
                logger.info(f"Sending /start to {bot_username} for {account_name}")
                await client.send_message(bot_username, "/start")
                logger.info(f"Sent /start to {bot_username} for {account_name}")
                await asyncio.sleep(3)
            except Exception as e:
                logger.warning(f"Failed with {bot_username}, trying SpamBot: {e}")
                bot_username = "SpamBot"
                await client.send_message(bot_username, "/start")
                logger.info(f"Sent /start to {bot_username} for {account_name}")
                await asyncio.sleep(3)
            
            self.active_appeals[user_id]['state'] = 'waiting_initial_response'
            logger.info(f"Waiting for spambot response for {account_name}...")
            
        except Exception as e:
            logger.error(f"Appeal process error: {e}")
            await self._notify_user(user_id, f"❌ Appeal process failed: {str(e)}")
            self.active_appeals.pop(user_id, None)

    async def _process_spambot_response(self, user_id: int, event):
        """Process response from spambot or spam info bot"""
        if user_id not in self.active_appeals:
            logger.warning(f"No active appeal for user {user_id}")
            return
            
        state = self.active_appeals[user_id]
        message_text = event.message.text.lower() if event.message.text else ""
        account_name = state.get('account_name', 'Unknown Account')
        
        logger.info(f"Processing spambot message for {account_name}: {message_text[:100]}...")
        
        # Prevent processing same message multiple times
        if state.get('last_processed_msg') == event.message.id:
            logger.debug(f"Skipping duplicate message {event.message.id}")
            return
        state['last_processed_msg'] = event.message.id
        
        # Detect restriction type and bot type
        is_spam_info_bot = "subscribe to telegram premium" in message_text
        has_captcha = "sorry that you had to contact" in message_text
        
        if is_spam_info_bot:
            state['bot_type'] = 'spam_info_bot'  # No captcha flow
        elif has_captcha:
            state['bot_type'] = 'regular_spambot'  # With captcha flow
        
        # 1. No restrictions - account is clean
        if "good news" in message_text and "no limits" in message_text:
            await self._notify_user(user_id, f"🎉 **{account_name}: No Restrictions**\n\nYour account is clean! No action needed.")
            self.active_appeals.pop(user_id, None)
            return
        
        # 2. Time-based restriction - cannot appeal, must wait
        if "limited until" in message_text and "automatically released" in message_text:
            await self._notify_user(
                user_id,
                f"⏰ **{account_name}: Time-Based Restriction**\n\n"
                f"❌ Cannot be appealed - must wait for automatic release\n\n"
                f"**Actions:**\n"
                f"• Wait for expiry date\n"
                f"• Avoid triggering actions\n"
                f"• Premium users get shorter times"
            )
            self.active_appeals.pop(user_id, None)
            return
        
        # 3. Illegal content - must email abuse@telegram.org
        if "illegal" in message_text and "public content" in message_text:
            await self._notify_user(
                user_id,
                f"🚫 **{account_name}: Illegal Content**\n\n"
                f"❌ Cannot appeal via bot\n\n"
                f"**Contact:** abuse@telegram.org\n"
                f"Include phone number and details"
            )
            self.active_appeals.pop(user_id, None)
            return
        
        # Flow 1: Spam Info Bot (no captcha, phone number issue)
        if state.get('bot_type') == 'spam_info_bot':
            # Step 1: Initial message with "Submit a complaint" button
            if "harsh response from our anti-spam systems" in message_text and event.message.buttons:
                await self._notify_user(user_id, f"⚠️ **{account_name}**: Spam Info Bot detected! Starting appeal...")
                await self._click_button(event, "submit a complaint")
                return
            
            # Step 2: Confirmation about not sending spam
            elif "never send this to strangers" in message_text:
                await self._notify_user(user_id, f"🔘 **{account_name}**: Sending confirmation response...")
                client = await self._get_user_client(user_id, account_name)
                if client:
                    await asyncio.sleep(random.uniform(2.0, 4.0))
                    await client.send_message("spambot", "No, I'll never do any of this!")
                    await self._notify_user(user_id, f"✅ **{account_name}**: Confirmation sent!")
                return
            
            # Step 3: Request for appeal details (no captcha)
            elif "write me some details" in message_text or "why do you think your account was limited" in message_text:
                await self._submit_appeal_message(user_id)
                return
            
            # Already submitted
            elif "already submitted" in message_text or "supervisors will check" in message_text:
                await self._notify_user(user_id, f"ℹ️ **{account_name}**: Appeal submitted! Supervisors will review.")
                await self._complete_appeal(user_id, True)
                return
        
        # Flow 2: Regular spambot (with captcha, user behavior issue)
        elif state.get('bot_type') == 'regular_spambot':
            # Step 1: Click "This is a mistake" - initial spambot message
            if ("sorry that you had to contact" in message_text or "anti-spam" in message_text or "some actions can trigger" in message_text) and event.message.buttons:
                await self._notify_user(user_id, f"⚠️ **{account_name}**: Restriction detected! Starting appeal process...")
                await self._click_button(event, "this is a mistake")
                return
            
            # Step 2: Click "Yes" to submit complaint
            elif "submit a complaint" in message_text and event.message.buttons:
                await self._click_button(event, "yes")
                return
            
            # Step 3: Click "No! Never did that!"
            elif "never sent this to strangers" in message_text and event.message.buttons:
                await self._click_button(event, "no! never did that!")
                return
            
            # Step 4: Handle captcha
            elif "verify you are a human" in message_text or "telegram.org/captcha" in event.message.text:
                urls = re.findall(r'https://telegram\.org/captcha[^\s\)]+', event.message.text)
                if urls:
                    await self._handle_manual_captcha(user_id, urls[0])
                return
            
            # Step 5: Click "Done"
            elif "done" in message_text and event.message.buttons:
                await self._click_button(event, "done")
                await self._complete_appeal(user_id, True)
                return
            
            # Appeal message request
            elif "write me some details" in message_text:
                await self._submit_appeal_message(user_id)
                return
            
            # Already submitted
            elif "already submitted" in message_text:
                await self._notify_user(user_id, f"ℹ️ **{account_name}**: Appeal already exists.")
                await self._complete_appeal(user_id, True)
                return

    async def _select_smart_appeal_message(self, context: str, user_id: int = None, account_name: str = None) -> str:
        """Enhanced AI-powered appeal message with multi-strategy optimization"""
        try:
            spam_type_keywords = {
                'spamblock': ['spamblock', 'spam block', 'flagged as spam', 'spam restrictions', 'spam limitation', 'spam-related'],
                'new_account': ['new account', 'recently created', 'fresh', 'just created', 'newly registered'],
                'two_way': ['two-way restriction', 'two way restriction', 'dual verification', 'two-step']
            }
            
            detected_spam_type = 'general'
            context_lower = context.lower()
            
            for spam_type, keywords in spam_type_keywords.items():
                if any(kw in context_lower for kw in keywords):
                    detected_spam_type = spam_type
                    break
            
            logger.info(f"Spam type: {detected_spam_type} | Context: {context[:80]}...")
            
            # Try AI generation with enhanced prompts
            ai_message = await self._generate_ai_appeal_message(context, detected_spam_type)
            if ai_message:
                logger.info(f"✓ AI generated: {len(ai_message)} chars")
                return ai_message
            
            # Enhanced template selection with quality scoring
            if not self.appeal_messages:
                return self._get_emergency_message(detected_spam_type)
            
            # Score and rank messages by relevance
            scored_messages = []
            for msg in self.appeal_messages:
                score = self._score_message_quality(msg, detected_spam_type)
                if score > 0:
                    scored_messages.append((score, msg))
            
            if scored_messages:
                scored_messages.sort(reverse=True)
                top_messages = [msg for _, msg in scored_messages[:20]]
                selected = random.choice(top_messages)
                logger.info(f"✓ Template selected: {len(selected)} chars (score: {scored_messages[0][0]})")
                return selected
            
            return self._get_emergency_message(detected_spam_type)
            
        except Exception as e:
            logger.error(f"Message selection error: {e}")
            return self._get_emergency_message('general')
    
    def _score_message_quality(self, message: str, spam_type: str) -> int:
        """Score message quality and relevance (0-100)"""
        score = 0
        msg_lower = message.lower()
        
        # Length scoring (optimal 200-500 chars)
        if 200 <= len(message) <= 500:
            score += 30
        elif 150 <= len(message) <= 600:
            score += 20
        elif len(message) > 100:
            score += 10
        
        # Type-specific matching
        if spam_type == 'spamblock':
            if 'spamblock' in msg_lower or 'spam block' in msg_lower:
                score += 40
            elif 'spam' in msg_lower:
                score += 20
