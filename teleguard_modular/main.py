"""TeleGuard - Main Entry Point"""
import asyncio
from telethon import TelegramClient
from config import load_config

# Import all modules
import account_settings
import otp_manager
import messaging
import channels
import contacts
import cleanup
import spam_master
import help as help_module
import support
import dev_panel

class BotManager:
    """Central bot manager"""
    def __init__(self, config):
        self.config = config
        self.bot = None
        self.user_states = {}
        self.temp_data = {}
    
    async def start(self):
        """Start the bot"""
        self.bot = TelegramClient(
            'teleguard_bot',
            self.config['api_id'],
            self.config['api_hash']
        )
        await self.bot.start(bot_token=self.config['bot_token'])
        
        # Register all modules
        account_settings.register(self)
        otp_manager.register(self)
        messaging.register(self)
        channels.register(self)
        contacts.register(self)
        cleanup.register(self)
        spam_master.register(self)
        help_module.register(self)
        support.register(self)
        dev_panel.register(self)
        
        print('[OK] TeleGuard started successfully!')
        await self.bot.run_until_disconnected()

async def main():
    """Main entry point"""
    config = load_config()
    bot_manager = BotManager(config)
    await bot_manager.start()

if __name__ == '__main__':
    asyncio.run(main())
