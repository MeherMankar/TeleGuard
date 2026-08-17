"""MongoDB Database Configuration for TeleGuard - Durable Storage"""

import logging
import os
import time
from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorClient
from ..utils.crypto_utils import DataEncryption

logger = logging.getLogger(__name__)


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

        # Try Atlas connection first
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
            await self._create_indexes()
            logger.info("Connected to MongoDB Atlas")
            return
        except Exception as e:
            logger.warning(f"MongoDB Atlas failed: {e}")
            if self.client:
                self.client.close()
                self.client = None

        # Fallback to local MongoDB
        try:
            logger.info("Trying local MongoDB...")
            self.client = AsyncIOMotorClient(
                "mongodb://localhost:27017/teleguard", serverSelectionTimeoutMS=3000
            )
            self.db = self.client["teleguard"]
            await self.client.admin.command("ping")
            await self._create_indexes()
            logger.info("Connected to local MongoDB")
            return
        except Exception:
            if self.client:
                self.client.close()
                self.client = None

        # Create mock database
        logger.warning("Using mock database for development")
        self._create_mock_db()

    def _create_mock_db(self):
        """Create mock database for development"""

        class MockCollection:
            async def find_one(self, query):
                return None

            async def insert_one(self, doc):
                class MockResult:
                    inserted_id = "mock_id"

                return MockResult()

            async def update_one(self, query, update, _upsert=False):
                pass

            async def delete_one(self, query):
                pass

            def find(self, query):
                class MockCursor:
                    async def to_list(self, length=None):
                        return []

                return MockCursor()

            async def create_index(self, *args, **kwargs):
                pass

        class MockDB:
            def __init__(self):
                self.users = MockCollection()
                self.accounts = MockCollection()
                self.sessions = MockCollection()
                self.user_settings = MockCollection()
                self.otp_protections = MockCollection()
                self.topic_mappings = MockCollection()
            # Session destroyer related collections (mocked for testing)
            self.session_destroyer_settings = MockCollection()
            self.trusted_sessions = MockCollection()
            self.session_destroyer_logs = MockCollection()
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
            
            # OTP protections: expire documents automatically using a datetime field
            # We store an `expires_at_dt` datetime when creating protections and
            # use a TTL index so entries are removed automatically when expired.
            try:
                await self.db.otp_protections.create_index(
                    "expires_at_dt", expireAfterSeconds=0
                )
            except Exception:
                # Index creation may fail on some MongoDB setups; non-fatal
                logger.warning("Could not create TTL index for otp_protections")
            # Session Destroyer indexes - wrap in try/except for mock DB
            try:
                await self.db.session_destroyer_settings.create_index("user_id", unique=True)
            except Exception:
                logger.debug("session_destroyer_settings collection missing or index creation failed")

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
            try:
                await self.db.trusted_sessions.create_index(
                    [("user_id", 1), ("account_id", 1)], unique=True
                )
            except Exception:
                logger.debug("trusted_sessions collection missing or index creation failed")
            try:
                await self.db.session_destroyer_logs.create_index(
                    [("user_id", 1), ("timestamp", -1)]
                )
            except Exception:
                logger.debug("session_destroyer_logs collection missing or index creation failed")

            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.warning(f"Failed to create some indexes: {e}")

    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()

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
                    "twofa_password": encrypted_password,
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
                "twofa_password": {"$exists": True},
            }
        )
        if account and account.get("twofa_password"):
            try:
                return _DE.decrypt_field(account["twofa_password"])
            except Exception:
                return None
        return None

    async def remove_2fa_password(self, user_id: int, account_id: str):
        """Remove 2FA password from account"""
        from bson import ObjectId

        await self.db.accounts.update_one(
            {"_id": ObjectId(account_id), "user_id": user_id},
            {"$unset": {"twofa_password": "", "twofa_updated_at": ""}},
        )

    async def get_2fa_password_by_phone(
        self, user_id: int, phone: str
    ) -> Optional[str]:
        """Get decrypted 2FA password by phone number"""
        from ..utils.crypto_utils import DataEncryption as _DE

        account = await self.db.accounts.find_one(
            {"user_id": user_id, "phone": phone, "twofa_password": {"$exists": True}}
        )
        if account and account.get("twofa_password"):
            try:
                return _DE.decrypt_field(account["twofa_password"])
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
