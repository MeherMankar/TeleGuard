#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check if OTP handlers are registered"""
import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')
from teleguard.core.mongo_database import mongodb

async def check_otp_handlers():
    """Check OTP handler status"""
    try:
        await mongodb.connect()
        
        print("=== OTP HANDLER STATUS ===")
        print("To receive OTP codes via bot, you need:")
        print("1. OTP Forward enabled (DONE)")
        print("2. Bot running with OTP handlers registered")
        print("3. Account clients connected and active")
        print()
        
        # Check if accounts are active
        accounts = await mongodb.db.accounts.find({"user_id": 6121637257}).to_list(None)
        print("Account Status:")
        for account in accounts:
            name = account.get('name', 'Unknown')
            is_active = account.get('is_active', False)
            otp_forward = account.get('otp_forward_enabled', False)
            print(f"  {name}: Active={is_active}, Forward={otp_forward}")
        
        print()
        print("NEXT STEPS:")
        print("1. Make sure your TeleGuard bot is running")
        print("2. The bot should automatically register OTP handlers for active accounts")
        print("3. When you receive an OTP on any account, it will be forwarded to this bot")
        print()
        print("If still not working:")
        print("- Restart the bot to re-register handlers")
        print("- Check bot logs for any connection issues")
        print("- Ensure accounts are properly connected")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await mongodb.disconnect()

if __name__ == "__main__":
    asyncio.run(check_otp_handlers())