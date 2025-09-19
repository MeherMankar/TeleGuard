"""Automation Engine for scheduled tasks and online maker

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import asyncio
import json
import logging
import time
from typing import Dict, List

from .mongo_database import mongodb

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
                await self._process_scheduled_jobs()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Automation loop error: {e}")
                await asyncio.sleep(60)



    async def _process_scheduled_jobs(self):
        """Process scheduled automation jobs"""
        try:
            # This is a placeholder for a more robust job scheduling system
            # For now, we will just execute all jobs every minute
            jobs = await mongodb.db.automation_jobs.find({"enabled": True}).to_list(
                length=None
            )
            for job in jobs:
                await self._execute_job(job)

        except Exception as e:
            logger.error(f"Process scheduled jobs error: {e}")

    async def _execute_job(self, job):
        """Execute a specific automation job"""
        try:
            config = json.loads(job.get("job_config", "{}"))
            account_id = job.get("account_id")

            if job.get("job_type") == "auto_reply":
                await self._execute_auto_reply(account_id, config)
            elif job.get("job_type") == "scheduled_post":
                await self._execute_scheduled_post(account_id, config)
            elif job.get("job_type") == "auto_join":
                await self._execute_auto_join(account_id, config)

        except Exception as e:
            logger.error(f"Execute job error: {e}")

    def _calculate_next_run(self, job) -> str:
        """Calculate next run time for job"""
        try:
            config = json.loads(job.job_config)
            interval = config.get("interval", 3600)  # Default 1 hour
            next_time = time.time() + interval
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(next_time))
        except Exception as e:
            logger.error(f"Error calculating next run time: {e}")
            # Default to 1 hour from now
            next_time = time.time() + 3600
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(next_time))

    async def _execute_auto_reply(self, account_id: int, config: Dict):
        """Execute auto-reply job"""
        try:
            message_text = config.get("message")
            if not message_text:
                logger.error(
                    f"No message configured for auto-reply job for account {account_id}"
                )
                return

            from bson import ObjectId

            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id)})
            if not account:
                logger.error(f"Account {account_id} not found for auto-reply job")
                return

            client = await self.fullclient_manager._get_account_client(
                account["user_id"], str(account_id)
            )
            if not client:
                logger.error(f"Client not found for account {account_id}")
                return

            dialogs = await client.get_dialogs()
            for dialog in dialogs:
                if dialog.unread_count > 0 and dialog.is_user:
                    messages = await client.get_messages(
                        dialog, limit=dialog.unread_count
                    )
                    for message in messages:
                        if not message.out:
                            await message.reply(message_text)
                            logger.info(
                                f"Auto-reply job: replied to {dialog.name} for account {account_id}"
                            )

        except Exception as e:
            logger.error(
                f"Error executing auto-reply job for account {account_id}: {e}"
            )

    async def _execute_scheduled_post(self, account_id: int, config: Dict):
        """Execute scheduled post job"""
        try:
            channel = config.get("channel")
            message = config.get("message")
            if not channel or not message:
                logger.error(
                    f"No channel or message configured for scheduled-post job for account {account_id}"
                )
                return

            from bson import ObjectId

            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id)})
            if not account:
                logger.error(f"Account {account_id} not found for scheduled-post job")
                return

            client = await self.fullclient_manager._get_account_client(
                account["user_id"], str(account_id)
            )
            if not client:
                logger.error(f"Client not found for account {account_id}")
                return

            await client.send_message(channel, message)

            logger.info(
                f"Scheduled-post job executed for account {account_id}, posted to {channel}"
            )

        except Exception as e:
            logger.error(
                f"Error executing scheduled-post job for account {account_id}: {e}"
            )

    async def _execute_auto_join(self, account_id: int, config: Dict):
        """Execute auto-join job"""
        try:
            channel_link = config.get("channel_link")
            if not channel_link:
                logger.error(
                    f"No channel_link configured for auto-join job for account {account_id}"
                )
                return

            from bson import ObjectId

            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id)})
            if not account:
                logger.error(f"Account {account_id} not found for auto-join job")
                return

            client = await self.fullclient_manager._get_account_client(
                account["user_id"], str(account_id)
            )
            if not client:
                logger.error(f"Client not found for account {account_id}")
                return

            from telethon.tl.functions.channels import JoinChannelRequest

            await client(JoinChannelRequest(channel_link))

            logger.info(
                f"Auto-join job executed for account {account_id}, joined {channel_link}"
            )

        except Exception as e:
            logger.error(f"Error executing auto-join job for account {account_id}: {e}")
