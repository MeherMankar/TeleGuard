"""Database operations for TeleGuard Protection system"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

MAX_RETAINED_SESSION_HASHES = 5000

class ProtectionStorage:
    """Handle persistence for OTP and Session Protection"""

    @staticmethod
    def _bound_session_hash_fields(data: Dict[str, Any]) -> Dict[str, Any]:
        bounded = dict(data)
        for field in ("trusted_hashes", "untrusted_hashes", "destroyed_hashes"):
            hashes = bounded.get(field)
            if isinstance(hashes, list):
                bounded[field] = hashes[-MAX_RETAINED_SESSION_HASHES:]
        return bounded

    @staticmethod
    async def get_account_settings(user_id: int, account_id: str) -> Dict[str, Any]:
        defaults = {
            "user_id": user_id,
            "account_id": str(account_id),
            "enabled": False,
            "enabled_at": None,
            "trusted_hashes": [],
            "untrusted_hashes": [],
            "destroyed_hashes": [],
            "allow_next": False,
            "allow_next_until": None,
            "pause_until": None,
            "last_check": None,
            "stats": {"sessions_destroyed": 0, "last_threat": None},
        }
        await mongodb.db.session_destroyer_account_settings.update_one(
            {"user_id": user_id, "account_id": str(account_id)},
            {"$setOnInsert": defaults},
            upsert=True,
        )
        settings = await mongodb.db.session_destroyer_account_settings.find_one(
            {"user_id": user_id, "account_id": str(account_id)},
            {
                "user_id": 1,
                "account_id": 1,
                "enabled": 1,
                "enabled_at": 1,
                "trusted_hashes": {"$slice": -MAX_RETAINED_SESSION_HASHES},
                "untrusted_hashes": {"$slice": -MAX_RETAINED_SESSION_HASHES},
                "destroyed_hashes": {"$slice": -MAX_RETAINED_SESSION_HASHES},
                "allow_next": 1,
                "allow_next_until": 1,
                "pause_until": 1,
                "last_check": 1,
                "stats": 1,
            },
        )
        if settings is None:
            raise RuntimeError(
                f"Session Destroyer settings missing for account {account_id}"
            )
        return settings

    @staticmethod
    async def update_account_settings(
        user_id: int, account_id: str, update_data: Dict[str, Any]
    ):
        await ProtectionStorage.get_account_settings(user_id, account_id)
        await mongodb.db.session_destroyer_account_settings.update_one(
            {"user_id": user_id, "account_id": str(account_id)},
            {"$set": ProtectionStorage._bound_session_hash_fields(update_data)},
            upsert=True,
        )

    @staticmethod
    async def add_account_trusted_hash(
        user_id: int, account_id: str, session_hash: int
    ):
        await ProtectionStorage.get_account_settings(user_id, account_id)
        await mongodb.db.session_destroyer_account_settings.update_one(
            {
                "user_id": user_id,
                "account_id": str(account_id),
                "trusted_hashes": {"$ne": session_hash},
            },
            {
                "$push": {
                    "trusted_hashes": {
                        "$each": [session_hash],
                        "$slice": -MAX_RETAINED_SESSION_HASHES,
                    }
                },
                "$pull": {"untrusted_hashes": session_hash},
            },
        )

    @staticmethod
    async def add_account_untrusted_hash(
        user_id: int, account_id: str, session_hash: int
    ):
        await ProtectionStorage.get_account_settings(user_id, account_id)
        await mongodb.db.session_destroyer_account_settings.update_one(
            {
                "user_id": user_id,
                "account_id": str(account_id),
                "untrusted_hashes": {"$ne": session_hash},
            },
            {
                "$pull": {"trusted_hashes": session_hash},
                "$push": {
                    "untrusted_hashes": {
                        "$each": [session_hash],
                        "$slice": -MAX_RETAINED_SESSION_HASHES,
                    }
                },
            },
        )

    @staticmethod
    async def add_account_destroyed_hash(
        user_id: int, account_id: str, session_hash: int
    ):
        await ProtectionStorage.get_account_settings(user_id, account_id)
        result = await mongodb.db.session_destroyer_account_settings.update_one(
            {
                "user_id": user_id,
                "account_id": str(account_id),
                "destroyed_hashes": {"$ne": session_hash},
            },
            {
                "$push": {
                    "destroyed_hashes": {
                        "$each": [session_hash],
                        "$slice": -MAX_RETAINED_SESSION_HASHES,
                    }
                },
                "$inc": {"stats.sessions_destroyed": 1},
                "$set": {"stats.last_threat": datetime.now(timezone.utc)},
                "$pull": {
                    "trusted_hashes": session_hash,
                    "untrusted_hashes": session_hash,
                },
            },
        )
        if result.modified_count:
            await ProtectionStorage.get_settings(user_id)
            await mongodb.db.protection_settings.update_one(
                {"user_id": user_id},
                {
                    "$inc": {"stats.sessions_destroyed": 1},
                    "$set": {"stats.last_threat": datetime.now(timezone.utc)},
                },
            )

    @staticmethod
    async def get_settings(user_id: int) -> Dict[str, Any]:
        """Get protection settings for a user"""
        try:
            settings_projection = {
                "user_id": 1,
                "otp_destroyer_enabled": 1,
                "session_destroyer_enabled": 1,
                "trusted_hashes": {"$slice": -MAX_RETAINED_SESSION_HASHES},
                "untrusted_hashes": {"$slice": -MAX_RETAINED_SESSION_HASHES},
                "destroyed_hashes": {"$slice": -MAX_RETAINED_SESSION_HASHES},
                "allow_next": 1,
                "allow_next_until": 1,
                "pause_until": 1,
                "enabled_at": 1,
                "last_check": 1,
                "stats": 1,
                "legacy_session_destroyer_migrated": 1,
            }
            settings = await mongodb.db.protection_settings.find_one(
                {"user_id": user_id}, settings_projection
            )
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
                    {"user_id": user_id}, settings_projection
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
                        {"user_id": user_id},
                        {"hashes": {"$slice": -MAX_RETAINED_SESSION_HASHES}},
                    ).to_list(length=200)
                    trusted_hashes = set(settings.get("trusted_hashes", []))
                    for trusted_doc in trusted_docs:
                        trusted_hashes.update(
                            (trusted_doc.get("hashes") or [])[
                                -MAX_RETAINED_SESSION_HASHES:
                            ]
                        )
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
            for field in ("trusted_hashes", "untrusted_hashes", "destroyed_hashes"):
                hashes = settings.get(field)
                if isinstance(hashes, list):
                    settings[field] = hashes[-MAX_RETAINED_SESSION_HASHES:]
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
                {
                    "$set": ProtectionStorage._bound_session_hash_fields(
                        update_data
                    )
                },
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
                {"user_id": user_id, "trusted_hashes": {"$ne": session_hash}},
                {
                    "$push": {
                        "trusted_hashes": {
                            "$each": [session_hash],
                            "$slice": -MAX_RETAINED_SESSION_HASHES,
                        }
                    },
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
                {"user_id": user_id, "untrusted_hashes": {"$ne": session_hash}},
                {
                    "$pull": {"trusted_hashes": session_hash},
                    "$push": {
                        "untrusted_hashes": {
                            "$each": [session_hash],
                            "$slice": -MAX_RETAINED_SESSION_HASHES,
                        }
                    },
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
                    "$push": {
                        "destroyed_hashes": {
                            "$each": [session_hash],
                            "$slice": -MAX_RETAINED_SESSION_HASHES,
                        }
                    },
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
        """Return enabled per-account destroyers, migrating legacy global settings."""
        try:
            legacy_users = await mongodb.db.protection_settings.find(
                {"session_destroyer_enabled": True}
            ).to_list(length=None)
            legacy_users.extend(
                await mongodb.db.session_destroyer_settings.find(
                    {"enabled": True}
                ).to_list(length=None)
            )
            for legacy in legacy_users:
                user_id = legacy["user_id"]
                accounts = await mongodb.db.accounts.find(
                    {"user_id": user_id, "is_active": True}
                ).to_list(length=None)
                legacy_enabled_at = legacy.get("enabled_at") or datetime.now(
                    timezone.utc
                )
                for account in accounts:
                    account_id = str(account["_id"])
                    existing = await mongodb.db.session_destroyer_account_settings.find_one(
                        {"user_id": user_id, "account_id": account_id}
                    )
                    if existing:
                        await mongodb.db.session_destroyer_account_settings.update_one(
                            {"user_id": user_id, "account_id": account_id},
                            {
                                "$set": {
                                    "enabled": True,
                                    "enabled_at": existing.get("enabled_at")
                                    or legacy_enabled_at,
                                }
                            },
                        )
                    else:
                        await ProtectionStorage.update_account_settings(
                            user_id,
                            account_id,
                            {
                                "enabled": True,
                                "enabled_at": legacy_enabled_at,
                            },
                        )
                await ProtectionStorage.update_settings(
                    user_id,
                    {
                        "session_destroyer_enabled": False,
                        "legacy_session_destroyer_migrated": True,
                    },
                )
                await mongodb.db.session_destroyer_settings.update_one(
                    {"user_id": user_id},
                    {"$set": {"enabled": False}},
                )
            cursor = mongodb.db.session_destroyer_account_settings.find(
                {"enabled": True}
            )
            active = await cursor.to_list(length=None)
            for settings in active:
                await ProtectionStorage.get_account_settings(
                    settings["user_id"], settings["account_id"]
                )
            return active
        except Exception as e:
            logger.error(f"Error getting active session destroyers: {e}")
            raise
