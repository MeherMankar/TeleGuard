import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from backend.auth.jwt import get_current_user_id
from teleguard.core.mongo_database import mongodb
from teleguard.utils.crypto_utils import DataEncryption

router = APIRouter(prefix="/chats", tags=["Chats"])
logger = logging.getLogger(__name__)


# ── Client resolver ───────────────────────────────────────────────────────────

def _get_bot_manager():
    try:
        from teleguard.core.bot_manager import bot_manager
        return bot_manager
    except Exception:
        return None


async def _resolve_client(user_id: int, account_name: str):
    """Resolve a live Telethon client with multiple fallback strategies."""
    bot_manager = _get_bot_manager()
    if not bot_manager:
        return None

    user_clients = bot_manager.user_clients.get(user_id, {})
    if not user_clients:
        return None

    # 1. Direct name match
    if account_name in user_clients:
        return user_clients[account_name]

    # 2. MongoDB lookup — find phone/name variants
    try:
        async for acc_doc in mongodb.db.accounts.find({"user_id": user_id}):
            try:
                acc = DataEncryption.decrypt_account_data(acc_doc)
                name = acc.get("name", "")
                phone = acc.get("phone", "")
                if name == account_name or phone == account_name:
                    for key in [name, phone]:
                        if key in user_clients:
                            return user_clients[key]
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"MongoDB lookup failed: {e}")

    # 3. Partial phone match
    clean = account_name.replace("+", "").replace(" ", "")
    for key, client in user_clients.items():
        if clean in str(key).replace("+", "").replace(" ", ""):
            return client

    # 4. Single account — return it regardless
    if len(user_clients) == 1:
        return next(iter(user_clients.values()))

    # 5. First connected client
    for client in user_clients.values():
        if client and client.is_connected():
            return client

    return None


# ── Media helpers ─────────────────────────────────────────────────────────────

def _extract_media_info(message) -> Optional[Dict[str, Any]]:
    """Extract rich media metadata from a Telethon message."""
    if not message.media:
        return None

    from telethon.tl.types import (
        MessageMediaPhoto,
        MessageMediaDocument,
        MessageMediaWebPage,
        DocumentAttributeVideo,
        DocumentAttributeFilename,
        DocumentAttributeAudio,
        DocumentAttributeAnimated,
        DocumentAttributeSticker,
    )

    media = message.media

    # Photo
    if isinstance(media, MessageMediaPhoto):
        photo = media.photo
        if photo and hasattr(photo, "sizes"):
            # Get the largest size dimensions
            sizes = [s for s in photo.sizes if hasattr(s, "w")]
            largest = max(sizes, key=lambda s: getattr(s, "w", 0)) if sizes else None
            return {
                "type": "photo",
                "id": str(photo.id),
                "width": getattr(largest, "w", None),
                "height": getattr(largest, "h", None),
                "has_spoiler": getattr(media, "spoiler", False),
            }

    # Document (video, file, sticker, gif, audio)
    if isinstance(media, MessageMediaDocument):
        doc = media.document
        if not doc:
            return None

        attrs = {type(a).__name__: a for a in getattr(doc, "attributes", [])}
        mime = getattr(doc, "mime_type", "") or ""

        # Video
        if "DocumentAttributeVideo" in attrs:
            vid = attrs["DocumentAttributeVideo"]
            return {
                "type": "video",
                "id": str(doc.id),
                "duration": getattr(vid, "duration", None),
                "width": getattr(vid, "w", None),
                "height": getattr(vid, "h", None),
                "size": doc.size,
                "round": getattr(vid, "round_message", False),
                "has_spoiler": getattr(media, "spoiler", False),
            }

        # Animated GIF
        if "DocumentAttributeAnimated" in attrs:
            return {
                "type": "gif",
                "id": str(doc.id),
                "size": doc.size,
                "mime": mime,
            }

        # Sticker
        if "DocumentAttributeSticker" in attrs:
            sticker = attrs["DocumentAttributeSticker"]
            return {
                "type": "sticker",
                "id": str(doc.id),
                "emoji": getattr(sticker, "alt", ""),
                "animated": mime == "application/x-tgsticker",
            }

        # Audio / Voice
        if "DocumentAttributeAudio" in attrs:
            audio = attrs["DocumentAttributeAudio"]
            return {
                "type": "voice" if getattr(audio, "voice", False) else "audio",
                "id": str(doc.id),
                "duration": getattr(audio, "duration", None),
                "title": getattr(audio, "title", None),
                "performer": getattr(audio, "performer", None),
                "size": doc.size,
            }

        # Generic file
        filename = None
        if "DocumentAttributeFilename" in attrs:
            filename = attrs["DocumentAttributeFilename"].file_name
        return {
            "type": "file",
            "id": str(doc.id),
            "filename": filename,
            "mime": mime,
            "size": doc.size,
        }

    # Web page preview
    if isinstance(media, MessageMediaWebPage):
        page = getattr(media, "webpage", None)
        if page and hasattr(page, "url"):
            photo_id = None
            if hasattr(page, "photo") and page.photo:
                photo_id = str(page.photo.id)
            return {
                "type": "webpage",
                "url": page.url,
                "title": getattr(page, "title", None),
                "description": getattr(page, "description", None),
                "site_name": getattr(page, "site_name", None),
                "photo_id": photo_id,
            }

    return {"type": "unknown"}


def _extract_buttons(message) -> Optional[List[List[Dict]]]:
    """Extract inline keyboard buttons from a message."""
    if not message.buttons:
        return None
    try:
        rows = []
        for row in message.buttons:
            buttons = row if isinstance(row, (list, tuple)) else [row]
            row_data = []
            for btn in buttons:
                btn_data = {"text": getattr(btn, "text", "")}
                if hasattr(btn, "url") and btn.url:
                    btn_data["url"] = btn.url
                    btn_data["type"] = "url"
                elif hasattr(btn, "data") and btn.data:
                    btn_data["data"] = btn.data.decode("utf-8", errors="replace")
                    btn_data["type"] = "callback"
                else:
                    btn_data["type"] = "unknown"
                row_data.append(btn_data)
            if row_data:
                rows.append(row_data)
        return rows if rows else None
    except Exception as e:
        logger.debug(f"Button extraction failed: {e}")
        return None


def _extract_forward_info(message) -> Optional[Dict]:
    """Extract forward header information."""
    fwd = getattr(message, "fwd_from", None)
    if not fwd:
        return None
    info = {}
    if hasattr(fwd, "from_name") and fwd.from_name:
        info["from_name"] = fwd.from_name
    if hasattr(fwd, "channel_post") and fwd.channel_post:
        info["channel_post"] = fwd.channel_post
    if hasattr(fwd, "date") and fwd.date:
        info["date"] = fwd.date.isoformat()
    return info if info else None


# ── Profile photo download ────────────────────────────────────────────────────

@router.get("/photo/{account_name}/{entity_id}")
async def get_entity_photo(
    account_name: str,
    entity_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """
    Download and proxy a Telegram entity's profile photo.
    entity_id can be a user ID, chat ID, or channel ID.
    Returns the image bytes with correct content-type.
    """
    client = await _resolve_client(user_id, account_name)
    if not client:
        raise HTTPException(status_code=404, detail="No active client")

    try:
        entity = await client.get_entity(entity_id)
        photo_bytes = await client.download_profile_photo(entity, bytes)
        if not photo_bytes:
            raise HTTPException(status_code=404, detail="No profile photo")
        return Response(content=photo_bytes, media_type="image/jpeg")
    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"Profile photo fetch failed for {entity_id}: {e}")
        raise HTTPException(status_code=404, detail="Photo unavailable")


@router.get("/media/{account_name}/{chat_id}/{message_id}")
async def get_message_media(
    account_name: str,
    chat_id: int,
    message_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """
    Download and proxy a message's media thumbnail/file.
    For photos and video thumbnails — returns image bytes.
    For other files — returns the raw bytes with correct MIME type.
    """
    client = await _resolve_client(user_id, account_name)
    if not client:
        raise HTTPException(status_code=404, detail="No active client")

    try:
        messages = await client.get_messages(chat_id, ids=message_id)
        if not messages or not messages.media:
            raise HTTPException(status_code=404, detail="No media in message")

        from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

        media = messages.media

        # Photo — download the medium-size thumbnail
        if isinstance(media, MessageMediaPhoto):
            data = await client.download_media(messages, bytes, thumb=-1)
            if not data:
                raise HTTPException(status_code=404, detail="Photo download failed")
            return Response(content=data, media_type="image/jpeg")

        # Document with thumbnail (video, file)
        if isinstance(media, MessageMediaDocument):
            doc = media.document
            # Try to get the thumbnail first (much smaller)
            if doc.thumbs:
                data = await client.download_media(messages, bytes, thumb=0)
                if data:
                    return Response(content=data, media_type="image/jpeg")
            # For small files (<2MB) download the whole thing
            if doc.size < 2 * 1024 * 1024:
                data = await client.download_media(messages, bytes)
                if data:
                    mime = getattr(doc, "mime_type", "application/octet-stream")
                    return Response(content=data, media_type=mime)

        raise HTTPException(status_code=404, detail="Media not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Media download failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Dialogs ───────────────────────────────────────────────────────────────────

@router.get("/dialogs/{account_name}")
async def get_dialogs(
    account_name: str,
    limit: int = 50,
    user_id: int = Depends(get_current_user_id),
):
    """Fetch dialog list with profile photo URLs."""
    client = await _resolve_client(user_id, account_name)
    if not client:
        logger.warning(f"No client for {account_name} (user {user_id})")
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
                    "media_type": _extract_media_info(dialog.message).get("type")
                    if dialog.message.media else None,
                }

            # Check if entity has a photo
            has_photo = bool(
                getattr(entity, "photo", None) and
                getattr(entity.photo, "photo_id", None)
            )

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
                "has_photo": has_photo,
                # Frontend uses this to build the photo URL
                "entity_id": dialog.id,
            })
        return dialogs
    except Exception as e:
        logger.error(f"Error fetching dialogs for {account_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Message history ───────────────────────────────────────────────────────────

@router.get("/history/{account_name}/{chat_id}")
async def get_chat_history(
    account_name: str,
    chat_id: int,
    limit: int = 50,
    user_id: int = Depends(get_current_user_id),
):
    """
    Fetch rich message history — includes media metadata, inline buttons,
    forward info, and reply context.
    """
    client = await _resolve_client(user_id, account_name)
    if not client:
        return []

    try:
        messages = []
        async for message in client.iter_messages(chat_id, limit=limit):
            # Reply context
            reply = None
            if message.reply_to_msg_id:
                reply = {"msg_id": message.reply_to_msg_id}
                # Try to get the replied message's text/type
                try:
                    replied = await client.get_messages(chat_id, ids=message.reply_to_msg_id)
                    if replied:
                        reply["text"] = (replied.message or "")[:80]
                        reply["sender_id"] = replied.sender_id
                        if replied.media:
                            info = _extract_media_info(replied)
                            reply["media_type"] = info.get("type") if info else None
                except Exception:
                    pass

            # Sender name
            sender_name = None
            if message.sender_id and (dialog_is_group := True):
                try:
                    sender = await message.get_sender()
                    if sender:
                        fn = getattr(sender, "first_name", "") or ""
                        ln = getattr(sender, "last_name", "") or ""
                        sender_name = f"{fn} {ln}".strip() or getattr(sender, "title", None)
                except Exception:
                    pass

            messages.append({
                "id": message.id,
                "text": message.message,
                "date": message.date.isoformat() if message.date else None,
                "out": message.out,
                "sender_id": message.sender_id,
                "sender_name": sender_name,
                "reply": reply,
                "forward": _extract_forward_info(message),
                "media": _extract_media_info(message),
                "buttons": _extract_buttons(message),
                "views": getattr(message, "views", None),
                "pinned": getattr(message, "pinned", False),
                "silent": getattr(message, "silent", False),
            })
        return messages
    except Exception as e:
        logger.error(f"Error fetching history for {chat_id} on {account_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
