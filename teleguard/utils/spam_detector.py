"""Intelligent spam limit detection and message selection system with AI"""

import asyncio
import logging
import random
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai

    from ..core.config import config

    if (
        hasattr(config, "ai")
        and hasattr(config.ai, "gemini_api_key")
        and config.ai.gemini_api_key
    ):
        genai.configure(api_key=config.ai.gemini_api_key)
        AI_AVAILABLE = True
    else:
        AI_AVAILABLE = False
except ImportError:
    AI_AVAILABLE = False


class SpamLimitType(Enum):
    """Types of spam limitations detected"""

    TWO_WAY_RESTRICTION = "two_way_restriction"
    SPAMBLOCK = "spamblock"
    NEW_ACCOUNT_RESTRICTION = "new_account_restriction"
    VERIFICATION_REQUIRED = "verification_required"
    GENERAL_RESTRICTION = "general_restriction"
    PROFESSIONAL_APPEAL = "professional_appeal"
    TECHNICAL_APPEAL = "technical_appeal"


class SpamDetector:
    """Detects spam limitation types and selects appropriate appeal messages"""

    def __init__(self, appeal_messages: List[str]):
        self.appeal_messages = appeal_messages
        self.categorized_messages = self._categorize_messages()
        self.ai_model = None
        if AI_AVAILABLE:
            try:
                self.ai_model = genai.GenerativeModel("gemini-pro")
                logger.info("AI-powered spam detection enabled")
            except Exception as e:
                logger.warning(f"AI initialization failed: {e}")
                self.ai_model = None

    def _categorize_messages(self) -> Dict[SpamLimitType, List[str]]:
        """Categorize messages by spam limit type"""
        categories = {limit_type: [] for limit_type in SpamLimitType}

        for message in self.appeal_messages:
            message_lower = message.lower()
            spam_type = self._detect_message_category(message_lower)
            categories[spam_type].append(message)

        return categories

    def _detect_message_category(self, message_lower: str) -> SpamLimitType:
        """Detect category for a single message"""
        if self._is_two_way_restriction(message_lower):
            return SpamLimitType.TWO_WAY_RESTRICTION
        elif self._is_spamblock(message_lower):
            return SpamLimitType.SPAMBLOCK
        elif self._is_new_account(message_lower):
            return SpamLimitType.NEW_ACCOUNT_RESTRICTION
        elif self._is_verification(message_lower):
            return SpamLimitType.VERIFICATION_REQUIRED
        elif self._is_professional(message_lower):
            return SpamLimitType.PROFESSIONAL_APPEAL
        elif self._is_technical(message_lower):
            return SpamLimitType.TECHNICAL_APPEAL
        else:
            return SpamLimitType.GENERAL_RESTRICTION

    def _is_two_way_restriction(self, text: str) -> bool:
        return any(kw in text for kw in ["two-way restriction", "two way restriction", "dual verification", "two-step verification", "dual authentication"])

    def _is_spamblock(self, text: str) -> bool:
        return any(kw in text for kw in ["spamblock", "spam block", "flagged with a spamblock", "spamblock restrictions", "blocked with a spamblock"])

    def _is_new_account(self, text: str) -> bool:
        return any(kw in text for kw in ["new account", "newly registered", "recently created", "fresh account", "first-time", "newcomer", "brand-new"])

    def _is_verification(self, text: str) -> bool:
        return any(kw in text for kw in ["verification", "captcha", "human verification", "identity confirmation", "authentication"])

    def _is_professional(self, text: str) -> bool:
        return any(kw in text for kw in ["professional", "business", "enterprise", "developer", "api", "technical", "research", "academic", "organization"])

    def _is_technical(self, text: str) -> bool:
        return any(kw in text for kw in ["cybersecurity", "accessibility", "medical", "emergency", "crisis", "humanitarian", "educational", "cultural"])

    async def ai_detect_spam_type(self, context: str) -> Optional[SpamLimitType]:
        """Use AI to detect spam limitation type"""
        if not self.ai_model or not context:
            return None

        try:
            prompt = f"""Analyze this Telegram SpamBot message and identify the spam limitation type:

"{context}"

Spam limitation types:
1. two_way_restriction - Account has two-way messaging restrictions
2. spamblock - Account is flagged with spamblock
3. new_account_restriction - New account limitations
4. verification_required - Human verification needed
5. general_restriction - General spam restrictions
6. professional_appeal - Business/professional use case
7. technical_appeal - Technical/research use case

Respond with only the type name (e.g., "spamblock"):"""

            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            ai_result = response.text.strip().lower()

            # Map AI response to enum
            type_mapping = {
                "two_way_restriction": SpamLimitType.TWO_WAY_RESTRICTION,
                "spamblock": SpamLimitType.SPAMBLOCK,
                "new_account_restriction": SpamLimitType.NEW_ACCOUNT_RESTRICTION,
                "verification_required": SpamLimitType.VERIFICATION_REQUIRED,
                "general_restriction": SpamLimitType.GENERAL_RESTRICTION,
                "professional_appeal": SpamLimitType.PROFESSIONAL_APPEAL,
                "technical_appeal": SpamLimitType.TECHNICAL_APPEAL,
            }

            return type_mapping.get(ai_result, None)

        except Exception as e:
            logger.warning(f"AI spam detection failed: {e}")
            return None

    def detect_spam_limit_type(self, context: str) -> SpamLimitType:
        """Detect the type of spam limitation from spambot context"""
        context_lower = context.lower()

        if self._is_two_way_restriction(context_lower):
            return SpamLimitType.TWO_WAY_RESTRICTION
        elif self._is_spamblock(context_lower):
            return SpamLimitType.SPAMBLOCK
        elif any(kw in context_lower for kw in ["new account", "recently created", "fresh registration"]):
            return SpamLimitType.NEW_ACCOUNT_RESTRICTION
        elif any(kw in context_lower for kw in ["verify", "captcha", "human verification", "prove you are human"]):
            return SpamLimitType.VERIFICATION_REQUIRED
        elif any(kw in context_lower for kw in ["professional", "business", "enterprise", "api access"]):
            return SpamLimitType.PROFESSIONAL_APPEAL
        else:
            return SpamLimitType.GENERAL_RESTRICTION

    def get_account_age_category(self, account_age_days: int) -> str:
        """Categorize account by age"""
        if account_age_days < 7:
            return "very_new"
        elif account_age_days < 30:
            return "new"
        elif account_age_days < 365:
            return "established"
        else:
            return "old"

    def select_optimal_message(
        self,
        spam_limit_type: SpamLimitType,
        account_age_days: int = 365,
        context: str = "",
        user_preferences: Dict = None,
    ) -> str:
        """Select the most appropriate appeal message"""

        # Get messages for the detected spam limit type
        candidate_messages = self.categorized_messages.get(spam_limit_type, [])

        # Fallback to general messages if no specific ones found
        if not candidate_messages:
            candidate_messages = self.categorized_messages[
                SpamLimitType.GENERAL_RESTRICTION
            ]

        # If still no messages, use all messages
        if not candidate_messages:
            candidate_messages = self.appeal_messages

        # Filter by account age if relevant
        account_age_category = self.get_account_age_category(account_age_days)
        age_filtered_messages = self._filter_by_account_age(
            candidate_messages, account_age_category
        )

        if age_filtered_messages:
            candidate_messages = age_filtered_messages

        # Filter by context keywords if available
        if context:
            context_filtered_messages = self._filter_by_context(
                candidate_messages, context
            )
            if context_filtered_messages:
                candidate_messages = context_filtered_messages

        # Apply user preferences if provided
        if user_preferences:
            preference_filtered_messages = self._filter_by_preferences(
                candidate_messages, user_preferences
            )
            if preference_filtered_messages:
                candidate_messages = preference_filtered_messages

        # Select random message from candidates
        return (
            random.choice(candidate_messages)
            if candidate_messages
            else random.choice(self.appeal_messages)
        )

    def select_from_messages(
        self,
        messages: List[str],
        spam_limit_type: SpamLimitType,
        account_age_days: int = 365,
    ) -> str:
        """Select message from provided list using spam detector logic"""
        if not messages:
            return None

        # Use the provided messages as our candidate pool
        candidate_messages = messages

        # Filter by account age if relevant
        account_age_category = self.get_account_age_category(account_age_days)
        age_filtered_messages = self._filter_by_account_age(
            candidate_messages, account_age_category
        )

        if age_filtered_messages:
            candidate_messages = age_filtered_messages

        # Select random message from candidates
        return (
            random.choice(candidate_messages)
            if candidate_messages
            else random.choice(messages)
        )

    def _filter_by_account_age(
        self, messages: List[str], age_category: str
    ) -> List[str]:
        """Filter messages based on account age"""
        filtered = []

        for message in messages:
            message_lower = message.lower()

            if age_category == "very_new" or age_category == "new":
                # Prefer messages mentioning new accounts
                if any(
                    keyword in message_lower
                    for keyword in [
                        "new",
                        "recently",
                        "just created",
                        "first time",
                        "newcomer",
                    ]
                ):
                    filtered.append(message)
            elif age_category == "old":
                # Prefer messages mentioning long-time usage
                if any(
                    keyword in message_lower
                    for keyword in [
                        "long time",
                        "years",
                        "experienced",
                        "regular user",
                        "always used",
                    ]
                ):
                    filtered.append(message)

        return filtered

    def _filter_by_context(self, messages: List[str], context: str) -> List[str]:
        """Filter messages based on spambot context"""
        context_lower = context.lower()
        filtered = []

        for message in messages:
            if self._matches_context(message.lower(), context_lower):
                filtered.append(message)

        return filtered

    def _matches_context(self, message_lower: str, context_lower: str) -> bool:
        """Check if message matches context"""
        if any(w in context_lower for w in ["mistake", "error", "wrong"]):
            return any(kw in message_lower for kw in ["mistake", "error", "wrong"])
        elif any(w in context_lower for w in ["details", "explain", "why"]):
            return len(message_lower) > 200
        elif any(w in context_lower for w in ["professional", "business"]):
            return any(kw in message_lower for kw in ["professional", "business", "work"])
        return False

    def _filter_by_preferences(
        self, messages: List[str], preferences: Dict
    ) -> List[str]:
        """Filter messages based on user preferences"""
        filtered = []
        tone = preferences.get("tone", "polite")
        length = preferences.get("length", "medium")

        for message in messages:
            if self._matches_preferences(message, tone, length):
                filtered.append(message)

        return filtered if filtered else messages

    def _matches_preferences(self, message: str, tone: str, length: str) -> bool:
        """Check if message matches preferences"""
        message_lower = message.lower()
        
        if tone == "formal" and any(w in message_lower for w in ["dear", "kindly", "respectfully"]):
            return True
        elif tone == "casual" and any(w in message_lower for w in ["hello", "hi", "hope you"]):
            return True
        elif length == "short" and len(message) < 300:
            return True
        elif length == "long" and len(message) > 500:
            return True
        elif length == "medium" and 300 <= len(message) <= 500:
            return True
        return False

    def get_detection_stats(self) -> Dict:
        """Get statistics about message categorization"""
        stats = {}
        for limit_type, messages in self.categorized_messages.items():
            stats[limit_type.value] = len(messages)

        stats["total_messages"] = len(self.appeal_messages)
        return stats

    def analyze_spambot_response(self, response_text: str) -> Dict:
        """Analyze spambot response to extract useful information"""
        response_lower = response_text.lower()

        analysis = {
            "spam_limit_type": self.detect_spam_limit_type(response_text),
            "requires_captcha": any(
                word in response_lower
                for word in [
                    "captcha",
                    "verify",
                    "human verification",
                    "prove you are human",
                ]
            ),
            "account_flagged": any(
                word in response_lower
                for word in ["flagged", "restricted", "limited", "blocked"]
            ),
            "appeal_possible": any(
                word in response_lower
                for word in ["appeal", "complaint", "review", "mistake"]
            ),
            "severity": self._assess_severity(response_text),
            "keywords": self._extract_keywords(response_text),
        }

        return analysis

    def _assess_severity(self, response_text: str) -> str:
        """Assess the severity of the spam limitation"""
        response_lower = response_text.lower()

        if any(
            word in response_lower
            for word in ["permanent", "banned", "terminated", "suspended"]
        ):
            return "high"
        elif any(
            word in response_lower
            for word in ["temporary", "review", "appeal", "mistake"]
        ):
            return "low"
        else:
            return "medium"

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from spambot response"""
        keywords = []
        text_lower = text.lower()

        # Common spam-related keywords
        spam_keywords = [
            "spam",
            "restriction",
            "limited",
            "blocked",
            "flagged",
            "verification",
            "captcha",
            "appeal",
            "mistake",
            "review",
            "complaint",
            "two-way",
            "spamblock",
            "human",
            "robot",
        ]

        for keyword in spam_keywords:
            if keyword in text_lower:
                keywords.append(keyword)

        return keywords

    async def ai_select_best_message(
        self, spam_type: SpamLimitType, context: str, account_age_days: int
    ) -> Optional[str]:
        """Use AI to select the best appeal message"""
        if not self.ai_model or not self.appeal_messages:
            return None

        try:
            messages_text = "\n\n---\n\n".join(
                [f"Message {i + 1}:\n{msg}" for i,
                 msg in enumerate(self.appeal_messages)]
            )

            prompt = f"""You are helping select the best Telegram spam appeal message.

Spam Type: {spam_type.value if spam_type else 'general'}
Account Age: {account_age_days} days
SpamBot Context: "{context}"

Available Messages:
{messages_text}

Select the most effective message number (1-{len(self.appeal_messages)}) that:
1. Best matches the spam type
2. Is appropriate for account age
3. Has the highest chance of success

Respond with only the message number:"""

            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            try:
                message_num = int(response.text.strip()) - 1
                if 0 <= message_num < len(self.appeal_messages):
                    return self.appeal_messages[message_num]
            except ValueError:
                pass

        except Exception as e:
            logger.warning(f"AI message selection failed: {e}")

        return None

    async def ai_select_from_messages(
        self,
        messages: List[str],
        spam_type: SpamLimitType,
        context: str,
        account_age_days: int,
    ) -> Optional[str]:
        """Use AI to select best message from provided list"""
        if not self.ai_model or not messages:
            return None

        try:
            messages_text = "\n\n---\n\n".join(
                [f"Message {i + 1}:\n{msg}" for i, msg in enumerate(messages)]
            )

            prompt = f"""You are helping select the best Telegram spam appeal message.

Spam Type: {spam_type.value if spam_type else 'general'}
Account Age: {account_age_days} days
SpamBot Context: "{context}"

Available Messages:
{messages_text}

Select the most effective message number (1-{len(messages)}) that:
1. Best matches the spam type
2. Is appropriate for account age
3. Has the highest chance of success

Respond with only the message number:"""

            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            try:
                message_num = int(response.text.strip()) - 1
                if 0 <= message_num < len(messages):
                    return messages[message_num]
            except ValueError:
                pass

        except Exception as e:
            logger.warning(f"AI message selection failed: {e}")

        return None

    async def ai_analyze_button_strategy(self, spambot_text: str) -> Dict:
        """Use AI to determine optimal button clicking strategy"""
        if not self.ai_model:
            return {"buttons": [], "strategy": "default"}

        try:
            prompt = f"""Analyze this SpamBot message and determine the optimal button clicking strategy:

"{spambot_text}"

Common SpamBot buttons and when to click them:
- "This is a mistake" - Click when bot asks about spam restrictions
- "Yes" - Click when asked to submit complaint
- "No! Never did that!" - Click when asked about sending spam to strangers
- "Done" - Click after completing appeal process

Respond with JSON format:
{{
  "next_button": "button_text_to_click",
  "confidence": "high/medium/low",
  "reasoning": "why this button"
}}"""

            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            import json

            try:
                return json.loads(response.text.strip())
            except json.JSONDecodeError:
                pass

        except Exception as e:
            logger.warning(f"AI button strategy failed: {e}")

        return {"buttons": [], "strategy": "default"}

    async def auto_detect_and_select_message(
        self, context: str = "", account_age_days: int = 365
    ) -> Tuple[str, SpamLimitType, Dict]:
        """Auto-detect spam type and select optimal message with AI"""

        # Try AI detection first
        spam_type = None
        if self.ai_model:
            try:
                spam_type = await self.ai_detect_spam_type(context)
            except Exception as e:
                logger.warning(f"AI detection failed: {e}")

        # Fallback to rule-based detection
        if not spam_type:
            spam_type = self.detect_spam_limit_type(context)

        # Try AI message selection first
        message = None
        if self.ai_model:
            try:
                message = await self.ai_select_best_message(
                    spam_type, context, account_age_days
                )
            except Exception as e:
                logger.warning(f"AI message selection failed: {e}")

        # Fallback to rule-based selection
        if not message:
            message = self.select_optimal_message(
                spam_limit_type=spam_type,
                account_age_days=account_age_days,
                context=context,
                user_preferences={"tone": "polite", "length": "medium"},
            )

        # Generate strategy info
        strategy = {
            "priority": (
                "high"
                if spam_type
                in [SpamLimitType.SPAMBLOCK, SpamLimitType.TWO_WAY_RESTRICTION]
                else "medium"
            ),
            "delay_seconds": 2,
            "retry_count": 1,
            "ai_enhanced": self.ai_model is not None,
        }

        return message, spam_type, strategy
