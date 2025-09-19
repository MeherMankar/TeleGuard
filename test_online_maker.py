#!/usr/bin/env python3
"""Test online maker functionality"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load environment variables
env_path = Path(__file__).parent / "config" / ".env"
load_dotenv(env_path)

async def test_online_maker():
    """Test online maker setup"""
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        print("❌ MONGO_URI not found")
        return
    
    try:
        client = AsyncIOMotorClient(mongo_uri)
        db = client.teleguard
        
        # Test connection
        await client.admin.command("ping")
        print("✅ Connected to MongoDB")
        
        # Check accounts with online maker enabled
        accounts = await db.accounts.find({"online_maker_enabled": True}).to_list(length=None)
        print(f"📊 Found {len(accounts)} accounts with online maker enabled")
        
        for account in accounts:
            user_id = account.get("user_id")
            phone = account.get("phone", "Unknown")
            name = account.get("name", "Unknown")
            display_name = account.get("display_name", "Unknown")
            
            print(f"  - User: {user_id}")
            print(f"    Phone: {phone}")
            print(f"    Name: {name}")
            print(f"    Display: {display_name}")
            print(f"    Session: {'Yes' if account.get('session_string') else 'No'}")
            print()
            
        # Check all accounts
        all_accounts = await db.accounts.find({}).to_list(length=None)
        print(f"📊 Total accounts: {len(all_accounts)}")
        
        for account in all_accounts:
            user_id = account.get("user_id")
            phone = account.get("phone", "Unknown")
            name = account.get("name", "Unknown")
            online_enabled = account.get("online_maker_enabled", False)
            
            print(f"  - User: {user_id}, Phone: {phone}, Name: {name}, Online: {online_enabled}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_online_maker())