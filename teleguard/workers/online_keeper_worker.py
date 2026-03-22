"""Online Keeper Worker - Keep accounts online continuously
Integrated from SessTg project
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from telethon import TelegramClient
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.network import ConnectionTcpFull

logger = logging.getLogger(__name__)


class OnlineKeeperWorker:
    """Worker to keep accounts online continuously"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.running = False
        self.tasks: Dict[str, asyncio.Task] = {}
        self.ping_interval = 30  # seconds
    
    async def start_keeping_online(self, user_id: int, account_name: str) -> bool:
        """Start keeping an account online
        
        Args:
            user_id: User ID
            account_name: Account name
        
        Returns:
            True if started successfully
        """
        task_key = f"{user_id}_{account_name}"
        
        if task_key in self.tasks:
            logger.warning(f"Online keeper already running for {account_name}")
            return False
        
        # Get client
        client = self.bot_manager.user_clients.get(user_id, {}).get(account_name)
        if not client:
            logger.error(f"Client not found for {account_name}")
            return False
        
        # Create task
        task = asyncio.create_task(self._keep_online_loop(user_id, account_name, client))
        self.tasks[task_key] = task
        
        logger.info(f"Started online keeper for {account_name}")
        return True
    
    async def stop_keeping_online(self, user_id: int, account_name: str) -> bool:
        """Stop keeping an account online
        
        Args:
            user_id: User ID
            account_name: Account name
        
        Returns:
            True if stopped successfully
        """
        task_key = f"{user_id}_{account_name}"
        
        if task_key not in self.tasks:
            logger.warning(f"Online keeper not running for {account_name}")
            return False
        
        # Cancel task
        task = self.tasks[task_key]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        del self.tasks[task_key]
        
        logger.info(f"Stopped online keeper for {account_name}")
        return True
    
    async def _keep_online_loop(self, user_id: int, account_name: str, client: TelegramClient):
        """Main loop to keep account online
        
        Args:
            user_id: User ID
            account_name: Account name
            client: Telegram client
        """
        try:
            # Get account info
            me = await client.get_me()
            phone = me.phone or "unknown"
            
            logger.info(f"Online keeper started for +{phone}")
            
            # Set online status
            await client(UpdateStatusRequest(offline=False))
            
            while True:
                await asyncio.sleep(self.ping_interval)
                
                if client and client.is_connected():
                    # Update online status
                    await client(UpdateStatusRequest(offline=False))
                    logger.debug(f"Pinged online status for +{phone}")
                else:
                    logger.warning(f"Client disconnected for +{phone}")
                    break
        
        except asyncio.CancelledError:
            logger.info(f"Online keeper cancelled for {account_name}")
            raise
        
        except Exception as e:
            logger.error(f"Online keeper error for {account_name}: {e}")
    
    async def start_all(self, user_id: int) -> Dict[str, bool]:
        """Start online keeper for all user accounts
        
        Args:
            user_id: User ID
        
        Returns:
            Dict mapping account names to success status
        """
        results = {}
        
        user_clients = self.bot_manager.user_clients.get(user_id, {})
        
        for account_name in user_clients:
            success = await self.start_keeping_online(user_id, account_name)
            results[account_name] = success
            await asyncio.sleep(1)  # Rate limiting
        
        return results
    
    async def stop_all(self, user_id: int) -> Dict[str, bool]:
        """Stop online keeper for all user accounts
        
        Args:
            user_id: User ID
        
        Returns:
            Dict mapping account names to success status
        """
        results = {}
        
        # Find all tasks for this user
        user_tasks = [
            key for key in self.tasks.keys()
            if key.startswith(f"{user_id}_")
        ]
        
        for task_key in user_tasks:
            account_name = task_key.split("_", 1)[1]
            success = await self.stop_keeping_online(user_id, account_name)
            results[account_name] = success
        
        return results
    
    def is_running(self, user_id: int, account_name: str) -> bool:
        """Check if online keeper is running for an account
        
        Args:
            user_id: User ID
            account_name: Account name
        
        Returns:
            True if running
        """
        task_key = f"{user_id}_{account_name}"
        return task_key in self.tasks
    
    def get_running_accounts(self, user_id: int) -> List[str]:
        """Get list of accounts with online keeper running
        
        Args:
            user_id: User ID
        
        Returns:
            List of account names
        """
        return [
            key.split("_", 1)[1]
            for key in self.tasks.keys()
            if key.startswith(f"{user_id}_")
        ]
    
    async def cleanup(self):
        """Cleanup all tasks"""
        logger.info("Cleaning up online keeper tasks...")
        
        for task in self.tasks.values():
            task.cancel()
        
        # Wait for all tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        
        self.tasks.clear()
        logger.info("Online keeper cleanup complete")
