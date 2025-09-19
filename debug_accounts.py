#!/usr/bin/env python3
"""Debug script to check accounts and fix auto-reply issues"""

import asyncio
import logging
from teleguard.core.mongo_database import mongodb
from teleguard.utils.data_encryption import DataEncryption

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_accounts():
    """Debug accounts for user"""
    user_id = 6121637257  # Your user ID from the logs
    
    try:
        # Connect to database
        await mongodb.connect()
        
        # Get all accounts for user
        encrypted_accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        
        print(f"\n=== ACCOUNTS FOR USER {user_id} ===")
        print(f"Found {len(encrypted_accounts)} accounts")
        
        for i, enc_acc in enumerate(encrypted_accounts, 1):
            try:
                # Decrypt account data
                account = DataEncryption.decrypt_account_data(enc_acc)
                
                print(f"\n--- Account {i} ---")
                print(f"ID: {enc_acc.get('_id')}")
                print(f"Name: {account.get('name', 'N/A')}")
                print(f"Phone: {account.get('phone', 'N/A')}")
                print(f"Username: {account.get('username', 'N/A')}")
                print(f"Auto-reply enabled: {account.get('auto_reply_enabled', False)}")
                print(f"Active: {account.get('is_active', False)}")
                
                # Check encrypted fields
                print(f"Encrypted fields: {[k for k in enc_acc.keys() if k.endswith('_enc')]}")
                
            except Exception as e:
                print(f"Error decrypting account {i}: {e}")
        
        # Check auto-reply settings
        print(f"\n=== AUTO-REPLY SETTINGS ===")
        settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id})
        if settings:
            print(f"Settings found: {settings}")
        else:
            print("No auto-reply settings found")
            
    except Exception as e:
        logger.error(f"Debug error: {e}")
    finally:
        await mongodb.disconnect()

if __name__ == "__main__":
    asyncio.run(debug_accounts())