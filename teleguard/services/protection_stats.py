"""Protection Statistics Service"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class ProtectionStats:
    """Service to handle protection metrics and analytics"""

    @staticmethod
    async def get_summary(user_id: int) -> Dict[str, Any]:
        """Get a summary of protection stats for the user"""
        try:
            settings = await mongodb.db.protection_settings.find_one({"user_id": user_id})
            if not settings:
                return {"otp_destroyed": 0, "sessions_destroyed": 0, "last_threat": None}
            
            return settings.get("stats", {})
        except Exception as e:
            logger.error(f"Error getting protection stats for {user_id}: {e}")
            return {}

    @staticmethod
    async def record_threat(user_id: int, threat_type: str):
        """Record a detected threat"""
        try:
            field = "stats.otp_destroyed" if threat_type == "otp" else "stats.sessions_destroyed"
            await mongodb.db.protection_settings.update_one(
                {"user_id": user_id},
                {
                    "$inc": {field: 1},
                    "$set": {"stats.last_threat": datetime.now(timezone.utc)}
                }
            )
        except Exception as e:
            logger.error(f"Error recording threat for {user_id}: {e}")
