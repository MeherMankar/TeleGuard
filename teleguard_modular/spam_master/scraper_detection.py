"""Split from contact_scraper.py - scraper_detection"""
        elif spam_type == 'two_way':
            if 'two-way' in msg_lower or 'two way' in msg_lower:
                score += 40
            elif 'restriction' in msg_lower:
                score += 15
        elif spam_type == 'new_account':
            if any(kw in msg_lower for kw in ['new account', 'newly registered', 'recently created']):
                score += 40
            elif 'new' in msg_lower or 'fresh' in msg_lower:
                score += 20
        else:
            # General messages - avoid specific types
            if 'two-way' not in msg_lower and 'two way' not in msg_lower:
                score += 25
        
        # Quality indicators
        quality_words = ['legitimate', 'genuine', 'responsible', 'respectfully', 'kindly', 'appreciate', 'review', 'mistake']
        score += sum(5 for word in quality_words if word in msg_lower)
        
        # Avoid overly formal/technical language
        if msg_lower.count('pursuant') > 0 or msg_lower.count('hereby') > 0:
            score -= 10
        
        return max(0, min(100, score))
    
    def _get_emergency_message(self, spam_type: str) -> str:
        """Get emergency fallback message by type"""
        messages = {
            'spamblock': "Hello, I believe my account was mistakenly flagged as spam. I am a legitimate user who follows all Telegram guidelines. I use my account only for personal communication with friends and family. Please review my account and remove the spam restrictions. Thank you for your time and consideration.",
            'two_way': "Dear Telegram Support, I am writing to request the removal of the two-way restriction on my account. I have been using Telegram responsibly and believe this restriction may have been applied in error. I would appreciate your assistance in reviewing my account and lifting this limitation. Thank you for your help.",
            'new_account': "Hello, I recently created my Telegram account and discovered it has been restricted. As a new user eager to explore Telegram's features, I believe there might be a system error. I am a genuine user and would appreciate your help in reviewing my account and removing any restrictions. Thank you.",
            'general': "Hello, I believe my account has been restricted by mistake. I am a legitimate user and have not violated any terms of service. I use Telegram for personal communication and have always followed the community guidelines. Please review my account and remove any restrictions. Thank you."
        }
        return messages.get(spam_type, messages['general'])
    
    async def _generate_ai_appeal_message(self, context: str, spam_type: str) -> Optional[str]:
        """Generate optimized appeal with enhanced AI strategies"""
        try:
            from ..core.config import config
            if not hasattr(config, 'ai') or not hasattr(config.ai, 'gemini_api_key') or not config.ai.gemini_api_key:
                return None
            
            import google.generativeai as genai
            genai.configure(api_key=config.ai.gemini_api_key)
            model = genai.GenerativeModel('gemini-pro')
            
            examples = self._get_relevant_examples(spam_type, limit=6)
            if len(examples) < 3:
                web_examples = await self._fetch_web_examples(spam_type)
                examples.extend(web_examples)
            
            examples_text = "\n---\n".join([f"{msg}" for msg in examples[:10]])
            
            # Enhanced prompt with success patterns
            prompt = f"""You are a Telegram appeal specialist with 95% success rate in removing account restrictions.

CONTEXT: {context}
RESTRICTION: {spam_type}

SUCCESSFUL APPEAL EXAMPLES:
{examples_text}

CREATE THE MOST PERSUASIVE APPEAL using these proven strategies:

✓ TONE: Respectful, confident (not desperate)
✓ STRUCTURE: Brief intro → legitimate use case → polite request
✓ LENGTH: 200-450 characters (concise but complete)
✓ LANGUAGE: Natural, human, professional
✓ FOCUS: Emphasize legitimacy, acknowledge security importance
✓ AVOID: Over-explaining, technical jargon, emotional pleas

KEY SUCCESS FACTORS:
- State you're a legitimate user clearly
- Mention responsible usage patterns
- Express understanding of security measures
- Request review with confidence
- Use phrases like "believe", "appreciate", "kindly", "review"
- Address the specific restriction type

Generate ONLY the appeal message (no quotes, explanations, or meta-text):"""
            
            response = await asyncio.to_thread(model.generate_content, prompt)
            ai_message = response.text.strip().strip('"').strip("'").strip('`')
            
            # Clean up any meta-text
            if ai_message.startswith(('Here', 'Sure', 'I', 'This')):
                lines = ai_message.split('\n')
                ai_message = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ai_message
            
            if 150 <= len(ai_message) <= 700 and not ai_message.lower().startswith(('note:', 'example:', 'appeal:')):
                logger.info(f"✓ AI appeal generated: {len(ai_message)} chars")
                return ai_message
            
        except Exception as e:
            logger.warning(f"AI generation failed: {e}")
        
        return None
    
    async def _fetch_web_examples(self, spam_type: str) -> list:
        """Generate high-quality examples using AI knowledge"""
        try:
            from ..core.config import config
            if not hasattr(config, 'ai') or not hasattr(config.ai, 'gemini_api_key'):
                return []
            
            import google.generativeai as genai
            genai.configure(api_key=config.ai.gemini_api_key)
            model = genai.GenerativeModel('gemini-pro')
            
            prompt = f"""Generate 4 highly effective Telegram appeal messages for {spam_type} restrictions.

REQUIREMENTS:
- Each 200-450 characters
- Different strategies (formal, casual, technical, empathetic)
- Address {spam_type} specifically
- Proven success patterns
- Natural, human language

FORMAT: Separate with '---'

Generate 4 diverse examples:"""
            
            response = await asyncio.to_thread(model.generate_content, prompt)
            examples = [ex.strip().strip('"').strip("'") for ex in response.text.split('---') if ex.strip() and 100 < len(ex.strip()) < 700]
            logger.info(f"✓ Generated {len(examples)} AI examples")
            return examples[:4]
            
        except Exception as e:
            logger.warning(f"Example generation failed: {e}")
            return []
    
    def _get_relevant_examples(self, spam_type: str, limit: int = 6) -> list:
        """Get high-quality relevant examples with scoring"""
        if not self.appeal_messages:
            return []
        
        scored = [(self._score_message_quality(msg, spam_type), msg) for msg in self.appeal_messages]
        scored = [(score, msg) for score, msg in scored if score > 30]
        scored.sort(reverse=True)
        
        selected = [msg for _, msg in scored[:limit]]
        logger.info(f"✓ Selected {len(selected)} quality examples (scores: {[s for s, _ in scored[:3]]})")
        return selected

    async def _click_button(self, event, button_text: str):
        """Click specific button with human-like delay"""
        try:
            await asyncio.sleep(random.uniform(1.5, 3.5))
            
            # Log available buttons for debugging
            available_buttons = []
            for row in event.message.buttons:
                for button in row:
                    available_buttons.append(button.text)
            logger.info(f"Available buttons: {available_buttons}")
            logger.info(f"Looking for button containing: '{button_text}'")
            
            for row in event.message.buttons:
                for button in row:
                    if button_text.lower() in button.text.lower():
                        logger.info(f"Clicking button: {button.text}")
                        await button.click()
                        await asyncio.sleep(random.uniform(2.5, 4.5))
                        return True
            
            logger.warning(f"Button '{button_text}' not found. Available: {available_buttons}")
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
            client = await self._get_user_client(user_id, account_name)
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
            client = await self._get_user_client(user_id, account_name)
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
            
            # Don't call _complete_appeal here - let the confirmation message trigger it
            
        except Exception as e:
            logger.error(f"Error submitting appeal message for {account_name}: {e}")
            # Only show error if it's a real failure, not just a user ID
            if not (str(e).isdigit() or 'FloodWaitError' in str(type(e).__name__)):
                error_msg = str(e) if str(e) else "Failed to send message to spambot"
                await self._notify_user(user_id, f"❌ Failed to submit appeal message: {error_msg}")

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
