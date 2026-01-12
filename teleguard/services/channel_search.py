"""Channel Search Service for TeleGuard"""

import logging

from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import Channel, Chat

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class ChannelSearch:
    """Handles channel search and discovery"""

    def __init__(self, account_manager):
        self.account_manager = account_manager

    async def search_channels(
        self, user_id: int, account_name: str, query: str, limit: int = 20
    ):
        """Search for channels by name or username"""
        try:
            client = await self._get_client(user_id, account_name)
            if not client:
                return False, "Account not connected"

            # Search using Telegram API
            results = await client(SearchRequest(q=query, limit=limit))

            channels = []
            for chat in results.chats:
                if isinstance(chat, (Channel, Chat)):
                    channels.append(
                        {
                            "id": chat.id,
                            "title": chat.title,
                            "username": getattr(chat, "username", None),
                            "type": (
                                "channel"
                                if getattr(chat, "broadcast", False)
                                else "group"
                            ),
                            "members_count": getattr(chat, "participants_count", 0),
                            "verified": getattr(chat, "verified", False),
                            "scam": getattr(chat, "scam", False),
                            "fake": getattr(chat, "fake", False),
                        }
                    )

            return True, channels

        except Exception as e:
            logger.error(f"Error searching channels: {e}")
            return False, str(e)

    async def get_popular_channels(self, category: str = "all"):
        """Get popular channels from database"""
        try:
            # This would typically come from a curated list or trending data
            popular_channels = [
                {
                    "title": "Telegram News",
                    "username": "telegram",
                    "type": "channel",
                    "category": "news",
                },
                {
                    "title": "Tech Updates",
                    "username": "techupdates",
                    "type": "channel",
                    "category": "tech",
                },
                {
                    "title": "Crypto Signals",
                    "username": "cryptosignals",
                    "type": "channel",
                    "category": "crypto",
                },
                {
                    "title": "Programming Tips",
                    "username": "programmingtips",
                    "type": "channel",
                    "category": "tech",
                },
                {
                    "title": "Daily News",
                    "username": "dailynews",
                    "type": "channel",
                    "category": "news",
                },
            ]

            if category != "all":
                popular_channels = [
                    ch for ch in popular_channels if ch.get("category") == category
                ]

            return popular_channels

        except Exception as e:
            logger.error(f"Error getting popular channels: {e}")
            return []

    async def get_recommended_channels(self, user_id: int):
        """Get recommended channels based on user's current channels"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            user_channels = await self._collect_user_channels(accounts, user_id)
            recommendations = self._generate_recommendations(user_channels)
            return recommendations[:10]
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return []

    async def _collect_user_channels(self, accounts, user_id: int) -> set:
        """Collect all user channels from accounts"""
        user_channels = set()
        for account in accounts:
            if hasattr(self.account_manager, "command_handlers"):
                success, channels = await self.account_manager.command_handlers.channel_manager.get_user_channels(user_id, account["phone"])
                if success:
                    for ch in channels:
                        if ch.get("username"):
                            user_channels.add(ch["username"].lower())
        return user_channels

    def _generate_recommendations(self, user_channels: set) -> list:
        """Generate recommendations based on user interests"""
        recommendations = []
        
        if any("tech" in ch or "programming" in ch for ch in user_channels):
            recommendations.extend(self._get_tech_recommendations())
        
        if any("crypto" in ch or "bitcoin" in ch for ch in user_channels):
            recommendations.extend(self._get_crypto_recommendations())
        
        if not recommendations:
            recommendations = self._get_default_recommendations()
        
        return recommendations

    def _get_tech_recommendations(self) -> list:
        return [
            {"title": "Python Developers", "username": "pythondev", "type": "channel", "reason": "Tech interest"},
            {"title": "Web Development", "username": "webdev", "type": "channel", "reason": "Programming focus"},
        ]

    def _get_crypto_recommendations(self) -> list:
        return [
            {"title": "Crypto News", "username": "cryptonews", "type": "channel", "reason": "Crypto interest"},
            {"title": "Trading Signals", "username": "tradingsignals", "type": "channel", "reason": "Trading focus"},
        ]

    def _get_default_recommendations(self) -> list:
        return [
            {"title": "General News", "username": "generalnews", "type": "channel", "reason": "Popular"},
            {"title": "Tech Updates", "username": "techupdates", "type": "channel", "reason": "Trending"},
        ]

    async def _get_client(self, user_id: int, account_name: str):
        """Get Telegram client for account"""
        try:
            if (
                not self.account_manager
                or user_id not in self.account_manager.user_clients
            ):
                return None

            return self.account_manager.user_clients[user_id].get(account_name)

        except Exception as e:
            logger.error(f"Error getting client: {e}")
            return None
