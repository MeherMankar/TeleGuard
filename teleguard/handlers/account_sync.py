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

            # Skip if name unchanged or key is phone number
            if current_key == new_name or current_key.startswith("+"):
                continue

            safe_old = current_key.encode("ascii", errors="replace").decode("ascii")
            safe_new = new_name.encode("ascii", errors="replace").decode("ascii")
            logger.info(f"Name change: '{safe_old}' -> '{safe_new}'")

            # Update database
            await mongodb.db.accounts.update_one(
                {"user_id": user_id, "name": current_key}, {"$set": {"name": new_name}}
            )

            # Update memory
            client_obj = bot_manager.user_clients[user_id].pop(current_key)
            bot_manager.user_clients[user_id][new_name] = client_obj

        except Exception as e:
            logger.error(f"Failed to sync name for {current_key}: {e}")
