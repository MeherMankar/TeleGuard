"""Automation Worker for scheduled tasks"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class AutomationWorker:
    """Background worker for automation tasks"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.running = False
        self.tasks = {}

    async def start(self):
        """Start automation worker"""
        self.running = True
        logger.info("Automation worker started")

        while self.running:
            try:
                await self._process_jobs()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Automation worker error: {e}")
                await asyncio.sleep(60)

    async def stop(self):
        """Stop automation worker"""
        self.running = False
        for task in self.tasks.values():
            task.cancel()
        logger.info("Automation worker stopped")

    async def _process_jobs(self):
        """Process pending automation jobs"""
        try:
            current_time = datetime.utcnow().isoformat()
            # Validate current_time to prevent injection
            if not isinstance(current_time, str):
                logger.error("Invalid current_time format")
                return
                
            jobs = await mongodb.db.automation_jobs.find(
                {"enabled": True, "next_run": {"$lte": current_time}}
            ).to_list(length=100)  # Limit results

            for job in jobs:
                await self._execute_job(job)

        except Exception as e:
            logger.error(f"Failed to process automation jobs: {e}")

    async def _execute_job(self, job: dict):
        """Execute a single automation job"""
        try:
            import json

            # Safely parse job config to prevent code injection
            try:
                config = json.loads(job["job_config"])
                if not isinstance(config, dict):
                    logger.error(f"Invalid job config format for job {job['_id']}")
                    return
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in job config for job {job['_id']}: {e}")
                return

            if job["job_type"] == "auto_reply":
                await self._handle_auto_reply(job["account_id"], config)
            elif job["job_type"] == "scheduled_message":
                await self._handle_scheduled_message(job["account_id"], config)
            elif job["job_type"] == "online_maker":
                await self._handle_online_maker(job["account_id"], config)

            # Update job timing
            update_data = {"last_run": datetime.utcnow().isoformat()}

            if config.get("interval"):
                next_run = datetime.utcnow() + timedelta(seconds=config["interval"])
                update_data["next_run"] = next_run.isoformat()
            else:
                update_data["enabled"] = False  # One-time job

            await mongodb.db.automation_jobs.update_one(
                {"_id": job["_id"]}, {"$set": update_data}
            )

        except Exception as e:
            logger.error(f"Failed to execute job {job['_id']}: {e}")

    async def _handle_auto_reply(self, account_id: str, config: Dict[str, Any]):
        """Handle auto-reply job"""
        # Implementation would depend on message handling system
        logger.info(f"Auto-reply job executed for account {account_id}")

    async def _handle_scheduled_message(self, account_id: str, config: Dict[str, Any]):
        """Handle scheduled message job"""
        # Implementation would send scheduled messages
        logger.info(f"Scheduled message job executed for account {account_id}")

    async def _handle_online_maker(self, account_id: str, config: Dict[str, Any]):
        """Handle online maker job"""
        if hasattr(self.bot_manager, "fullclient_manager"):
            # Get user_id from account with validation
            from bson import ObjectId
            from bson.errors import InvalidId
            
            try:
                # Validate ObjectId format to prevent injection
                if not ObjectId.is_valid(account_id):
                    logger.error(f"Invalid account_id format: {account_id}")
                    return
                    
                account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id)})
            except InvalidId as e:
                logger.error(f"Invalid ObjectId: {account_id} - {e}")
                return
            if account:
                await self.bot_manager.fullclient_manager.update_online_status(
                    account["user_id"], account_id
                )
