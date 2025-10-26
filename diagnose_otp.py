"""OTP Destroyer Diagnostic Tool"""
import asyncio
import logging
from teleguard.core.config import config
from teleguard.core.mongo_database import init_db, mongodb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def diagnose_otp():
    """Diagnose OTP destroyer issues"""
    print("=" * 60)
    print("OTP DESTROYER DIAGNOSTIC TOOL")
    print("=" * 60)
    
    try:
        # Initialize database
        print("\n1. Checking database connection...")
        await init_db()
        print("   ✅ Database connected")
        
        # Check accounts
        print("\n2. Checking accounts...")
        accounts = await mongodb.db.accounts.find({}).to_list(None)
        print(f"   Total accounts: {len(accounts)}")
        
        if not accounts:
            print("   ❌ No accounts found!")
            print("   → Add accounts via /start in the bot")
            return
        
        # Check OTP settings
        print("\n3. Checking OTP destroyer settings...")
        destroyer_enabled = 0
        forward_enabled = 0
        active_accounts = 0
        
        for account in accounts:
            name = account.get('name', 'Unknown')
            is_active = account.get('is_active', False)
            destroyer = account.get('otp_destroyer_enabled', False)
            forward = account.get('otp_forward_enabled', False)
            has_session = bool(account.get('session_string'))
            
            if is_active:
                active_accounts += 1
            if destroyer:
                destroyer_enabled += 1
            if forward:
                forward_enabled += 1
            
            status = "🟢" if is_active else "🔴"
            print(f"   {status} {name}:")
            print(f"      Active: {is_active}")
            print(f"      Has Session: {has_session}")
            print(f"      OTP Destroyer: {'✅' if destroyer else '❌'}")
            print(f"      OTP Forward: {'✅' if forward else '❌'}")
        
        print(f"\n   Summary:")
        print(f"   - Active accounts: {active_accounts}/{len(accounts)}")
        print(f"   - OTP Destroyer enabled: {destroyer_enabled}")
        print(f"   - OTP Forward enabled: {forward_enabled}")
        
        # Check for issues
        print("\n4. Checking for common issues...")
        issues = []
        
        if active_accounts == 0:
            issues.append("❌ No active accounts - accounts need to be connected")
        
        if destroyer_enabled == 0 and forward_enabled == 0:
            issues.append("❌ OTP features not enabled on any account")
        
        for account in accounts:
            if account.get('otp_destroyer_enabled') and not account.get('session_string'):
                issues.append(f"❌ {account.get('name')}: OTP enabled but no session string")
            
            if account.get('otp_destroyer_enabled') and not account.get('is_active'):
                issues.append(f"⚠️ {account.get('name')}: OTP enabled but account inactive")
        
        if issues:
            print("   Issues found:")
            for issue in issues:
                print(f"   {issue}")
        else:
            print("   ✅ No issues found")
        
        # Recommendations
        print("\n5. Recommendations:")
        if destroyer_enabled == 0:
            print("   → Enable OTP Destroyer via bot menu:")
            print("     /start → Account Settings → Select Account → OTP Manager → Enable Destroyer")
        
        if active_accounts < len(accounts):
            print("   → Restart bot to reconnect inactive accounts")
        
        print("\n" + "=" * 60)
        print("DIAGNOSTIC COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Diagnostic failed: {e}")
        logger.error(f"Diagnostic error: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(diagnose_otp())
