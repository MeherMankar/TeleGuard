#!/usr/bin/env python3
"""
TeleGuard - Telegram Account Manager Bot - Main Entry Point

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import and run the bot
from bot import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())