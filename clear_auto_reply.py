#!/usr/bin/env python3
"""Emergency script to clear all auto-reply data"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from teleguard.core.mongo_database import mongodb

async def clear_all_auto_reply():
    """Clear all auto-reply data from database"""
    try:
        # Connect to database
        await mongodb.connect()
        
        # Clear all auto-reply settings
        result1 = await mongodb.db.auto_reply_settings.delete_many({})
        print(f"Deleted {result1.deleted_count} auto-reply settings")
        
        # Clear account auto-reply flags
        result2 = await mongodb.db.accounts.update_many(
            {},
            {"$unset": {"auto_reply_enabled": ""}}
        )
        print(f"Updated {result2.modified_count} accounts")
        
        print("✅ All auto-reply data cleared!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await mongodb.disconnect()

if __name__ == "__main__":
    asyncio.run(clear_all_auto_reply())