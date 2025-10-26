"""Quick OTP Status Check"""
import asyncio
from teleguard.core.mongo_database import init_db, mongodb

async def check():
    await init_db()
    print("\n=== OTP STATUS CHECK ===\n")
    
    accounts = await mongodb.db.accounts.find({}).to_list(None)
    print(f"Total accounts: {len(accounts)}\n")
    
    for account in accounts:
        name = account.get('name', 'Unknown')
        active = account.get('is_active', False)
        destroyer = account.get('otp_destroyer_enabled', False)
        has_session = bool(account.get('session_string'))
        
        print(f"Account: {name}")
        print(f"  Active: {active}")
        print(f"  Has Session: {has_session}")
        print(f"  OTP Destroyer: {destroyer}")
        print()

if __name__ == "__main__":
    asyncio.run(check())
