#!/usr/bin/env python3
"""Simple debug script for features"""

import asyncio
import logging
from teleguard.core.mongo_database import mongodb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_features():
    """Check feature status"""
    user_id = 6121637257
    
    try:
        await mongodb.connect()
        
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        
        print(f"Found {len(accounts)} accounts")
        
        for i, account in enumerate(accounts, 1):
            name = account.get('name', 'Unknown')
            phone = account.get('phone', 'N/A')
            
            online_maker = account.get('online_maker_enabled', False)
            otp_destroyer = account.get('otp_destroyer_enabled', False)
            auto_reply = account.get('auto_reply_enabled', False)
            is_active = account.get('is_active', False)
            
            print(f"\nAccount {i}: {name}")
            print(f"Phone: {phone}")
            print(f"Active: {is_active}")
            print(f"Online Maker: {online_maker}")
            print(f"OTP Destroyer: {otp_destroyer}")
            print(f"Auto Reply: {auto_reply}")
            
            # Check if features are working
            if not online_maker:
                print("ISSUE: Online Maker disabled")
            if not otp_destroyer:
                print("ISSUE: OTP Destroyer disabled")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await mongodb.disconnect()

if __name__ == "__main__":
    asyncio.run(check_features())