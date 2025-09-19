#!/usr/bin/env python3
"""
Database consistency check script
"""
import asyncio
import logging
from teleguard.core.mongo_database import get_db, init_db
from teleguard.db_helpers import decrypt_with_fernet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_database_consistency():
    """Check database for inconsistencies and corruption"""
    await init_db()
    db = await get_db()
    
    logger.info("Starting database consistency check...")
    
    issues = []
    total_accounts = 0
    
    async for account in db.accounts.find({}):
        total_accounts += 1
        account_id = str(account['_id'])
        display_name = account.get('display_name', 'Unknown')
        
        # Check required fields
        if not account.get('user_id'):
            issues.append(f"Account {display_name} missing user_id")
        
        if not account.get('phone'):
            issues.append(f"Account {display_name} missing phone")
        
        # Check session string
        session_string = account.get('session_string')
        if not session_string:
            issues.append(f"Account {display_name} missing session_string")
        elif session_string.strip() == '':
            issues.append(f"Account {display_name} has empty session_string")
        else:
            # Try to decrypt session string
            try:
                decrypted = decrypt_with_fernet(session_string)
                if not decrypted or len(decrypted) < 10:
                    issues.append(f"Account {display_name} has invalid session_string")
            except Exception as e:
                issues.append(f"Account {display_name} session_string decryption failed: {e}")
        
        # Check display name
        if not account.get('display_name') or account.get('display_name') == 'Unknown':
            issues.append(f"Account {account.get('phone', account_id)} needs display_name update")
    
    # Check user settings
    settings_count = await db.user_settings.count_documents({})
    
    # Check audit logs
    audit_count = await db.audit_logs.count_documents({})
    
    # Report results
    logger.info(f"Database consistency check completed:")
    logger.info(f"  Total accounts: {total_accounts}")
    logger.info(f"  User settings: {settings_count}")
    logger.info(f"  Audit logs: {audit_count}")
    logger.info(f"  Issues found: {len(issues)}")
    
    if issues:
        logger.warning("Issues found:")
        for issue in issues:
            logger.warning(f"  - {issue}")
    else:
        logger.info("No issues found - database is consistent!")
    
    return issues

if __name__ == "__main__":
    asyncio.run(check_database_consistency())