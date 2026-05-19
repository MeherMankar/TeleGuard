"""Database connections for backup system"""

import logging
from ..core.mongo_database import mongodb, init_db
from ..core.redis_cache import redis_cache, init_redis

logger = logging.getLogger(__name__)

# Global connections for backwards compatibility
db = None
redis = None


async def init_connections():
    """Initialize database connections using shared managers"""
    global db, redis
    try:
        await init_db()
        db = mongodb.db
        logger.info("MongoDB connected for backups (shared instance)")
    except Exception as e:
        logger.error(f"MongoDB connection failed for backups: {e}")

    try:
        await init_redis()
        if redis_cache.connected:
            redis = redis_cache.client
            logger.info("Redis connected for backups (shared instance)")
        else:
            redis = None
    except Exception as e:
        logger.warning(f"Redis connection failed for backups: {e}")
        redis = None


async def fetch_snapshot_collections():
    """Fetch all collections for snapshot"""
    global db
    if db is None:
        await init_connections()
    data = {}
    # Users collection
    users_cursor = db.users.find({}, {"_id": 0})
    data["users"] = await users_cursor.to_list(length=None)
    # Accounts collection
    accounts_cursor = db.accounts.find({}, {"_id": 0})
    data["accounts"] = await accounts_cursor.to_list(length=None)
    # Backup metadata
    meta_cursor = db.backups_meta.find({}, {"_id": 0})
    data["backups_meta"] = await meta_cursor.to_list(length=None)
    return data


async def store_backup_meta(meta_data):
    """Store backup metadata in MongoDB or Redis fallback"""
    try:
        if db is not None:
            await db.backups_meta.insert_one(meta_data)
        elif redis is not None:
            await redis.lpush("backup_meta", str(meta_data))
            await redis.ltrim("backup_meta", 0, 99)  # Keep last 100
    except Exception as e:
        logger.error(f"Failed to store backup meta: {e}")


async def get_old_telegram_messages(older_than_timestamp):
    """Get old Telegram backup messages for cleanup"""
    if db is None:
        return []
    if not isinstance(older_than_timestamp, (int, float)):
        return []
    cursor = db.backups_meta.find(
        {"type": "telegram_snapshot", "timestamp": {"$lt": int(older_than_timestamp)}}
    )
    return await cursor.to_list(length=None)


async def delete_backup_meta(message_id):
    """Delete backup metadata"""
    if db is not None:
        await db.backups_meta.delete_one({"message_id": message_id})
