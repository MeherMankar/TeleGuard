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

    async def stop_online_maker(self, user_id: int, account_name: str):
        """Stop online maker for an account"""
        task_key = f"{user_id}:{account_name}"
        if task_key in self.running_tasks:
            self.running_tasks[task_key].cancel()
            del self.running_tasks[task_key]

    async def _online_loop(self, user_id: int, account_name: str):
        """Main online maker loop with proper 24/7 operation"""
        ping_count = 0
        try:
            while True:
                # Find account by multiple criteria
                account = None
                for field in ["name", "phone", "display_name"]:
                    account = await mongodb.db.accounts.find_one(
                        {"user_id": user_id, field: account_name}
                    )
                    if account:
                        break

                if not account or not account.get("online_maker_enabled", False):
                    logger.info(
                        f"Online maker disabled or account not found for {account_name}"
                    )
                    break

                user_clients_dict = self.user_clients.get(user_id, {})
                client = None

                # Try different keys to find the client
                possible_keys = [
                    account_name,
                    account.get("phone"),
                    account.get("name"),
                    account.get("display_name"),
                ]

                for key in possible_keys:
                    if key and key in user_clients_dict:
                        client = user_clients_dict[key]
                        if client and client.is_connected():
                            break
                        client = None

                if not client:
                    logger.warning(
                        f"Client not found or disconnected for {account_name}"
                    )
                    await asyncio.sleep(60)  # Wait 1 minute before retrying
                    continue
                try:
                    # Send update status to stay online
                    from telethon.tl.functions.account import UpdateStatusRequest

                    await client(UpdateStatusRequest(offline=False))
                    ping_count += 1
                except Exception as e:
                    error_msg = str(e)
                    if (
                        "authorization key" in error_msg
                        and "simultaneously" in error_msg
                    ):
                        logger.warning("Session conflict, stopping online maker")
                        await mongodb.db.accounts.update_one(
                            {
                                "user_id": user_id,
                                "$or": [
                                    {"name": account_name},
                                    {"phone": account_name},
                                ],
                            },
                            {"$set": {"online_maker_enabled": False}},
                        )
                        break
                    elif "FLOOD_WAIT" in error_msg:
                        import re

                        wait_time = re.search(r"(\d+)", error_msg)
                        if wait_time:
                            wait_seconds = min(
                                int(wait_time.group(1)), 300
                            )  # Max 5 minutes
                            logger.warning(f"Flood wait, waiting {wait_seconds}s")
                            await asyncio.sleep(wait_seconds)
                        continue
                    else:
                        logger.error(f"Online status update failed: {e}")
                # Smart interval system for 24/7 operation
                # More frequent pings during active hours, less during night
                import time

                current_hour = time.localtime().tm_hour
                if 6 <= current_hour <= 23:  # Active hours (6 AM - 11 PM)
                    base_interval = random.randint(45, 90)  # 45-90 seconds
                else:  # Night hours (12 AM - 5 AM)
                    base_interval = random.randint(90, 180)  # 1.5-3 minutes
                await asyncio.sleep(base_interval)
                # Take strategic breaks to avoid detection
                # Every 50-80 pings (40-120 minutes), take a 2-8 minute break
                if ping_count > 0 and ping_count % random.randint(50, 80) == 0:
                    break_time = random.randint(120, 480)  # 2-8 minutes
                    await asyncio.sleep(break_time)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Online maker error: {e}")
        finally:
            # Clean up task
            task_key = f"{user_id}:{account_name}"
            self.running_tasks.pop(task_key, None)

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
