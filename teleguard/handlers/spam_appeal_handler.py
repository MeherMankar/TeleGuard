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
        self.captcha_attempts = {}  # Track captcha attempts per user
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
                
                # Show appeal mode selection
                buttons = [
                    [Button.inline("🤖 Automatic (with captcha bypass)", b"appeal_auto")],
                    [Button.inline("👤 Manual Human Verification", b"appeal_manual")],
                    [Button.inline("❌ Cancel", b"appeal_cancel")]
                ]
                
                await event.reply(
                    "🛡️ **Spam Appeal Process**\n\n"
                    "Choose your preferred appeal method:\n\n"
                    "🤖 **Automatic Mode:**\n"
                    "• AI handles entire process\n"
                    "• Attempts captcha bypass\n"
                    "• Faster but may fail on complex captchas\n\n"
                    "👤 **Manual Mode:**\n"
                    "• Human verification required\n"
                    "• No automatic captcha bypass\n"
                    "• More reliable for complex captchas\n\n"
                    "Select your preferred method:",
                    buttons=buttons
                )
                
            except Exception as e:
                logger.error(f"Appeal command error: {e}")
                await event.reply("❌ Error starting the appeal process. Please try again.")

        @self.bot.on(events.NewMessage(pattern=r"^/appeal_status$"))
        async def appeal_status_command(event):
            user_id = event.sender_id
            
            if user_id not in self.active_appeals:
                await event.reply("ℹ️ No active appeal process found.")
                return
                
            state = self.active_appeals[user_id]
            elapsed = int(asyncio.get_event_loop().time() - state['start_time'])
            mode = state.get('mode', 'auto')
            mode_text = "🤖 Automatic" if mode == "auto" else "👤 Manual"
            
            status_text = f"📊 **Appeal Status**\n\n"
            status_text += f"Mode: {mode_text}\n"
            status_text += f"State: {state['state']}\n"
            status_text += f"Elapsed: {elapsed}s\n"
            
            if state.get('captcha_url'):
                status_text += f"Captcha: Detected\n"
                if mode == "manual" and state['state'] == 'waiting_manual_captcha':
                    status_text += f"\n⚠️ **Action Required:**\n"
                    status_text += f"Complete captcha verification manually\n"
                    status_text += f"Use /continue_appeal for options"
            
            await event.reply(status_text)

        @self.bot.on(events.NewMessage(pattern=r"^/cancel_appeal$"))
        async def cancel_appeal_command(event):
            user_id = event.sender_id
            
            if user_id in self.active_appeals:
                self.active_appeals.pop(user_id)
                await event.reply("❌ Appeal process cancelled.")
            else:
                await event.reply("ℹ️ No active appeal to cancel.")
        
        @self.bot.on(events.NewMessage(pattern=r"^/check_selenium$"))
        async def check_selenium_command(event):
            """Check Selenium setup for captcha bypass"""
            try:
                from ..utils.selenium_check import diagnose_selenium_issue
                
                await event.reply("🔍 Checking Selenium setup...")
                diagnosis = await diagnose_selenium_issue()
                await event.reply(diagnosis)
                
            except Exception as e:
                await event.reply(
                    f"❌ **Selenium Check Failed**\n\n"
                    f"Error: {str(e)}\n\n"
                    f"Please install Selenium manually:\n"
                    f"`pip install selenium webdriver-manager`"
                )
        
        @self.bot.on(events.NewMessage(pattern=r"^/continue_appeal$"))
        async def continue_appeal_command(event):
            user_id = event.sender_id
            
            if user_id not in self.active_appeals:
                await event.reply("ℹ️ No active appeal process found.")
                return
            
            state = self.active_appeals[user_id]
            if state['state'] == 'waiting_manual_captcha':
                buttons = [
                    [Button.inline("✅ I completed the captcha", b"captcha_done")],
                    [Button.inline("🔄 Get new captcha link", b"captcha_refresh")],
                    [Button.inline("❌ Cancel appeal", b"captcha_cancel")]
                ]
                
                captcha_url = state.get('captcha_url', 'Not available')
                await event.reply(
                    f"🔄 **Continue Appeal Process**\n\n"
                    f"Current captcha: `{captcha_url}`\n\n"
                    f"Please complete the captcha verification and confirm below:",
                    buttons=buttons
                )
            else:
                await event.reply(
                    f"ℹ️ **Current State:** {state['state']}\n\n"
                    f"Cannot continue from this state.\n"
                    f"Use /appeal_status to check progress."
                )

        @self.bot.on(events.CallbackQuery(pattern=b"appeal_(auto|manual|cancel)"))
        async def appeal_mode_callback(event):
            user_id = event.sender_id
            mode = event.data.decode().split('_')[1]
            
            try:
                await event.delete()
                
                if mode == "cancel":
                    await event.respond("❌ Appeal process cancelled.")
                    return
                
                # Initialize appeal state with selected mode
                self.active_appeals[user_id] = {
                    'state': 'starting',
                    'mode': mode,  # 'auto' or 'manual'
                    'captcha_url': None,
                    'start_time': asyncio.get_event_loop().time()
                }
                
                if mode == "auto":
                    await event.respond(
                        "🤖 **Automatic Appeal Mode**\n\n"
                        "Starting automated process with captcha bypass...\n"
                        "⏳ Please wait..."
                    )
                else:  # manual
                    await event.respond(
                        "👤 **Manual Human Verification Mode**\n\n"
                        "Starting manual verification process...\n"
                        "You will handle captchas manually.\n"
                        "⏳ Please wait..."
                    )
                
                # Start the appeal process
                await self._start_appeal_process(user_id)
                
            except Exception as e:
                logger.error(f"Appeal mode callback error: {e}")
                await event.respond("❌ Error starting the appeal process. Please try again.")

        @self.bot.on(events.NewMessage(pattern=r"^/appeal_help$"))
        async def appeal_help_command(event):
            """Show detailed appeal help and troubleshooting"""
            help_text = (
                "🎆 **Spam Appeal System Help**\n\n"
                "🚀 **Quick Start:**\n"
                "/appeal - Start appeal process (choose mode)\n"
                "/appeal_status - Check current appeal status\n"
                "/continue_appeal - Continue after manual captcha\n"
                "/cancel_appeal - Cancel active appeal\n\n"
                "🔧 **Troubleshooting:**\n"
                "/check_selenium - Test captcha bypass setup\n"
                "/appeal_help - Show this help message\n\n"
                "🤖 **Automatic Mode:**\n"
                "1. Bot contacts @spambot automatically\n"
                "2. Navigates through appeal questions\n"
                "3. Attempts automatic captcha bypass\n"
                "4. Falls back to manual if needed\n"
                "5. Submits AI-selected appeal message\n\n"
                "👤 **Manual Mode:**\n"
                "1. Bot contacts @spambot automatically\n"
                "2. Navigates through appeal questions\n"
                "3. Prompts you for manual captcha completion\n"
                "4. You complete captcha in browser\n"
                "5. Submits AI-selected appeal message\n\n"
                "⚠️ **Manual Steps (if automation fails):**\n"
                "1. Go to @spambot in Telegram\n"
                "2. Send /start\n"
                "3. Click 'This is a mistake'\n"
                "4. Click 'Yes' to submit complaint\n"
                "5. Click 'No! Never did that!'\n"
                "6. Complete captcha verification\n"
                "7. Click 'Done' to finish\n\n"
                "📞 **Need Help?** Contact support for assistance."
            )
            await event.reply(help_text)
        
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
                    self.captcha_attempts.pop(user_id, None)
                    await event.respond("❌ Appeal process cancelled.")
                    return
                
                elif action == "refresh":
                    await event.respond(
                        "🔄 **Refreshing Captcha**\n\n"
                        "Requesting new captcha from @spambot...\n"
                        "⏳ Please wait..."
                    )
                    
                    client = self._get_user_client(user_id)
                    if client:
                        async for message in client.iter_messages("spambot", limit=5):
                            if "telegram.org/captcha" in message.text:
                                urls = re.findall(r'https://telegram\.org/captcha[^\s\)]+', message.text)
                                if urls:
                                    new_captcha_url = urls[0]
                                    state['captcha_url'] = new_captcha_url
                                    await self._handle_manual_captcha(user_id, new_captcha_url)
                                    return
                        
                        await event.respond("⚠️ No fresh captcha found. Please go to @spambot manually.")
                    else:
                        await event.respond("❌ No active client found.")
                
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
            await self._notify_user(
                user_id, 
                "✅ **Contacted @spambot**\n\n"
                "Waiting for initial response...\n"
                "⏱️ This usually takes 5-10 seconds.\n\n"
                "Use /appeal_status to check progress."
            )
            
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
                
                # Check if manual mode is selected
                if state.get('mode') == 'manual':
                    await self._handle_manual_captcha(user_id, captcha_url)
                    return
                
                # Automatic mode with bypass attempts
                if user_id not in self.captcha_attempts:
                    self.captcha_attempts[user_id] = 0
                self.captcha_attempts[user_id] += 1
                
                if self.captcha_attempts[user_id] > 3:
                    await self._notify_user(
                        user_id,
                        f"⚠️ **Too Many Captcha Attempts**\n\n"
                        f"The system has attempted {self.captcha_attempts[user_id]} captchas.\n"
                        f"Switching to manual verification...\n\n"
                        f"**Manual Steps:**\n"
                        f"1. Go to @spambot\n"
                        f"2. Complete captcha: `{captcha_url}`\n"
                        f"3. Use /continue_appeal when done\n\n"
                        f"The appeal process will continue automatically."
                    )
                    state['mode'] = 'manual'  # Switch to manual mode
                    await self._handle_manual_captcha(user_id, captcha_url)
                    return
                
                await self._notify_user(
                    user_id,
                    f"🔍 **Captcha Detected (#{self.captcha_attempts[user_id]})**\n\n"
                    f"URL: `{captcha_url}`\n\n"
                    f"🤖 Attempting automatic bypass..."
                )
                
                success = await self._bypass_captcha(user_id, captcha_url)
                if success:
                    state['state'] = 'captcha_solved'
                    await asyncio.sleep(5)  # Wait longer before clicking Done
                    await self._auto_click_done(user_id)
                else:
                    # Fallback to manual mode
                    state['mode'] = 'manual'
                    await self._handle_manual_captcha(user_id, captcha_url)
                    
        # Step 5: Final submission - click "Done"
        elif "done" in message_text and event.message.buttons:
            await self._click_button(event, "done")
            state['state'] = 'appeal_submitted'
            await self._notify_user(user_id, "✅ Clicked 'Done' - Appeal submitted!")
            await self._complete_appeal(user_id, True)
            
        # Handle appeal form submission
        elif "write me some details" in message_text or "why do you think" in message_text:
            await self._submit_appeal_message(user_id)
            
        # Handle already submitted complaint
        elif "already submitted a complaint" in message_text or "supervisors will check" in message_text:
            state['state'] = 'already_submitted'
            await self._notify_user(user_id, "ℹ️ Appeal already exists. Supervisors will review it soon.")
            await self._complete_appeal(user_id, True)

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
                error_msg = result.get('error', 'Unknown error')
                manual_url = result.get('manual_url', captcha_url)
                
                await self._notify_user(
                    user_id,
                    f"❌ **Automatic Bypass Failed**\n\n"
                    f"Error: {error_msg}\n"
                    f"Method: {result.get('method', 'unknown')}\n\n"
                    f"🔄 **Manual Verification Required**\n"
                    f"Please open: `{manual_url}`\n\n"
                    f"**Instructions:**\n"
                    f"1. Click the link above\n"
                    f"2. Complete the verification\n"
                    f"3. Return here and use /continue_appeal"
                )
                return False
                
        except Exception as e:
            logger.error(f"Captcha bypass failed: {e}")
            await self._notify_user(
                user_id,
                f"⚠️ **Bypass System Error**\n\n"
                f"Error: {str(e)}\n\n"
                f"🔄 **Manual Completion Required**\n"
                f"Please open: `{captcha_url}`\n\n"
                f"Complete the captcha and use /continue_appeal when done."
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
            
            await self._notify_user(
                user_id, 
                "⚠️ **Done Button Not Found**\n\n"
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
                "⚠️ **Manual Action Required**\n\n"
                "Please go to @spambot and click the 'Done' button to complete your appeal."
            )

    async def _submit_appeal_message(self, user_id: int):
        """Submit AI-selected appeal message based on spam bot context"""
        try:
            client = self._get_user_client(user_id)
            if not client:
                return
            
            # Get recent spam bot message for context
            context = ""
            async for message in client.iter_messages("spambot", limit=3):
                if message.text:
                    context += message.text + " "
                    break
            
            # AI-powered message selection
            appeal_message = await self._select_smart_appeal_message(context)
            await client.send_message("spambot", appeal_message)
            
            self.active_appeals[user_id]['state'] = 'final_submitted'
            await self._notify_user(
                user_id,
                f"🤖 **AI-Selected Appeal Submitted**\n\n"
                f"Message: {appeal_message[:150]}...\n\n"
                f"✅ Appeal process completed!"
            )
            
            await self._complete_appeal(user_id, True)
            
        except Exception as e:
            logger.error(f"Error submitting appeal: {e}")
            await self._notify_user(user_id, "❌ Failed to submit appeal message.")

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
                f"⚠️ **No automatic bypass will be attempted in manual mode**"
            )
            
            await self.bot.send_message(user_id, "Choose an action:", buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error handling manual captcha: {e}")
            await self._notify_user(user_id, "❌ Error setting up manual verification.")

    async def _complete_appeal(self, user_id: int, success: bool):
        """Complete the appeal process"""
        state = self.active_appeals.get(user_id, {})
        mode = state.get('mode', 'auto')
        
        if success:
            mode_text = "🤖 Automatic" if mode == "auto" else "👤 Manual"
            await self._notify_user(
                user_id,
                f"🎉 **Appeal Process Completed!**\n\n"
                f"Mode: {mode_text}\n"
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
                f"3. Check /check_selenium for captcha issues\n"
                f"4. Contact support if problems persist"
            )
        
        # Clean up
        self.active_appeals.pop(user_id, None)
        self.captcha_attempts.pop(user_id, None)

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
                "⏰ **Appeal Process Timed Out**\n\n"
                "The automated process took too long.\n\n"
                "**What to do:**\n"
                "• Try /appeal again\n"
                "• Check @spambot manually\n"
                "• Use /appeal_help for guidance"
            )
            self.active_appeals.pop(user_id, None)
            self.captcha_attempts.pop(user_id, None)
    
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
    
    async def _select_smart_appeal_message(self, context: str) -> str:
        """AI-powered appeal message selection based on context and account age"""
        try:
            context_lower = context.lower()
            
            # Get account age
            account_age_days = await self._get_account_age_days()
            is_new_account = account_age_days < 30  # Less than 30 days = new
            
            # Age-based selection first
            if is_new_account:
                new_keywords = ['new', 'recently', 'just created', 'started using', 'first time']
                new_messages = [msg for msg in self.appeal_messages if any(kw in msg.lower() for kw in new_keywords)]
                if new_messages:
                    return random.choice(new_messages)
            else:
                old_keywords = ['long time', 'years', 'experienced', 'regular user', 'always used']
                old_messages = [msg for msg in self.appeal_messages if any(kw in msg.lower() for kw in old_keywords)]
                if old_messages:
                    return random.choice(old_messages)
            
            # Context-based selection
            if any(word in context_lower for word in ['advertising', 'promotional', 'spam']):
                personal_messages = [msg for msg in self.appeal_messages if 'personal' in msg.lower() or 'friends' in msg.lower()]
                if personal_messages:
                    return random.choice(personal_messages)
            
            elif any(word in context_lower for word in ['mistake', 'error', 'wrong']):
                mistake_messages = [msg for msg in self.appeal_messages if 'mistake' in msg.lower() or 'error' in msg.lower()]
                if mistake_messages:
                    return random.choice(mistake_messages)
            
            elif any(word in context_lower for word in ['details', 'explain', 'why']):
                detailed_messages = [msg for msg in self.appeal_messages if len(msg) > 100]
                if detailed_messages:
                    return random.choice(detailed_messages)
            
            return random.choice(self.appeal_messages)
            
        except Exception as e:
            logger.error(f"Error in smart message selection: {e}")
            return random.choice(self.appeal_messages)
    
    async def _get_account_age_days(self) -> int:
        """Get account creation age in days"""
        try:
            # Get first available user client
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
    
    async def setup_client_handler(self, user_id: int, client):
        """Setup spambot handler for a specific client"""
        @client.on(events.NewMessage(from_users='spambot'))
        async def handle_spambot_message(event):
            if user_id in self.active_appeals:
                try:
                    await self._process_spambot_response(user_id, event)
                except Exception as e:
                    logger.error(f"Error processing spambot message: {e}")
