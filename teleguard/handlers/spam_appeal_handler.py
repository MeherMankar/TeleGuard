"""Enhanced handler for appealing spam restrictions with captcha bypass"""

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
    """Handles automated spam appeal process with captcha bypass"""

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
        
        # Fallback messages
        return [
            "Hello, I believe my account has been restricted by mistake. I am a legitimate user and have not violated any terms of service. Please review my account and remove any restrictions.",
            "I am writing to appeal the spam restrictions placed on my account. I have been using Telegram responsibly for legitimate purposes only. Please investigate and lift the restrictions."
        ]

    def register_handlers(self):
        """Register enhanced appeal handlers"""
        
        @self.bot.on(events.NewMessage(pattern=r"^/appeal(?:\s+(.+))?$"))
        async def appeal_command(event):
            user_id = event.sender_id
            account_name = event.pattern_match.group(1) if event.pattern_match.group(1) else None
            
            try:
                if user_id in self.active_appeals:
                    await event.reply("⚠️ You already have an active appeal process. Please wait for it to complete.")
                    return
                
                # Initialize appeal state
                self.active_appeals[user_id] = {
                    'state': 'starting',
                    'account_name': account_name,
                    'captcha_url': None,
                    'start_time': asyncio.get_event_loop().time()
                }
                
                await event.reply(
                    "🛡️ **Starting Spam Appeal Process**\n\n"
                    "I will now initiate an automated appeal with @spambot.\n"
                    "This process includes:\n"
                    "• Automatic captcha handling\n"
                    "• Appeal message submission\n"
                    "• Status monitoring\n\n"
                    "⏳ Please wait..."
                )
                
                # Start the appeal process
                await self._start_appeal_process(user_id)
                
            except Exception as e:
                logger.error(f"Appeal command error: {e}")
                self.active_appeals.pop(user_id, None)
                await event.reply("❌ Error starting the appeal process. Please try again.")

        @self.bot.on(events.NewMessage(pattern=r"^/appeal_status$"))
        async def appeal_status_command(event):
            user_id = event.sender_id
            
            if user_id not in self.active_appeals:
                await event.reply("ℹ️ No active appeal process found.")
                return
                
            state = self.active_appeals[user_id]
            elapsed = int(asyncio.get_event_loop().time() - state['start_time'])
            
            status_text = f"📊 **Appeal Status**\n\n"
            status_text += f"State: {state['state']}\n"
            status_text += f"Elapsed: {elapsed}s\n"
            if state.get('captcha_url'):
                status_text += f"Captcha: Detected\n"
            
            await event.reply(status_text)

        @self.bot.on(events.NewMessage(pattern=r"^/cancel_appeal$"))
        async def cancel_appeal_command(event):
            user_id = event.sender_id
            
            if user_id in self.active_appeals:
                self.active_appeals.pop(user_id)
                await event.reply("❌ Appeal process cancelled.")
            else:
                await event.reply("ℹ️ No active appeal to cancel.")
        
        @self.bot.on(events.NewMessage(pattern=r"^/continue_appeal$"))
        async def continue_appeal_command(event):
            user_id = event.sender_id
            
            if user_id not in self.active_appeals:
                await event.reply("ℹ️ No active appeal process found.")
                return
            
            state = self.active_appeals[user_id]
            if state['state'] == 'waiting_manual_captcha':
                state['state'] = 'captcha_solved'
                await event.reply("✅ Captcha completed. Looking for Done button...")
                await self._auto_click_done(user_id)
            else:
                await event.reply(f"ℹ️ Current state: {state['state']}. Cannot continue from this state.")

        # Spambot handlers will be setup per client

    async def _start_appeal_process(self, user_id: int):
        """Start the automated appeal process"""
        try:
            client = self._get_user_client(user_id)
            if not client:
                await self._notify_user(user_id, "❌ No active account found.")
                self.active_appeals.pop(user_id, None)
                return
            
            await self.setup_client_handler(user_id, client)
            await client.send_message("spambot", "/start")
            
            self.active_appeals[user_id]['state'] = 'waiting_initial_response'
            await self._notify_user(user_id, "✅ Contacted @spambot. Waiting for response...")
            
            asyncio.create_task(self._appeal_timeout(user_id, 300))
            
        except Exception as e:
            logger.error(f"Failed to start appeal process: {e}")
            await self._notify_user(user_id, f"❌ Failed to contact @spambot: {str(e)}")
            self.active_appeals.pop(user_id, None)

    async def _process_spambot_response(self, user_id: int, event):
        """Process response from spambot"""
        state = self.active_appeals[user_id]
        message_text = event.message.text.lower()
        
        # Step 1: Initial response - click "This is a mistake"
        if ("hello" in message_text or "very sorry" in message_text or "anti-spam systems" in message_text) and event.message.buttons:
            await self._click_button(event, "this is a mistake")
            state['state'] = 'clicked_mistake'
            await self._notify_user(user_id, "✅ Clicked 'This is a mistake'")
            
        # Step 2: Complaint confirmation - click "Yes"
        elif "submit a complaint" in message_text and event.message.buttons:
            await self._click_button(event, "yes")
            state['state'] = 'clicked_yes'
            await self._notify_user(user_id, "✅ Clicked 'Yes' to submit complaint")
            
        # Step 3: Never did spam - click "No! Never did that!"
        elif "never sent this to strangers" in message_text and event.message.buttons:
            await self._click_button(event, "no! never did that!")
            state['state'] = 'clicked_never'
            await self._notify_user(user_id, "✅ Clicked 'No! Never did that!'")
            
        # Step 4: Captcha verification
        elif "verify you are a human" in message_text or "telegram.org/captcha" in event.message.text:
            urls = re.findall(r'https://telegram\.org/captcha[^\s\)]+', event.message.text)
            if urls:
                captcha_url = urls[0]
                state['captcha_url'] = captcha_url
                state['state'] = 'captcha_detected'
                
                await self._notify_user(
                    user_id,
                    f"🔍 **Captcha Detected**\n\n"
                    f"URL: `{captcha_url}`\n\n"
                    f"🤖 Attempting bypass..."
                )
                
                success = await self._bypass_captcha(user_id, captcha_url)
                if success:
                    state['state'] = 'captcha_solved'
                    await self._auto_click_done(user_id)
                else:
                    await self._notify_user(
                        user_id,
                        f"⚠️ Manual captcha required: `{captcha_url}`\nUse /continue_appeal when done"
                    )
                    state['state'] = 'waiting_manual_captcha'
                    
        # Step 5: Final submission - click "Done"
        elif "done" in message_text and event.message.buttons:
            await self._click_button(event, "done")
            state['state'] = 'appeal_submitted'
            await self._notify_user(user_id, "✅ Clicked 'Done' - Appeal submitted!")
            await self._complete_appeal(user_id, True)
            
        # Handle appeal form submission
        elif "write me some details" in message_text or "why do you think" in message_text:
            await self._submit_appeal_message(user_id)

    async def _bypass_captcha(self, user_id: int, captcha_url: str) -> bool:
        """Attempt to bypass captcha using advanced methods"""
        try:
            from ..utils.captcha_bypass import captcha_bypass
            
            # Notify user of bypass attempt
            await self._notify_user(
                user_id,
                f"🔄 **Attempting Captcha Bypass**\n\n"
                f"Strategy: Advanced Multi-Method\n"
                f"URL: `{captcha_url}`\n\n"
                f"⏳ This may take 30-60 seconds..."
            )
            
            # Try automatic bypass with multiple strategies
            result = await captcha_bypass.bypass_captcha(captcha_url, strategy="auto")
            
            if result['success']:
                await self._notify_user(
                    user_id,
                    f"✅ **Captcha Bypassed Successfully!**\n\n"
                    f"Method: {result.get('method', 'unknown')}\n"
                    f"Strategy: {result.get('strategy', 'N/A')}\n\n"
                    f"🔄 Continuing with appeal process..."
                )
                return True
            else:
                await self._notify_user(
                    user_id,
                    f"❌ **Automatic Bypass Failed**\n\n"
                    f"Error: {result.get('error', 'Unknown error')}\n"
                    f"Method: {result.get('method', 'unknown')}\n\n"
                    f"🔄 Falling back to manual verification..."
                )
                return False
                
        except Exception as e:
            logger.error(f"Captcha bypass failed: {e}")
            await self._notify_user(
                user_id,
                f"⚠️ **Bypass System Error**\n\n"
                f"Error: {str(e)}\n\n"
                f"🔄 Please complete captcha manually."
            )
            return False

    async def _check_for_continue_button(self, user_id: int):
        """Check for continue button in recent messages"""
        try:
            client = self._get_user_client(user_id)
            if not client:
                return
            
            async for message in client.iter_messages("spambot", limit=3):
                if message.buttons and 'continue' in message.text.lower():
                    await self._handle_continue_button(user_id, message)
                    break
        except Exception as e:
            logger.error(f"Error checking for continue button: {e}")

    async def _click_button(self, event, button_text: str):
        """Click specific button by text"""
        try:
            for row in event.message.buttons:
                for button in row:
                    if button_text.lower() in button.text.lower():
                        await button.click()
                        await asyncio.sleep(1)
                        return True
            return False
        except Exception as e:
            logger.error(f"Error clicking button: {e}")
            return False
    
    async def _auto_click_done(self, user_id: int):
        """Automatically find and click Done button"""
        try:
            client = self._get_user_client(user_id)
            if not client:
                return
            
            await asyncio.sleep(3)
            
            # Check recent messages for Done button
            async for message in client.iter_messages("spambot", limit=10):
                if message.buttons:
                    for row in message.buttons:
                        for button in row:
                            if "done" in button.text.lower():
                                await button.click()
                                await self._notify_user(user_id, "✅ Automatically clicked 'Done' button!")
                                return
            
            # If no Done button found, wait and try again
            await asyncio.sleep(5)
            async for message in client.iter_messages("spambot", limit=5):
                if message.buttons:
                    for row in message.buttons:
                        for button in row:
                            if "done" in button.text.lower():
                                await button.click()
                                await self._notify_user(user_id, "✅ Found and clicked 'Done' button!")
                                return
            
            await self._notify_user(user_id, "⚠️ Done button not found. Please click it manually in spambot chat.")
            
        except Exception as e:
            logger.error(f"Error auto-clicking done: {e}")
            await self._notify_user(user_id, "⚠️ Please click 'Done' button manually in spambot chat.")

    async def _submit_appeal_message(self, user_id: int):
        """Submit appeal message from loaded templates"""
        try:
            client = self._get_user_client(user_id)
            if not client:
                return
            
            # Select random appeal message from loaded file
            appeal_message = random.choice(self.appeal_messages)
            await client.send_message("spambot", appeal_message)
            
            self.active_appeals[user_id]['state'] = 'final_submitted'
            await self._notify_user(
                user_id,
                f"📝 **Appeal Details Submitted**\n\n"
                f"Message: {appeal_message[:150]}...\n\n"
                f"✅ Appeal process completed!"
            )
            
            await self._complete_appeal(user_id, True)
            
        except Exception as e:
            logger.error(f"Error submitting appeal: {e}")
            await self._notify_user(user_id, "❌ Failed to submit appeal message.")

    async def _complete_appeal(self, user_id: int, success: bool):
        """Complete the appeal process"""
        if success:
            await self._notify_user(
                user_id,
                "🎉 **Appeal Process Completed!**\n\n"
                "✅ Your appeal has been successfully submitted to Telegram.\n"
                "📧 You should receive a response within 24-48 hours.\n\n"
                "💡 Check your account restrictions periodically."
            )
        else:
            await self._notify_user(
                user_id,
                "❌ **Appeal Process Failed**\n\n"
                "The automated appeal could not be completed.\n"
                "Please try the manual process or contact support."
            )
        
        # Clean up
        self.active_appeals.pop(user_id, None)

    async def _notify_user(self, user_id: int, message: str):
        """Send notification to user"""
        try:
            await self.bot.send_message(user_id, message)
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")

    async def _appeal_timeout(self, user_id: int, timeout_seconds: int):
        """Handle appeal timeout"""
        await asyncio.sleep(timeout_seconds)
        
        if user_id in self.active_appeals:
            await self._notify_user(
                user_id,
                "⏰ Appeal process timed out. Please try again with /appeal"
            )
            self.active_appeals.pop(user_id, None)
    
    def _get_user_client(self, user_id: int):
        """Get first available user client"""
        try:
            user_clients = self.bot_manager.user_clients.get(user_id, {})
            for client in user_clients.values():
                if client and client.is_connected():
                    return client
            return None
        except Exception as e:
            logger.error(f"Error getting user client: {e}")
            return None
    
    async def setup_client_handler(self, user_id: int, client):
        """Setup spambot handler for a specific client"""
        @client.on(events.NewMessage(from_users='spambot'))
        async def handle_spambot_message(event):
            if user_id in self.active_appeals:
                try:
                    await self._process_spambot_response(user_id, event)
                except Exception as e:
                    logger.error(f"Error processing spambot message: {e}")
