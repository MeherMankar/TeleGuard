"""Scheduler for session backup jobs

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .mongo_store import cleanup_old_sessions, init_mongo_indexes
from .session_backup import SessionBackupManager

logger = logging.getLogger(__name__)


class SessionScheduler:
    """Manages scheduled session backup jobs"""

    def __init__(self, bot_client=None):
        self.scheduler = AsyncIOScheduler()
        self.backup_manager = SessionBackupManager()
        self.bot_client = bot_client
        self.running = False

    async def start(self):
        """Start the scheduler"""
        if self.running:
            return

        try:
            # Initialize MongoDB indexes
            init_mongo_indexes()

            # Add jobs
            self.scheduler.add_job(
                self._push_sessions_job,
                IntervalTrigger(minutes=30),
                id="push_sessions",
                name="Push sessions to GitHub",
                max_instances=1,
            )

            self.scheduler.add_job(
                self._compact_history_job,
                IntervalTrigger(hours=8),
                id="compact_history",
                name="Compact GitHub history",
                max_instances=1,
            )

            self.scheduler.add_job(
                self._cleanup_old_sessions_job,
                IntervalTrigger(hours=24),
                id="cleanup_sessions",
                name="Cleanup old MongoDB sessions",
                max_instances=1,
            )

            # Add new backup jobs if bot_client is available
            if self.bot_client:
                self.scheduler.add_job(
                    self._push_user_settings_job,
                    IntervalTrigger(hours=6),  # Runs every 6 hours
                    id="push_user_settings",
                    name="Push user settings to Telegram",
                    max_instances=1,
                )

                self.scheduler.add_job(
                    self._push_user_ids_job,
                    IntervalTrigger(hours=6),  # Runs every 6 hours
                    id="push_user_ids",
                    name="Push user IDs to Telegram",
                    max_instances=1,
                )

                self.scheduler.add_job(
                    self._push_session_files_job,
                    IntervalTrigger(hours=12),  # Runs every 12 hours
                    id="push_session_files",
                    name="Push session files to Telegram",
                    max_instances=1,
                )

            self.scheduler.start()
            self.running = True

            logger.info("Session scheduler started")

        except Exception as e:
            logger.error(f"Failed to start session scheduler: {e}")
            raise

    async def stop(self):
        """Stop the scheduler"""
        if not self.running:
            return

        try:
            self.scheduler.shutdown(wait=True)
            self.running = False
            logger.info("Session scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")

    async def _push_sessions_job(self):
        """Job to push sessions to GitHub"""
        try:
            logger.info("Running scheduled session push job")
            success = self.backup_manager.push_sessions_batch()
            if success:
                logger.info("Session push job completed successfully")
            else:
                logger.warning("Session push job failed")
        except Exception as e:
            logger.error(f"Session push job error: {e}")

    async def _compact_history_job(self):
        """Job to compact GitHub history"""
        try:
            logger.info("Running scheduled history compaction job")
            success = self.backup_manager.compact_history()
            if success:
                logger.info("History compaction job completed successfully")
            else:
                logger.warning("History compaction job failed")
        except Exception as e:
            logger.error(f"History compaction job error: {e}")

    async def _cleanup_old_sessions_job(self):
        """Job to cleanup old sessions from MongoDB"""
        try:
            logger.info("Running scheduled MongoDB cleanup job")
            count = cleanup_old_sessions(days=7)
            logger.info(f"MongoDB cleanup completed, removed {count} old sessions")
        except Exception as e:
            logger.error(f"MongoDB cleanup job error: {e}")

    def trigger_push_now(self):
        """Manually trigger session push"""
        if self.running:
            self.scheduler.add_job(
                self._push_sessions_job, id="manual_push", name="Manual session push"
            )

    def trigger_user_settings_push_now(self):
        """Manually trigger user settings push"""
        if self.running and self.bot_client:
            self.scheduler.add_job(
                self._push_user_settings_job, id="manual_user_settings_push", name="Manual user settings push"
            )

    def trigger_user_ids_push_now(self):
        """Manually trigger user IDs push"""
        if self.running and self.bot_client:
            self.scheduler.add_job(
                self._push_user_ids_job, id="manual_user_ids_push", name="Manual user IDs push"
            )

    def trigger_session_files_push_now(self):
        """Manually trigger session files push"""
        if self.running and self.bot_client:
            self.scheduler.add_job(
                self._push_session_files_job, id="manual_session_files_push", name="Manual session files push"
            )

    def trigger_compact_now(self):
        """Manually trigger history compaction"""
        if self.running:
            self.scheduler.add_job(
                self._compact_history_job,
                id="manual_compact",
                name="Manual history compaction",
            )

    async def _push_user_settings_job(self):
        """Job to push user settings to Telegram channels"""
        try:
            logger.info("Running scheduled user settings push to Telegram job")
            success = await self.backup_manager.push_user_settings_to_telegram(self.bot_client)
            if success:
                logger.info("Telegram user settings push job completed successfully")
            else:
                logger.warning("Telegram user settings push job failed")
        except Exception as e:
            logger.error(f"Telegram user settings push job error: {e}")

    async def _push_user_ids_job(self):
        """Job to push user IDs to Telegram channels"""
        try:
            logger.info("Running scheduled user IDs push to Telegram job")
            success = await self.backup_manager.push_user_ids_to_telegram(self.bot_client)
            if success:
                logger.info("Telegram user IDs push job completed successfully")
            else:
                logger.warning("Telegram user IDs push job failed")
        except Exception as e:
            logger.error(f"Telegram user IDs push job error: {e}")

    async def _push_session_files_job(self):
        """Job to push session files to Telegram channels"""
        try:
            logger.info("Running scheduled session files push to Telegram job")
            success = await self.backup_manager.push_session_files_to_telegram(self.bot_client)
            if success:
                logger.info("Telegram session files push job completed successfully")
            else:
                logger.warning("Telegram session files push job failed")
        except Exception as e:
            logger.error(f"Telegram session files push job error: {e}")
