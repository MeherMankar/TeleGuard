#!/usr/bin/env python3
"""Clear all OTP disable passwords from database"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from teleguard.core.database import get_session, init_db
from teleguard.core.models import Account


async def clear_passwords():
    """Clear all OTP disable passwords"""
    await init_db()

    async with get_session() as session:
        from sqlalchemy import select, update

        # Clear all passwords
        await session.execute(update(Account).values(otp_destroyer_disable_auth=None))
        await session.commit()

        print("All OTP disable passwords cleared")


if __name__ == "__main__":
    asyncio.run(clear_passwords())
