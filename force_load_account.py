"""Force load account and register OTP handlers"""
import asyncio
import sys
from teleguard.core.mongo_database import init_db, mongodb
from teleguard.core.config import config
from telethon import TelegramClient
from telethon.sessions import StringSession

async def force_load():
    print("\n=== FORCE LOADING ACCOUNT ===\n")
    
    await init_db()
    
    # Get account
    accounts = await mongodb.db.accounts.find({}).to_list(None)
    if not accounts:
        print("ERROR: No accounts found!")
        return
    
    account = accounts[0]
    print(f"Found account: {account.get('name', 'Unknown')}")
    print(f"OTP Destroyer enabled: {account.get('otp_destroyer_enabled', False)}")
    
    if not account.get('session_string'):
        print("ERROR: No session string!")
        return
    
    # Mark as active
    await mongodb.db.accounts.update_one(
        {"_id": account["_id"]},
        {"$set": {"is_active": True}}
    )
    print("Marked account as active")
    
    # Test connection
    try:
        session_string = account['session_string']
        client = TelegramClient(
            StringSession(session_string),
            config.telegram.api_id,
            config.telegram.api_hash
        )
        
        print("Connecting to Telegram...")
        await client.connect()
        
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"Connected successfully as: {me.first_name}")
            print("\nAccount is ready for OTP destroyer!")
            print("\nNow restart the bot with: python main.py")
        else:
            print("ERROR: Session not authorized!")
        
        await client.disconnect()
        
    except Exception as e:
        print(f"ERROR: {e}")
        print("\nThe session may be invalid. Try re-adding the account.")

if __name__ == "__main__":
    asyncio.run(force_load())
