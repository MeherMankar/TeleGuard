#!/usr/bin/env python3
"""
Simple bot startup script for testing
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from teleguard import AccountManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s'
)

# Silence noisy modules
for mod in ["telethon", "pymongo", "motor", "asyncio"]:
    logging.getLogger(mod).setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

async def main():
    """Start the bot"""
    try:
        print("🚀 Starting TeleGuard Bot...")
        
        async with AccountManager() as bot:
            print("✅ Bot started successfully!")
            print("📝 Send /start to the bot to begin")
            print("🛡️ OTP Destroyer protection is active")
            print("🔧 Admin commands: /otp_debug, /otp_fix")
            print("\n" + "="*50)
            
            await bot.run()
            
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"Bot error: {e}")

if __name__ == "__main__":
    asyncio.run(main())