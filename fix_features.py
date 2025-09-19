#!/usr/bin/env python3
"""Fix online maker and OTP destroyer issues"""

import asyncio
import logging
from teleguard.core.mongo_database import mongodb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_features():
    """Fix feature issues"""
    user_id = 6121637257
    
    try:
        await mongodb.connect()
        
        # Get accounts
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        
        print(f"Fixing features for {len(accounts)} accounts...")
        
        for account in accounts:
            account_name = account.get('name', 'Unknown')
            
            # Ensure all features are properly enabled
            update_data = {
                "online_maker_enabled": True,
                "otp_destroyer_enabled": True,
                "is_active": True,
                "auto_reply_enabled": True
            }
            
            result = await mongodb.db.accounts.update_one(
                {"_id": account["_id"]},
                {"$set": update_data}
            )
            
            print(f"Updated {account_name}: {result.modified_count} changes")
        
        print("\n=== RESTART YOUR BOT NOW ===")
        print("The features should work after bot restart.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await mongodb.disconnect()

if __name__ == "__main__":
    asyncio.run(fix_features())