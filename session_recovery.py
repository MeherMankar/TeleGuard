#!/usr/bin/env python3
"""Session conflict recovery script"""

import asyncio
import logging
from teleguard.core.mongo_database import mongodb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def recover_sessions():
    """Clear session conflicts and reset accounts"""
    user_id = 6121637257
    
    try:
        await mongodb.connect()
        
        # Clear all session conflicts
        result = await mongodb.db.accounts.update_many(
            {"user_id": user_id},
            {"$unset": {"session_conflict": "", "last_conflict": ""}}
        )
        
        print(f"Cleared session conflicts for {result.modified_count} accounts")
        
        # Re-enable online maker for accounts that had it enabled
        result2 = await mongodb.db.accounts.update_many(
            {"user_id": user_id, "online_maker_enabled": {"$ne": True}},
            {"$set": {"online_maker_enabled": True}}
        )
        
        print(f"Re-enabled online maker for {result2.modified_count} accounts")
        
        print("\nSession conflicts cleared. Restart the bot to apply changes.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await mongodb.disconnect()

if __name__ == "__main__":
    asyncio.run(recover_sessions())