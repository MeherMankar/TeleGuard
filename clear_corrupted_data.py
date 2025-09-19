#!/usr/bin/env python3
"""
Clear corrupted encrypted data from MongoDB

This script removes corrupted encrypted data that cannot be decrypted
"""

import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient

async def clear_corrupted_data():
    """Clear corrupted encrypted data from MongoDB"""
    
    # Connect to MongoDB
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        print("MONGO_URI environment variable required")
        return
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client.teleguard
    
    try:
        # Test connection
        await client.admin.command("ping")
        print("Connected to MongoDB")
        
        # Clear corrupted users
        users_result = await db.users.delete_many({
            "$or": [
                {"developer_mode_enc": {"$exists": True}},
                {"settings_enc": {"$exists": True}},
                {"preferences_enc": {"$exists": True}}
            ]
        })
        print(f"Removed {users_result.deleted_count} corrupted user records")
        
        # Clear corrupted accounts
        accounts_result = await db.accounts.delete_many({
            "$or": [
                {"session_string_enc": {"$exists": True}},
                {"name_enc": {"$exists": True}},
                {"phone_enc": {"$exists": True}}
            ]
        })
        print(f"Removed {accounts_result.deleted_count} corrupted account records")
        
        print("Database cleanup completed")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv("config/.env")
    
    asyncio.run(clear_corrupted_data())