#!/usr/bin/env python3
"""
Migration script to add OTP forward fields to Account model

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from teleguard.core.database import engine, get_session


async def migrate_otp_fields():
    """Add OTP forward fields to accounts table"""

    migrations = [
        "ALTER TABLE accounts ADD COLUMN otp_forward_enabled BOOLEAN DEFAULT FALSE",
        "ALTER TABLE accounts ADD COLUMN otp_temp_passthrough BOOLEAN DEFAULT FALSE",
    ]

    async with get_session() as session:
        for migration in migrations:
            try:
                await session.execute(text(migration))
                print(f"[OK] Executed: {migration}")
            except Exception as e:
                if (
                    "duplicate column name" in str(e).lower()
                    or "already exists" in str(e).lower()
                ):
                    print(f"[WARN] Column already exists: {migration}")
                else:
                    print(f"[ERROR] Failed: {migration} - {e}")

        await session.commit()
        print("[OK] Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(migrate_otp_fields())
