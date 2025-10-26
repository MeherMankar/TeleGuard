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
                await event.delete()
                await event.respond("❌ Appeal process cancelled.")
            except Exception as e:
                logger.error(f"Appeal cancel callback error: {e}")

        @self.bot.on(events.CallbackQuery(pattern=b"captcha_(done|refresh|cancel)"))
        async def captcha_callback(event):
            user_id = event.sender_id
            action = event.data.decode().split('_')[1]
            try:
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
            client = self._get_user_client(user_id, account_name)
            
            if not client:
                await self._notify_user(user_id, f"❌ Account '{account_name}' not connected.")
                self.active_appeals.pop(user_id, None)
                return
            
            if not client.is_connected():
                await self._notify_user(user_id, f"❌ Account '{account_name}' not connected.")
                self.active_appeals.pop(user_id, None)
                return
            
            self.active_appeals[user_id]['state'] = 'starting'
            await self._notify_user(user_id, f"🛡️ **Starting Appeal for {account_name}**\n\n⏳ This may take 30 seconds to 1 minute...")
            
            # Setup handler first
            await self.setup_client_handler(user_id, client)
            logger.info(f"Handler setup complete for {account_name}")
            
            # Short delay then send /start
            await asyncio.sleep(random.uniform(2.0, 5.0))
            logger.info(f"Sending /start to spambot for {account_name}")
            await client.send_message("spambot", "/start")
            logger.info(f"Sent /start to spambot for {account_name}")
            
            self.active_appeals[user_id]['state'] = 'waiting_initial_response'
            
        except Exception as e:
            logger.error(f"Appeal process error: {e}")
            await self._notify_user(user_id, f"❌ Appeal process failed: {str(e)}")
            self.active_appeals.pop(user_id, None)

    async def _process_spambot_response(self, user_id: int, event):
        """Process response from spambot"""
        if user_id not in self.active_appeals:
            return
            
        state = self.active_appeals[user_id]
        message_text = event.message.text.lower()
        account_name = state.get('account_name', 'Unknown Account')
        
        # Prevent processing same message multiple times
        if state.get('last_processed_msg') == event.message.id:
            return
        state['last_processed_msg'] = event.message.id
        
        # No restrictions - complete silently
        if "good news, no limits are currently applied" in message_text:
            await self._notify_user(user_id, f"🎉 **{account_name}**: No restrictions found! Your account is clean.")
            # Complete without the full appeal completion message
            self.active_appeals.pop(user_id, None)
            return
        
        # Step 1: Click "This is a mistake"
        if ("hello" in message_text or "anti-spam" in message_text) and event.message.buttons:
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
        
        # Step 3: Never did spam - click "No! Never did that!"
        elif "never sent this to strangers" in message_text and event.message.buttons:
            await self._click_button(event, "no! never did that!")
            state['state'] = 'clicked_never'
            await self._notify_user(user_id, f"✅ **{account_name}:** Clicked 'No! Never did that!'")
        
        # Step 4: Captcha verification
        elif ("verify you are a human" in message_text or "telegram.org/captcha" in event.message.text):
            urls = re.findall(r'https://telegram\.org/captcha[^\s\)]+', event.message.text)
            if urls:
                captcha_url = urls[0]
                state['captcha_url'] = captcha_url
                state['state'] = 'captcha_detected'
                await self._handle_manual_captcha(user_id, captcha_url)
        
        # Step 5: Final submission - click "Done"
        elif "done" in message_text and event.message.buttons:
            await self._click_button(event, "done")
            state['state'] = 'appeal_submitted'
            await self._notify_user(user_id, f"✅ **{account_name}:** Clicked 'Done' - Appeal submitted!")
            await self._complete_appeal(user_id, True)
        
        elif "write me some details" in message_text or "why do you think" in message_text:
            logger.info(f"SpamBot requested appeal details for user {user_id}, account {account_name}")
            await self._submit_appeal_message(user_id)
        
        elif "already submitted a complaint" in message_text or "supervisors will check" in message_text:
            state['state'] = 'already_submitted'
            await self._notify_user(user_id, f"ℹ️ **{account_name}:** Appeal already exists. Supervisors will review it soon.")
            await self._complete_appeal(user_id, True)

    async def _select_smart_appeal_message(self, context: str, user_id: int = None, account_name: str = None) -> str:
        """AI-powered appeal message selection based on account age"""
        try:
            if not self.appeal_messages:
                logger.error("No appeal messages loaded from file - using emergency fallback")
                return "Hello, I believe my account has been restricted by mistake. I am a legitimate user and have not violated any terms of service. Please review my account and remove any restrictions. Thank you."
            
            # Get specific account age
            account_age_days = await self._get_account_age_days(user_id, account_name)
            logger.info(f"Account age: {account_age_days} days - filtering messages accordingly")
            
            # Filter messages based on account age
            age_appropriate_messages = []
            
            for message in self.appeal_messages:
                message_lower = message.lower()
                
                # For old accounts (365+ days), use messages with "old", "long-time", "years", etc.
                if account_age_days >= 365:
                    old_keywords = ['old', 'long-time', 'years', 'longtime', 'established', 'veteran', 'experienced', 'since', 'for years', 'long time']
                    if any(keyword in message_lower for keyword in old_keywords):
                        age_appropriate_messages.append(message)
                        logger.debug(f"Added old account message: {message[:50]}...")
                
                # For newer accounts (< 365 days), avoid "old" messages
                else:
                    old_keywords = ['old', 'long-time', 'years', 'longtime', 'established', 'veteran', 'experienced', 'since', 'for years', 'long time']
                    if not any(keyword in message_lower for keyword in old_keywords):
                        age_appropriate_messages.append(message)
                        logger.debug(f"Added new account message: {message[:50]}...")
            
            # Use age-appropriate messages if found, otherwise fallback to all messages
            messages_to_use = age_appropriate_messages if age_appropriate_messages else self.appeal_messages
            logger.info(f"Using {len(messages_to_use)} age-appropriate messages (account age: {account_age_days} days)")
            
            # Try AI selection from filtered messages if spam detector available
            if hasattr(self.bot_manager, 'spam_detector'):
                detector = self.bot_manager.spam_detector
                try:
                    analysis = detector.analyze_spambot_response(context)
                    spam_limit_type = analysis.get('spam_limit_type')
                    
                    if hasattr(detector, 'ai_select_from_messages'):
                        selected_message = await detector.ai_select_from_messages(
                            messages_to_use, spam_limit_type, context, account_age_days
                        )
                        if selected_message:
                            logger.info(f"AI selected age-appropriate message: {len(selected_message)} chars")
                            return selected_message
                    
                    if hasattr(detector, 'select_from_messages'):
                        selected_message = detector.select_from_messages(
                            messages_to_use, spam_limit_type, account_age_days
                        )
                        if selected_message:
                            logger.info(f"Rule-based selected age-appropriate message: {len(selected_message)} chars")
                            return selected_message
                            
                except Exception as e:
                    logger.warning(f"AI/Rule-based selection failed: {e}")
            
            # Random selection from age-appropriate messages
            selected = random.choice(messages_to_use)
            logger.info(f"Random age-appropriate selection: {len(selected)} chars")
            return selected
            
        except Exception as e:
            logger.error(f"Error in smart message selection: {e}")
            if self.appeal_messages:
                return random.choice(self.appeal_messages)
            return "Hello, I believe my account has been restricted by mistake. I am a legitimate user and have not violated any terms of service. Please review my account and remove any restrictions. Thank you."

    async def _click_button(self, event, button_text: str):
        """Click specific button with minimal delay"""
        try:
            await asyncio.sleep(random.uniform(1.0, 3.0))
            
            for row in event.message.buttons:
                for button in row:
                    if button_text.lower() in button.text.lower():
                        await button.click()
                        await asyncio.sleep(random.uniform(2.0, 4.0))
                        return True
            return False
        except Exception as e:
            logger.error(f"Error clicking button: {e}")
            return False

    async def _handle_manual_captcha(self, user_id: int, captcha_url: str):
        """Handle manual captcha verification process"""
        try:
            state = self.active_appeals[user_id]
            state['state'] = 'waiting_manual_captcha'
            
            buttons = [
                [Button.inline("✅ I completed the captcha", b"captcha_done")],
                [Button.inline("🔄 Get new captcha link", b"captcha_refresh")],
                [Button.inline("❌ Cancel appeal", b"captcha_cancel")]
            ]
            
            await self._notify_user(
                user_id,
                f"👤 **Manual Human Verification Required**\n\n"
                f"🔗 **Captcha URL:**\n`{captcha_url}`\n\n"
                f"📋 **Step-by-Step Instructions:**\n"
                f"1️⃣ Click the captcha link above\n"
                f"2️⃣ Complete the human verification in browser\n"
                f"3️⃣ Wait for automatic redirect to Telegram\n"
                f"4️⃣ Return here and click '✅ I completed the captcha'\n\n"
                f"💡 **Tips:**\n"
                f"• Keep this chat open during verification\n"
                f"• The captcha may take 30-60 seconds to load\n"
                f"• If stuck, use '🔄 Get new captcha link'\n\n"
                f"⚠️ **Manual verification required for all captchas**"
            )
            
            await self.bot.send_message(user_id, "Choose an action:", buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error handling manual captcha: {e}")
            await self._notify_user(user_id, "❌ Error setting up manual verification.")

    async def _auto_click_done(self, user_id: int):
        """Automatically find and click Done button"""
        try:
            # Get account name and specific client
            account_name = self.active_appeals[user_id].get('account_name', 'Unknown Account')
            client = self._get_user_client(user_id, account_name)
            if not client:
                await self._notify_user(user_id, f"❌ Account '{account_name}' client not found.")
                return
            
            # Realistic human behavior: read confirmation, then look for button
            confirmation_reading = random.uniform(3.0, 6.0)
            await asyncio.sleep(confirmation_reading)
            
            # Additional thinking/scanning time
            scanning_delay = random.uniform(2.0, 4.0)
            await asyncio.sleep(scanning_delay)
            async for message in client.iter_messages("spambot", limit=10):
                if message.buttons:
                    for row in message.buttons:
                        for button in row:
                            if "done" in button.text.lower():
                                await button.click()
                                await self._notify_user(user_id, f"✅ **{account_name}:** Automatically clicked 'Done' button!")
                                return
            
            await self._notify_user(
                user_id, 
                f"⚠️ **{account_name}: Done Button Not Found**\n\n"
                "Please manually:\n"
                "1. Go to @spambot chat\n"
                "2. Look for 'Done' button\n"
                "3. Click it to complete the appeal\n\n"
                "If no button is visible, the appeal may already be submitted."
            )
        except Exception as e:
            logger.error(f"Error auto-clicking done: {e}")
            await self._notify_user(
                user_id, 
                f"⚠️ **{account_name}: Manual Action Required**\n\n"
                "Please go to @spambot and click the 'Done' button to complete your appeal."
            )

    async def _submit_appeal_message(self, user_id: int):
        """Submit AI-selected appeal message with extremely human-like behavior"""
        try:
            # Get account name and specific client
            account_name = self.active_appeals[user_id].get('account_name', 'Unknown Account')
            client = self._get_user_client(user_id, account_name)
            if not client:
                await self._notify_user(user_id, f"❌ Account '{account_name}' client not found.")
                return
            
            # Get context from stored data or recent messages
            context = self.active_appeals[user_id].get('context', '')
            if not context:
                async for message in client.iter_messages("spambot", limit=3):
                    if message.text:
                        context += message.text + " "
                        break
            
            # Realistic human behavior: read and think about the situation
            reading_context_time = len(context) * 0.08 + random.uniform(5.0, 12.0)
            await asyncio.sleep(reading_context_time)
            
            # Get account age for display
            account_age_days = await self._get_account_age_days(user_id, account_name)
            age_years = account_age_days // 365
            age_months = (account_age_days % 365) // 30
            
            # Format age display
            if age_years > 0:
                age_display = f"{age_years} year{'s' if age_years != 1 else ''}"
                if age_months > 0:
                    age_display += f", {age_months} month{'s' if age_months != 1 else ''}"
            elif age_months > 0:
                age_display = f"{age_months} month{'s' if age_months != 1 else ''}"
            else:
                age_display = f"{account_age_days} day{'s' if account_age_days != 1 else ''}"
            
            # Use intelligent message selection with account age filtering
            appeal_message = await self._select_smart_appeal_message(context, user_id, account_name)
            
            # Log the selected message for debugging
            logger.info(f"Selected appeal message for {account_name}: {len(appeal_message)} chars")
            logger.debug(f"Appeal message preview: {appeal_message[:100]}...")
            
            # Check if sending appeal message is safe
            session_id = f"{user_id}_{account_name}"
            await session_protection.check_message_safety(session_id, appeal_message, "spambot")
            
            # Notify user that message is being sent with account age
            await self._notify_user(
                user_id,
                f"📝 **Sending Appeal Message**\n\n"
                f"📱 Account: {account_name}\n"
                f"📅 Account Age: {age_display} ({account_age_days} days)\n"
                f"📄 Message Length: {len(appeal_message)} characters\n"
                f"⏳ Composing message with human-like behavior..."
            )
            
            # Simulate realistic message composition behavior
            await self._simulate_human_message_composition(client, "spambot", appeal_message)
            
            # Send the appeal message
            logger.info(f"Sending appeal message to spambot for account {account_name}")
            await client.send_message("spambot", appeal_message)
            logger.info(f"Appeal message sent successfully for account {account_name}")
            
            # Record message for protection tracking
            await session_protection.record_message_sent(session_id)
            
            self.active_appeals[user_id]['state'] = 'final_submitted'
            
            # Get spam analysis for better reporting
            spam_analysis = self.active_appeals[user_id].get('spam_analysis', {})
            spam_type = spam_analysis.get('spam_limit_type', {})
            spam_type_name = spam_type.value.replace('_', ' ').title() if hasattr(spam_type, 'value') else 'General'
            
            await self._notify_user(
                user_id,
                f"🤖 **Smart Appeal Submitted**\n\n"
                f"📱 **Account:** {account_name}\n"
                f"📄 **Message Sent:** {len(appeal_message)} characters\n"
                f"🎯 **Detected Type:** {spam_type_name}\n"
                f"🔧 **Strategy:** Auto-optimized for spam type\n\n"
                f"✅ **Appeal message successfully sent to @spambot!**\n\n"
                f"📧 You should receive a response within 24-48 hours."
            )
            
            await self._complete_appeal(user_id, True)
            
        except Exception as e:
            logger.error(f"Error submitting appeal message for {account_name}: {e}")
            await self._notify_user(user_id, f"❌ Failed to submit appeal message: {str(e)}")

    async def _complete_appeal(self, user_id: int, success: bool):
        """Complete the appeal process"""
        state = self.active_appeals.get(user_id, {})
        mode = state.get('mode', 'auto')
        
        # Re-enable session protection after appeal completion
        try:
            from ..core.mongo_database import mongodb
            await mongodb.db.accounts.update_many(
                {"user_id": user_id},
                {
                    '$unset': {
                        'session_protection_disabled': '',
                        'protection_bypass_until': ''
                    }
                }
            )
        except Exception as e:
            logger.error(f"Error re-enabling session protection: {e}")
        
        if success:
            mode_text = "🤖 Automatic" if mode == "auto" else "👤 Manual"
            account_name = state.get('account_name', 'Unknown Account')
            await self._notify_user(
                user_id,
                f"🎉 **Appeal Process Completed!**\n\n"
                f"📱 **Account:** {account_name}\n"
                f"Mode: {mode_text} (Smart Detection)\n"
                f"✅ Your appeal has been successfully submitted to Telegram.\n"
                f"📧 You should receive a response within 24-48 hours.\n\n"
                f"💡 **Next Steps:**\n"
                f"• Check your account restrictions periodically\n"
                f"• Monitor @spambot for updates\n"
                f"• Be patient - reviews can take 1-3 days\n\n"
                f"🔄 If no response after 72 hours, you can submit another appeal."
            )
        else:
            await self._notify_user(
                user_id,
                f"❌ **Appeal Process Failed**\n\n"
                f"The appeal could not be completed.\n\n"
                f"**Options:**\n"
                f"1. Try /appeal again (choose different mode)\n"
                f"2. Use /appeal_help for manual steps\n"
                f"3. Contact support if problems persist"
            )
        
        self.active_appeals.pop(user_id, None)

    async def _appeal_timeout(self, user_id: int, timeout_seconds: int):
        """Handle appeal timeout"""
        await asyncio.sleep(timeout_seconds)
        if user_id in self.active_appeals:
            await self._notify_user(
                user_id,
                "⏰ **Appeal Process Timed Out**\n\n"
                "The automated process took too long.\n\n"
                "**What to do:**\n"
                "• Try /appeal again\n"
                "• Check @spambot manually\n"
                "• Use /appeal_help for guidance"
            )
            self.active_appeals.pop(user_id, None)

    async def _get_account_age_days(self, user_id: int = None, account_name: str = None) -> int:
        """Get specific account creation age in days"""
        try:
            # Get specific client if provided
            if user_id and account_name:
                client = self._get_user_client(user_id, account_name)
                if client and client.is_connected():
                    me = await client.get_me()
                    if hasattr(me, 'date') and me.date:
                        from datetime import datetime
                        creation_date = me.date
                        age_days = (datetime.now() - creation_date).days
                        logger.info(f"Account {account_name} age: {age_days} days")
                        return age_days
            
            # Fallback to any available client
            for uid, clients in self.bot_manager.user_clients.items():
                for client in clients.values():
                    if client and client.is_connected():
                        me = await client.get_me()
                        if hasattr(me, 'date') and me.date:
                            from datetime import datetime
                            creation_date = me.date
                            age_days = (datetime.now() - creation_date).days
                            return age_days
            return 365  # Default to old account if can't determine
        except Exception as e:
            logger.error(f"Error getting account age: {e}")
            return 365  # Default to old account

    def _get_user_client(self, user_id: int, account_name: str = None):
        """Get specific user client by account name or first available"""
        try:
            user_clients = self.bot_manager.user_clients.get(user_id, {})
            
            # If account name specified, try to find that specific client
            if account_name:
                # Try exact match first
                client = user_clients.get(account_name)
                if client and client.is_connected():
                    return client
            
            # Fallback to first available client
            for client in user_clients.values():
                if client and client.is_connected():
                    return client
            return None
        except Exception as e:
            logger.error(f"Error getting user client: {e}")
            return None

    async def _notify_user(self, user_id: int, message: str):
        """Send notification to user"""
        try:
            await self.bot.send_message(user_id, message)
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")

    async def _start_appeal_for_account(self, user_id: int, account_name: str, context: str, event):
        """Start appeal process for specific account"""
        try:
            # Store account name in active appeals for tracking
            if user_id not in self.active_appeals:
                self.active_appeals[user_id] = {}
            self.active_appeals[user_id]['account_name'] = account_name
            self.active_appeals[user_id]['context'] = context
            self.active_appeals[user_id]['state'] = 'new'
            
            # Load account client if not already loaded
            client = self._get_user_client(user_id, account_name)
            if not client:
                await event.respond("⏳ Loading account client...")
                # Get account from database
                from ..core.mongo_database import mongodb
                account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
                if not account or not account.get('session_string'):
                    await event.respond("❌ Account not found or no session available.")
                    return
                
                # Load the client
                try:
                    await self.bot_manager.start_user_client(user_id, account_name, account['session_string'])
                    await event.respond("✅ Account loaded successfully!")
                    # Get the newly loaded client
                    client = self._get_user_client(user_id, account_name)
                    if not client:
                        await event.respond("❌ Failed to get loaded client.")
                        return
                except Exception as e:
                    logger.error(f"Failed to load account {account_name}: {e}")
                    await event.respond(f"❌ Failed to load account: {str(e)}")
                    return
            
            # Start the appeal process directly
            await self._start_appeal_process(user_id)
            
        except Exception as e:
            logger.error(f"Start appeal for account error: {e}")
            await event.respond("❌ Error starting appeal process.")
    
    async def _simulate_human_message_composition(self, client, target, message: str):
        """Simulate realistic human message composition with word complexity analysis"""
        try:
            # Show typing indicator
            if len(message) > 20:
                try:
                    from telethon.tl.functions.messages import SetTypingRequest
                    from telethon.tl.types import SendMessageTypingAction
                    await client(SetTypingRequest(peer=target, action=SendMessageTypingAction()))
                except Exception:
                    pass
            
            # Analyze words and calculate realistic typing time
            words = message.split()
            total_typing_time = 0
            
            for word in words:
                # Base time for 37 WPM (1.62 seconds per word)
                base_time = 1.62
                
                # Adjust for word complexity
                word_lower = word.lower().strip('.,!?;:')
                
                # Longer words take more time
                if len(word_lower) > 8:
                    base_time *= 1.4  # 40% slower for long words
                elif len(word_lower) > 5:
                    base_time *= 1.2  # 20% slower for medium words
                
                # Complex/uncommon words take longer
                complex_words = ['restricted', 'legitimate', 'violation', 'communication', 'investigation', 
                               'unauthorized', 'verification', 'circumstances', 'misunderstanding', 'reconsider']
                if word_lower in complex_words:
                    base_time *= 1.3
                
                # Technical terms slower
                if word_lower in ['telegram', 'spambot', 'account', 'restrictions', 'appeal']:
                    base_time *= 1.1
                
                # Common words faster
                common_words = ['the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'man', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she', 'too', 'use']
                if word_lower in common_words:
                    base_time *= 0.8  # 20% faster for common words
                
                total_typing_time += base_time
            
            # Add thinking pauses for appeal composition
            thinking_time = random.uniform(3.0, 6.0)
            total_time = total_typing_time + thinking_time
            
            # Split into realistic segments with natural pauses
            segments = max(2, min(5, len(words) // 12))
            segment_time = total_time / segments
            
            for i in range(segments):
                await asyncio.sleep(segment_time)
                
                # Refresh typing indicator
                if i < segments - 1 and len(message) > 80:
                    try:
                        from telethon.tl.functions.messages import SetTypingRequest
                        from telethon.tl.types import SendMessageTypingAction
                        await client(SetTypingRequest(peer=target, action=SendMessageTypingAction()))
                    except Exception:
                        pass
            
            # Final review pause
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
        except Exception as e:
            logger.warning(f"Composition simulation error: {e}")
            await asyncio.sleep(random.uniform(8.0, 15.0))

    async def setup_client_handler(self, user_id: int, client):
        """Setup spambot handler for a specific client"""
        # Remove existing handlers to prevent duplicates
        client.remove_event_handler(lambda e: True, events.NewMessage)
        
        @client.on(events.NewMessage(from_users='spambot'))
        async def handle_spambot_message(event):
            if user_id in self.active_appeals:
                try:
                    await self._process_spambot_response(user_id, event)
                except Exception as e:
                    logger.error(f"Error processing spambot message: {e}")