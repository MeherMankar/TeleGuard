"""Database migrations for OTP Destroyer enhancements

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import asyncio
import logging
from sqlalchemy import text
from database import get_session, engine

logger = logging.getLogger(__name__)

async def migrate_otp_destroyer_fields():
    """Add OTP destroyer fields to accounts table"""
    migrations = [
        "ALTER TABLE accounts ADD COLUMN otp_destroyer_enabled BOOLEAN DEFAULT FALSE",
        "ALTER TABLE accounts ADD COLUMN otp_destroyed_at TIMESTAMP NULL", 
        "ALTER TABLE accounts ADD COLUMN otp_destroyer_disable_auth TEXT NULL",
        "ALTER TABLE accounts ADD COLUMN otp_audit_log TEXT DEFAULT '[]'",
        "ALTER TABLE accounts ADD COLUMN menu_message_id INTEGER NULL",
        "ALTER TABLE accounts ADD COLUMN twofa_password TEXT NULL"
    ]
    
    async with engine.begin() as conn:
        for migration in migrations:
            try:
                await conn.execute(text(migration))
                logger.info(f"Applied migration: {migration}")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    logger.info(f"Column already exists: {migration}")
                else:
                    logger.error(f"Migration failed: {migration} - {e}")
                    raise

async def migrate_users_table():
    """Add user-level settings"""
    migrations = [
        "ALTER TABLE users ADD COLUMN developer_mode BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN main_menu_message_id INTEGER NULL"
    ]
    
    async with engine.begin() as conn:
        for migration in migrations:
            try:
                await conn.execute(text(migration))
                logger.info(f"Applied migration: {migration}")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    logger.info(f"Column already exists: {migration}")
                else:
                    logger.error(f"Migration failed: {migration} - {e}")

async def run_all_migrations():
    """Run all pending migrations"""
    logger.info("Starting database migrations...")
    await migrate_otp_destroyer_fields()
    await migrate_users_table()
    logger.info("All migrations completed")

if __name__ == "__main__":
    asyncio.run(run_all_migrations())