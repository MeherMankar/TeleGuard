import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException

from backend.auth.jwt import get_current_user_id

router = APIRouter(prefix="/chats", tags=["Chats"])
logger = logging.getLogger(__name__)


def _get_bot_manager():
    try:
        from teleguard.core.bot_manager import bot_manager
        return bot_manager
    except Exception:
        return None


@router.get("/dialogs/{account_name}")
async def get_dialogs(
    account_name: str,
    limit: int = 50,
    user_id: int = Depends(get_current_user_id),
):
    """Fetch dialogs (chat list) for a specific account from the live bot client."""
    bot_manager = _get_bot_manager()
    if not bot_manager:
        raise HTTPException(status_code=503, detail="Bot manager not initialized")

    client = bot_manager.get_client(user_id, {"name": account_name})
    if not client:
        raise HTTPException(status_code=404, detail=f"No active client for account '{account_name}'. Ensure the account is connected.")

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
    bot_manager = _get_bot_manager()
    if not bot_manager:
        raise HTTPException(status_code=503, detail="Bot manager not initialized")

    client = bot_manager.get_client(user_id, {"name": account_name})
    if not client:
        raise HTTPException(status_code=404, detail=f"No active client for account '{account_name}'")

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
