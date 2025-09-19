"""Backup scheduler using AsyncIOScheduler"""

import os
import logging
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .backups import (
    create_snapshot, encrypt_snapshot, push_to_github, 
    force_orphan_push, upload_to_telegram, cleanup_telegram_messages
)

logger = logging.getLogger(__name__)

class BackupScheduler:
    def __init__(self, bot_client=None):
        self.scheduler = AsyncIOScheduler()
        self.bot_client = bot_client
        self.running = False
    
    async def hourly_job(self):
        """Hourly backup job"""
        try:
            logger.info("Starting hourly backup job")
            
            # Create snapshot
            snapshot_path = await create_snapshot()
            
            # Read snapshot for operations
            with open(snapshot_path, "rb") as f:
                snapshot_bytes = f.read()
            
            # Push plain snapshot to GitHub
            push_to_github(snapshot_path)
            
            # Create and push encrypted version for public access
            encrypted_bytes = encrypt_snapshot(snapshot_bytes)
            encrypted_path = snapshot_path + ".enc"
            with open(encrypted_path, "wb") as f:
                f.write(encrypted_bytes)
            push_to_github(encrypted_path)
            
            # Upload to Telegram if bot client available
            if self.bot_client:
                filename = os.path.basename(snapshot_path)
                await upload_to_telegram(self.bot_client, snapshot_bytes, filename)
            
            logger.info("Hourly backup job completed successfully")
            
        except Exception as e:
            logger.error(f"Hourly backup job failed: {e}")
    
    async def cleanup_job(self):
        """8-hour cleanup job"""
        try:
            logger.info("Starting cleanup job")
            
            # Get latest snapshot for orphan push
            snapshot_dir = os.getenv("SNAPSHOT_DIR", "/tmp")
            if os.path.exists(snapshot_dir):
                snapshots = [f for f in os.listdir(snapshot_dir) if f.startswith("teleguard_snapshot_") and f.endswith(".json")]
                if snapshots:
                    latest_snapshot = sorted(snapshots)[-1]
                    latest_path = os.path.join(snapshot_dir, latest_snapshot)
                    
                    # Force orphan push to clean GitHub history
                    force_orphan_push(latest_path)
            
            # Cleanup old Telegram messages
            if self.bot_client:
                await cleanup_telegram_messages(self.bot_client, older_than_seconds=8*3600)
            
            logger.info("Cleanup job completed successfully")
            
        except Exception as e:
            logger.error(f"Cleanup job failed: {e}")
    
    def start_scheduler(self):
        """Start the backup scheduler"""
        if self.running:
            logger.warning("Backup scheduler already running")
            return
        
        # Add hourly job (at minute 0 of every hour)
        self.scheduler.add_job(
            self.hourly_job,
            CronTrigger(minute=0),
            id="hourly_backup",
            replace_existing=True
        )
        
        # Add cleanup job (every 8 hours at minute 5)
        self.scheduler.add_job(
            self.cleanup_job,
            CronTrigger(hour="*/8", minute=5),
            id="cleanup_backup", 
            replace_existing=True
        )
        
        self.scheduler.start()
        self.running = True
        logger.info("Backup scheduler started - hourly backups and 8-hour cleanup enabled")
    
    def stop_scheduler(self):
        """Stop the backup scheduler"""
        if self.running:
            self.scheduler.shutdown()
            self.running = False
            logger.info("Backup scheduler stopped")

# Global scheduler instance
backup_scheduler = None

def start_scheduler(bot_client=None):
    """Start the global backup scheduler"""
    global backup_scheduler
    
    if backup_scheduler is None:
        backup_scheduler = BackupScheduler(bot_client)
    
    backup_scheduler.start_scheduler()

def stop_scheduler():
    """Stop the global backup scheduler"""
    global backup_scheduler
    
    if backup_scheduler:
        backup_scheduler.stop_scheduler()