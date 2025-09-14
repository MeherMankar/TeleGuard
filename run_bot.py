#!/usr/bin/env python3
"""Simple TeleGuard Bot Runner - Bypasses health checks for development"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv("config/.env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Suppress noisy logs
logging.getLogger("telethon").setLevel(logging.WARNING)

async def main():
    """Simple main function"""
    try:
        print("Starting TeleGuard Bot...")
        
        # Import and start bot manager
        from teleguard.core.bot_manager import BotManager
        
        async with BotManager() as bot_manager:
            print("TeleGuard Bot started successfully!")
            print("Press Ctrl+C to stop.\n")
            
            # Run until disconnected
            await bot_manager.run()
            
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())