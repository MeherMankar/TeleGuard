#!/usr/bin/env python3
"""
Manual backup script with data encryption for TeleGuard
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from teleguard.core.config import API_ID, API_HASH, BOT_TOKEN
from teleguard.utils.session_backup import SessionBackupManager
from telethon import TelegramClient

async def manual_backup():
    """Run manual backup to Telegram channel"""
    try:
        # Initialize bot client
        bot = TelegramClient('manual_backup_session', API_ID, API_HASH)
        await bot.start(bot_token=BOT_TOKEN)
        
        # Connect to MongoDB
        from teleguard.core.mongo_database import mongodb
        await mongodb.connect()
        
        # Initialize backup manager
        backup_manager = SessionBackupManager()
        
        print("Starting manual backup...")
        
        # Backup user settings (encrypted)
        print("1. Backing up user settings...")
        settings_success = await backup_manager.push_user_settings_to_telegram(bot)
        if settings_success:
            print("User settings backup completed")
        else:
            print("User settings backup failed")
        
        # Backup user IDs (unencrypted)
        print("2. Backing up user IDs...")
        ids_success = await backup_manager.push_user_ids_to_telegram(bot)
        if ids_success:
            print("User IDs backup completed")
        else:
            print("User IDs backup failed")
        
        # Backup session files (encrypted)
        print("3. Backing up session files...")
        sessions_files_success = await backup_manager.push_session_files_to_telegram(bot)
        if sessions_files_success:
            print("Session files backup completed")
        else:
            print("Session files backup failed")
        
        # Backup sessions (GitHub)
        print("4. Backing up sessions to GitHub...")
        sessions_success = backup_manager.push_sessions_batch()
        if sessions_success:
            print("GitHub sessions backup completed")
        else:
            print("GitHub sessions backup failed")
        
        # Encrypt existing data (if needed)
        print("5. Checking for unencrypted data...")
        try:
            from teleguard.utils.data_encryption import DataEncryption
            from teleguard.core.mongo_database import mongodb
            
            await mongodb.connect()
            
            # Check and migrate users
            users = await mongodb.db.users.find({}).to_list(length=None)
            user_count = 0
            for user in users:
                if not any(key.endswith('_enc') for key in user.keys()):
                    encrypted_data = DataEncryption.encrypt_user_data(user)
                    await mongodb.db.users.replace_one({"_id": user["_id"]}, encrypted_data)
                    user_count += 1
            
            # Check and migrate accounts
            accounts = await mongodb.db.accounts.find({}).to_list(length=None)
            account_count = 0
            for account in accounts:
                if not any(key.endswith('_enc') for key in account.keys()):
                    encrypted_data = DataEncryption.encrypt_account_data(account)
                    await mongodb.db.accounts.replace_one({"_id": account["_id"]}, encrypted_data)
                    account_count += 1
            
            if user_count > 0 or account_count > 0:
                print(f"Data encryption completed: {user_count} users, {account_count} accounts")
            else:
                print("All data already encrypted")
                
            await mongodb.disconnect()
                
        except Exception as e:
            print(f"Data encryption failed: {e}")
        
        print("\nManual backup completed!")
        
    except Exception as e:
        print(f"Backup failed: {e}")
    finally:
        if 'bot' in locals():
            await bot.disconnect()
        if 'mongodb' in locals():
            await mongodb.disconnect()

if __name__ == "__main__":
    asyncio.run(manual_backup())