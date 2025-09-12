"""Database migrations for full Telegram client features

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import asyncio
import logging
import os
import sys

from sqlalchemy import text

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from teleguard.core.database import engine, get_session

logger = logging.getLogger(__name__)


async def migrate_fullclient_fields():
    """Add full client management fields to accounts table"""
    migrations = [
        # Profile management fields
        "ALTER TABLE accounts ADD COLUMN profile_photo_id TEXT NULL",
        "ALTER TABLE accounts ADD COLUMN username TEXT NULL",
        "ALTER TABLE accounts ADD COLUMN about TEXT NULL",
        # Automation fields
        "ALTER TABLE accounts ADD COLUMN online_maker_enabled BOOLEAN DEFAULT FALSE",
        "ALTER TABLE accounts ADD COLUMN online_maker_interval INTEGER DEFAULT 3600",
        "ALTER TABLE accounts ADD COLUMN automation_rules TEXT DEFAULT '[]'",
        "ALTER TABLE accounts ADD COLUMN last_online_update TIMESTAMP NULL",
        # Session management fields
        "ALTER TABLE accounts ADD COLUMN session_health_check TIMESTAMP NULL",
        "ALTER TABLE accounts ADD COLUMN active_sessions_count INTEGER DEFAULT 0",
        "ALTER TABLE accounts ADD COLUMN last_session_check TIMESTAMP NULL",
        # Security and audit fields
        "ALTER TABLE accounts ADD COLUMN login_alerts_enabled BOOLEAN DEFAULT TRUE",
        "ALTER TABLE accounts ADD COLUMN webhook_url TEXT NULL",
        "ALTER TABLE accounts ADD COLUMN api_access_enabled BOOLEAN DEFAULT FALSE",
        "ALTER TABLE accounts ADD COLUMN api_key_hash TEXT NULL",
        # Co-owner permissions
        "ALTER TABLE co_owners ADD COLUMN permissions TEXT DEFAULT '{}'",
        "ALTER TABLE co_owners ADD COLUMN added_by INTEGER NULL",
        "ALTER TABLE co_owners ADD COLUMN added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    ]

    async with engine.begin() as conn:
        for migration in migrations:
            try:
                await conn.execute(text(migration))
                logger.info(f"Applied migration: {migration}")
            except Exception as e:
                if (
                    "duplicate column name" in str(e).lower()
                    or "already exists" in str(e).lower()
                ):
                    logger.info(f"Column already exists: {migration}")
                else:
                    logger.error(f"Migration failed: {migration} - {e}")
                    raise


async def migrate_automation_tables():
    """Create tables for automation features"""
    migrations = [
        """
        CREATE TABLE IF NOT EXISTS automation_jobs (
            id INTEGER PRIMARY KEY,
            account_id INTEGER NOT NULL,
            job_type TEXT NOT NULL,
            job_config TEXT NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            last_run TIMESTAMP NULL,
            next_run TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts (id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS message_templates (
            id INTEGER PRIMARY KEY,
            account_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            content TEXT NOT NULL,
            media_path TEXT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts (id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY,
            account_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT NOT NULL,
            ip_address TEXT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        """,
    ]

    async with engine.begin() as conn:
        for migration in migrations:
            try:
                await conn.execute(text(migration))
                logger.info(f"Created table: {migration.split('(')[0].split()[-1]}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info(
                        f"Table already exists: {migration.split('(')[0].split()[-1]}"
                    )
                else:
                    logger.error(f"Table creation failed: {e}")
                    raise


async def run_fullclient_migrations():
    """Run all full client migrations"""
    logger.info("Starting full client database migrations...")
    await migrate_fullclient_fields()
    await migrate_automation_tables()
    logger.info("Full client migrations completed")


if __name__ == "__main__":
    asyncio.run(run_fullclient_migrations())
