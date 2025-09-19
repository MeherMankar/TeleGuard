#!/usr/bin/env python3
"""
Migration script to populate display names for existing accounts
Run this once to fix "Unknown (Unknown)" display names
"""

import asyncio
import logging
import os
import sys
from telethon import TelegramClient
from telethon.sessions import StringSession

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from teleguard.core.config import API_ID, API_HASH
from teleguard.core.mongo_database import mongodb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def format_display_name(me):
    """Format display name from Telegram user object"""
    first = getattr(me, 'first_name', None) or ''
    last = getattr(me, 'last_name', None) or ''
    username = getattr(me, 'username', None)
    
    name = ' '.join(part for part in (first, last) if part)
    if name:
        return name
    elif username:
        return f'@{username}'
    else:
        return 'Unknown'

async def migrate_account_names():
    """Fetch and store real account names for all accounts"""
    try:
        await mongodb.connect()
        accounts = await mongodb.db.accounts.find({}).to_list(length=None)
        
        logger.info(f"Found {len(accounts)} accounts to migrate")
        
        for i, account in enumerate(accounts, 1):
            try:
                phone = account.get('phone', 'Unknown')
                session_string = account.get('session_string')
                
                if not session_string:
                    logger.warning(f"Account {phone} has no session string, skipping")
                    continue
                
                logger.info(f"[{i}/{len(accounts)}] Processing {phone}...")
                
                # Decrypt session if needed
                from teleguard.utils.data_encryption import decrypt_with_fernet
                try:
                    decrypted_session = decrypt_with_fernet(session_string)
                    if decrypted_session:
                        session_string = decrypted_session
                except:
                    pass  # Session might not be encrypted
                
                # Create client and fetch user info
                client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
                await client.connect()
                
                if not await client.is_user_authorized():
                    logger.warning(f"Account {phone} is not authorized, skipping")
                    await client.disconnect()
                    continue
                
                me = await client.get_me()
                
                # Format display name
                first_name = getattr(me, 'first_name', None) or ''
                last_name = getattr(me, 'last_name', None) or ''
                username = getattr(me, 'username', None)
                display_name = format_display_name(me)
                
                # Update database
                await mongodb.db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$set": {
                        "first_name": first_name,
                        "last_name": last_name,
                        "username": username,
                        "display_name": display_name,
                        "name": display_name  # Update name field too
                    }}
                )
                
                logger.info(f"✅ Updated {phone} -> {display_name}")
                await client.disconnect()
                
                # Rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Failed to process {account.get('phone', 'Unknown')}: {e}")
                await asyncio.sleep(1)
                continue
        
        logger.info("Migration completed!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
    finally:
        try:
            await mongodb.close()
        except AttributeError:
            pass  # MongoDB object might not have close method

if __name__ == "__main__":
    asyncio.run(migrate_account_names())