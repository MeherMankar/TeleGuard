"""Account age updater worker for daily updates"""
import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AccountAgeUpdater:
    """Updates account age information daily"""
    
    def __init__(self, account_manager):
        self.account_manager = account_manager
        self.running = False
        self.update_task = None
    
    async def start(self):
        """Start the daily update task"""
        if self.running:
            return
        
        self.running = True
        self.update_task = asyncio.create_task(self._daily_update_loop())
        logger.info("Account age updater started")
    
    async def stop(self):
        """Stop the daily update task"""
        self.running = False
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
        logger.info("Account age updater stopped")
    
    async def _daily_update_loop(self):
        """Main loop for daily updates"""
        while self.running:
            try:
                # Calculate time until next midnight
                now = datetime.now()
                tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                sleep_seconds = (tomorrow - now).total_seconds()
                
                logger.info(f"Next account age update in {sleep_seconds/3600:.1f} hours")
                
                # Sleep until midnight
                await asyncio.sleep(sleep_seconds)
                
                if self.running:
                    await self._update_all_account_ages()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in daily update loop: {e}")
                # Sleep for 1 hour on error
                await asyncio.sleep(3600)
    
    async def _update_all_account_ages(self):
        """Update age information for all accounts"""
        try:
            from ..core.mongo_database import mongodb
            
            # Get all accounts
            accounts = await mongodb.db.accounts.find({}).to_list(length=None)
            updated_count = 0
            
            logger.info(f"Starting age update for {len(accounts)} accounts")
            
            for account in accounts:
                try:
                    user_id = account.get('user_id')
                    account_name = account.get('name')
                    
                    if not user_id or not account_name:
                        continue
                    
                    # Get client for THIS SPECIFIC account
                    client = None
                    if (hasattr(self.account_manager, 'user_clients') and 
                        user_id in self.account_manager.user_clients):
                        user_clients = self.account_manager.user_clients[user_id]
                        
                        # Try account name (most reliable)
                        client = user_clients.get(account_name)
                        
                        # Try phone number
                        if not client and account.get('phone'):
                            client = user_clients.get(account['phone'])
                        
                        # Try display name
                        if not client and account.get('display_name'):
                            client = user_clients.get(account['display_name'])
                        
                        # DO NOT use fallback - skip if client not found for THIS account
                        if not client:
                            logger.warning(f"No client found for account {account_name}, skipping")
                            continue
                        
                        if client and hasattr(client, 'is_connected') and client.is_connected():
                            try:
                                from datetime import timezone
                                from ..utils.account_age_estimator import AccountAgeEstimator
                                
                                me = await client.get_me()
                                telegram_user_id = int(me.id)  # Ensure int for precision
                                
                                # Use ID-based estimation (per-account, never cached globally)
                                creation_date, method = await AccountAgeEstimator.estimate_creation_date(telegram_user_id)
                                
                                if creation_date:
                                    now = datetime.now(timezone.utc)
                                    if creation_date.tzinfo is None:
                                        creation_date = creation_date.replace(tzinfo=timezone.utc)
                                    age_days = max(0, (now - creation_date).days)
                                    
                                    # Debug log per account
                                    logger.info(f"Account {account_name} (ID={telegram_user_id}): {creation_date.isoformat()} via {method} -> {age_days} days")
                                    
                                    await mongodb.db.accounts.update_one(
                                        {"_id": account["_id"]},
                                        {
                                            "$set": {
                                                "creation_date": creation_date,
                                                "age_days": age_days,
                                                "telegram_user_id": telegram_user_id,
                                                "last_age_update": datetime.now(timezone.utc)
                                            }
                                        }
                                    )
                                    updated_count += 1
                            except Exception as e:
                                logger.error(f"Failed to get user info for {account_name}: {e}")
                                continue
                                
                except Exception as e:
                    logger.error(f"Error updating age for account {account.get('name', 'Unknown')}: {e}")
                    continue
            
            logger.info(f"Updated age information for {updated_count} accounts")
            
        except Exception as e:
            logger.error(f"Error in update_all_account_ages: {e}")