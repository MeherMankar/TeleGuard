"""handler for appealing spam restrictions with manual captcha verification"""
import asyncio
import logging
import random
import re
from pathlib import Path
from typing import Dict, Optional
from telethon import events
from telethon.tl.custom import Button

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
            if messages_file.exists():
                content = messages_file.read_text(encoding='utf-8')
                messages = [msg.strip() for msg in content.split('\n\n') if msg.strip()]
                return messages
        except Exception as e:
            logger.error(f"Failed to load appeal messages: {e}")
        return []

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
        
        @self.bot.on(events.NewMessage(pattern=r"^/appeal(?:\s+(.+))?$"))
        async def appeal_command(event):
            user_id = event.sender_id
            try:
                # Get accounts from database to show proper names
                from ..core.mongo_database import mongodb
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
            # Get account name for better tracking
            account_name = self.active_appeals[user_id].get('account_name', 'Unknown Account')
            
            # Get the specific client for this account
            client = self._get_user_client(user_id, account_name)
            if not client:
                await self._notify_user(user_id, f"❌ Account '{account_name}' client not found or not connected.")
                self.active_appeals.pop(user_id, None)
                return
            
            # Verify we have the right client
            try:
                me = await client.get_me()
                actual_name = me.first_name or 'Unknown'
                logger.info(f"Using client for account: {actual_name} (requested: {account_name})")
            except Exception as e:
                logger.error(f"Failed to verify client: {e}")
            
            # Setup spambot message handler for this client
            await self.setup_client_handler(user_id, client)
            
            # Realistic human behavior: brief moment before starting
            initial_hesitation = random.uniform(0.8, 2.5)
            await asyncio.sleep(initial_hesitation)
            
            await client.send_message("spambot", "/start")
            self.active_appeals[user_id]['state'] = 'waiting_initial_response'
            await self._notify_user(
                user_id, 
                f"🔍 **Checking {account_name}...**\n\n"
                f"⏳ Please wait..."
            )
            
            # Set timeout for the appeal process
            asyncio.create_task(self._appeal_timeout(user_id, 300))
            
        except Exception as e:
            logger.error(f"Failed to start appeal process: {e}")
            await self._notify_user(user_id, f"❌ Failed to contact @spambot: {str(e)}")
            self.active_appeals.pop(user_id, None)

    async def _process_spambot_response(self, user_id: int, event):
        """Process response from spambot with intelligent analysis"""
        if user_id not in self.active_appeals:
            return
            
        state = self.active_appeals[user_id]
        message_text = event.message.text.lower()
        
        # Analyze the spambot response using AI-enhanced spam detector
        try:
            if hasattr(self.bot_manager, 'spam_detector'):
                analysis = self.bot_manager.spam_detector.analyze_spambot_response(event.message.text)
                
                # Try AI button strategy analysis
                ai_strategy = None
                if hasattr(self.bot_manager.spam_detector, 'ai_analyze_button_strategy'):
                    try:
                        ai_strategy = await self.bot_manager.spam_detector.ai_analyze_button_strategy(event.message.text)
                    except Exception as e:
                        logger.warning(f"AI button strategy failed: {e}")
                
                # Store analysis in state for later use
                state['spam_analysis'] = analysis
                state['ai_strategy'] = ai_strategy
                
                # Skip analysis message for cleaner output
                # Store analysis in state for later use only
                pass
            
        except Exception as e:
            logger.error(f"Error analyzing spambot response: {e}")
        
        # Get account name for status messages
        account_name = state.get('account_name', 'Unknown Account')
        
        # Check if account has no restrictions (cancel appeal)
        if "good news, no limits are currently applied" in message_text or "you're free as a bird" in message_text:
            await self._notify_user(
                user_id,
                f"🎉 **{account_name}: No Restrictions!**\n\n"
                f"✅ Your account is unrestricted. No appeal needed."
            )
            self.active_appeals.pop(user_id, None)
            return
        
        # Step 1: Initial response - click "This is a mistake"
        if (("hello" in message_text or "very sorry" in message_text or "anti-spam systems" in message_text) 
            and event.message.buttons):
            await self._click_button(event, "this is a mistake")
            state['state'] = 'clicked_mistake'
            await self._notify_user(user_id, f"✅ **{account_name}:** Clicked 'This is a mistake'")
        
        # Step 2: Complaint confirmation - click "Yes"
        elif "submit a complaint" in message_text and event.message.buttons:
            await self._click_button(event, "yes")
            state['state'] = 'clicked_yes'
            await self._notify_user(user_id, f"✅ **{account_name}:** Clicked 'Yes' to submit complaint")
        
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
            await self._submit_appeal_message(user_id)
        
        elif "already submitted a complaint" in message_text or "supervisors will check" in message_text:
            state['state'] = 'already_submitted'
            await self._notify_user(user_id, f"ℹ️ **{account_name}:** Appeal already exists. Supervisors will review it soon.")
            await self._complete_appeal(user_id, True)

    async def _select_smart_appeal_message(self, context: str) -> str:
        """AI-powered appeal message selection using integrated spam detector"""
        try:
            if hasattr(self.bot_manager, 'spam_detector'):
                detector = self.bot_manager.spam_detector
                
                # Analyze spambot response to detect spam limit type
                analysis = detector.analyze_spambot_response(context)
                spam_limit_type = analysis['spam_limit_type']
                
                # Get account age for better message selection
                account_age_days = await self._get_account_age_days()
                
                # Try AI-enhanced message selection first
                selected_message = None
                if hasattr(detector, 'ai_select_best_message'):
                    try:
                        selected_message = await detector.ai_select_best_message(
                            spam_limit_type, context, account_age_days
                        )
                        if selected_message:
                            logger.info(f"AI selected message for {spam_limit_type.value}: {len(selected_message)} chars")
                    except Exception as e:
                        logger.warning(f"AI message selection failed: {e}")
                
                # Fallback to rule-based selection
                if not selected_message:
                    selected_message = detector.select_optimal_message(
                        spam_limit_type=spam_limit_type,
                        account_age_days=account_age_days,
                        context=context,
                        user_preferences={'tone': 'polite', 'length': 'medium'}
                    )
                    logger.info(f"Rule-based message selected for {spam_limit_type.value}: {len(selected_message)} chars")
                
                return selected_message
            else:
                logger.warning("Spam detector not available, using random message")
                return random.choice(self.appeal_messages) if self.appeal_messages else "Please review my account restrictions."
            
        except Exception as e:
            logger.error(f"Error in smart message selection: {e}")
            return random.choice(self.appeal_messages) if self.appeal_messages else "Please review my account restrictions."

    async def _click_button(self, event, button_text: str):
        """Click specific button with extremely human-like behavior"""
        try:
            # Realistic human behavior: read message first
            message_length = len(event.message.text or "")
            reading_time = max(2.0, message_length * 0.05)  # Read at human speed
            reading_time += random.uniform(1.0, 3.0)  # Add thinking time
            await asyncio.sleep(reading_time)
            
            # Sometimes hesitate before clicking (like real humans)
            if random.random() < 0.4:  # 40% chance to hesitate
                await asyncio.sleep(random.uniform(0.5, 2.0))
            
            # Look for the button (scanning behavior)
            scan_delay = random.uniform(0.3, 1.2)
            await asyncio.sleep(scan_delay)
            
            for row in event.message.buttons:
                for button in row:
                    if button_text.lower() in button.text.lower():
                        # Small delay before clicking (cursor movement)
                        await asyncio.sleep(random.uniform(0.1, 0.5))
                        await button.click()
                        
                        # Post-click delay (processing/waiting for response)
                        post_click_delay = random.uniform(0.8, 2.5)
                        await asyncio.sleep(post_click_delay)
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
            
            context = ""
            async for message in client.iter_messages("spambot", limit=3):
                if message.text:
                    context += message.text + " "
                    break
            
            # Realistic human behavior: read and think about the situation
            reading_context_time = len(context) * 0.08 + random.uniform(5.0, 12.0)
            await asyncio.sleep(reading_context_time)
            
            # Use intelligent message selection
            appeal_message = await self._select_smart_appeal_message(context)
            
            # Simulate realistic message composition behavior
            await self._simulate_human_message_composition(client, "spambot", appeal_message)
            
            await client.send_message("spambot", appeal_message)
            
            self.active_appeals[user_id]['state'] = 'final_submitted'
            
            # Get spam analysis for better reporting
            spam_analysis = self.active_appeals[user_id].get('spam_analysis', {})
            spam_type = spam_analysis.get('spam_limit_type', {})
            spam_type_name = spam_type.value.replace('_', ' ').title() if hasattr(spam_type, 'value') else 'General'
            
            await self._notify_user(
                user_id,
                f"🤖 **Smart Appeal Submitted**\n\n"
                f"📱 **Account:** {account_name}\n"
                f"Detected Type: {spam_type_name}\n"
                f"Message Length: {len(appeal_message)} characters\n"
                f"Strategy: Auto-optimized for spam type\n\n"
                f"✅ Appeal process completed!"
            )
            
            await self._complete_appeal(user_id, True)
            
        except Exception as e:
            logger.error(f"Error submitting appeal: {e}")
            await self._notify_user(user_id, "❌ Failed to submit appeal message.")

    async def _complete_appeal(self, user_id: int, success: bool):
        """Complete the appeal process"""
        state = self.active_appeals.get(user_id, {})
        mode = state.get('mode', 'auto')
        
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

    async def _get_account_age_days(self) -> int:
        """Get account creation age in days"""
        try:
            for user_id, clients in self.bot_manager.user_clients.items():
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
            
            # Start the appeal process directly
            await self._start_appeal_process(user_id)
            
        except Exception as e:
            logger.error(f"Start appeal for account error: {e}")
            await event.respond("❌ Error starting appeal process.")
    
    async def _simulate_human_message_composition(self, client, target, message: str):
        """Simulate extremely realistic human message composition"""
        # Start typing indicator
        await client.send_typing(target)
        
        # Realistic composition behavior
        words = message.split()
        word_count = len(words)
        
        # Simulate thinking and composing (like writing an appeal)
        base_composition_time = word_count * random.uniform(0.8, 1.5)  # Slower for appeals
        
        # Add pauses for thinking about what to write
        thinking_pauses = random.randint(2, 4)
        for _ in range(thinking_pauses):
            pause_duration = random.uniform(1.0, 4.0)
            base_composition_time += pause_duration
        
        # Break composition into segments (like real writing)
        segments = max(2, word_count // 8)
        segment_time = base_composition_time / segments
        
        for i in range(segments):
            # Compose segment
            await asyncio.sleep(segment_time * random.uniform(0.6, 1.4))
            
            # Occasional longer pauses (thinking, rephrasing)
            if random.random() < 0.5:  # 50% chance
                thinking_pause = random.uniform(1.5, 5.0)
                await asyncio.sleep(thinking_pause)
            
            # Refresh typing indicator (like real typing)
            if i < segments - 1:
                await client.send_typing(target)
        
        # Final review pause before sending
        review_time = random.uniform(2.0, 6.0)
        await asyncio.sleep(review_time)

    async def setup_client_handler(self, user_id: int, client):
        """Setup spambot handler for a specific client"""
        @client.on(events.NewMessage(from_users='spambot'))
        async def handle_spambot_message(event):
            if user_id in self.active_appeals:
                try:
                    await self._process_spambot_response(user_id, event)
                except Exception as e:
                    logger.error(f"Error processing spambot message: {e}")