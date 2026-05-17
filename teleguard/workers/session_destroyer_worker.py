"""
Session Destroyer Worker
Background task to periodically monitor and protect accounts.
"""

import asyncio
import logging
import time
from typing import Dict, Any

from ..sync.session_destroyer_db import SessionDestroyerDB
from ..services.session_destroyer_service import SessionDestroyerService
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class SessionDestroyerWorker:
    """Background worker for Session Destroyer feature"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.service = SessionDestroyerService(self.bot_manager)
        self.is_running = False
        self._task = None
        self.check_interval = 60 # Check every 60 seconds

    async def start(self):
        """Start the background worker"""
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("🚀 Session Destroyer Worker started")

    async def stop(self):
        """Stop the background worker"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Session Destroyer Worker stopped")

    async def _run_loop(self):
        """Main worker loop"""
        while self.is_running:
            try:
                await self._check_all_protected_accounts()
            except Exception as e:
                logger.error(f"Error in Session Destroyer worker loop: {e}")
            
            await asyncio.sleep(self.check_interval)

    async def _check_all_protected_accounts(self):
        """Find all users with Session Destroyer enabled and check their accounts"""
        try:
            # Find all users with Session Destroyer enabled
            cursor = mongodb.db.session_destroyer_settings.find({"enabled": True})
            protected_users = await cursor.to_list(length=None)
            
            for user_settings in protected_users:
                user_id = user_settings["user_id"]
                
                # Get all active accounts for this user from DB
                from ..utils.crypto_utils import DataEncryption
                accounts_enc = await mongodb.db.accounts.find({"user_id": user_id, "is_active": True}).to_list(length=None)
                
                for acc_doc in accounts_enc:
                    account = DataEncryption.decrypt_account_data(acc_doc)
                    client = self.bot_manager.get_client(user_id, account)
                    if not client or not client.is_connected():
                        continue
                    
                    account_id = str(account["_id"])
                    account_name = account.get("name")
                    
                    # Process protection for this specific account
                    await self.service.process_account_protection(
                        user_id, account_id, client, account_name
                    )
                    
                    # Small delay between accounts to prevent flood
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error checking protected accounts: {e}")
