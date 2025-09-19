"""Main backup operations module"""

import os
import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path

from .db import fetch_snapshot_collections, init_connections
from .crypto import encrypt_bytes
from .github_sync import push_hourly_snapshot, force_orphan_push_latest
from .telegram_backup import upload_snapshot, cleanup_old_telegram_messages

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = os.getenv("SNAPSHOT_DIR", tempfile.gettempdir())

async def create_snapshot():
    """Create JSON snapshot of database collections"""
    await init_connections()
    
    # Fetch all data
    data = await fetch_snapshot_collections()
    
    # Create snapshot metadata
    meta = {
        "created_at": datetime.utcnow().isoformat(),
        "version": "1.0",
        "collections": list(data.keys()),
        "total_records": sum(len(v) if isinstance(v, list) else 1 for v in data.values())
    }
    
    payload = {
        "meta": meta,
        "data": data
    }
    
    # Create snapshot file
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f"teleguard_snapshot_{timestamp}.json"
    filepath = os.path.join(SNAPSHOT_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, default=str, indent=2)
    
    logger.info(f"Created snapshot: {filename} ({meta['total_records']} records)")
    return filepath

def encrypt_snapshot(snapshot_bytes: bytes) -> bytes:
    """Encrypt snapshot bytes using AES-GCM"""
    return encrypt_bytes(snapshot_bytes)

def push_to_github(snapshot_path: str, branch: str = "backups"):
    """Push snapshot to GitHub repository"""
    push_hourly_snapshot(snapshot_path)

def force_orphan_push(snapshot_path: str, branch: str = "backups"):
    """Create orphan branch with only latest snapshot"""
    force_orphan_push_latest(snapshot_path)

async def upload_to_telegram(bot_client, snapshot_bytes: bytes, filename: str):
    """Upload snapshot to Telegram channel"""
    return await upload_snapshot(bot_client, snapshot_bytes, filename)

async def cleanup_telegram_messages(bot_client, older_than_seconds: int):
    """Clean up old Telegram backup messages"""
    await cleanup_old_telegram_messages(bot_client, older_than_seconds)