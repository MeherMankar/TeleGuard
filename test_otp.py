#!/usr/bin/env python3
"""
Quick OTP functionality test script
"""
import asyncio
import logging
from teleguard.core.mongo_database import init_db, mongodb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_otp_settings():
    """Test OTP settings in database"""
    try:
        await init_db()
        
        # Find accounts with OTP settings
        accounts = await mongodb.db.accounts.find({}).to_list(None)
        
        print(f"Found {len(accounts)} accounts:")
        for account in accounts:
            user_id = account.get('user_id')
            name = account.get('name', 'Unknown')
            destroyer_enabled = account.get('otp_destroyer_enabled', False)
            forward_enabled = account.get('otp_forward_enabled', False)
            
            print(f"  User {user_id} - {name}:")
            print(f"    OTP Destroyer: {'✅ Enabled' if destroyer_enabled else '❌ Disabled'}")
            print(f"    OTP Forward: {'✅ Enabled' if forward_enabled else '❌ Disabled'}")
            print()
        
        if not accounts:
            print("No accounts found. Add accounts via /start in the bot first.")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_otp_settings())