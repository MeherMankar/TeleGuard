"""OTP Destroyer Fix Script"""
import asyncio
import logging
from teleguard.core.config import config
from teleguard.core.mongo_database import init_db, mongodb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_otp():
    """Fix common OTP destroyer issues"""
    print("=" * 60)
    print("OTP DESTROYER FIX TOOL")
    print("=" * 60)
    
    try:
        await init_db()
        print("\n✅ Database connected")
        
        # Get all accounts
        accounts = await mongodb.db.accounts.find({}).to_list(None)
        
        if not accounts:
            print("\n❌ No accounts found. Add accounts first via /start")
            return
        
        print(f"\nFound {len(accounts)} accounts")
        print("\nApplying fixes...")
        
        fixed_count = 0
        
        for account in accounts:
            name = account.get('name', 'Unknown')
            fixes_applied = []
            
            # Fix 1: Ensure is_active is set
            if 'is_active' not in account:
                await mongodb.db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$set": {"is_active": True}}
                )
                fixes_applied.append("Set is_active=True")
            
            # Fix 2: Initialize OTP settings if missing
            if 'otp_destroyer_enabled' not in account:
                await mongodb.db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$set": {"otp_destroyer_enabled": False}}
                )
                fixes_applied.append("Initialized otp_destroyer_enabled")
            
            if 'otp_forward_enabled' not in account:
                await mongodb.db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$set": {"otp_forward_enabled": False}}
                )
                fixes_applied.append("Initialized otp_forward_enabled")
            
            # Fix 3: Initialize audit_log if missing
            if 'audit_log' not in account:
                await mongodb.db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$set": {"audit_log": []}}
                )
                fixes_applied.append("Initialized audit_log")
            
            # Fix 4: Remove conflicting flags
            if account.get('needs_reauth') or account.get('session_conflict'):
                await mongodb.db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$unset": {"needs_reauth": "", "session_conflict": ""}}
                )
                fixes_applied.append("Removed conflict flags")
            
            if fixes_applied:
                print(f"\n✅ {name}:")
                for fix in fixes_applied:
                    print(f"   - {fix}")
                fixed_count += 1
        
        if fixed_count > 0:
            print(f"\n✅ Fixed {fixed_count} accounts")
            print("\n⚠️ IMPORTANT: Restart the bot for changes to take effect!")
        else:
            print("\n✅ All accounts are properly configured")
        
        print("\n" + "=" * 60)
        print("FIX COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Fix failed: {e}")
        logger.error(f"Fix error: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(fix_otp())
