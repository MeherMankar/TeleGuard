"""API Security utilities"""

import hashlib
import logging

from ..core.database import get_session
from ..core.models import Account, User

logger = logging.getLogger(__name__)


async def validate_api_key(api_key: str) -> int:
    """Validate API key and return user_id"""
    try:
        # Simple API key format: user_id:hash
        parts = api_key.split(":")
        if len(parts) != 2:
            return None

        user_id_str, key_hash = parts
        user_id = int(user_id_str)

        # Validate against stored API key (simplified)
        async with get_session() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(Account)
                .join(User)
                .where(User.telegram_id == user_id, Account.api_access_enabled == True)
            )
            account = result.scalar_one_or_none()

            if account and account.api_key_hash == key_hash:
                return user_id

        return None

    except Exception as e:
        logger.error(f"API key validation error: {e}")
        return None
