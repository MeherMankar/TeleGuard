"""MongoDB Database Configuration for TeleGuard"""

import logging
import os
from typing import Any, Dict, Optional

from motor.motor_asyncio import AsyncIOMotorClient
from ..utils.data_encryption import DataEncryption

logger = logging.getLogger(__name__)


class MongoDB:
    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self):
        """Connect to MongoDB"""
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise ValueError("MONGO_URI environment variable required")

        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client.teleguard

        # Test connection
        await self.client.admin.command("ping")
        logger.info("Connected to MongoDB")

    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()

    # User operations
    async def create_user(self, telegram_id: int, **kwargs):
        """Create or update user"""
        user_data = {"telegram_id": telegram_id, "developer_mode": False, **kwargs}
        encrypted_data = DataEncryption.encrypt_user_data(user_data)
        await self.db.users.update_one(
            {"telegram_id": telegram_id}, {"$set": encrypted_data}, upsert=True
        )

    async def get_user(self, telegram_id: int):
        """Get user by telegram_id"""
        encrypted_user = await self.db.users.find_one({"telegram_id": telegram_id})
        if encrypted_user:
            return DataEncryption.decrypt_user_data(encrypted_user)
        return None

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
        encrypted_data = DataEncryption.encrypt_account_data(account_data)
        result = await self.db.accounts.insert_one(encrypted_data)
        return str(result.inserted_id)

    async def get_user_accounts(self, user_id: int):
        """Get all accounts for user"""
        cursor = self.db.accounts.find({"user_id": user_id})
        encrypted_accounts = await cursor.to_list(length=None)
        return [DataEncryption.decrypt_account_data(acc) for acc in encrypted_accounts]

    async def get_account(self, account_id: str):
        """Get account by ID"""
        from bson import ObjectId

        encrypted_account = await self.db.accounts.find_one({"_id": ObjectId(account_id)})
        if encrypted_account:
            return DataEncryption.decrypt_account_data(encrypted_account)
        return None

    async def update_account(self, account_id: str, **kwargs):
        """Update account"""
        from bson import ObjectId

        encrypted_updates = DataEncryption.encrypt_account_data(kwargs)
        await self.db.accounts.update_one(
            {"_id": ObjectId(account_id)}, {"$set": encrypted_updates}
        )

    async def delete_account(self, account_id: str):
        """Delete account"""
        from bson import ObjectId

        await self.db.accounts.delete_one({"_id": ObjectId(account_id)})

    async def get_account_by_phone(self, user_id: int, phone: str):
        """Get account by phone number"""
        # For phone lookup, we need to search by encrypted phone
        encrypted_phone = DataEncryption.encrypt_field(phone)
        encrypted_account = await self.db.accounts.find_one({"user_id": user_id, "phone_enc": encrypted_phone})
        if encrypted_account:
            return DataEncryption.decrypt_account_data(encrypted_account)
        return None

    async def add_audit_entry(self, account_id: str, entry: dict):
        """Add audit log entry to account"""
        from bson import ObjectId
        import time
        
        entry["timestamp"] = time.time()
        encrypted_entry = DataEncryption.encrypt_field(entry)
        await self.db.accounts.update_one(
            {"_id": ObjectId(account_id)},
            {"$push": {"audit_log_enc": encrypted_entry}}
        )

    async def get_active_accounts(self, user_id: int):
        """Get active accounts for user"""
        # For active lookup, we need to search by encrypted is_active
        encrypted_active = DataEncryption.encrypt_field(True)
        cursor = self.db.accounts.find({"user_id": user_id, "is_active_enc": encrypted_active})
        encrypted_accounts = await cursor.to_list(length=None)
        return [DataEncryption.decrypt_account_data(acc) for acc in encrypted_accounts]


# Global MongoDB instance
mongodb = MongoDB()


async def init_db():
    """Initialize MongoDB connection"""
    await mongodb.connect()


async def get_db():
    """Get MongoDB database instance"""
    return mongodb.db
