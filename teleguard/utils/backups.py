"""Unified Backup System for TeleGuard - Telegram + Database Snapshots"""

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Optional

from ..core.config import TELEGRAM_BACKUP_CHANNEL

logger = logging.getLogger(__name__)
SNAPSHOT_DIR = os.getenv("SNAPSHOT_DIR", tempfile.gettempdir())


class TelegramBackup:
    """Simple backup to Telegram channel"""

    def __init__(self, bot_client):
        self.bot = bot_client
        self.channel_id = (
            int(TELEGRAM_BACKUP_CHANNEL) if TELEGRAM_BACKUP_CHANNEL else None
        )

    async def backup_user_settings(self):
        """Backup all user settings to Telegram"""
        if not self.channel_id:
            raise Exception("Telegram backup channel not configured")

        try:
            from ..core.database_manager import db_manager
            from ..core.mongo_database import mongodb

            users = await mongodb.db.users.find({}).to_list(length=None)

            settings_data = []
            for user in users:
                user_settings = await db_manager.get_user_settings(
                    user.get("telegram_id")
                )
                if user_settings:
                    settings_data.append(
                        {
                            "user_id": user.get("telegram_id"),
                            "settings": user_settings,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

            if settings_data:
                backup_content = json.dumps(settings_data, indent=2, default=str)
                filename = f"user_settings_backup_{
                    datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

                await self.bot.send_file(
                    self.channel_id,
                    backup_content.encode(),
                    file_name=filename,
                    caption=f"🔧 User Settings Backup\n📅 {
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n👥 {
                        len(settings_data)} users",
                )
                logger.info(f"Backed up settings for {len(settings_data)} users")
            else:
                await self.bot.send_message(
                    self.channel_id, "📝 No user settings found to backup"
                )

        except Exception as e:
            logger.error(f"User settings backup failed: {e}")
            raise

    async def backup_user_ids(self):
        """Backup all user IDs to Telegram"""
        if not self.channel_id:
            raise Exception("Telegram backup channel not configured")

        try:
            from ..core.mongo_database import mongodb

            users = await mongodb.db.users.find({}).to_list(length=None)

            user_ids = []
            for user in users:
                user_ids.append(
                    {
                        "telegram_id": user.get("telegram_id"),
                        "created_at": user.get("created_at", "unknown"),
                        "last_active": user.get("last_active", "unknown"),
                    }
                )

            if user_ids:
                backup_content = json.dumps(user_ids, indent=2, default=str)
                filename = (
                    f"user_ids_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )

                await self.bot.send_file(
                    self.channel_id,
                    backup_content.encode(),
                    file_name=filename,
                    caption=f"🆔 User IDs Backup\n📅 {
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n👥 {
                        len(user_ids)} users",
                )
                logger.info(f"Backed up {len(user_ids)} user IDs")
            else:
                await self.bot.send_message(
                    self.channel_id, "📝 No user IDs found to backup"
                )

        except Exception as e:
            logger.error(f"User IDs backup failed: {e}")
            raise

    async def backup_session_files(self):
        """Backup session file information to Telegram"""
        if not self.channel_id:
            raise Exception("Telegram backup channel not configured")

        try:
            from ..core.mongo_database import mongodb

            accounts = await mongodb.db.accounts.find({}).to_list(length=None)

            session_info = []
            for account in accounts:
                session_info.append(
                    {
                        "account_id": str(account.get("_id")),
                        "user_id": account.get("user_id"),
                        "phone": account.get("phone", "unknown"),
                        "status": account.get("status", "unknown"),
                        "created_at": account.get("created_at", "unknown"),
                        "has_session": bool(account.get("session_string")),
                    }
                )

            if session_info:
                backup_content = json.dumps(session_info, indent=2, default=str)
                filename = f"session_info_backup_{
                    datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

                await self.bot.send_file(
                    self.channel_id,
                    backup_content.encode(),
                    file_name=filename,
                    caption=f"📱 Session Info Backup\n📅 {
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n📱 {
                        len(session_info)} accounts",
                )
                logger.info(f"Backed up info for {len(session_info)} sessions")
            else:
                await self.bot.send_message(
                    self.channel_id, "📝 No session info found to backup"
                )

        except Exception as e:
            logger.error(f"Session info backup failed: {e}")
            raise


class AutoBackup:
    """Automatic backup system that triggers on database changes"""

    def __init__(self, bot_client):
        self.bot = bot_client
        self.channel_id = (
            int(TELEGRAM_BACKUP_CHANNEL) if TELEGRAM_BACKUP_CHANNEL else None
        )
        self._backup_queue = asyncio.Queue()
        self._backup_task = None

    async def start(self):
        """Start the backup worker"""
        if self.channel_id and not self._backup_task:
            self._backup_task = asyncio.create_task(self._backup_worker())
            logger.info("Auto backup system started")

    async def stop(self):
        """Stop the backup worker"""
        if self._backup_task:
            self._backup_task.cancel()
            self._backup_task = None

    async def _backup_worker(self):
        """Background worker that processes backup queue"""
        while True:
            try:
                backup_data = await self._backup_queue.get()
                await self._send_backup(backup_data)
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Backup worker error: {e}")

    async def _send_backup(self, data):
        """Send backup data to Telegram channel"""
        try:
            if not self.channel_id:
                return

            filename = f"{data['type']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            content = json.dumps(data, indent=2, default=str)

            await self.bot.send_file(
                self.channel_id,
                content.encode(),
                file_name=filename,
                caption=f"🔄 Auto Backup: {
                    data['action']}\n📅 {
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            )
            logger.info(f"Auto backup sent: {data['action']}")
        except Exception as e:
            logger.error(f"Failed to send backup: {e}")

    def trigger_account_backup(self, action: str, user_id: int, account_data: dict):
        """Trigger backup when account is added/removed"""
        if not self.channel_id:
            return

        backup_data = {
            "type": "account_change",
            "action": action,
            "user_id": user_id,
            "account_data": account_data,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            self._backup_queue.put_nowait(backup_data)
        except asyncio.QueueFull:
            logger.warning("Backup queue full, skipping backup")

    def trigger_user_backup(self, action: str, user_id: int, user_data: dict):
        """Trigger backup when user data changes"""
        if not self.channel_id:
            return

        backup_data = {
            "type": "user_change",
            "action": action,
            "user_id": user_id,
            "user_data": user_data,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            self._backup_queue.put_nowait(backup_data)
        except asyncio.QueueFull:
            logger.warning("Backup queue full, skipping backup")


# Global auto backup instance
_auto_backup: Optional[AutoBackup] = None


def init_auto_backup(bot_client):
    """Initialize auto backup system"""
    global _auto_backup
    _auto_backup = AutoBackup(bot_client)
    return _auto_backup


async def start_auto_backup():
    """Start auto backup system"""
    if _auto_backup:
        await _auto_backup.start()


async def stop_auto_backup():
    """Stop auto backup system"""
    if _auto_backup:
        await _auto_backup.stop()


def backup_account_change(action: str, user_id: int, account_data: dict):
    """Trigger account change backup"""
    if _auto_backup:
        _auto_backup.trigger_account_backup(action, user_id, account_data)


def backup_user_change(action: str, user_id: int, user_data: dict):
    """Trigger user change backup"""
    if _auto_backup:
        _auto_backup.trigger_user_backup(action, user_id, user_data)


# Database snapshot functionality
async def create_snapshot():
    """Create JSON snapshot of database collections"""
    try:
        from ..sync.db import fetch_snapshot_collections, init_connections

        await init_connections()

        # Fetch all data
        data = await fetch_snapshot_collections()
        meta = {
            "created_at": datetime.utcnow().isoformat(),
            "version": "1.0",
            "collections": list(data.keys()),
            "total_records": sum(
                len(v) if isinstance(v, list) else 1 for v in data.values()
            ),
        }
        payload = {"meta": meta, "data": data}

        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"teleguard_snapshot_{timestamp}.json"
        filepath = os.path.join(SNAPSHOT_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, default=str, indent=2)

        logger.info(f"Created snapshot: {filename} ({meta['total_records']} records)")
        return filepath

    except Exception as e:
        logger.error(f"Failed to create database snapshot: {e}")
        raise


def encrypt_snapshot(snapshot_bytes: bytes) -> bytes:
    """Encrypt snapshot bytes using AES-GCM"""
    try:
        from ..sync.crypto import encrypt_bytes

        return encrypt_bytes(snapshot_bytes)
    except Exception as e:
        logger.error(f"Failed to encrypt snapshot: {e}")
        return snapshot_bytes


def push_to_github(snapshot_path: str, _branch: str = "backups"):
    """Push snapshot to GitHub repository"""
    try:
        from .session_backup import SessionBackupManager

        manager = SessionBackupManager()
        if not manager.enabled:
            logger.warning("GitHub sync disabled")
            return

        manager.ensure_local_clone()
        # Copy snapshot to workdir
        import shutil

        target_dir = manager.workdir / "snapshots"
        target_dir.mkdir(exist_ok=True)
        shutil.copy(snapshot_path, target_dir / os.path.basename(snapshot_path))

        manager.commit_and_push(f"Database snapshot: {os.path.basename(snapshot_path)}")
        logger.info(f"Pushed snapshot {snapshot_path} to GitHub")
    except Exception as e:
        logger.error(f"GitHub push failed: {e}")


def force_orphan_push(snapshot_path: str, _branch: str = "backups"):
    """Create orphan branch with only latest snapshot (feature removed)"""
    logger.warning("GitHub sync feature has been removed")


async def upload_to_telegram(bot_client, snapshot_bytes: bytes, filename: str):
    """Upload snapshot to Telegram channel"""
    try:
        from ..sync.telegram_backup import upload_snapshot

        return await upload_snapshot(bot_client, snapshot_bytes, filename)
    except Exception as e:
        logger.error(f"Failed to upload to Telegram: {e}")
        return False


async def cleanup_telegram_messages(bot_client, older_than_seconds: int):
    """Clean up old Telegram backup messages"""
    try:
        from ..sync.telegram_backup import cleanup_old_telegram_messages

        await cleanup_old_telegram_messages(bot_client, older_than_seconds)
    except Exception as e:
        logger.error(f"Failed to cleanup Telegram messages: {e}")
