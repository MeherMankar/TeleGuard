"""Online Maker Worker for keeping accounts online"""

import asyncio
import logging
from datetime import datetime, timedelta

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class OnlineMakerWorker:
    """Background worker to keep accounts online"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.running = False

    async def start(self):
        """Start online maker worker"""
        self.running = True
        logger.info("Online maker worker started")

        while self.running:
            try:
                await self._update_online_accounts()
                await asyncio.sleep(300)  # Check every 5 minutes
            except Exception as e:
                logger.error(f"Online maker worker error: {e}")
                await asyncio.sleep(300)

    async def stop(self):
        """Stop online maker worker"""
        self.running = False
        logger.info("Online maker worker stopped")

    async def _update_online_accounts(self):
        """Update online status for enabled accounts"""
        try:
            accounts = await mongodb.db.accounts.find(
                {"online_maker_enabled": True, "is_active": True}
            ).to_list(length=None)

            for account in accounts:
                try:
                    # Check if it's time to update
                    if self._should_update_online(account):
                        if hasattr(self.bot_manager, "fullclient_manager"):
                            (
                                success,
                                msg,
                            ) = await self.bot_manager.fullclient_manager.update_online_status(
                                account["user_id"], str(account["_id"])
                            )
                            if success:
                                account_name = account.get('phone') or account.get('name', 'unknown')
                                logger.debug(
                                    f"Updated online status for account {account_name}"
                                )
                            else:
                                account_name = account.get('phone') or account.get('name', 'unknown')
                                logger.warning(
                                    f"Failed to update online status for {account_name}: {msg}"
                                )
                except Exception as e:
                    logger.error(
                        f"Error updating online status for account {account['_id']}: {e}"
                    )

        except Exception as e:
            logger.error(f"Failed to update online accounts: {e}")

    def _should_update_online(self, account: dict) -> bool:
        """Check if account should be updated based on interval"""
        if not account.get("last_online_update"):
            return True

        try:
            last_update = datetime.fromisoformat(account["last_online_update"])
            interval = timedelta(seconds=account.get("online_maker_interval", 3600))
            return datetime.utcnow() - last_update >= interval
        except Exception:
            return True  # Update if we can't parse the timestamp
