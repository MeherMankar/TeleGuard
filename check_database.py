#!/usr/bin/env python3
"""Check database contents"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from teleguard.core.mongo_database import mongodb
from teleguard.utils.data_encryption import DataEncryption

async def check_database():
    """Check what's in the database"""
    try:
        await mongodb.connect()
        
        # Check users
        users = await mongodb.db.users.find({}).to_list(length=None)
        print(f"Users in database: {len(users)}")
        for user in users:
            decrypted = DataEncryption.decrypt_user_data(user) if any(k.endswith('_enc') for k in user.keys()) else user
            print(f"  - User ID: {decrypted.get('telegram_id', 'Unknown')}")
        
        # Check accounts
        accounts = await mongodb.db.accounts.find({}).to_list(length=None)
        print(f"\nAccounts in database: {len(accounts)}")
        for account in accounts:
            decrypted = DataEncryption.decrypt_account_data(account) if any(k.endswith('_enc') for k in account.keys()) else account
            print(f"  - Account: {decrypted.get('name', 'Unknown')} (User: {account.get('user_id', 'Unknown')})")
            print(f"    Has session: {'Yes' if decrypted.get('session_string') else 'No'}")
            print(f"    Is active: {decrypted.get('is_active', False)}")
        
        await mongodb.disconnect()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_database())