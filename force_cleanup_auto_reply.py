#!/usr/bin/env python3
"""Force cleanup all auto-reply handlers and data"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from teleguard.core.mongo_database import mongodb

async def force_cleanup():
    """Force cleanup all auto-reply data and handlers"""
    try:
        await mongodb.connect()
        
        print("Starting force cleanup...")
        
        # 1. Clear all auto-reply settings
        result1 = await mongodb.db.auto_reply_settings.delete_many({})
        print(f"Deleted {result1.deleted_count} auto-reply settings")
        
        # 2. Disable auto-reply for all accounts
        result2 = await mongodb.db.accounts.update_many(
            {},
            {"$unset": {"auto_reply_enabled": ""}}
        )
        print(f"Updated {result2.modified_count} accounts")
        
        # 3. Clear any cached auto-reply data
        result3 = await mongodb.db.cache.delete_many({"type": "auto_reply"})
        print(f"Cleared {result3.deleted_count} cache entries")
        
        print("\nForce cleanup complete!")
        print("Next steps:")
        print("1. Restart the bot")
        print("2. Re-enable auto-reply per account")
        print("3. Add new keywords")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
    finally:
        try:
            await mongodb.disconnect()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(force_cleanup())