#!/usr/bin/env python3
"""
Cleanup script to remove orphaned accounts without session strings
"""
import asyncio
import logging
from teleguard.core.mongo_database import get_db, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def cleanup_orphaned_accounts():
    """Remove accounts that have no session string"""
    await init_db()
    db = await get_db()
    
    # Find accounts without session strings
    orphaned_accounts = []
    async for account in db.accounts.find({}):
        session_string = account.get('session_string')
        if not session_string or session_string.strip() == '':
            orphaned_accounts.append(account)
    
    logger.info(f"Found {len(orphaned_accounts)} orphaned accounts")
    
    if not orphaned_accounts:
        logger.info("No orphaned accounts found")
        return
    
    # Show what will be deleted
    for account in orphaned_accounts:
        display_name = account.get('display_name', 'Unknown')
        phone = account.get('phone', 'No phone')
        logger.info(f"Will delete: {display_name} ({phone})")
    
    # Confirm deletion
    confirm = input(f"\nDelete {len(orphaned_accounts)} orphaned accounts? (y/N): ")
    if confirm.lower() != 'y':
        logger.info("Cleanup cancelled")
        return
    
    # Delete orphaned accounts
    deleted_count = 0
    for account in orphaned_accounts:
        result = await db.accounts.delete_one({'_id': account['_id']})
        if result.deleted_count > 0:
            deleted_count += 1
            logger.info(f"Deleted account: {account.get('display_name', 'Unknown')}")
    
    logger.info(f"Cleanup completed! Deleted {deleted_count} orphaned accounts")

if __name__ == "__main__":
    asyncio.run(cleanup_orphaned_accounts())