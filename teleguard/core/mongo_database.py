"""MongoDB Database Configuration for TeleGuard - Durable Storage"""

import logging
import os
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError

from ..utils.crypto_utils import DataEncryption

logger = logging.getLogger(__name__)

MAX_ACCOUNT_AUDIT_ENTRIES = 200
SESSION_DESTROYER_LOG_RETENTION_SECONDS = 90 * 24 * 60 * 60
SENSITIVE_ACCOUNT_AUDIT_FIELDS = {
    "code",
    "otp",
    "otp_code",
    "token",
    "password",
    "session_string",
    "session_string_enc",
    "twofa_password",
    "twofa_password_enc",
    "twofa_password_hash",
    "api_hash",
    "api_hash_enc",
    "phone_code_hash",
    "auth_key",
}


def sanitize_account_audit_entry(entry: dict) -> dict:
    def sanitize(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: sanitize(item)
                for key, item in value.items()
                if not isinstance(key, str)
                or key.casefold() not in SENSITIVE_ACCOUNT_AUDIT_FIELDS
            }
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        return value

    return sanitize(entry)


class MongoDB:
    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self):
        """Connect to MongoDB with optimized settings for durable storage"""
        if self.client is not None:
            return
        mongo_uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
        if not mongo_uri:
            raise ValueError("MONGO_URI or MONGODB_URI environment variable required")
        environment = os.getenv("ENVIRONMENT", "production").lower()
        allow_mock_database = environment in {"development", "testing"}
        connection_error: Optional[Exception] = None

        # Try the configured MongoDB endpoint first.
        try:
            self.client = AsyncIOMotorClient(
                mongo_uri,
                maxPoolSize=5,
                minPoolSize=1,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=10000,
                retryWrites=True,
                w="majority",
                readPreference="primary",
            )
            db_name = os.getenv("MONGO_DB_NAME", "teleguard")
            self.db = self.client[db_name]
            await self.client.admin.command("ping")
            await self._migrate_account_audit_logs()
            await self._create_indexes()
            await self._migrate_legacy_otp_expirations()
            logger.info("Connected to configured MongoDB")
            return
        except Exception as e:
            connection_error = e
            logger.warning(f"Configured MongoDB connection failed: {e}")
            if self.client:
                self.client.close()
                self.client = None
            self.db = None

        if allow_mock_database:
            try:
                logger.info("Trying local MongoDB...")
                self.client = AsyncIOMotorClient(
                    "mongodb://localhost:27017/teleguard",
                    serverSelectionTimeoutMS=3000,
                )
                self.db = self.client["teleguard"]
                await self.client.admin.command("ping")
                await self._migrate_account_audit_logs()
                await self._create_indexes()
                await self._migrate_legacy_otp_expirations()
                logger.info("Connected to local MongoDB")
                return
            except Exception as e:
                logger.warning(f"Local MongoDB connection failed: {e}")
                if self.client:
                    self.client.close()
                    self.client = None
                self.db = None

            logger.warning("Using mock database in %s environment", environment)
            self._create_mock_db()
            return

        raise RuntimeError(
            "Could not connect to configured MongoDB; refusing to start without "
            "durable storage"
        ) from connection_error

    def _create_mock_db(self):
        """Create mock database for development"""

        class MockCollection:
            def __init__(self):
                self.documents = []

            @staticmethod
            def _matches(document, query):
                if not query:
                    return True
                for key, expected in query.items():
                    value = document
                    for part in key.split("."):
                        value = value.get(part) if isinstance(value, dict) else None
                    if isinstance(expected, dict):
                        if "$ne" in expected and (
                            value == expected["$ne"]
                            or isinstance(value, list) and expected["$ne"] in value
                        ):
                            return False
                        if "$in" in expected and not (
                            value in expected["$in"]
                            or isinstance(value, list)
                            and any(item in expected["$in"] for item in value)
                        ):
                            return False
                        if "$nin" in expected and (
                            value in expected["$nin"]
                            or isinstance(value, list)
                            and any(item in expected["$nin"] for item in value)
                        ):
                            return False
                    elif value != expected and not (
                        isinstance(value, list) and expected in value
                    ):
                        return False
                return True

            @staticmethod
            def _set_path(document, key, value):
                parts = key.split(".")
                target = document
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                target[parts[-1]] = value

            @staticmethod
            def _get_path(document, key):
                value = document
                for part in key.split("."):
                    value = value.get(part) if isinstance(value, dict) else None
                return value

            @staticmethod
            def _unset_path(document, key):
                parts = key.split(".")
                target = document
                for part in parts[:-1]:
                    target = target.get(part)
                    if not isinstance(target, dict):
                        return
                target.pop(parts[-1], None)

            @staticmethod
            def _project(document, projection):
                if not projection:
                    return document.copy()
                projected = {}
                if projection.get("_id", 1) and "_id" in document:
                    projected["_id"] = document["_id"]
                for key, option in projection.items():
                    if key == "_id" or not option or key not in document:
                        continue
                    value = document[key]
                    if isinstance(option, dict) and "$slice" in option:
                        if isinstance(value, list):
                            limit = option["$slice"]
                            value = value[:limit] if limit >= 0 else value[limit:]
                    projected[key] = value
                return projected

            def _apply_update(self, document, update, inserting=False):
                for key, value in update.get("$set", {}).items():
                    self._set_path(document, key, value)
                if inserting:
                    for key, value in update.get("$setOnInsert", {}).items():
                        self._set_path(document, key, value)
                for key, value in update.get("$inc", {}).items():
                    current = self._get_path(document, key) or 0
                    self._set_path(document, key, current + value)
                for key, value in update.get("$addToSet", {}).items():
                    current = list(self._get_path(document, key) or [])
                    values = value.get("$each", []) if isinstance(value, dict) else [value]
                    current.extend(item for item in values if item not in current)
                    self._set_path(document, key, current)
                for key, value in update.get("$pull", {}).items():
                    current = list(self._get_path(document, key) or [])
                    self._set_path(document, key, [item for item in current if item != value])
                for key, value in update.get("$push", {}).items():
                    current = list(self._get_path(document, key) or [])
                    if isinstance(value, dict) and "$each" in value:
                        current.extend(value["$each"])
                        slice_count = value.get("$slice")
                        if slice_count is not None:
                            current = (
                                current[:slice_count]
                                if slice_count >= 0
                                else current[slice_count:]
                            )
                    else:
                        current.append(value)
                    self._set_path(document, key, current)
                for key in update.get("$unset", {}):
                    self._unset_path(document, key)

            async def find_one(self, query, projection=None):
                for document in self.documents:
                    if self._matches(document, query):
                        return self._project(document, projection)
                return None

            async def insert_one(self, doc):
                stored = doc.copy()
                stored.setdefault("_id", SimpleNamespace(__str__=lambda: "mock_id"))
                self.documents.append(stored)
                return SimpleNamespace(inserted_id=stored["_id"])

            async def update_one(self, query, update, upsert=False, **kwargs):
                for document in self.documents:
                    if self._matches(document, query):
                        self._apply_update(document, update)
                        return SimpleNamespace(
                            matched_count=1,
                            modified_count=1,
                            upserted_id=None,
                        )
                if upsert:
                    inserted = {
                        key: value
                        for key, value in query.items()
                        if not isinstance(value, dict)
                    }
                    self._apply_update(inserted, update, inserting=True)
                    inserted.setdefault("_id", SimpleNamespace(__str__=lambda: "mock_id"))
                    self.documents.append(inserted)
                    return SimpleNamespace(
                        matched_count=0,
                        modified_count=0,
                        upserted_id=inserted["_id"],
                    )
                return SimpleNamespace(
                    matched_count=0, modified_count=0, upserted_id=None
                )

            async def delete_one(self, query):
                for index, document in enumerate(self.documents):
                    if self._matches(document, query):
                        del self.documents[index]
                        return SimpleNamespace(deleted_count=1)
                return SimpleNamespace(deleted_count=0)

            async def delete_many(self, query):
                before = len(self.documents)
                self.documents = [
                    document
                    for document in self.documents
                    if not self._matches(document, query)
                ]
                return SimpleNamespace(deleted_count=before - len(self.documents))

            async def count_documents(self, query=None):
                return sum(
                    1
                    for document in self.documents
                    if self._matches(document, query or {})
                )

            def find(self, query, projection=None):
                collection = self

                class MockCursor:
                    async def to_list(self, length=None):
                        matches = [
                            collection._project(document, projection)
                            for document in collection.documents
                            if collection._matches(document, query)
                        ]
                        return matches if length is None else matches[:length]

                return MockCursor()

            async def create_index(self, *args, **kwargs):
                pass

        class MockReplayCollection(MockCollection):
            def __init__(self):
                self.used_ids = set()

            async def insert_one(self, doc):
                if doc["_id"] in self.used_ids:
                    raise DuplicateKeyError("Duplicate Telegram init data")
                self.used_ids.add(doc["_id"])
                return SimpleNamespace(inserted_id=doc["_id"])

        class MockDB:
            def __init__(self):
                self.users = MockCollection()
                self.accounts = MockCollection()
                self.sessions = MockCollection()
                self.user_settings = MockCollection()
                self.otp_protections = MockCollection()
                self.topic_mappings = MockCollection()
                self.proxies = MockCollection()
                self.automation_jobs = MockCollection()
                self.auto_reply_settings = MockCollection()
                self.auto_replies_sent_count = MockCollection()
                self.telegram_init_data_replays = MockReplayCollection()
                self.revoked_tokens = MockCollection()
                # Session destroyer related collections (mocked for testing)
                self.session_destroyer_settings = MockCollection()
                self.session_destroyer_account_settings = MockCollection()
                self.trusted_sessions = MockCollection()
                self.session_destroyer_logs = MockCollection()
                self._extra_collections = {}

            def __getattr__(self, name):
                collection = self._extra_collections.setdefault(name, MockCollection())
                return collection
        self.db = MockDB()
        logger.info("Mock database ready")

    async def _create_indexes(self):
        """Create database indexes for optimal performance"""
        try:
            # User indexes
            await self.db.users.create_index("telegram_id", unique=True)
            # Account indexes
            await self.db.accounts.create_index(
                [("user_id", 1), ("phone", 1)], unique=True
            )
            await self.db.accounts.create_index("user_id")
            await self.db.accounts.create_index("is_active")
            # Session indexes
            await self.db.sessions.create_index([("user_id", 1), ("account_id", 1)])
            await self.db.sessions.create_index("created_at")

            # Settings indexes
            await self.db.user_settings.create_index("user_id", unique=True)
            
            # Topic mappings indexes
            await self.db.topic_mappings.create_index(
                [("user_id", 1), ("account_id", 1)]
            )
            await self.db.topic_mappings.create_index("topic_id")
            
            # These expirations bound persisted OTP and authentication state.
            await self.db.otp_protections.create_index(
                "expires_at_dt", expireAfterSeconds=0
            )
            await self.db.telegram_init_data_replays.create_index(
                "expires_at", expireAfterSeconds=0
            )
            await self.db.revoked_tokens.create_index(
                "expires_at", expireAfterSeconds=0
            )
            # Keep the legacy user-level settings index best-effort; per-account
            # settings and trusted-session indexes below are required.
            try:
                await self.db.session_destroyer_settings.create_index("user_id", unique=True)
            except Exception:
                logger.debug("session_destroyer_settings collection missing or index creation failed")
            await self.db.session_destroyer_account_settings.create_index(
                [("user_id", 1), ("account_id", 1)], unique=True
            )
            await self.db.session_destroyer_account_settings.create_index(
                [("enabled", 1), ("user_id", 1)]
            )

            # Media dump indexes
            try:
                await self.db.media_index.create_index(
                    [("category", 1), ("source_chat", 1), ("_id", 1)]
                )
                await self.db.media_index.create_index("file_unique", unique=True)
                await self.db.media_dump_jobs.create_index("job_id", unique=True)
                await self.db.media_dump_jobs.create_index([("admin_id", 1), ("created_at", -1)])
            except Exception:
                logger.debug("media_index / media_dump_jobs index creation skipped")
            await self.db.trusted_sessions.create_index(
                [("user_id", 1), ("account_id", 1)], unique=True
            )
            try:
                await self.db.session_destroyer_logs.create_index(
                    [("user_id", 1), ("timestamp", -1)]
                )
            except Exception:
                logger.debug("session_destroyer_logs query index creation failed")
            await self.db.session_destroyer_logs.create_index(
                "timestamp",
                expireAfterSeconds=SESSION_DESTROYER_LOG_RETENTION_SECONDS,
            )

            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.exception("Failed to create required MongoDB indexes")
            raise RuntimeError("MongoDB index initialization failed") from e

    async def _migrate_account_audit_logs(self):
        """Remove sensitive historical values and cap legacy account audit arrays."""
        if self.client is None:
            return

        sensitive_paths = [
            f"audit_log.{field}" for field in SENSITIVE_ACCOUNT_AUDIT_FIELDS
        ] + [
            f"audit_log.details.{field}"
            for field in SENSITIVE_ACCOUNT_AUDIT_FIELDS
        ]
        cursor = self.db.accounts.find(
            {
                "$or": [
                    {f"{path}": {"$exists": True}} for path in sensitive_paths
                ]
                + [
                    {
                        f"audit_log.{MAX_ACCOUNT_AUDIT_ENTRIES}": {
                            "$exists": True
                        }
                    }
                ]
            },
            {"audit_log": 1},
        )
        async for account in cursor:
            entries = account.get("audit_log", [])
            if not isinstance(entries, list):
                entries = []
            sanitized = []
            for entry in entries[-MAX_ACCOUNT_AUDIT_ENTRIES:]:
                if not isinstance(entry, dict):
                    continue
                sanitized.append(sanitize_account_audit_entry(entry))
            if sanitized != entries:
                await self.db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$set": {"audit_log": sanitized}},
                )

    async def _migrate_legacy_otp_expirations(self):
        """Backfill BSON dates so legacy OTP protections are handled by the TTL index."""
        if self.client is None:
            return

        cursor = self.db.otp_protections.find(
            {
                "expires_at_dt": {"$exists": False},
                "expires_at": {"$type": "number"},
            },
            {"expires_at": 1},
        )
        now = time.time()
        async for document in cursor:
            expires_at = int(document["expires_at"])
            if expires_at <= now:
                await self.db.otp_protections.delete_one(
                    {"_id": document["_id"]}
                )
                continue
            await self.db.otp_protections.update_one(
                {"_id": document["_id"]},
                {
                    "$set": {
                        "expires_at_dt": datetime.fromtimestamp(
                            expires_at, tz=timezone.utc
                        )
                    }
                },
            )

    async def append_account_audit_log(
        self, query: dict, entry: dict, update_fields: Optional[dict] = None
    ):
        safe_entry = sanitize_account_audit_entry(entry)
        update = dict(update_fields or {})
        update["$push"] = {
            "audit_log": {
                "$each": [safe_entry],
                "$slice": -MAX_ACCOUNT_AUDIT_ENTRIES,
            }
        }
        await self.db.accounts.update_one(
            query,
            update,
        )

    async def disconnect(self):
        """Disconnect from MongoDB"""
        client = self.client
        self.client = None
        self.db = None
        if client:
            client.close()

    # User operations
    async def create_user(self, telegram_id: int, **kwargs):
        """Create or update user"""
        user_data = {"telegram_id": telegram_id, "developer_mode": False, **kwargs}
        await self.db.users.update_one(
            {"telegram_id": telegram_id}, {"$set": user_data}, upsert=True
        )

    async def get_user(self, telegram_id: int):
        """Get user by telegram_id"""
        user = await self.db.users.find_one({"telegram_id": telegram_id})
        return user

    async def update_user(self, telegram_id: int, **kwargs):
        """Update specific user fields without overwriting unspecified ones"""
        if not kwargs:
            return
        await self.db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": kwargs},
            upsert=False,
        )

    # Account operations
    async def create_account(self, user_id: int, phone: str, **kwargs):
        """Create account"""
        account_data = {
            "user_id": user_id,
            "phone": phone,
            "name": phone,
            "is_active": True,
            "otp_destroyer_enabled": False,
            **kwargs,
        }
        result = await self.db.accounts.insert_one(
            DataEncryption.encrypt_account_data(account_data)
        )
        return str(result.inserted_id)

    async def get_user_accounts(self, user_id: int):
        """Get all accounts for user"""
        cursor = self.db.accounts.find({"user_id": user_id})
        accounts = await cursor.to_list(length=None)
        return accounts

    async def get_account(self, account_id: str):
        """Get account by ID"""
        from bson import ObjectId

        account = await self.db.accounts.find_one({"_id": ObjectId(account_id)})
        return account

    async def update_account(self, account_id: str, **kwargs):
        """Update account"""
        from bson import ObjectId

        await self.db.accounts.update_one(
            {"_id": ObjectId(account_id)}, {"$set": kwargs}
        )

    async def delete_account(self, account_id: str):
        """Delete account"""
        from bson import ObjectId

        await self.db.accounts.delete_one({"_id": ObjectId(account_id)})

    async def get_account_by_phone(self, user_id: int, phone: str):
        """Get account by phone number"""
        account = await self.db.accounts.find_one({"user_id": user_id, "phone": phone})
        return account

    async def get_active_accounts(self, user_id: int):
        """Get active accounts for user"""
        cursor = self.db.accounts.find({"user_id": user_id, "is_active": True})
        accounts = await cursor.to_list(length=None)
        return accounts

    # Session Management (Durable Storage)
    async def store_session(self, user_id: int, account_id: str, session_data: dict):
        """Store session data durably"""
        session_doc = {
            "user_id": user_id,
            "account_id": account_id,
            "session_data": session_data,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        await self.db.sessions.update_one(
            {"user_id": user_id, "account_id": account_id},
            {"$set": session_doc},
            upsert=True,
        )

    async def get_session(self, user_id: int, account_id: str) -> Optional[dict]:
        """Get stored session data"""
        session = await self.db.sessions.find_one(
            {"user_id": user_id, "account_id": account_id}
        )
        return session

    async def delete_session(self, user_id: int, account_id: str):
        """Delete session data"""
        await self.db.sessions.delete_one(
            {"user_id": user_id, "account_id": account_id}
        )

    async def get_user_sessions(self, user_id: int) -> List[dict]:
        """Get all sessions for user"""
        cursor = self.db.sessions.find({"user_id": user_id})
        sessions = await cursor.to_list(length=None)
        return sessions

    # User Settings (Durable Storage)
    async def store_user_settings(self, user_id: int, settings: dict):
        """Store user settings"""
        settings_doc = {
            "user_id": user_id,
            "settings": settings,
            "updated_at": time.time(),
        }
        await self.db.user_settings.update_one(
            {"user_id": user_id}, {"$set": settings_doc}, upsert=True
        )

    # 2FA Management (Durable Storage)
    async def store_2fa_password(self, user_id: int, account_id: str, password: str):
        """Store encrypted 2FA password for account"""
        from bson import ObjectId

        from ..utils.crypto_utils import DataEncryption as _DE

        encrypted_password = _DE.encrypt_field(password)
        await self.db.accounts.update_one(
            {"_id": ObjectId(account_id), "user_id": user_id},
            {
                "$set": {
                    "twofa_password_enc": encrypted_password,
                    "twofa_updated_at": time.time(),
                }
            },
        )

    async def get_2fa_password(self, user_id: int, account_id: str) -> Optional[str]:
        """Get decrypted 2FA password for account"""
        from bson import ObjectId

        from ..utils.crypto_utils import DataEncryption as _DE

        account = await self.db.accounts.find_one(
            {
                "_id": ObjectId(account_id),
                "user_id": user_id,
            }
        )
        encrypted_password = (
            account.get("twofa_password_enc") or account.get("twofa_password")
            if account
            else None
        )
        if encrypted_password:
            try:
                return _DE.decrypt_field(encrypted_password)
            except Exception:
                return None
        return None

    async def remove_2fa_password(self, user_id: int, account_id: str):
        """Remove the stored 2FA password from an owned account."""
        from bson import ObjectId

        result = await self.db.accounts.update_one(
            {"_id": ObjectId(account_id), "user_id": user_id},
            {
                "$unset": {
                    "twofa_password": "",
                    "twofa_password_enc": "",
                    "twofa_updated_at": "",
                }
            },
        )
        return result.matched_count > 0

    async def get_2fa_password_by_phone(
        self, user_id: int, phone: str
    ) -> Optional[str]:
        """Get decrypted 2FA password by phone number"""
        from ..utils.crypto_utils import DataEncryption as _DE

        account = await self.db.accounts.find_one(
            {"user_id": user_id, "phone": phone}
        )
        encrypted_password = (
            account.get("twofa_password_enc") or account.get("twofa_password")
            if account
            else None
        )
        if encrypted_password:
            try:
                return _DE.decrypt_field(encrypted_password)
            except Exception:
                return None
        return None

    async def get_user_settings(self, user_id: int) -> Optional[dict]:
        """Get user settings"""
        settings = await self.db.user_settings.find_one({"user_id": user_id})
        return settings.get("settings") if settings else None

    async def delete_user_settings(self, user_id: int):
        """Delete user settings"""
        await self.db.user_settings.delete_one({"user_id": user_id})

    # Backup and Recovery
    async def create_backup_snapshot(self, user_id: int) -> dict:
        """Create backup snapshot of user data"""
        user = await self.get_user(user_id)
        accounts = await self.get_user_accounts(user_id)
        sessions = await self.get_user_sessions(user_id)
        settings = await self.get_user_settings(user_id)
        snapshot = {
            "user": user,
            "accounts": accounts,
            "sessions": sessions,
            "settings": settings,
            "created_at": time.time(),
        }
        return snapshot

    async def restore_from_snapshot(self, user_id: int, snapshot: dict):
        """Restore user data from snapshot"""
        # Restore user
        if snapshot.get("user"):
            await self.create_user(user_id, **snapshot["user"])
        # Restore accounts
        if snapshot.get("accounts"):
            for account in snapshot["accounts"]:
                account.pop("_id", None)
                await self.create_account(user_id, **account)
        # Restore sessions
        if snapshot.get("sessions"):
            for session in snapshot["sessions"]:
                await self.store_session(
                    user_id, session["account_id"], session["session_data"]
                )
        # Restore settings
        if snapshot.get("settings"):
            await self.store_user_settings(user_id, snapshot["settings"])
        logger.info(f"Restored user {user_id} from backup snapshot")


# Global MongoDB instance
mongodb = MongoDB()


async def init_db():
    """Initialize MongoDB connection"""
    if mongodb.client is None:
        await mongodb.connect()


async def get_db():
    """Get MongoDB database instance"""
    return mongodb.db
