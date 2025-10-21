#!/usr/bin/env python3
"""
Cleanup orphaned accounts from database
"""
import asyncio
import logging
from teleguard.core.mongo_database import init_db, mongodb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def cleanup_accounts():
    """Remove accounts marked as inactive or orphaned"""
    try:
        await init_db()
        
        # Find all accounts
        all_accounts = await mongodb.db.accounts.find({}).to_list(None)
        print(f"Found {len(all_accounts)} total accounts")
        
        # Find inactive accounts
        inactive_accounts = await mongodb.db.accounts.find({"is_active": False}).to_list(None)
        print(f"Found {len(inactive_accounts)} inactive accounts")
        
        # Find accounts needing reauth
        reauth_accounts = await mongodb.db.accounts.find({"needs_reauth": True}).to_list(None)
        print(f"Found {len(reauth_accounts)} accounts needing reauth")
        
        # Show accounts to be cleaned
        cleanup_candidates = []
        for account in all_accounts:
            if (not account.get('is_active', True) or 
                account.get('needs_reauth', False) or
                not account.get('session_string')):
                cleanup_candidates.append(account)
        
        if cleanup_candidates:
            print(f"\nAccounts to cleanup ({len(cleanup_candidates)}):")
            for account in cleanup_candidates:
                user_id = account.get('user_id')
                name = account.get('name', 'Unknown')
                phone = account.get('phone', 'Unknown')
                reason = []
                if not account.get('is_active', True):
                    reason.append("inactive")
                if account.get('needs_reauth', False):
                    reason.append("needs_reauth")
                if not account.get('session_string'):
                    reason.append("no_session")
                
                print(f"  User {user_id} - {name} ({phone}) - {', '.join(reason)}")
            
            confirm = input(f"\nDelete these {len(cleanup_candidates)} accounts? (y/N): ")
            if confirm.lower() == 'y':
                # Delete inactive accounts
                result1 = await mongodb.db.accounts.delete_many({"is_active": False})
                result2 = await mongodb.db.accounts.delete_many({"needs_reauth": True})
                result3 = await mongodb.db.accounts.delete_many({"session_string": {"$exists": False}})
                
                total_deleted = result1.deleted_count + result2.deleted_count + result3.deleted_count
                print(f"✅ Deleted {total_deleted} accounts")
            else:
                print("❌ Cleanup cancelled")
        else:
            print("✅ No accounts need cleanup")
            
        # Show remaining accounts
        remaining = await mongodb.db.accounts.find({}).to_list(None)
        print(f"\nRemaining accounts: {len(remaining)}")
        for account in remaining:
            user_id = account.get('user_id')
            name = account.get('name', 'Unknown')
            destroyer = "✅" if account.get('otp_destroyer_enabled') else "❌"
            forward = "✅" if account.get('otp_forward_enabled') else "❌"
            print(f"  User {user_id} - {name}: Destroyer {destroyer} | Forward {forward}")
            
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")

if __name__ == "__main__":
    asyncio.run(cleanup_accounts())