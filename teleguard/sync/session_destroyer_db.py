"""
Database operations for TeleGuard Session Destroyer
Durable storage for settings, logs, and trusted sessions.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
from bson import ObjectId

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class SessionDestroyerDB:
    """Handles MongoDB persistence for the Session Destroyer feature"""

    @staticmethod
    async def get_settings(user_id: int) -> Dict[str, Any]:
        """Get or initialize session destroyer settings for a user"""
        try:
            settings = await mongodb.db.session_destroyer_settings.find_one({"user_id": user_id})
            if not settings:
                settings = {
                    "user_id": user_id,
                    "enabled": False,
                    "created_at": time.time(),
                    "updated_at": time.time()
                }
                await mongodb.db.session_destroyer_settings.insert_one(settings)
            return settings
        except Exception as e:
            logger.error(f"Error getting session destroyer settings: {e}")
            return {"enabled": False}

    @staticmethod
    async def update_settings(user_id: int, enabled: bool):
        """Update session destroyer enabled state"""
        try:
            await mongodb.db.session_destroyer_settings.update_one(
                {"user_id": user_id},
                {"$set": {"enabled": enabled, "updated_at": time.time()}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error updating session destroyer settings: {e}")

    @staticmethod
    async def get_trusted_sessions(user_id: int, account_id: str) -> Set[int]:
        """Get set of trusted session hashes for an account"""
        try:
            doc = await mongodb.db.trusted_sessions.find_one({"user_id": user_id, "account_id": account_id})
            if doc:
                return set(doc.get("hashes", []))
            return set()
        except Exception as e:
            logger.error(f"Error getting trusted sessions: {e}")
            return set()

    @staticmethod
    async def save_trusted_sessions(user_id: int, account_id: str, hashes: List[int]):
        """Save/Overwrite trusted session hashes for an account"""
        try:
            await mongodb.db.trusted_sessions.update_one(
                {"user_id": user_id, "account_id": account_id},
                {"$set": {"hashes": hashes, "updated_at": time.time()}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error saving trusted sessions: {e}")

    @staticmethod
    async def add_trusted_hash(user_id: int, account_id: str, session_hash: int):
        """Add a single hash to trusted list"""
        try:
            await mongodb.db.trusted_sessions.update_one(
                {"user_id": user_id, "account_id": account_id},
                {"$addToSet": {"hashes": session_hash}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error adding trusted hash: {e}")

    @staticmethod
    async def log_destruction(user_id: int, account_id: str, session_info: Dict[str, Any]):
        """Log a session destruction event"""
        try:
            log_entry = {
                "user_id": user_id,
                "account_id": account_id,
                "device": session_info.get("device", "Unknown"),
                "ip": session_info.get("ip", "Unknown"),
                "platform": session_info.get("platform", "Unknown"),
                "app_version": session_info.get("app_version", "Unknown"),
                "country": session_info.get("country", "Unknown"),
                "hash": session_info.get("hash"),
                "timestamp": datetime.now(timezone.utc),
                "success": session_info.get("success", True)
            }
            await mongodb.db.session_destroyer_logs.insert_one(log_entry)
            
            # Also update global stats if needed
            await mongodb.db.users.update_one(
                {"telegram_id": user_id},
                {"$inc": {"destroyed_sessions_count": 1}, "$set": {"last_destroyed_session_time": time.time()}}
            )
        except Exception as e:
            logger.error(f"Error logging destruction: {e}")

    @staticmethod
    async def get_logs(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent destruction logs for a user"""
        try:
            cursor = mongodb.db.session_destroyer_logs.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Error getting destruction logs: {e}")
            return []

    @staticmethod
    async def get_stats(user_id: int) -> Dict[str, Any]:
        """Get session destroyer statistics for a user"""
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            destroyed_count = user.get("destroyed_sessions_count", 0) if user else 0
            last_time = user.get("last_destroyed_session_time") if user else None
            
            # Count protected accounts (active accounts for this user if feature is enabled)
            settings = await SessionDestroyerDB.get_settings(user_id)
            is_enabled = settings.get("enabled", False)
            
            protected_accounts = 0
            if is_enabled:
                protected_accounts = await mongodb.db.accounts.count_documents({"user_id": user_id, "is_active": True})
            
            return {
                "destroyed_count": destroyed_count,
                "last_time": last_time,
                "protected_accounts": protected_accounts
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"destroyed_count": 0, "last_time": None, "protected_accounts": 0}
