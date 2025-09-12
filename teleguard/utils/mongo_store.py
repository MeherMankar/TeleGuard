"""MongoDB integration for session temporary storage

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import logging
import os
from datetime import datetime, timezone

from pymongo import ASCENDING, MongoClient

logger = logging.getLogger(__name__)

# MongoDB connection
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["rambadb"]

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
    # Validate inputs to prevent NoSQL injection
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

    # Check if same hash already exists and is persisted
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
        # Topics indexes
        topics.create_index(
            [("managed_account_id", ASCENDING), ("remote_user_id", ASCENDING)],
            unique=True,
        )
        topics.create_index(
            [("topic_chat_id", ASCENDING), ("message_thread_id", ASCENDING)]
        )
        topics.create_index([("status", ASCENDING)])
        topics.create_index([("last_activity", ASCENDING)])

        # Topic messages indexes
        topic_messages.create_index([("topic_id", ASCENDING)])
        topic_messages.create_index([("status", ASCENDING)])
        topic_messages.create_index([("ts", ASCENDING)])

        logger.info("Topic routing indexes created successfully")
    except Exception as e:
        logger.error(f"Failed to create topic indexes: {e}")
        raise
