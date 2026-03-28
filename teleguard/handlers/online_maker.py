"""Online maker handler to keep accounts online with breaks
Integrated with SessTg online keeper features
"""

import asyncio
import logging
import random
from typing import Dict, List

from telethon.tl.functions.account import UpdateStatusRequest
from telethon.network import ConnectionTcpFull

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class OnlineMaker:
    """Keeps accounts online with periodic breaks"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.user_clients = bot_manager.user_clients
        self.running_tasks = {}
        self.ping_interval = 30  # Default ping interval in seconds
        self.stats: Dict[str, Dict] = {}  # Track statistics per account

    async def start_online_maker(self, user_id: int, account_name: str) -> bool:
        """Start online maker for an account
        
        Returns:
            True if started successfully
        """
        task_key = f"{user_id}:{account_name}"
        if task_key in self.running_tasks:
            logger.warning(f"Online maker already running for {account_name}")
            return False
        
        task = asyncio.create_task(self._online_loop(user_id, account_name))
        self.running_tasks[task_key] = task
        
        # Initialize stats
        self.stats[task_key] = {
            'started_at': asyncio.get_event_loop().time(),
            'ping_count': 0,
            'last_ping': None,
            'errors': 0
        }
        
        logger.info(f"Started online maker for {account_name}")
        return True

    async def stop_online_maker(self, user_id: int, account_name: str) -> bool:
        """Stop online maker for an account
        
        Returns:
            True if stopped successfully
        """
        task_key = f"{user_id}:{account_name}"
        if task_key not in self.running_tasks:
            logger.warning(f"Online maker not running for {account_name}")
            return False
        
        self.running_tasks[task_key].cancel()
        
        try:
            await self.running_tasks[task_key]
        except asyncio.CancelledError:
            pass
        
        del self.running_tasks[task_key]
        
        # Clean up stats
        if task_key in self.stats:
            del self.stats[task_key]
        
        logger.info(f"Stopped online maker for {account_name}")
        return True

    async def _online_loop(self, user_id: int, account_name: str):
        """Main online maker loop with proper 24/7 operation"""
        task_key = f"{user_id}:{account_name}"
        ping_count = 0
        
        try:
            # Get account info for logging
            account = await self._find_account(user_id, account_name)
            if account:
                me_info = f"+{account.get('phone', 'unknown')}"
                logger.info(f"Online keeper started for {me_info}")
            
            while True:
                account = await self._find_account(user_id, account_name)
                if not account or not account.get("online_maker_enabled", False):
                    logger.info(f"Online maker disabled or account not found for {account_name}")
                    break
                
                client = await self._find_connected_client(user_id, account_name, account)
                if not client:
                    await asyncio.sleep(60)
                    continue
                
                # Update online status
                update_success = await self._update_online_status(client)
                
                if update_success:
                    ping_count += 1
                    # Update stats
                    if task_key in self.stats:
                        self.stats[task_key]['ping_count'] = ping_count
                        self.stats[task_key]['last_ping'] = asyncio.get_event_loop().time()
                    logger.debug(f"Pinged online status for {me_info if account else account_name}")
                elif update_success is None:
                    # Session conflict
                    await self._disable_online_maker(user_id, account_name)
                    break
                else:
                    # Error occurred
                    if task_key in self.stats:
                        self.stats[task_key]['errors'] += 1
                
                # Use ping interval instead of calculated interval
                await asyncio.sleep(self.ping_interval)
                
                # Take strategic breaks
                if self._should_take_break(ping_count):
                    break_time = random.randint(120, 480)
                    logger.debug(f"Taking {break_time}s break for {account_name}")
                    await asyncio.sleep(break_time)
                    
        except asyncio.CancelledError:
            logger.info(f"Online keeper cancelled for {account_name}")
            raise
        except Exception as e:
            logger.error(f"Online maker error for {account_name}: {e}")
        finally:
            self.running_tasks.pop(task_key, None)
            if task_key in self.stats:
                del self.stats[task_key]

    async def setup_existing_online_makers(self):
        """Set up online makers for accounts that have it enabled"""
        try:
            accounts = await mongodb.db.accounts.find(
                {"online_maker_enabled": True, "is_active": True}
            ).to_list(length=None)
            for account in accounts:
                account_identifier = account.get("phone") or account.get(
                    "name", "unknown"
                )
                user_id = account["user_id"]
                user_clients = self.user_clients.get(user_id, {})
                client_found = False
                for key in [
                    account_identifier,
                    account.get("name"),
                    account.get("phone"),
                ]:
                    if key and key in user_clients:
                        client = user_clients[key]
                        if client and client.is_connected():
                            client_found = True
                            break
                if client_found:
                    await self.start_online_maker(user_id, account_identifier)
        except Exception as e:
            logger.error(f"Failed to setup existing online makers: {e}")
    
    async def start_all(self, user_id: int) -> Dict[str, bool]:
        """Start online maker for all user accounts
        
        Returns:
            Dict mapping account names to success status
        """
        results = {}
        
        try:
            accounts = await mongodb.db.accounts.find(
                {"user_id": user_id, "is_active": True}
            ).to_list(length=None)
            
            for account in accounts:
                account_name = account.get("phone") or account.get("name", "unknown")
                success = await self.start_online_maker(user_id, account_name)
                results[account_name] = success
                await asyncio.sleep(1)  # Rate limiting
        
        except Exception as e:
            logger.error(f"Failed to start all online makers: {e}")
        
        return results
    
    async def stop_all(self, user_id: int) -> Dict[str, bool]:
        """Stop online maker for all user accounts
        
        Returns:
            Dict mapping account names to success status
        """
        results = {}
        
        # Find all tasks for this user
        user_tasks = [
            key for key in self.running_tasks.keys()
            if key.startswith(f"{user_id}:")
        ]
        
        for task_key in user_tasks:
            account_name = task_key.split(":", 1)[1]
            success = await self.stop_online_maker(user_id, account_name)
            results[account_name] = success
        
        return results
    
    def is_running(self, user_id: int, account_name: str) -> bool:
        """Check if online maker is running for an account"""
        task_key = f"{user_id}:{account_name}"
        return task_key in self.running_tasks
    
    def get_running_accounts(self, user_id: int) -> List[str]:
        """Get list of accounts with online maker running"""
        return [
            key.split(":", 1)[1]
            for key in self.running_tasks.keys()
            if key.startswith(f"{user_id}:")
        ]
    
    def get_stats(self, user_id: int, account_name: str) -> Dict:
        """Get statistics for an account"""
        task_key = f"{user_id}:{account_name}"
        return self.stats.get(task_key, {})

    async def cleanup(self):
        """Stop all online maker tasks"""
        logger.info("Cleaning up online maker tasks...")
        
        for task in self.running_tasks.values():
            task.cancel()
        
        # Wait for all tasks to complete
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks.values(), return_exceptions=True)
        
        self.running_tasks.clear()
        self.stats.clear()
        logger.info("Online maker cleanup complete")

    async def force_offline(self, user_id: int, account_name: str) -> bool:
        """Force set account offline"""
        try:
            from telethon.tl.functions.account import UpdateStatusRequest

            client = self.user_clients.get(user_id, {}).get(account_name)
            if client and client.is_connected():
                await client(UpdateStatusRequest(offline=True))
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to force offline: {e}")
            return False

    async def force_offline_all(self, user_id: int) -> int:
        """Force all user accounts offline"""
        count = 0
        try:
            user_clients = self.user_clients.get(user_id, {})
            for account_name in user_clients.keys():
                if await self.force_offline(user_id, account_name):
                    count += 1
            return count
        except Exception as e:
            logger.error(f"Failed to force offline all accounts: {e}")
            return count

    async def _find_account(self, user_id: int, account_name: str):
        """Find account by multiple criteria"""
        for field in ["name", "phone", "display_name"]:
            account = await mongodb.db.accounts.find_one({" user_id": user_id, field: account_name})
            if account:
                return account
        return None

    async def _find_connected_client(self, user_id: int, account_name: str, account: dict):
        """Find connected client for account"""
        user_clients_dict = self.user_clients.get(user_id, {})
        possible_keys = [account_name, account.get("phone"), account.get("name"), account.get("display_name")]
        for key in possible_keys:
            if key and key in user_clients_dict:
                client = user_clients_dict[key]
                if client and client.is_connected():
                    return client
        logger.warning(f"Client not found or disconnected for {account_name}")
        return None

    async def _update_online_status(self, client):
        """Update online status, returns True on success, False on error, None on session conflict"""
        try:
            from telethon.tl.functions.account import UpdateStatusRequest
            await client(UpdateStatusRequest(offline=False))
            return True
        except Exception as e:
            error_msg = str(e)
            if "authorization key" in error_msg and "simultaneously" in error_msg:
                logger.warning("Session conflict, stopping online maker")
                return None
            elif "FLOOD_WAIT" in error_msg:
                import re
                wait_time = re.search(r"(\d+)", error_msg)
                if wait_time:
                    wait_seconds = min(int(wait_time.group(1)), 300)
                    logger.warning(f"Flood wait, waiting {wait_seconds}s")
                    await asyncio.sleep(wait_seconds)
            else:
                logger.error(f"Online status update failed: {e}")
            return False

    async def _disable_online_maker(self, user_id: int, account_name: str):
        """Disable online maker for account"""
        await mongodb.db.accounts.update_one(
            {"user_id": user_id, "$or": [{"name": account_name}, {"phone": account_name}]},
            {"$set": {"online_maker_enabled": False}}
        )

    def _calculate_interval(self) -> int:
        """Calculate smart interval based on time of day"""
        import time
        current_hour = time.localtime().tm_hour
        if 6 <= current_hour <= 23:
            return random.randint(45, 90)
        return random.randint(90, 180)

    def _should_take_break(self, ping_count: int) -> bool:
        """Determine if should take strategic break"""
        return ping_count > 0 and ping_count % random.randint(50, 80) == 0
