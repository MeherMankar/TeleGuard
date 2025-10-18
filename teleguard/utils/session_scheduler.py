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
            init_mongo_indexes()
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
    
    # Advanced task scheduling methods
    async def schedule_task(self, user_id: int, account_id: str, task_type: str, 
                          parameters: Dict[str, Any], schedule_time: datetime, 
                          repeat: bool = False, repeat_interval: Optional[timedelta] = None,
                          notify_completion: bool = True) -> str:
        """Schedule a new task"""
        try:
            task_id = f"{task_type}_{user_id}_{account_id}_{int(datetime.now().timestamp())}"
            
            task_info = {
                "id": task_id,
                "type": task_type,
                "user_id": user_id,
                "account_id": account_id,
                "parameters": parameters,
                "next_run": schedule_time,
                "repeat": repeat,
                "repeat_interval": repeat_interval.total_seconds() if repeat_interval else None,
                "notify_completion": notify_completion,
                "created_at": datetime.now()
            }
            
            self.scheduled_tasks[task_id] = task_info
            await self._save_scheduled_task(task_id, task_info)
            
            logger.info(f"Scheduled task {task_id}: {task_type} for {schedule_time}")
            return task_id
            
        except Exception as e:
            logger.error(f"Error scheduling task: {e}")
            raise
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task"""
        try:
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
                if not task.done():
                    task.cancel()
                self.running_tasks.pop(task_id, None)
            
            if task_id in self.scheduled_tasks:
                self.scheduled_tasks.pop(task_id, None)
                await self._remove_scheduled_task(task_id)
                logger.info(f"Cancelled task {task_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}")
            return False
    
    async def get_user_tasks(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all tasks for a user"""
        try:
            user_tasks = []
            for task_id, task_info in self.scheduled_tasks.items():
                if task_info["user_id"] == user_id:
                    task_status = "running" if task_id in self.running_tasks else "scheduled"
                    user_tasks.append({
                        **task_info,
                        "status": task_status
                    })
            
            return user_tasks
            
        except Exception as e:
            logger.error(f"Error getting user tasks: {e}")
            return []
    
    async def _save_scheduled_task(self, task_id: str, task_info: Dict[str, Any]):
        """Save scheduled task to database"""
        try:
            await mongodb.db.scheduled_tasks.update_one(
                {"_id": task_id},
                {"$set": {
                    "type": task_info["type"],
                    "user_id": task_info["user_id"],
                    "account_id": task_info["account_id"],
                    "parameters": task_info["parameters"],
                    "next_run": task_info["next_run"],
                    "repeat": task_info["repeat"],
                    "repeat_interval": task_info["repeat_interval"],
                    "notify_completion": task_info["notify_completion"],
                    "created_at": task_info["created_at"]
                }},
                upsert=True
            )
            
        except Exception as e:
            logger.error(f"Error saving scheduled task: {e}")
    
    async def _remove_scheduled_task(self, task_id: str):
        """Remove scheduled task from database"""
        try:
            await mongodb.db.scheduled_tasks.delete_one({"_id": task_id})
        except Exception as e:
            logger.error(f"Error removing scheduled task: {e}")

# Global scheduler instance
_scheduler = None

def get_scheduler():
    """Get global scheduler instance"""
    return _scheduler

def init_scheduler(bot_client=None, bot_manager=None):
    """Initialize global scheduler"""
    global _scheduler
    _scheduler = SessionScheduler(bot_client, bot_manager)
    return _scheduler
