"""Data encryption migration script

Migrates existing unencrypted data to encrypted format.

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from teleguard.core.mongo_database import mongodb
from teleguard.utils.data_encryption import DataEncryption

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_users():
    """Migrate user data to encrypted format"""
    logger.info("Starting user data migration...")
    
    # Get all users
    users = await mongodb.db.users.find({}).to_list(length=None)
    migrated_count = 0
    
    for user in users:
        # Check if already encrypted (has _enc fields)
        if any(key.endswith('_enc') for key in user.keys()):
            continue
        
        # Encrypt user data
        encrypted_data = DataEncryption.encrypt_user_data(user)
        
        # Update in database
        await mongodb.db.users.replace_one(
            {"_id": user["_id"]}, 
            encrypted_data
        )
        migrated_count += 1
    
    logger.info(f"Migrated {migrated_count} users")


async def migrate_accounts():
    """Migrate account data to encrypted format"""
    logger.info("Starting account data migration...")
    
    # Get all accounts
    accounts = await mongodb.db.accounts.find({}).to_list(length=None)
    migrated_count = 0
    
    for account in accounts:
        # Check if already encrypted (has _enc fields)
        if any(key.endswith('_enc') for key in account.keys()):
            continue
        
        # Encrypt account data
        encrypted_data = DataEncryption.encrypt_account_data(account)
        
        # Update in database
        await mongodb.db.accounts.replace_one(
            {"_id": account["_id"]}, 
            encrypted_data
        )
        migrated_count += 1
    
    logger.info(f"Migrated {migrated_count} accounts")


async def main():
    """Run migration"""
    try:
        # Connect to database
        await mongodb.connect()
        logger.info("Connected to MongoDB")
        
        # Run migrations
        await migrate_users()
        await migrate_accounts()
        
        logger.info("Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        await mongodb.disconnect()


if __name__ == "__main__":
    asyncio.run(main())