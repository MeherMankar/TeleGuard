#!/usr/bin/env python3
"""Simple session test"""

import asyncio
from teleguard.core.mongo_database import mongodb

async def simple_test():
    user_id = 6121637257
    
    try:
        await mongodb.connect()
        
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        
        print(f"Found {len(accounts)} accounts")
        
        for account in accounts:
            name = account.get('name', 'Unknown')
            online_maker = account.get('online_maker_enabled', False)
            otp_destroyer = account.get('otp_destroyer_enabled', False)
            session_conflict = account.get('session_conflict', False)
            
            print(f"Account: {name}")
            print(f"  Online Maker: {online_maker}")
            print(f"  OTP Destroyer: {otp_destroyer}")
            print(f"  Session Conflict: {session_conflict}")
            print()
        
        # Test session conflict marking
        if accounts:
            test_account = accounts[0]
            print(f"Testing conflict marking on: {test_account.get('name')}")
            
            # Mark conflict
            await mongodb.db.accounts.update_one(
                {"_id": test_account["_id"]},
                {"$set": {"session_conflict": True}}
            )
            print("Conflict marked")
            
            # Clear conflict
            await mongodb.db.accounts.update_one(
                {"_id": test_account["_id"]},
                {"$unset": {"session_conflict": ""}}
            )
            print("Conflict cleared")
            
        print("Session handling test completed successfully")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await mongodb.disconnect()

if __name__ == "__main__":
    asyncio.run(simple_test())