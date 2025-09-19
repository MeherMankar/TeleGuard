"""Database connections for backup system"""

import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Environment variables
MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Global connections
mongo_client = None
db = None
redis = None

async def init_connections():
    """Initialize database connections"""
    global mongo_client, db, redis
    
    if not mongo_client and MONGO_URI:
        mongo_client = AsyncIOMotorClient(MONGO_URI)
        db = mongo_client.teleguard
        await mongo_client.admin.command("ping")
        logger.info("MongoDB connected for backups")
    
    if not redis:
        try:
            redis = aioredis.from_url(REDIS_URL, decode_responses=True)
            await redis.ping()
            logger.info("Redis connected for backups")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            redis = None

async def fetch_snapshot_collections():
    """Fetch all collections for snapshot"""
    if not db:
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
        if db:
            await db.backups_meta.insert_one(meta_data)
        elif redis:
            await redis.lpush("backup_meta", str(meta_data))
            await redis.ltrim("backup_meta", 0, 99)  # Keep last 100
    except Exception as e:
        logger.error(f"Failed to store backup meta: {e}")

async def get_old_telegram_messages(older_than_timestamp):
    """Get old Telegram backup messages for cleanup"""
    if not db:
        return []
    
    cursor = db.backups_meta.find({
        "type": "telegram_snapshot",
        "timestamp": {"$lt": older_than_timestamp}
    })
    return await cursor.to_list(length=None)

async def delete_backup_meta(message_id):
    """Delete backup metadata"""
    if db:
        await db.backups_meta.delete_one({"message_id": message_id})