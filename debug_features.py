#!/usr/bin/env python3
"""Debug script to check online maker and OTP destroyer status"""

import asyncio
import logging
from teleguard.core.mongo_database import mongodb
from teleguard.utils.data_encryption import DataEncryption

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_features():
    """Debug online maker and OTP destroyer for user"""
    user_id = 6121637257  # Your user ID
    
    try:
        # Connect to database
        await mongodb.connect()
        
        # Get all accounts for user
        encrypted_accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        
        print(f"\n=== FEATURE STATUS FOR USER {user_id} ===")
        print(f"Found {len(encrypted_accounts)} accounts")
        
        for i, enc_acc in enumerate(encrypted_accounts, 1):
            try:
                # Decrypt account data
                account = DataEncryption.decrypt_account_data(enc_acc)
                
                print(f"\n--- Account {i}: {account.get('name', 'N/A')} ---")
                print(f"Phone: {account.get('phone', 'N/A')}")
                print(f"Active: {account.get('is_active', False)}")
                
                # Online Maker Status
                online_maker = account.get('online_maker_enabled', False)
                print(f"Online Maker: {'✅ Enabled' if online_maker else '❌ Disabled'}")
                
                # OTP Destroyer Status
                otp_destroyer = account.get('otp_destroyer_enabled', False)
                print(f"OTP Destroyer: {'✅ Enabled' if otp_destroyer else '❌ Disabled'}")
                
                # Auto-reply Status
                auto_reply = account.get('auto_reply_enabled', False)
                print(f"Auto-Reply: {'✅ Enabled' if auto_reply else '❌ Disabled'}")
                
                # Check all available fields
                print(f"Available fields: {list(account.keys())}")
                
            except Exception as e:
                print(f"Error decrypting account {i}: {e}")
                print(f"Raw account data: {enc_acc}")
        
        print(f"\n=== FIXING ISSUES ===")
        
        # Enable online maker and OTP destroyer for all accounts
        for enc_acc in encrypted_accounts:
            try:
                account = DataEncryption.decrypt_account_data(enc_acc)
                account_name = account.get('name', 'Unknown')
                
                # Update account with proper feature flags
                update_data = {
                    "online_maker_enabled": True,
                    "otp_destroyer_enabled": True,
                    "is_active": True
                }
                
                result = await mongodb.db.accounts.update_one(
                    {"_id": enc_acc["_id"]},
                    {"$set": update_data}
                )
                
                if result.modified_count > 0:
                    print(f"✅ Updated {account_name}: Online Maker + OTP Destroyer enabled")
                else:
                    print(f"⚠️ No changes made to {account_name}")
                    
            except Exception as e:
                print(f"❌ Error updating account: {e}")
                
    except Exception as e:
        logger.error(f"Debug error: {e}")
    finally:
        await mongodb.disconnect()

if __name__ == "__main__":
    asyncio.run(debug_features())