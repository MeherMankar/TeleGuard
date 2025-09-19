"""Telegram channel backup operations"""

import os
import io
import logging
from datetime import datetime, timezone
from telethon import TelegramClient

from .db import store_backup_meta, get_old_telegram_messages, delete_backup_meta

logger = logging.getLogger(__name__)

TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID") or os.getenv("TELEGRAM_BACKUP_CHANNEL")

async def upload_snapshot(bot_client: TelegramClient, snapshot_bytes: bytes, filename: str):
    """Upload snapshot to Telegram channel"""
    if not TELEGRAM_CHANNEL_ID:
        logger.warning("TELEGRAM_CHANNEL_ID not configured, skipping Telegram backup")
        return None
    
    try:
        channel_id = int(TELEGRAM_CHANNEL_ID)
        
        # Send document to channel
        message = await bot_client.send_file(
            channel_id,
            snapshot_bytes,
            attributes=[],
            file_name=filename,
            caption=f"📊 Backup snapshot: {filename}"
        )
        
        # Store metadata
        meta_data = {
            "type": "telegram_snapshot",
            "message_id": message.id,
            "chat_id": channel_id,
            "timestamp": datetime.now(timezone.utc),
            "filename": filename
        }
        
        await store_backup_meta(meta_data)
        
        logger.info(f"Uploaded snapshot to Telegram: {filename}")
        return message
        
    except Exception as e:
        logger.error(f"Failed to upload snapshot to Telegram: {e}")
        return None

async def cleanup_old_telegram_messages(bot_client: TelegramClient, older_than_seconds: int = 8*3600):
    """Delete old backup messages from Telegram channel"""
    if not TELEGRAM_CHANNEL_ID:
        return
    
    try:
        cutoff_time = datetime.now(timezone.utc).timestamp() - older_than_seconds
        cutoff_datetime = datetime.fromtimestamp(cutoff_time, tz=timezone.utc)
        
        old_messages = await get_old_telegram_messages(cutoff_datetime)
        
        deleted_count = 0
        for msg_data in old_messages:
            try:
                await bot_client.delete_messages(
                    msg_data["chat_id"], 
                    [msg_data["message_id"]]
                )
                await delete_backup_meta(msg_data["message_id"])
                deleted_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to delete message {msg_data['message_id']}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old Telegram backup messages")
            
    except Exception as e:
        logger.error(f"Failed to cleanup old Telegram messages: {e}")