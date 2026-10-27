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
                await mongodb.db.protection_settings.update_one(
                    {"user_id": user_id},
                    {
                        "$setOnInsert": {
                            "otp_destroyer_enabled": False,
                            "session_destroyer_enabled": False,
                            "trusted_hashes": [],
                            "untrusted_hashes": [],
                            "destroyed_hashes": [],
                            "allow_next": False,
                            "pause_until": None,
                            "enabled_at": None,
                            "last_check": None,
                            "stats": {
                                "otp_destroyed": 0,
                                "sessions_destroyed": 0,
                                "last_threat": None,
                            },
                        }
                    },
                    upsert=True,
                )
                settings = await mongodb.db.protection_settings.find_one(
                    {"user_id": user_id}
                )
            if settings is None:
                raise RuntimeError(
                    f"Protection settings were not created for user {user_id}"
                )
            if not settings.get("legacy_session_destroyer_migrated"):
                legacy = await mongodb.db.session_destroyer_settings.find_one(
                    {"user_id": user_id}
                )
                migration = {"legacy_session_destroyer_migrated": True}
                if legacy and legacy.get("enabled"):
                    trusted_docs = await mongodb.db.trusted_sessions.find(
                        {"user_id": user_id}
                    ).to_list(length=None)
                    trusted_hashes = set(settings.get("trusted_hashes", []))
                    for trusted_doc in trusted_docs:
                        trusted_hashes.update(trusted_doc.get("hashes", []))
                    migration.update(
                        {
                            "session_destroyer_enabled": True,
                            "enabled_at": datetime.now(timezone.utc),
                            "trusted_hashes": list(trusted_hashes),
                        }
                    )
                await mongodb.db.protection_settings.update_one(
                    {"user_id": user_id}, {"$set": migration}
                )
                settings.update(migration)
            return settings
        except Exception as e:
            logger.error(f"Error getting protection settings for {user_id}: {e}")
            raise

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
            raise

    @staticmethod
    async def add_trusted_hash(user_id: int, session_hash: int):
        """Add a session hash to trusted list"""
        try:
            await mongodb.db.protection_settings.update_one(
                {"user_id": user_id},
                {
                    "$addToSet": {"trusted_hashes": session_hash},
                    "$pull": {"untrusted_hashes": session_hash},
                },
            )
        except Exception as e:
            logger.error(f"Error adding trusted hash for {user_id}: {e}")
            raise

    @staticmethod
    async def add_untrusted_hash(user_id: int, session_hash: int):
        """Explicitly mark a session as untrusted across watcher restarts."""
        try:
            await mongodb.db.protection_settings.update_one(
                {"user_id": user_id},
                {
                    "$pull": {"trusted_hashes": session_hash},
                    "$addToSet": {"untrusted_hashes": session_hash},
                },
            )
        except Exception as e:
            logger.error(f"Error adding untrusted hash for {user_id}: {e}")
            raise

    @staticmethod
    async def add_destroyed_hash(user_id: int, session_hash: int):
        """Add a session hash to destroyed list and update stats"""
        try:
            await mongodb.db.protection_settings.update_one(
                {
                    "user_id": user_id,
                    "destroyed_hashes": {"$ne": session_hash},
                },
                {
                    "$addToSet": {"destroyed_hashes": session_hash},
                    "$inc": {"stats.sessions_destroyed": 1},
                    "$set": {"stats.last_threat": datetime.now(timezone.utc)},
                    "$pull": {
                        "trusted_hashes": session_hash,
                        "untrusted_hashes": session_hash,
                    },
                }
            )
        except Exception as e:
            logger.error(f"Error adding destroyed hash for {user_id}: {e}")
            raise

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
            raise

    @staticmethod
    async def get_all_active_session_destroyers() -> List[Dict[str, Any]]:
        """Get all users who have session destroyer enabled"""
        try:
            legacy_users = await mongodb.db.session_destroyer_settings.find(
                {"enabled": True}
            ).to_list(length=None)
            for legacy_user in legacy_users:
                await ProtectionStorage.get_settings(legacy_user["user_id"])
            cursor = mongodb.db.protection_settings.find(
                {"session_destroyer_enabled": True}
            )
            return await cursor.to_list(length=None)
        except Exception as e:
            logger.error(f"Error getting active session destroyers: {e}")
            raise
