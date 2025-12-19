#!/usr/bin/env python3
"""Debug OTP forwarding issues"""
import asyncio
import logging
from teleguard.core.mongo_database import mongodb

async def debug_otp_settings():
    """Debug OTP settings for all accounts"""
    try:
        # Connect to database
        await mongodb.connect()
        
        # Get all accounts
        accounts = await mongodb.db.accounts.find({}).to_list(None)
        
        print("=== OTP DEBUG REPORT ===")
        print(f"Total accounts: {len(accounts)}")
        print()
        
        for account in accounts:
            user_id = account.get('user_id')
            name = account.get('name', 'Unknown')
            phone = account.get('phone', 'Unknown')
            is_active = account.get('is_active', False)
            otp_destroyer = account.get('otp_destroyer_enabled', False)
            otp_forward = account.get('otp_forward_enabled', False)
            
            print(f"Account: {name} ({phone})")
            print(f"  User ID: {user_id}")
            print(f"  Active: {is_active}")
            print(f"  OTP Destroyer: {otp_destroyer}")
            print(f"  OTP Forward: {otp_forward}")
            print()
        
        # Check for recent OTP activity
        print("=== RECENT OTP ACTIVITY ===")
        for account in accounts:
            audit_log = account.get('audit_log', [])
            recent_otp = [entry for entry in audit_log if 'otp' in entry.get('action', '').lower()][-5:]
            if recent_otp:
                print(f"Account {account.get('name')}:")
                for entry in recent_otp:
                    import time
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry.get('timestamp', 0)))
                    print(f"  {timestamp}: {entry.get('action')}")
                print()
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await mongodb.disconnect()

if __name__ == "__main__":
    asyncio.run(debug_otp_settings())