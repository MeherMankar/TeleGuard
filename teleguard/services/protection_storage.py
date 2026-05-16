"""Database operations for TeleGuard Protection system"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class ProtectionStorage:
    """Handle persistence for OTP and Session Protection"""

    @staticmethod
    async def get_settings(user_id: int) -> Dict[str, Any]:
        """Get protection settings for a user"""
        try:
            settings = await mongodb.db.protection_settings.find_one({"user_id": user_id})
            if not settings:
                # Initialize default settings
                settings = {
                    "user_id": user_id,
                    "otp_destroyer_enabled": False,
                    "session_destroyer_enabled": False,
                    "trusted_hashes": [],
                    "destroyed_hashes": [],
                    "allow_next": False,
                    "pause_until": None,
                    "enabled_at": datetime.now(timezone.utc),
                    "last_check": None,
                    "stats": {
                        "otp_destroyed": 0,
                        "sessions_destroyed": 0,
                        "last_threat": None
                    }
                }
                await mongodb.db.protection_settings.insert_one(settings)
            return settings
        except Exception as e:
            logger.error(f"Error getting protection settings for {user_id}: {e}")
            return {}

    @staticmethod
    async def update_settings(user_id: int, update_data: Dict[str, Any]):
        """Update protection settings"""
        try:
            await mongodb.db.protection_settings.update_one(
                {"user_id": user_id},
                {"$set": update_data},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error updating protection settings for {user_id}: {e}")

    @staticmethod
    async def add_trusted_hash(user_id: int, session_hash: int):
        """Add a session hash to trusted list"""
        try:
            await mongodb.db.protection_settings.update_one(
                {"user_id": user_id},
                {"$addToSet": {"trusted_hashes": session_hash}}
            )
        except Exception as e:
            logger.error(f"Error adding trusted hash for {user_id}: {e}")

    @staticmethod
    async def add_destroyed_hash(user_id: int, session_hash: int):
        """Add a session hash to destroyed list and update stats"""
        try:
            await mongodb.db.protection_settings.update_one(
                {"user_id": user_id},
                {
                    "$addToSet": {"destroyed_hashes": session_hash},
                    "$inc": {"stats.sessions_destroyed": 1},
                    "$set": {"stats.last_threat": datetime.now(timezone.utc)}
                }
            )
        except Exception as e:
            logger.error(f"Error adding destroyed hash for {user_id}: {e}")

    @staticmethod
    async def increment_otp_stats(user_id: int):
        """Increment OTP destruction stats"""
        try:
            await mongodb.db.protection_settings.update_one(
                {"user_id": user_id},
                {
                    "$inc": {"stats.otp_destroyed": 1},
                    "$set": {"stats.last_threat": datetime.now(timezone.utc)}
                }
            )
        except Exception as e:
            logger.error(f"Error incrementing OTP stats for {user_id}: {e}")

    @staticmethod
    async def get_all_active_session_destroyers() -> List[Dict[str, Any]]:
        """Get all users who have session destroyer enabled"""
        try:
            cursor = mongodb.db.protection_settings.find({
                "session_destroyer_enabled": True,
                "$or": [
                    {"pause_until": None},
                    {"pause_until": {"$lt": datetime.now(timezone.utc)}}
                ]
            })
            return await cursor.to_list(length=None)
        except Exception as e:
            logger.error(f"Error getting active session destroyers: {e}")
            return []
