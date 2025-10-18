"""Unified MongoDB integration and secure database operations
Developed by:
- @Meher_Mankar
- @Gutkesh
GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pymongo import ASCENDING, MongoClient
from bson import ObjectId
from bson.errors import InvalidId
logger = logging.getLogger(__name__)
# MongoDB connection from environment
MONGO_URI = os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI or MONGODB_URI environment variable is required")

DB_NAME = os.environ.get("MONGO_DB_NAME", "teleguard")
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
# Collections
sessions_temp = db["sessions_temp"]
session_audit = db["session_audit"]
sessions_manifest_archive = db["sessions_manifest_archive"]
def init_mongo_indexes():
    """Initialize MongoDB indexes"""
    try:
        # Sessions temp indexes
        sessions_temp.create_index([("account_id", ASCENDING)])
        sessions_temp.create_index([("created_at", ASCENDING)])
        sessions_temp.create_index([("persisted_to_github", ASCENDING)])
        # Audit indexes
        session_audit.create_index([("ts", ASCENDING)])
        session_audit.create_index([("action", ASCENDING)])
        logger.info("MongoDB indexes created successfully")
    except Exception as e:
        logger.error(f"Failed to create MongoDB indexes: {e}")
        raise
def store_session_temp(
    account_id: str, encrypted_bytes: bytes, sha256_hash: str
) -> dict:
    """Store encrypted session in temporary MongoDB collection"""
    if (
        not isinstance(account_id, str)
        or not account_id.replace("_", "").replace("-", "").isalnum()
    ):
        raise ValueError("Invalid account_id format")
    if (
        not isinstance(sha256_hash, str)
        or len(sha256_hash) != 64
        or not all(c in "0123456789abcdef" for c in sha256_hash.lower())
    ):
        raise ValueError("Invalid SHA256 hash format")
    now = datetime.now(timezone.utc)
    existing = sessions_temp.find_one({"account_id": account_id})
    if (
        existing
        and existing.get("sha256") == sha256_hash
        and existing.get("persisted_to_github")
    ):
        # Just update timestamp
        sessions_temp.update_one(
            {"_id": existing["_id"]}, {"$set": {"last_updated": now}}
        )
        return existing
    # Store new/updated session
    doc = {
        "account_id": account_id,
        "enc_blob": encrypted_bytes,
        "sha256": sha256_hash,
        "created_at": now,
        "last_updated": now,
        "persisted_to_github": False,
        "github_path": None,
        "github_commit": None,
        "manifest_version": None,
    }
    sessions_temp.update_one({"account_id": account_id}, {"$set": doc}, upsert=True)
    return sessions_temp.find_one({"account_id": account_id})
def get_unpersisted_sessions() -> list:
    """Get sessions that haven't been pushed to GitHub"""
    return list(sessions_temp.find({"persisted_to_github": False}))
def mark_session_persisted(account_id: str, commit_sha: str, manifest_version: str):
    """Mark session as persisted to GitHub"""
    sessions_temp.update_one(
        {"account_id": account_id},
        {
            "$set": {
                "persisted_to_github": True,
                "github_commit": commit_sha,
                "github_path": f"sessions/{account_id}.enc",
                "manifest_version": manifest_version,
            }
        },
    )
def log_audit_event(
    account_id: str, action: str, details: dict, initiator: str = "system"
):
    """Log audit event"""
    session_audit.insert_one(
        {
            "account_id": account_id,
            "action": action,
            "details": details,
            "ts": datetime.utcnow(),
            "initiator": initiator,
        }
    )
def cleanup_old_sessions(days: int = 7):
    """Clean up old persisted sessions from MongoDB"""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = sessions_temp.delete_many(
        {"persisted_to_github": True, "created_at": {"$lt": cutoff}}
    )
    logger.info(f"Cleaned up {result.deleted_count} old sessions from MongoDB")
    return result.deleted_count
# Topic routing collections
topics = db["topics"]
topic_messages = db["topic_messages"]

def init_topic_indexes():
    """Initialize topic routing indexes"""
    try:
        topics.create_index(
            [("managed_account_id", ASCENDING), ("remote_user_id", ASCENDING)],
            unique=True,
        )
        topics.create_index(
            [("topic_chat_id", ASCENDING), ("message_thread_id", ASCENDING)]
        )
        topics.create_index([("status", ASCENDING)])
        topics.create_index([("last_activity", ASCENDING)])
        topic_messages.create_index([("topic_id", ASCENDING)])
        topic_messages.create_index([("status", ASCENDING)])
        topic_messages.create_index([("ts", ASCENDING)])
    except Exception as e:
        logger.error(f"Failed to create topic indexes: {e}")
        raise

class SecureDatabase:
    """Secure database operations wrapper"""
    def __init__(self, db_instance):
        self.db = db_instance

    def _validate_user_id(self, user_id: Any) -> Optional[int]:
        if user_id is None:
            return None
        try:
            uid = int(user_id)
            return uid if uid > 0 else None
        except (ValueError, TypeError, OverflowError):
            return None

    def _validate_object_id(self, obj_id: Any) -> Optional[str]:
        try:
            if isinstance(obj_id, str) and ObjectId.is_valid(obj_id):
                return str(ObjectId(obj_id))
        except InvalidId:
            pass
        return None

    def _sanitize_text_input(self, text: str, max_length: int = 1000) -> str:
        if not isinstance(text, str):
            return ""
        import re
        clean_text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        clean_text = ' '.join(clean_text.split())
        return clean_text[:max_length] if clean_text else ""

    def _validate_database_field(self, field_name: str) -> bool:
        if not isinstance(field_name, str):
            return False
        import re
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', field_name))

    async def find_user_account(self, user_id: int, account_id: str) -> Optional[Dict]:
        clean_user_id = self._validate_user_id(user_id)
        clean_account_id = self._validate_object_id(account_id)
        if not clean_user_id or not clean_account_id:
            return None
        try:
            return await self.db.accounts.find_one({
                "user_id": clean_user_id,
                "_id": ObjectId(clean_account_id)
            })
        except Exception:
            return None

    async def update_user_account(self, user_id: int, account_id: str, 
                                update_data: Dict[str, Any]) -> bool:
        clean_user_id = self._validate_user_id(user_id)
        clean_account_id = self._validate_object_id(account_id)
        if not clean_user_id or not clean_account_id:
            return False
        safe_update = self._sanitize_update_data(update_data)
        if not safe_update:
            return False
        try:
            result = await self.db.accounts.update_one(
                {"user_id": clean_user_id, "_id": ObjectId(clean_account_id)},
                {"$set": safe_update}
            )
            return result.modified_count > 0
        except Exception:
            return False

    async def find_user_accounts(self, user_id: int) -> List[Dict]:
        clean_user_id = self._validate_user_id(user_id)
        if not clean_user_id:
            return []
        try:
            cursor = self.db.accounts.find({"user_id": clean_user_id})
            return await cursor.to_list(length=None)
        except Exception:
            return []

    async def create_audit_entry(self, user_id: int, account_id: str, 
                               action: str, details: Dict[str, Any]) -> bool:
        clean_user_id = self._validate_user_id(user_id)
        clean_account_id = self._validate_object_id(account_id)
        clean_action = self._sanitize_text_input(action, 100)
        if not clean_user_id or not clean_account_id or not clean_action:
            return False
        safe_details = self._sanitize_dict(details)
        try:
            audit_entry = {
                "user_id": clean_user_id,
                "account_id": clean_account_id,
                "action": clean_action,
                "details": safe_details,
                "timestamp": datetime.now(timezone.utc),
                "ip_address": None
            }
            await self.db.audit_logs.insert_one(audit_entry)
            return True
        except Exception:
            return False

    def _sanitize_update_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(data, dict):
            return None
        safe_data = {}
        allowed_fields = {
            'otp_destroyer_enabled', 'otp_forward_enabled', 'auto_reply_enabled',
            'online_maker_enabled', 'simulation_enabled', 'display_name',
            'last_activity', 'is_active', 'settings'
        }
        for key, value in data.items():
            if not self._validate_database_field(key) or key not in allowed_fields:
                continue
            if isinstance(value, str):
                safe_data[key] = self._sanitize_text_input(value)
            elif isinstance(value, (bool, int, float)):
                safe_data[key] = value
            elif isinstance(value, dict):
                safe_data[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                safe_data[key] = self._sanitize_list(value)
        return safe_data if safe_data else None

    def _sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        safe_dict = {}
        for key, value in data.items():
            if not self._validate_database_field(key):
                continue
            if isinstance(value, str):
                safe_dict[key] = self._sanitize_text_input(value)
            elif isinstance(value, (bool, int, float)):
                safe_dict[key] = value
            elif isinstance(value, dict):
                safe_dict[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                safe_dict[key] = self._sanitize_list(value)
        return safe_dict

    def _sanitize_list(self, data: List[Any]) -> List[Any]:
        if not isinstance(data, list):
            return []
        safe_list = []
        for item in data[:100]:
            if isinstance(item, str):
                safe_list.append(self._sanitize_text_input(item))
            elif isinstance(item, (bool, int, float)):
                safe_list.append(item)
            elif isinstance(item, dict):
                safe_list.append(self._sanitize_dict(item))
        return safe_list
