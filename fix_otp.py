#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix OTP forwarding for all accounts"""
import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')
from teleguard.core.mongo_database import mongodb

async def enable_otp_forward_all():
    """Enable OTP forwarding for all accounts"""
    try:
        await mongodb.connect()
        
        # Enable OTP forwarding for all accounts
        result = await mongodb.db.accounts.update_many(
            {"user_id": 6121637257},  # Your user ID
            {"$set": {"otp_forward_enabled": True}}
        )
        
        print(f"Enabled OTP forwarding for {result.modified_count} accounts")
        
        # Verify the changes
        accounts = await mongodb.db.accounts.find({"user_id": 6121637257}).to_list(None)
        for account in accounts:
            name = account.get('name', 'Unknown')
            forward_enabled = account.get('otp_forward_enabled', False)
            print(f"  {name}: OTP Forward = {forward_enabled}")
        
        print("\nOTP forwarding is now enabled for all your accounts!")
        print("You should now receive OTP codes via the bot.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await mongodb.disconnect()

if __name__ == "__main__":
    asyncio.run(enable_otp_forward_all())