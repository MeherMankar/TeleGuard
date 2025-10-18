#!/usr/bin/env python3
"""Quick fix for session validation errors with user notifications"""
import asyncio
import os
from teleguard.core.mongo_database import init_db, mongodb
from teleguard.core.config import config
from teleguard.utils.account_invalidation import AccountInvalidationHandler
from telethon import TelegramClient

async def quick_fix_with_notifications():
    """Remove invalid accounts and notify users"""
    await init_db()
    
    # Initialize bot client for notifications
    bot = None
    try:
        bot = TelegramClient('temp_bot', config.telegram.api_id, config.telegram.api_hash)
        await bot.start(bot_token=config.telegram.bot_token)
        print("Bot connected for notifications")
        
        # Create mock bot manager for invalidation handler
        class MockBotManager:
            def __init__(self, bot):
                self.bot = bot
                self.user_clients = {}
        
        mock_bot_manager = MockBotManager(bot)
        invalidation_handler = AccountInvalidationHandler(mock_bot_manager)
        
        # Find all accounts with session errors
        invalid_accounts = await mongodb.db.accounts.find({
            "$or": [
                {"needs_reauth": True},
                {"error_reason": {"$exists": True}},
                {"is_active": False}
            ]
        }).to_list(length=None)
        
        print(f"Found {len(invalid_accounts)} invalid accounts")
        
        # Process each invalid account with rate limiting
        for i, account in enumerate(invalid_accounts):
            try:
                user_id = account.get('user_id')
                account_name = account.get('name', 'Unknown')
                phone = account.get('phone', 'Unknown')
                error_reason = account.get('error_reason', 'Session invalidated')
                
                # Send notification and remove account
                await invalidation_handler.handle_account_invalidation(
                    user_id, account_name, phone, error_reason
                )
                print(f"✅ Processed account {account_name} ({phone}) for user {user_id}")
                
                # Rate limiting between notifications
                if i < len(invalid_accounts) - 1:
                    await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ Failed to process account {account.get('name', 'Unknown')}: {e}")
                await asyncio.sleep(0.5)
        
        print(f"\n✅ Processed {len(invalid_accounts)} invalid accounts with notifications")
        print("Users have been notified about removed accounts")
        
    except Exception as e:
        print(f"❌ Error during notification process: {e}")
        # Fallback to simple removal without notifications
        result = await mongodb.db.accounts.delete_many({
            "$or": [
                {"needs_reauth": True},
                {"error_reason": {"$exists": True}},
                {"is_active": False}
            ]
        })
        print(f"✅ Removed {result.deleted_count} invalid accounts (no notifications sent)")
    
    finally:
        if bot and bot.is_connected():
            await bot.disconnect()
        print("Now restart the bot!")

async def quick_fix():
    """Simple removal without notifications (fallback)"""
    await init_db()
    
    result = await mongodb.db.accounts.delete_many({
        "$or": [
            {"needs_reauth": True},
            {"error_reason": {"$exists": True}},
            {"is_active": False}
        ]
    })
    
    print(f"✅ Removed {result.deleted_count} invalid accounts")
    print("Now restart the bot and add accounts again!")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--notify":
        asyncio.run(quick_fix_with_notifications())
    else:
        print("Use --notify flag to send notifications to users")
        asyncio.run(quick_fix())