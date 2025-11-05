"""MongoDB Database Configuration for TeleGuard - Durable Storage"""
import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
from ..utils.data_encryption import DataEncryption
from datetime import datetime
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
        # Optimized connection settings with DNS fallback
        self.client = AsyncIOMotorClient(
            mongo_uri,
            maxPoolSize=5,
            minPoolSize=1,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=20000,
            retryWrites=True,
            w="majority",
            readPreference="primary"
        )
        db_name = os.getenv("MONGO_DB_NAME", "teleguard")
        self.db = self.client[db_name]
        # Test connection
        try:
            await self.client.admin.command("ping")
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            raise e
        
        await self._create_indexes()
        logger.info("Connected to MongoDB with durable storage configuration")
    async def _create_indexes(self):
        """Create database indexes for optimal performance"""
        try:
            # User indexes
            await self.db.users.create_index("telegram_id", unique=True)
            # Account indexes
            await self.db.accounts.create_index([("user_id", 1), ("phone", 1)], unique=True)
            await self.db.accounts.create_index("user_id")
            await self.db.accounts.create_index("is_active")
            # Session indexes
            await self.db.sessions.create_index([("user_id", 1), ("account_id", 1)])
            await self.db.sessions.create_index("created_at")
            # Audit log indexes
            await self.db.audit_logs.create_index([("user_id", 1), ("timestamp", -1)])
            await self.db.audit_logs.create_index("timestamp")
            # Settings indexes
            await self.db.user_settings.create_index("user_id", unique=True)
            # OTP protections: expire documents automatically using a datetime field
            # We store an `expires_at_dt` datetime when creating protections and
            # use a TTL index so entries are removed automatically when expired.
            try:
                await self.db.otp_protections.create_index("expires_at_dt", expireAfterSeconds=0)
            except Exception:
                # Index creation may fail on some MongoDB setups; non-fatal
                logger.warning("Could not create TTL index for otp_protections")
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
        result = await self.db.accounts.insert_one(account_data)
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
    async def add_audit_entry(self, account_id: str, entry: dict):
        """Add audit log entry to account"""
        from bson import ObjectId
        import time
        entry["timestamp"] = time.time()
        await self.db.accounts.update_one(
            {"_id": ObjectId(account_id)},
            {"$push": {"audit_log": entry}}
        )
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
            "updated_at": time.time()
        }
        await self.db.sessions.update_one(
            {"user_id": user_id, "account_id": account_id},
            {"$set": session_doc},
            upsert=True
        )
    async def get_session(self, user_id: int, account_id: str) -> Optional[dict]:
        """Get stored session data"""
        session = await self.db.sessions.find_one({
            "user_id": user_id,
            "account_id": account_id
        })
        return session
    async def delete_session(self, user_id: int, account_id: str):
        """Delete session data"""
        await self.db.sessions.delete_one({
            "user_id": user_id,
            "account_id": account_id
        })
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
            "updated_at": time.time()
        }
        await self.db.user_settings.update_one(
            {"user_id": user_id},
            {"$set": settings_doc},
            upsert=True
        )
    # 2FA Management (Durable Storage)
    async def store_2fa_password(self, user_id: int, account_id: str, password: str):
        """Store encrypted 2FA password for account"""
        from bson import ObjectId
        # Encrypt the password
        encrypted_password = DataEncryption.encrypt_data(password)
        await self.db.accounts.update_one(
            {"_id": ObjectId(account_id), "user_id": user_id},
            {"$set": {
                "twofa_password": encrypted_password,
                "twofa_updated_at": time.time()
            }}
        )
    async def get_2fa_password(self, user_id: int, account_id: str) -> Optional[str]:
        """Get decrypted 2FA password for account"""
        from bson import ObjectId
        account = await self.db.accounts.find_one({
            "_id": ObjectId(account_id),
            "user_id": user_id,
            "twofa_password": {"$exists": True}
        })
        if account and account.get("twofa_password"):
            try:
                return DataEncryption.decrypt_data(account["twofa_password"])
            except Exception:
                return None
        return None
    async def remove_2fa_password(self, user_id: int, account_id: str):
        """Remove 2FA password from account"""
        from bson import ObjectId
        await self.db.accounts.update_one(
            {"_id": ObjectId(account_id), "user_id": user_id},
            {"$unset": {
                "twofa_password": "",
                "twofa_updated_at": ""
            }}
        )
    async def get_2fa_password_by_phone(self, user_id: int, phone: str) -> Optional[str]:
        """Get decrypted 2FA password by phone number"""
        account = await self.db.accounts.find_one({
            "user_id": user_id,
            "phone": phone,
            "twofa_password": {"$exists": True}
        })
        if account and account.get("twofa_password"):
            try:
                return DataEncryption.decrypt_data(account["twofa_password"])
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
    # Audit Logging (Durable Storage)
    async def add_audit_log(self, user_id: int, action: str, details: dict = None):
        """Add audit log entry"""
        log_entry = {
            "user_id": user_id,
            "action": action,
            "details": details or {},
            "timestamp": time.time()
        }
        await self.db.audit_logs.insert_one(log_entry)
    async def get_audit_logs(self, user_id: int, limit: int = 100) -> List[dict]:
        """Get audit logs for user"""
        cursor = self.db.audit_logs.find(
            {"user_id": user_id}
        ).sort("timestamp", -1).limit(limit)
        logs = await cursor.to_list(length=None)
        return logs
    async def cleanup_old_audit_logs(self, days: int = 30):
        """Clean up old audit logs"""
        cutoff_time = time.time() - (days * 24 * 3600)
        result = await self.db.audit_logs.delete_many({
            "timestamp": {"$lt": cutoff_time}
        })
        logger.info(f"Cleaned up {result.deleted_count} old audit log entries")
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
            "created_at": time.time()
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
                    user_id,
                    session["account_id"],
                    session["session_data"]
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
async def cleanup_old_data():
    """Cleanup old data from MongoDB"""
    await mongodb.cleanup_old_audit_logs()