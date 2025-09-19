"""Online maker handler to keep accounts online with breaks"""

import asyncio
import logging
import random
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class OnlineMaker:
    """Keeps accounts online with periodic breaks"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.user_clients = bot_manager.user_clients
        self.running_tasks = {}
        
    async def start_online_maker(self, user_id: int, account_name: str):
        """Start online maker for an account"""
        task_key = f"{user_id}:{account_name}"
        
        if task_key in self.running_tasks:
            return
            
        task = asyncio.create_task(self._online_loop(user_id, account_name))
        self.running_tasks[task_key] = task
        logger.info(f"Online maker started for {account_name}")
        
    async def stop_online_maker(self, user_id: int, account_name: str):
        """Stop online maker for an account"""
        task_key = f"{user_id}:{account_name}"
        
        if task_key in self.running_tasks:
            self.running_tasks[task_key].cancel()
            del self.running_tasks[task_key]
            logger.info(f"Online maker stopped for {account_name}")
            
    async def _online_loop(self, user_id: int, account_name: str):
        """Main online maker loop"""
        try:
            while True:
                # Check if online maker is still enabled
                account = await mongodb.db.accounts.find_one({
                    "user_id": user_id,
                    "phone": account_name
                })
                
                # If not found by phone, try by name
                if not account:
                    account = await mongodb.db.accounts.find_one({
                        "user_id": user_id,
                        "name": account_name
                    })
                
                if not account or not account.get("online_maker_enabled", False):
                    break
                    
                # Get client - try both account_name and phone as keys
                user_clients_dict = self.user_clients.get(user_id, {})
                client = user_clients_dict.get(account_name)
                
                # If not found by account_name, try to find by phone or other identifier
                if not client and account:
                    phone = account.get('phone')
                    name = account.get('name')
                    display_name = account.get('display_name')
                    
                    for key in [phone, name, display_name]:
                        if key and key in user_clients_dict:
                            client = user_clients_dict[key]
                            break
                
                if not client or not client.is_connected():
                    logger.warning(f"Client not found or disconnected for {account_name}")
                    break
                    
                try:
                    # Send typing action to stay online
                    from telethon import functions, types
                    await client(functions.messages.SetTypingRequest(
                        peer='me',
                        action=types.SendMessageTypingAction()
                    ))
                    logger.debug(f"Online ping sent for {account_name}")
                except Exception as e:
                    logger.error(f"Online ping failed for {account_name}: {e}")
                    
                # Random interval between 2-5 minutes for online pings
                interval = random.randint(120, 300)
                await asyncio.sleep(interval)
                
                # Random break every 15-25 pings (30-120 minutes)
                if random.randint(1, 20) == 1:
                    break_time = random.randint(300, 1800)  # 5-30 minutes break
                    logger.info(f"Online maker taking {break_time}s break for {account_name}")
                    await asyncio.sleep(break_time)
                    
        except asyncio.CancelledError:
            logger.info(f"Online maker cancelled for {account_name}")
        except Exception as e:
            logger.error(f"Online maker error for {account_name}: {e}")
        finally:
            # Clean up task
            task_key = f"{user_id}:{account_name}"
            self.running_tasks.pop(task_key, None)
            
    async def setup_existing_online_makers(self):
        """Set up online makers for accounts that have it enabled"""
        try:
            accounts = await mongodb.db.accounts.find({
                "online_maker_enabled": True
            }).to_list(length=None)
            
            for account in accounts:
                account_identifier = account.get("phone") or account.get("name", "unknown")
                await self.start_online_maker(account["user_id"], account_identifier)
                
        except Exception as e:
            logger.error(f"Failed to setup existing online makers: {e}")
            
    async def cleanup(self):
        """Stop all online maker tasks"""
        for task in self.running_tasks.values():
            task.cancel()
        self.running_tasks.clear()
    
    async def force_offline(self, user_id: int, account_name: str) -> bool:
        """Force set account offline"""
        try:
            from telethon.tl.functions.account import UpdateStatusRequest
            
            client = self.user_clients.get(user_id, {}).get(account_name)
            if client and client.is_connected():
                await client(UpdateStatusRequest(offline=True))
                logger.info(f"Forced {account_name} offline")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to force offline {account_name}: {e}")
            return False
    
    async def force_offline_all(self, user_id: int) -> int:
        """Force all user accounts offline"""
        count = 0
        try:
            user_clients = self.user_clients.get(user_id, {})
            
            for account_name in user_clients.keys():
                if await self.force_offline(user_id, account_name):
                    count += 1
                    
            logger.info(f"Forced {count} accounts offline for user {user_id}")
            return count
            
        except Exception as e:
            logger.error(f"Failed to force offline all accounts: {e}")
            return count