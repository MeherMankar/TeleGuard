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

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.backup_manager = SessionBackupManager()
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

    def trigger_compact_now(self):
        """Manually trigger history compaction"""
        if self.running:
            self.scheduler.add_job(
                self._compact_history_job,
                id="manual_compact",
                name="Manual history compaction",
            )
