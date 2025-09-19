"""Simplified bot manager for cloud deployments"""

import asyncio
import logging
import os
from telethon import TelegramClient, events

logger = logging.getLogger(__name__)

class CloudBotManager:
    """Minimal bot manager for cloud platforms"""
    
    def __init__(self):
        self.bot = None
        self.running = False
        
    async def start(self):
        """Start bot with minimal setup"""
        try:
            api_id = os.getenv("API_ID")
            api_hash = os.getenv("API_HASH") 
            bot_token = os.getenv("BOT_TOKEN")
            
            if not all([api_id, api_hash, bot_token]):
                logger.error("Missing required environment variables")
                return False
                
            self.bot = TelegramClient('cloud_bot', int(api_id), api_hash)
            await self.bot.start(bot_token=bot_token)
            
            @self.bot.on(events.NewMessage(pattern='/start'))
            async def start_handler(event):
                await event.reply("🤖 TeleGuard is running on cloud platform!")
            
            self.running = True
            logger.info("Cloud bot started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start cloud bot: {e}")
            return False
    
    async def keep_alive(self):
        """Keep bot alive with connection monitoring"""
        while self.running:
            try:
                if self.bot and not self.bot.is_connected():
                    await self.bot.connect()
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Keep alive error: {e}")
                await asyncio.sleep(10)
    
    async def stop(self):
        """Stop the bot"""
        self.running = False
        if self.bot:
            await self.bot.disconnect()

cloud_bot = CloudBotManager()