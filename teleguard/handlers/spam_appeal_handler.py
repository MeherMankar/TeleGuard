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
from ..utils.crypto_utils import DataEncryption

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
            messages_file = (
                Path(__file__).parent.parent / "data" / "appeal_messages.txt"
            )
            logger.info(f"Attempting to load appeal messages from: {messages_file}")

            if messages_file.exists():
                content = messages_file.read_text(encoding="utf-8")
                # Split by double newlines and filter out empty messages
                messages = [
                    msg.strip()
                    for msg in content.split("\n\n")
                    if msg.strip() and len(msg.strip()) > 50
                ]
                logger.info(
                    f"Successfully loaded {len(messages)} appeal messages from file"
                )

                # Log first few messages for verification
                for i, msg in enumerate(messages[:3]):
                    logger.debug(f"Appeal message {i + 1} preview: {msg[:100]}...")

                return messages
            else:
                logger.warning(f"Appeal messages file not found: {messages_file}")
        except Exception as e:
            logger.error(f"Failed to load appeal messages: {e}")

        # Return default messages if file loading fails
        default_messages = [
            "Hello, I believe my account has been restricted by mistake. I am a legitimate user and have not violated any terms of service. I use Telegram for personal communication with friends and family. Please review my account and remove any restrictions. Thank you for your time and consideration.",
            "I am writing to appeal the spam restrictions placed on my account. I have been using Telegram responsibly for legitimate purposes only. I believe this restriction was applied in error. I would appreciate if you could review my case and restore my account to normal status.",
            "Dear Telegram Support, my account has been flagged as spam, but I assure you this is a mistake. I only use Telegram to communicate with close contacts and have never engaged in spam activities. Please investigate and lift the restrictions on my account.",
        ]
        logger.info(f"Using {len(default_messages)} default appeal messages")
        return default_messages

    def register_handlers(self):
        """Register appeal handlers with smart detection"""
        self.bot.on(events.NewMessage(pattern=r"^/spam_stats$"))(self._spam_stats_handler)
        self.bot.on(events.NewMessage(pattern=r"^/test_appeal_messages$"))(self._test_appeal_messages_handler)
        self.bot.on(events.NewMessage(pattern=r"^/appeal(?:\s+(.+))?$"))(self._appeal_command_handler)
        self.bot.on(events.CallbackQuery(pattern=b"appeal_account_id:(.+)"))(self._appeal_account_callback_handler)
        self.bot.on(events.CallbackQuery(pattern=b"appeal_cancel"))(self._appeal_cancel_handler)
        self.bot.on(events.CallbackQuery(pattern=b"captcha_(done|refresh|cancel)"))(self._captcha_callback_handler)

    async def _start_appeal_process(self, user_id: int):
        """Start the automated appeal process"""
        try:
            # Check if appeal exists
            if user_id not in self.active_appeals:
                logger.error(f"No active appeal found for user {user_id}")
                return

            # Prevent duplicate appeals (but allow 'new' state to proceed)
            current_state = self.active_appeals[user_id].get("state")
            if current_state and current_state not in ["new", "starting"]:
                logger.info(
                    f"Appeal already in progress for user {user_id}, state: {current_state}"
                )
                return

            account_name = self.active_appeals[user_id].get(
                "account_name", "Unknown Account"
            )
            logger.info(f"Getting client for account: {account_name}")
            client = await self._get_user_client(user_id, account_name)

            if not client:
                await self._notify_user(
                    user_id, f"❌ Account '{account_name}' not connected."
                )
                self.active_appeals.pop(user_id, None)
                return

            if not client.is_connected():
                await self._notify_user(
                    user_id, f"❌ Account '{account_name}' not connected."
                )
                self.active_appeals.pop(user_id, None)
                return

            # Verify we got the correct client
            try:
                me = await client.get_me()
                actual_name = me.first_name or "Unknown"
                logger.info(
                    f"Using client for: {actual_name} (requested: {account_name})"
                )
            except Exception as e:
                logger.warning(f"Could not verify client identity: {e}")

            self.active_appeals[user_id]["state"] = "starting"
            await self._notify_user(
                user_id,
                f"🛡️ **Starting Appeal for {account_name}**\n\n⏳ This may take 30 seconds to 1 minute...",
            )

            # Setup handler first
            await self.setup_client_handler(user_id, client)
            logger.info(f"Handler setup complete for {account_name}")

            # Longer delay before sending /start (human reads, thinks)
            await asyncio.sleep(random.uniform(8.0, 15.0))

            # Try both bot usernames
            bot_username = "spambot"
            try:
                logger.info(f"Sending /start to {bot_username} for {account_name}")
                await client.send_message(bot_username, "/start")
                logger.info(f"Sent /start to {bot_username} for {account_name}")
                await asyncio.sleep(random.uniform(5.0, 8.0))
            except Exception as e:
                logger.warning(f"Failed with {bot_username}, trying SpamBot: {e}")
                bot_username = "SpamBot"
                await client.send_message(bot_username, "/start")
                logger.info(f"Sent /start to {bot_username} for {account_name}")
                await asyncio.sleep(random.uniform(5.0, 8.0))

            self.active_appeals[user_id]["state"] = "waiting_initial_response"
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
        account_name = state.get("account_name", "Unknown Account")

        logger.info(
            f"Processing spambot message for {account_name}: {message_text[:100]}..."
        )

        # Prevent processing same message multiple times
        if state.get("last_processed_msg") == event.message.id:
            logger.debug(f"Skipping duplicate message {event.message.id}")
            return
        state["last_processed_msg"] = event.message.id

        # Detect restriction type and bot type
        is_spam_info_bot = "subscribe to telegram premium" in message_text
        has_captcha = "sorry that you had to contact" in message_text

        if is_spam_info_bot:
            state["bot_type"] = "spam_info_bot"  # No captcha flow
        elif has_captcha:
            state["bot_type"] = "regular_spambot"  # With captcha flow

        # 1. No restrictions - account is clean
        if "good news" in message_text and "no limits" in message_text:
            await self._notify_user(
                user_id,
                f"🎉 **{account_name}: No Restrictions**\n\nYour account is clean! No action needed.",
            )
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
                f"• Premium users get shorter times",
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
                f"Include phone number and details",
            )
            self.active_appeals.pop(user_id, None)
            return

        # Flow 1: Spam Info Bot (no captcha, phone number issue)
        if state.get("bot_type") == "spam_info_bot":
            # Step 1: Initial message with "Submit a complaint" button
            if (
                "harsh response from our anti-spam systems" in message_text
                and event.message.buttons
            ):
                await self._notify_user(
                    user_id,
                    f"⚠️ **{account_name}**: Spam Info Bot detected! Starting appeal...",
                )
                await self._click_button(event, "submit a complaint")
                return

            # Step 2: Confirmation about not sending spam
            elif "never send this to strangers" in message_text:
                await self._notify_user(
                    user_id, f"🔘 **{account_name}**: Sending confirmation response..."
                )
                client = await self._get_user_client(user_id, account_name)
                if client:
                    await asyncio.sleep(random.uniform(2.0, 4.0))
                    await client.send_message(
                        "spambot", "No, I'll never do any of this!"
                    )
                    await self._notify_user(
                        user_id, f"✅ **{account_name}**: Confirmation sent!"
                    )
                return

            # Step 3: Request for appeal details (no captcha)
            elif (
                "write me some details" in message_text
                or "why do you think your account was limited" in message_text
            ):
                await self._submit_appeal_message(user_id)
                return

            # Already submitted
            elif (
                "already submitted" in message_text
                or "supervisors will check" in message_text
            ):
                await self._notify_user(
                    user_id,
                    f"ℹ️ **{account_name}**: Appeal submitted! Supervisors will review.",
                )
                await self._complete_appeal(user_id, True)
                return

        # Flow 2: Regular spambot (with captcha, user behavior issue)
        elif state.get("bot_type") == "regular_spambot":
            # Step 1: Click "This is a mistake" - initial spambot message
            if (
                "sorry that you had to contact" in message_text
                or "anti-spam" in message_text
                or "some actions can trigger" in message_text
            ) and event.message.buttons:
                await self._notify_user(
                    user_id,
                    f"⚠️ **{account_name}**: Restriction detected! Starting appeal process...",
                )
                await self._click_button(event, "this is a mistake")
                return

            # Step 2: Click "Yes" to submit complaint
            elif "submit a complaint" in message_text and event.message.buttons:
                await self._click_button(event, "yes")
                return

            # Step 3: Click "No! Never did that!"
            elif (
                "never sent this to strangers" in message_text and event.message.buttons
            ):
                await self._click_button(event, "no! never did that!")
                return

            # Step 4: Handle captcha
            elif (
                "verify you are a human" in message_text
                or "telegram.org/captcha" in event.message.text
            ):
                urls = re.findall(
                    r"https://telegram\.org/captcha[^\s\)]+", event.message.text
                )
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
                await self._notify_user(
                    user_id, f"ℹ️ **{account_name}**: Appeal already exists."
                )
                await self._complete_appeal(user_id, True)
                return

    async def _select_smart_appeal_message(
        self, context: str, user_id: int = None, account_name: str = None
    ) -> str:
        """Enhanced AI-powered appeal message with multi-strategy optimization"""
        try:
            spam_type_keywords = {
                "spamblock": [
                    "spamblock",
                    "spam block",
                    "flagged as spam",
                    "spam restrictions",
                    "spam limitation",
                    "spam-related",
                ],
                "new_account": [
                    "new account",
                    "recently created",
                    "fresh",
                    "just created",
                    "newly registered",
                ],
                "two_way": [
                    "two-way restriction",
                    "two way restriction",
                    "dual verification",
                    "two-step",
                ],
            }

            detected_spam_type = "general"
            context_lower = context.lower()

            for spam_type, keywords in spam_type_keywords.items():
                if any(kw in context_lower for kw in keywords):
                    detected_spam_type = spam_type
                    break

            logger.info(f"Spam type: {detected_spam_type} | Context: {context[:80]}...")

            # Try AI generation with enhanced prompts
            ai_message = await self._generate_ai_appeal_message(
                context, detected_spam_type
            )
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
                logger.info(
                    f"✓ Template selected: {
                        len(selected)} chars (score: {
                        scored_messages[0][0]})"
                )
                return selected

            return self._get_emergency_message(detected_spam_type)

        except Exception as e:
            logger.error(f"Message selection error: {e}")
            return self._get_emergency_message("general")

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
        if spam_type == "spamblock":
            if "spamblock" in msg_lower or "spam block" in msg_lower:
                score += 40
            elif "spam" in msg_lower:
                score += 20
        elif spam_type == "two_way":
            if "two-way" in msg_lower or "two way" in msg_lower:
                score += 40
            elif "restriction" in msg_lower:
                score += 15
        elif spam_type == "new_account":
            if any(
                kw in msg_lower
                for kw in ["new account", "newly registered", "recently created"]
            ):
                score += 40
            elif "new" in msg_lower or "fresh" in msg_lower:
                score += 20
        else:
            # General messages - avoid specific types
            if "two-way" not in msg_lower and "two way" not in msg_lower:
                score += 25

        # Quality indicators
        quality_words = [
            "legitimate",
            "genuine",
            "responsible",
            "respectfully",
            "kindly",
            "appreciate",
            "review",
            "mistake",
        ]
        score += sum(5 for word in quality_words if word in msg_lower)

        # Avoid overly formal/technical language
        if msg_lower.count("pursuant") > 0 or msg_lower.count("hereby") > 0:
            score -= 10

        return max(0, min(100, score))

    def _get_emergency_message(self, spam_type: str) -> str:
        """Get emergency fallback message by type"""
        messages = {
            "spamblock": "Hello, I believe my account was mistakenly flagged as spam. I am a legitimate user who follows all Telegram guidelines. I use my account only for personal communication with friends and family. Please review my account and remove the spam restrictions. Thank you for your time and consideration.",
            "two_way": "Dear Telegram Support, I am writing to request the removal of the two-way restriction on my account. I have been using Telegram responsibly and believe this restriction may have been applied in error. I would appreciate your assistance in reviewing my account and lifting this limitation. Thank you for your help.",
            "new_account": "Hello, I recently created my Telegram account and discovered it has been restricted. As a new user eager to explore Telegram's features, I believe there might be a system error. I am a genuine user and would appreciate your help in reviewing my account and removing any restrictions. Thank you.",
            "general": "Hello, I believe my account has been restricted by mistake. I am a legitimate user and have not violated any terms of service. I use Telegram for personal communication and have always followed the community guidelines. Please review my account and remove any restrictions. Thank you.",
        }
        return messages.get(spam_type, messages["general"])

    async def _generate_ai_appeal_message(
        self, context: str, spam_type: str
    ) -> Optional[str]:
        """Generate optimized appeal with enhanced AI strategies"""
        try:
            from ..core.config import config

            if (
                not hasattr(config, "ai")
                or not hasattr(config.ai, "gemini_api_key")
                or not config.ai.gemini_api_key
            ):
                return None

            import google.generativeai as genai

            genai.configure(api_key=config.ai.gemini_api_key)
            model = genai.GenerativeModel("gemini-pro")

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
            ai_message = response.text.strip().strip('"').strip("'").strip("`")

            # Clean up any meta-text
            if ai_message.startswith(("Here", "Sure", "I", "This")):
                lines = ai_message.split("\n")
                ai_message = (
                    "\n".join(lines[1:]).strip() if len(lines) > 1 else ai_message
                )

            if 150 <= len(ai_message) <= 700 and not ai_message.lower().startswith(
                ("note:", "example:", "appeal:")
            ):
                logger.info(f"✓ AI appeal generated: {len(ai_message)} chars")
                return ai_message

        except Exception as e:
            logger.warning(f"AI generation failed: {e}")

        return None

    async def _fetch_web_examples(self, spam_type: str) -> list:
        """Generate high-quality examples using AI knowledge"""
        try:
            from ..core.config import config

            if not hasattr(config, "ai") or not hasattr(config.ai, "gemini_api_key"):
                return []

            import google.generativeai as genai

            genai.configure(api_key=config.ai.gemini_api_key)
            model = genai.GenerativeModel("gemini-pro")

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
            examples = [
                ex.strip().strip('"').strip("'")
                for ex in response.text.split("---")
                if ex.strip() and 100 < len(ex.strip()) < 700
            ]
            logger.info(f"✓ Generated {len(examples)} AI examples")
            return examples[:4]

        except Exception as e:
            logger.warning(f"Example generation failed: {e}")
            return []

    def _get_relevant_examples(self, spam_type: str, limit: int = 6) -> list:
        """Get high-quality relevant examples with scoring"""
        if not self.appeal_messages:
            return []

        scored = [
            (self._score_message_quality(msg, spam_type), msg)
            for msg in self.appeal_messages
        ]
        scored = [(score, msg) for score, msg in scored if score > 30]
        scored.sort(reverse=True)

        selected = [msg for _, msg in scored[:limit]]
        logger.info(
            f"✓ Selected {len(selected)} quality examples (scores: {[s for s, _ in scored[:3]]})"
        )
        return selected

    async def _click_button(self, event, button_text: str):
        """Click specific button with human-like delay"""
        try:
            await asyncio.sleep(random.uniform(4.0, 8.0))

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
                        await asyncio.sleep(random.uniform(5.0, 10.0))
                        return True

            logger.warning(
                f"Button '{button_text}' not found. Available: {available_buttons}"
            )
            return False
        except Exception as e:
            logger.error(f"Error clicking button: {e}")
            return False

    async def _handle_manual_captcha(self, user_id: int, captcha_url: str):
        """Handle manual captcha verification process"""
        try:
            state = self.active_appeals[user_id]
            state["state"] = "waiting_manual_captcha"

            buttons = [
                [Button.inline("✅ I completed the captcha", b"captcha_done")],
                [Button.inline("🔄 Get new captcha link", b"captcha_refresh")],
                [Button.inline("❌ Cancel appeal", b"captcha_cancel")],
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
                f"⚠️ **Manual verification required for all captchas**",
            )

            await self.bot.send_message(user_id, "Choose an action:", buttons=buttons)

        except Exception as e:
            logger.error(f"Error handling manual captcha: {e}")
            await self._notify_user(user_id, "❌ Error setting up manual verification.")

    async def _auto_click_done(self, user_id: int):
        """Automatically find and click Done button"""
        try:
            # Get account name and specific client
            account_name = self.active_appeals[user_id].get(
                "account_name", "Unknown Account"
            )
            client = await self._get_user_client(user_id, account_name)
            if not client:
                await self._notify_user(
                    user_id, f"❌ Account '{account_name}' client not found."
                )
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
                                await self._notify_user(
                                    user_id,
                                    f"✅ **{account_name}:** Automatically clicked 'Done' button!",
                                )
                                return

            await self._notify_user(
                user_id,
                f"⚠️ **{account_name}: Done Button Not Found**\n\n"
                "Please manually:\n"
                "1. Go to @spambot chat\n"
                "2. Look for 'Done' button\n"
                "3. Click it to complete the appeal\n\n"
                "If no button is visible, the appeal may already be submitted.",
            )
        except Exception as e:
            logger.error(f"Error auto-clicking done: {e}")
            await self._notify_user(
                user_id,
                f"⚠️ **{account_name}: Manual Action Required**\n\n"
                "Please go to @spambot and click the 'Done' button to complete your appeal.",
            )

    async def _submit_appeal_message(self, user_id: int):
        """Submit AI-selected appeal message with extremely human-like behavior"""
        try:
            # Get account name and specific client
            account_name = self.active_appeals[user_id].get(
                "account_name", "Unknown Account"
            )
            client = await self._get_user_client(user_id, account_name)
            if not client:
                await self._notify_user(
                    user_id, f"❌ Account '{account_name}' client not found."
                )
                return

            # Get context from stored data or recent messages
            context = self.active_appeals[user_id].get("context", "")
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
                    age_display += (
                        f", {age_months} month{'s' if age_months != 1 else ''}"
                    )
            elif age_months > 0:
                age_display = f"{age_months} month{'s' if age_months != 1 else ''}"
            else:
                age_display = (
                    f"{account_age_days} day{'s' if account_age_days != 1 else ''}"
                )

            # Use intelligent message selection with account age filtering
            appeal_message = await self._select_smart_appeal_message(
                context, user_id, account_name
            )

            # Log the selected message for debugging
            logger.info(
                f"Selected appeal message for {account_name}: {
                    len(appeal_message)} chars"
            )
            logger.debug(f"Appeal message preview: {appeal_message[:100]}...")

            # Check if sending appeal message is safe
            session_id = f"{user_id}_{account_name}"
            await session_protection.check_message_safety(
                session_id, appeal_message, "spambot"
            )

            # Notify user that message is being sent with account age
            await self._notify_user(
                user_id,
                f"📝 **Sending Appeal Message**\n\n"
                f"📱 Account: {account_name}\n"
                f"📅 Account Age: {age_display} ({account_age_days} days)\n"
                f"📄 Message Length: {len(appeal_message)} characters\n"
                f"⏳ Composing message with human-like behavior...",
            )

            # Simulate realistic message composition behavior
            await self._simulate_human_message_composition(
                client, "spambot", appeal_message
            )

            # Send the appeal message
            logger.info(f"Sending appeal message to spambot for account {account_name}")
            await client.send_message("spambot", appeal_message)
            logger.info(f"Appeal message sent successfully for account {account_name}")

            # Record message for protection tracking
            await session_protection.record_message_sent(session_id)

            self.active_appeals[user_id]["state"] = "final_submitted"

            # Get spam analysis for better reporting
            spam_analysis = self.active_appeals[user_id].get("spam_analysis", {})
            spam_type = spam_analysis.get("spam_limit_type", {})
            spam_type_name = (
                spam_type.value.replace("_", " ").title()
                if hasattr(spam_type, "value")
                else "General"
            )

            await self._notify_user(
                user_id,
                f"🤖 **Smart Appeal Submitted**\n\n"
                f"📱 **Account:** {account_name}\n"
                f"📄 **Message Sent:** {len(appeal_message)} characters\n"
                f"🎯 **Detected Type:** {spam_type_name}\n"
                f"🔧 **Strategy:** Auto-optimized for spam type\n\n"
                f"✅ **Appeal message successfully sent to @spambot!**\n\n"
                f"📧 You should receive a response within 24-48 hours.",
            )

            # Don't call _complete_appeal here - let the confirmation message trigger it

        except Exception as e:
            logger.error(f"Error submitting appeal message for {account_name}: {e}")
            # Only show error if it's a real failure, not just a user ID
            if not (str(e).isdigit() or "FloodWaitError" in str(type(e).__name__)):
                error_msg = str(e) if str(e) else "Failed to send message to spambot"
                await self._notify_user(
                    user_id, f"❌ Failed to submit appeal message: {error_msg}"
                )

    async def _complete_appeal(self, user_id: int, success: bool):
        """Complete the appeal process"""
        state = self.active_appeals.get(user_id, {})
        mode = state.get("mode", "auto")

        # Re-enable session protection after appeal completion
        try:
            from ..core.mongo_database import mongodb

            await mongodb.db.accounts.update_many(
                {"user_id": user_id},
                {
                    "$unset": {
                        "session_protection_disabled": "",
                        "protection_bypass_until": "",
                    }
                },
            )
        except Exception as e:
            logger.error(f"Error re-enabling session protection: {e}")

        if success:
            mode_text = "🤖 Automatic" if mode == "auto" else "👤 Manual"
            account_name = state.get("account_name", "Unknown Account")
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
                f"🔄 If no response after 72 hours, you can submit another appeal.",
            )
        else:
            await self._notify_user(
                user_id,
                "❌ **Appeal Process Failed**\n\n"
                "The appeal could not be completed.\n\n"
                "**Options:**\n"
                "1. Try /appeal again (choose different mode)\n"
                "2. Use /appeal_help for manual steps\n"
                "3. Contact support if problems persist",
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
                "• Use /appeal_help for guidance",
            )
            self.active_appeals.pop(user_id, None)

    async def _get_account_age_days(
        self, user_id: int = None, account_name: str = None
    ) -> int:
        """Get specific account creation age in days"""
        try:
            from datetime import datetime, timezone

            # Get specific client if provided
            if user_id and account_name:
                client = await self._get_user_client(user_id, account_name)
                if client:
                    try:
                        # Ensure client is connected
                        if not client.is_connected():
                            await client.connect()

                        me = await client.get_me()
                        if me and hasattr(me, "date") and me.date:
                            # Handle timezone-aware datetime
                            creation_date = me.date
                            if creation_date.tzinfo is None:
                                creation_date = creation_date.replace(
                                    tzinfo=timezone.utc
                                )

                            now = datetime.now(timezone.utc)
                            age_days = (now - creation_date).days

                            logger.info(
                                f"✓ Account {account_name} age: {age_days} days ({
                                    age_days / 365:.1f} years)"
                            )
                            return max(0, age_days)  # Ensure non-negative
                    except Exception as e:
                        logger.warning(f"Failed to get age for {account_name}: {e}")

            # Fallback: try any available client
            if user_id and user_id in self.bot_manager.user_clients:
                for client_name, client in self.bot_manager.user_clients[
                    user_id
                ].items():
                    try:
                        if client and client.is_connected():
                            me = await client.get_me()
                            if me and hasattr(me, "date") and me.date:
                                creation_date = me.date
                                if creation_date.tzinfo is None:
                                    creation_date = creation_date.replace(
                                        tzinfo=timezone.utc
                                    )

                                now = datetime.now(timezone.utc)
                                age_days = (now - creation_date).days
                                logger.info(
                                    f"✓ Fallback age from {client_name}: {age_days} days"
                                )
                                return max(0, age_days)
                    except Exception as e:
                        logger.debug(f"Fallback client {client_name} failed: {e}")
                        continue

            logger.warning(
                f"Could not determine account age for {account_name}, using default"
            )
            return 365  # Default to 1 year if can't determine

        except Exception as e:
            logger.error(f"Error getting account age: {e}")
            return 365  # Default to 1 year

    async def _get_user_client(self, user_id: int, account_name: str = None):
        """Get specific user client by account name or first available"""
        try:
            user_clients = self.bot_manager.user_clients.get(user_id, {})
            # Safe logging - encode Unicode characters for display only
            try:
                safe_account_name = (
                    account_name.encode("ascii", errors="replace").decode("ascii")
                    if account_name
                    else None
                )
                safe_keys = [
                    k.encode("ascii", errors="replace").decode("ascii")
                    for k in user_clients.keys()
                ]
                logger.info(
                    f"Looking for client '{safe_account_name}' among {
                        len(user_clients)} clients"
                )
                logger.info(f"Available client keys: {safe_keys}")
            except BaseException:
                pass  # Skip logging if encoding fails

            # If account name specified, try to find that specific client
            if account_name:
                # Try exact match first (use original Unicode name)
                client = user_clients.get(account_name)
                if client and client.is_connected():
                    return client

                # Try to find by checking all stored names for this account
                from ..core.mongo_database import mongodb

                try:
                    # Try multiple query patterns
                    account = await mongodb.db.accounts.find_one(
                        {"user_id": user_id, "name": account_name}
                    )
                    if not account:
                        account = await mongodb.db.accounts.find_one(
                            {"user_id": user_id, "display_name": account_name}
                        )
                    if not account:
                        account = await mongodb.db.accounts.find_one(
                            {"user_id": user_id, "phone": account_name}
                        )
                    if not account:
                        # Try case-insensitive search
                        account = await mongodb.db.accounts.find_one(
                            {
                                "user_id": user_id,
                                "name": {
                                    "$regex": f"^{account_name}$",
                                    "$options": "i",
                                },
                            }
                        )

                    if account:
                        # Try all possible client key variations
                        for key in ["phone", "name", "display_name", "first_name"]:
                            if key in account and account[key]:
                                client = user_clients.get(account[key])
                                if client and client.is_connected():
                                    return client
                except Exception as e:
                    logger.error(f"Database lookup error: {e}")

            # DON'T fallback if account_name was specified - return None to force error
            if account_name:
                try:
                    safe_account_name = account_name.encode(
                        "ascii", errors="replace"
                    ).decode("ascii")
                    safe_keys = [
                        k.encode("ascii", errors="replace").decode("ascii")
                        for k in user_clients.keys()
                    ]
                    logger.error(
                        f"Could not find client for specified account: {safe_account_name}"
                    )
                    logger.error(f"Available clients: {safe_keys}")
                except BaseException:
                    logger.error("Could not find client for account (Unicode name)")
                # Try case-insensitive match with original Unicode names
                for key, client in user_clients.items():
                    if (
                        key.lower() == account_name.lower()
                        and client
                        and client.is_connected()
                    ):
                        return client
                return None

            # Only use fallback if no specific account was requested
            for name, client in user_clients.items():
                if client and client.is_connected():
                    logger.warning(f"Using fallback client: {name}")
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

    async def _start_appeal_for_account(
        self, user_id: int, account_name: str, context: str, event
    ):
        """Start appeal process for specific account"""
        try:
            # Store account name in active appeals for tracking
            if user_id not in self.active_appeals:
                self.active_appeals[user_id] = {}
            self.active_appeals[user_id]["account_name"] = account_name
            self.active_appeals[user_id]["context"] = context
            self.active_appeals[user_id]["state"] = "new"

            # Load account client if not already loaded
            client = await self._get_user_client(user_id, account_name)
            if not client:
                await event.respond("⏳ Loading account client...")
                # Get account from database
                from ..core.mongo_database import mongodb

                account = await mongodb.db.accounts.find_one(
                    {"user_id": user_id, "name": account_name}
                )
                if not account:
                    await event.respond("❌ Account not found or no session available.")
                    return
                account = DataEncryption.decrypt_account_data(account)
                if not account.get("session_string"):
                    await event.respond("❌ Account not found or no session available.")
                    return

                # Load the client
                try:
                    await self.bot_manager.start_user_client(
                        user_id, account_name, account["session_string"]
                    )
                    await asyncio.sleep(2)
                    await event.respond("✅ Account loaded successfully!")
                    client = await self._get_user_client(user_id, account_name)
                    if not client:
                        await event.respond("❌ Failed to get loaded client.")
                        return
                except Exception as e:
                    error_str = str(e)
                    if "E11000" in error_str or "duplicate key" in error_str:
                        logger.info(
                            f"Account {account_name} already loaded, continuing..."
                        )
                        client = await self._get_user_client(user_id, account_name)
                        if client:
                            await event.respond("✅ Account already loaded!")
                        else:
                            await event.respond(
                                "❌ Account exists but client not found."
                            )
                            return
                    else:
                        logger.error(f"Failed to load account {account_name}: {e}")
                        await event.respond(
                            "❌ Failed to load account\n\n"
                            "The account may need re-authentication.\n"
                            "Please remove and re-add it in Account Settings."
                        )
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

                    await client(
                        SetTypingRequest(peer=target, action=SendMessageTypingAction())
                    )
                except Exception:
                    pass

            # Analyze words and calculate realistic typing time
            words = message.split()
            total_typing_time = 0

            for word in words:
                # Base time for 37 WPM (1.62 seconds per word)
                base_time = 1.62

                # Adjust for word complexity
                word_lower = word.lower().strip(".,!?;:")

                # Longer words take more time
                if len(word_lower) > 8:
                    base_time *= 1.4  # 40% slower for long words
                elif len(word_lower) > 5:
                    base_time *= 1.2  # 20% slower for medium words

                # Complex/uncommon words take longer
                complex_words = [
                    "restricted",
                    "legitimate",
                    "violation",
                    "communication",
                    "investigation",
                    "unauthorized",
                    "verification",
                    "circumstances",
                    "misunderstanding",
                    "reconsider",
                ]
                if word_lower in complex_words:
                    base_time *= 1.3

                # Technical terms slower
                if word_lower in [
                    "telegram",
                    "spambot",
                    "account",
                    "restrictions",
                    "appeal",
                ]:
                    base_time *= 1.1

                # Common words faster
                common_words = [
                    "the",
                    "and",
                    "for",
                    "are",
                    "but",
                    "not",
                    "you",
                    "all",
                    "can",
                    "had",
                    "her",
                    "was",
                    "one",
                    "our",
                    "out",
                    "day",
                    "get",
                    "has",
                    "him",
                    "his",
                    "how",
                    "man",
                    "new",
                    "now",
                    "old",
                    "see",
                    "two",
                    "way",
                    "who",
                    "boy",
                    "did",
                    "its",
                    "let",
                    "put",
                    "say",
                    "she",
                    "too",
                    "use",
                ]
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

                        await client(
                            SetTypingRequest(
                                peer=target, action=SendMessageTypingAction()
                            )
                        )
                    except Exception:
                        pass

            # Final review pause
            await asyncio.sleep(random.uniform(2.0, 4.0))

        except Exception as e:
            logger.warning(f"Composition simulation error: {e}")
            await asyncio.sleep(random.uniform(8.0, 15.0))

    async def setup_client_handler(self, user_id: int, client):
        """Setup spambot handler for a specific client"""
        logger.info(f"Setting up spambot handler for user {user_id}")

        @client.on(events.NewMessage(chats=["spambot", "SpamBot"], incoming=True))
        async def handle_spambot_message(event):
            logger.info(
                f"Received message from spambot: {event.message.text[:50] if event.message.text else 'No text'}..."
            )
            if user_id in self.active_appeals:
                try:
                    await self._process_spambot_response(user_id, event)
                except Exception as e:
                    logger.error(f"Error processing spambot message: {e}")
            else:
                logger.warning(f"No active appeal for user {user_id}")

        logger.info(f"Handler registered successfully for user {user_id}")

    async def _spam_stats_handler(self, event):
        """Show spam detector statistics"""
        try:
            if hasattr(self.bot_manager, "spam_detector"):
                stats = self.bot_manager.spam_detector.get_detection_stats()
                stats_text = "📊 **Spam Detector Statistics**\n\n"
                for spam_type, count in stats.items():
                    if spam_type != "total_messages":
                        type_name = spam_type.replace("_", " ").title()
                        stats_text += f"• {type_name}: {count} messages\n"
                stats_text += f"\n📝 Total Messages: {stats.get('total_messages', 0)}"
                await event.reply(stats_text)
            else:
                await event.reply("❌ Spam detector not available")
        except Exception as e:
            logger.error(f"Spam stats command error: {e}")
            await event.reply("❌ Error getting spam statistics")

    async def _test_appeal_messages_handler(self, event):
        """Test appeal message loading and selection"""
        user_id = event.sender_id
        try:
            from ..core.config import config
            if user_id not in config.security.admin_ids:
                await event.reply("❌ Admin access required")
                return
            message_count = len(self.appeal_messages)
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

    async def _appeal_command_handler(self, event):
        """Handle /appeal command"""
        user_id = event.sender_id
        try:
            from ..core.mongo_database import mongodb
            await self._disable_session_protection(user_id)
            accounts = await mongodb.db.accounts.find(
                {"user_id": user_id, "is_active": True}
            ).to_list(length=None)
            if not accounts:
                await event.reply("❌ No accounts found. Add an account first using /start")
                return
            context = event.pattern_match.group(1) if event.pattern_match.group(1) else ""
            if len(accounts) > 1:
                await self._show_account_selection(event, accounts)
            else:
                account = accounts[0]
                display_name = account.get("display_name") or account.get("name") or account.get("phone", "Unknown")
                await self._start_appeal_for_account(user_id, display_name, context, event)
        except Exception as e:
            logger.error(f"Appeal command error: {e}")
            await event.reply("❌ Error sending smart appeal. Please try again.")

    async def _disable_session_protection(self, user_id: int):
        """Disable session protection for appeal process"""
        from ..core.mongo_database import mongodb
        await mongodb.db.accounts.update_many(
            {"user_id": user_id},
            {
                "$set": {
                    "session_protection_disabled": True,
                    "protection_bypass_until": int(asyncio.get_event_loop().time()) + 1800,
                },
                "$unset": {
                    "session_protection_active": "",
                    "protection_cooldown": "",
                    "last_protection_trigger": "",
                },
            },
        )

    async def _show_account_selection(self, event, accounts):
        """Show account selection buttons"""
        buttons = []
        for account in accounts[:10]:
            display_name = account.get("display_name") or account.get("name") or account.get("phone", "Unknown")
            buttons.append([Button.inline(f"📱 {display_name}", f"appeal_account_id:{account['_id']}")])
        buttons.append([Button.inline("❌ Cancel", "appeal_cancel")])
        await event.reply(
            f"🧠 **Smart Spam Appeal**\n\n"
            f"Select account to appeal spam restrictions:\n\n"
            f"📊 Available accounts: {len(accounts)}",
            buttons=buttons,
        )

    async def _appeal_account_callback_handler(self, event):
        """Handle account selection callback"""
        user_id = event.sender_id
        account_id = event.data.decode().split(":", 1)[1]
        try:
            await event.answer()
            try:
                try:
                    await event.edit("")
                except Exception:
                    try:
                        await event.delete()
                    except Exception:
                        pass
            except Exception:
                pass
            from bson import ObjectId
            from ..core.mongo_database import mongodb
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                await event.respond("❌ Account not found.")
                return
            account_name = account.get("name") or account.get("phone") or account.get("display_name", "Unknown")
            await asyncio.sleep(random.uniform(0.2, 0.8))
            await self._start_appeal_for_account(user_id, account_name, "", event)
        except Exception as e:
            logger.error(f"Appeal account callback error: {e}")
            await event.respond("❌ Error starting appeal process.")

    async def _appeal_cancel_handler(self, event):
        """Handle appeal cancellation"""
        try:
            await event.answer()
            try:
                try:
                    await event.edit("")
                except Exception:
                    try:
                        await event.delete()
                    except Exception:
                        pass
            except Exception:
                pass
            await event.respond("❌ Appeal process cancelled.")
        except Exception as e:
            logger.error(f"Appeal cancel callback error: {e}")

    async def _captcha_callback_handler(self, event):
        """Handle captcha verification callbacks"""
        user_id = event.sender_id
        action = event.data.decode().split("_")[1]
        try:
            await event.answer()
            try:
                try:
                    await event.edit("")
                except Exception:
                    try:
                        await event.delete()
                    except Exception:
                        pass
            except Exception:
                pass
            if user_id not in self.active_appeals:
                await event.respond("⚠️ No active appeal process found.")
                return
            state = self.active_appeals[user_id]
            if action == "cancel":
                self.active_appeals.pop(user_id, None)
                await event.respond("❌ Appeal process cancelled.")
            elif action == "done":
                state["state"] = "captcha_solved"
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
