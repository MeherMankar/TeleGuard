"""Automation Engine for scheduled tasks and online maker

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import asyncio
import logging
import time
import json
from typing import Dict, List
from database import get_session
from models import Account, AutomationJob

logger = logging.getLogger(__name__)

class AutomationEngine:
    """Handles automated tasks for accounts"""
    
    def __init__(self, user_clients: Dict, fullclient_manager):
        self.user_clients = user_clients
        self.fullclient_manager = fullclient_manager
        self.running = False
        self.tasks = {}
        
    async def start(self):
        """Start automation engine"""
        self.running = True
        asyncio.create_task(self._automation_loop())
        logger.info("Automation engine started")
    
    async def stop(self):
        """Stop automation engine"""
        self.running = False
        for task in self.tasks.values():
            task.cancel()
        logger.info("Automation engine stopped")
    
    async def _automation_loop(self):
        """Main automation loop"""
        while self.running:
            try:
                await self._process_online_maker()
                await self._process_scheduled_jobs()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Automation loop error: {e}")
                await asyncio.sleep(60)
    
    async def _process_online_maker(self):
        """Process online maker for all enabled accounts"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account).where(Account.online_maker_enabled == True)
                )
                accounts = result.scalars().all()
                
                for account in accounts:
                    try:
                        # Check if it's time to update online status
                        if self._should_update_online(account):
                            # Find user_id for this account
                            user_result = await session.execute(
                                select(Account.owner_id).where(Account.id == account.id)
                            )
                            owner = user_result.scalar_one_or_none()
                            if owner:
                                success, msg = await self.fullclient_manager.update_online_status(
                                    owner, account.id
                                )
                                if success:
                                    logger.info(f"Updated online status for {account.name}")
                                    
                    except Exception as e:
                        logger.error(f"Online maker error for {account.name}: {e}")
                        
        except Exception as e:
            logger.error(f"Process online maker error: {e}")
    
    def _should_update_online(self, account) -> bool:
        """Check if account should update online status"""
        if not account.last_online_update:
            return True
            
        try:
            last_update = time.strptime(account.last_online_update, '%Y-%m-%d %H:%M:%S')
            last_timestamp = time.mktime(last_update)
            current_timestamp = time.time()
            
            return (current_timestamp - last_timestamp) >= account.online_maker_interval
        except:
            return True
    
    async def _process_scheduled_jobs(self):
        """Process scheduled automation jobs"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(AutomationJob).where(
                        AutomationJob.enabled == True,
                        AutomationJob.next_run <= time.strftime('%Y-%m-%d %H:%M:%S')
                    )
                )
                jobs = result.scalars().all()
                
                for job in jobs:
                    try:
                        await self._execute_job(job)
                        # Update last run and next run
                        job.last_run = time.strftime('%Y-%m-%d %H:%M:%S')
                        job.next_run = self._calculate_next_run(job)
                        await session.commit()
                        
                    except Exception as e:
                        logger.error(f"Job execution error for job {job.id}: {e}")
                        
        except Exception as e:
            logger.error(f"Process scheduled jobs error: {e}")
    
    async def _execute_job(self, job: AutomationJob):
        """Execute a specific automation job"""
        try:
            config = json.loads(job.job_config)
            
            if job.job_type == "auto_reply":
                await self._execute_auto_reply(job.account_id, config)
            elif job.job_type == "scheduled_post":
                await self._execute_scheduled_post(job.account_id, config)
            elif job.job_type == "auto_join":
                await self._execute_auto_join(job.account_id, config)
                
        except Exception as e:
            logger.error(f"Execute job error: {e}")
    
    def _calculate_next_run(self, job: AutomationJob) -> str:
        """Calculate next run time for job"""
        try:
            config = json.loads(job.job_config)
            interval = config.get('interval', 3600)  # Default 1 hour
            next_time = time.time() + interval
            return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(next_time))
        except:
            # Default to 1 hour from now
            next_time = time.time() + 3600
            return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(next_time))
    
    async def _execute_auto_reply(self, account_id: int, config: Dict):
        """Execute auto-reply job"""
        # TODO: REVIEW - Implement auto-reply logic
        logger.info(f"Auto-reply job executed for account {account_id}")
    
    async def _execute_scheduled_post(self, account_id: int, config: Dict):
        """Execute scheduled post job"""
        # TODO: REVIEW - Implement scheduled post logic
        logger.info(f"Scheduled post job executed for account {account_id}")
    
    async def _execute_auto_join(self, account_id: int, config: Dict):
        """Execute auto-join job"""
        # TODO: REVIEW - Implement auto-join logic
        logger.info(f"Auto-join job executed for account {account_id}")