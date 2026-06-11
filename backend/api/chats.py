import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException

from backend.auth.jwt import get_current_user_id
from teleguard.core.mongo_database import mongodb
from teleguard.utils.crypto_utils import DataEncryption

router = APIRouter(prefix="/chats", tags=["Chats"])
logger = logging.getLogger(__name__)


def _get_bot_manager():
    try:
        from teleguard.core.bot_manager import bot_manager
        return bot_manager
    except Exception:
        return None


async def _resolve_client(user_id: int, account_name: str):
    """
    Resolve a Telethon client for a given account name.
    Tries: display name, phone, all keys in user_clients dict.
    Falls back to first connected client if only one account exists.
    """
    bot_manager = _get_bot_manager()
    if not bot_manager:
        return None

    user_clients = bot_manager.user_clients.get(user_id, {})
    if not user_clients:
        return None

    # 1. Direct name match
    if account_name in user_clients:
        return user_clients[account_name]

    # 2. Look up in MongoDB to find phone/name variations
    try:
        doc = await mongodb.db.accounts.find_one({"user_id": user_id})
        if doc:
            decrypted = DataEncryption.decrypt_account_data(doc)
            # Try each account
            async for acc_doc in mongodb.db.accounts.find({"user_id": user_id}):
                try:
                    acc = DataEncryption.decrypt_account_data(acc_doc)
                    name = acc.get("name", "")
                    phone = acc.get("phone", "")

                    # Match by name or phone
                    if name == account_name or phone == account_name:
                        # Try both as client keys
                        for key in [name, phone, name.replace("+", ""), phone.replace("+", "")]:
                            if key in user_clients:
                                return user_clients[key]
                except Exception:
                    continue
    except Exception as e:
        logger.debug(f"MongoDB lookup failed: {e}")

    # 3. Partial match — account_name might be truncated or have different format
    account_clean = account_name.replace("+", "").replace(" ", "")
    for key, client in user_clients.items():
        key_clean = str(key).replace("+", "").replace(" ", "")
        if account_clean in key_clean or key_clean in account_clean:
            return client

    # 4. If only one client, return it regardless of name
    if len(user_clients) == 1:
        return next(iter(user_clients.values()))

    # 5. Return first connected client as last resort
    for client in user_clients.values():
        if client and client.is_connected():
            return client

    return None


@router.get("/dialogs/{account_name}")
async def get_dialogs(
    account_name: str,
    limit: int = 50,
    user_id: int = Depends(get_current_user_id),
):
    """Fetch dialogs (chat list) for an account."""
    client = await _resolve_client(user_id, account_name)
    if not client:
        # Return empty list instead of 404 — frontend handles "No chats yet"
        logger.warning(f"No client found for {account_name} (user {user_id})")
        return []

    try:
        dialogs = []
        async for dialog in client.iter_dialogs(limit=limit):
            entity = dialog.entity
            last_message = None
            if dialog.message:
                last_message = {
                    "id": dialog.message.id,
                    "text": dialog.message.message,
                    "date": dialog.message.date.isoformat() if dialog.message.date else None,
                    "out": dialog.message.out,
                }
            dialogs.append({
                "id": dialog.id,
                "name": dialog.name,
                "title": dialog.title,
                "is_group": dialog.is_group or getattr(entity, "megagroup", False),
                "is_channel": dialog.is_channel and not getattr(entity, "megagroup", False),
                "is_user": dialog.is_user,
                "unread_count": dialog.unread_count,
                "last_message": last_message,
                "pinned": dialog.pinned,
            })
        return dialogs
    except Exception as e:
        logger.error(f"Error fetching dialogs for {account_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{account_name}/{chat_id}")
async def get_chat_history(
    account_name: str,
    chat_id: int,
    limit: int = 50,
    user_id: int = Depends(get_current_user_id),
):
    """Fetch message history for a chat."""
    client = await _resolve_client(user_id, account_name)
    if not client:
        return []

    try:
        messages = []
        async for message in client.iter_messages(chat_id, limit=limit):
            messages.append({
                "id": message.id,
                "text": message.message,
                "date": message.date.isoformat() if message.date else None,
                "out": message.out,
                "sender_id": message.sender_id,
                "reply_to_msg_id": message.reply_to_msg_id,
                "media": bool(message.media),
            })
        return messages
    except Exception as e:
        logger.error(f"Error fetching history for {chat_id} on {account_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
