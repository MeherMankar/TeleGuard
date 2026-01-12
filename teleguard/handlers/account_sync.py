"""Account Name Sync - Auto-update names from Telegram"""

import logging

logger = logging.getLogger(__name__)


async def sync_account_names(bot_manager, user_id):
    """Sync account names from Telegram to database and memory"""
    if user_id not in bot_manager.user_clients:
        return

    from ..core.mongo_database import mongodb

    active_sessions = list(bot_manager.user_clients[user_id].items())

    for current_key, client in active_sessions:
        if not client or not client.is_connected():
            continue

        try:
            me = await client.get_me()
            if not me:
                continue

            new_name = f"{me.first_name or ''} {me.last_name or ''}".strip()
            if _should_skip_sync(current_key, new_name):
                continue

            _log_name_change(current_key, new_name)
            await _update_database(mongodb, user_id, current_key, new_name)
            _update_memory(bot_manager, user_id, current_key, new_name)

        except Exception as e:
            logger.error(f"Failed to sync name for {current_key}: {e}")


def _should_skip_sync(current_key: str, new_name: str) -> bool:
    """Check if sync should be skipped"""
    return current_key == new_name or current_key.startswith("+")


def _log_name_change(old_name: str, new_name: str):
    """Log name change with safe encoding"""
    safe_old = old_name.encode("ascii", errors="replace").decode("ascii")
    safe_new = new_name.encode("ascii", errors="replace").decode("ascii")
    logger.info(f"Name change: '{safe_old}' -> '{safe_new}'")


async def _update_database(mongodb, user_id: int, old_name: str, new_name: str):
    """Update account name in database"""
    await mongodb.db.accounts.update_one(
        {"user_id": user_id, "name": old_name}, {"$set": {"name": new_name}}
    )


def _update_memory(bot_manager, user_id: int, old_name: str, new_name: str):
    """Update account name in memory"""
    client_obj = bot_manager.user_clients[user_id].pop(old_name)
    bot_manager.user_clients[user_id][new_name] = client_obj
