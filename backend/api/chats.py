import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from backend.auth.jwt import get_current_user_id
from teleguard.core.mongo_database import mongodb
from teleguard.utils.crypto_utils import DataEncryption

router = APIRouter(prefix="/chats", tags=["Chats"])
logger = logging.getLogger(__name__)


def _safe_str(v) -> Optional[str]:
    """
    Coerce a value to a plain Python str, or None if empty.
    Handles Telegram's MessageEntityMention, MessageEntityBold, etc.
    that Telethon sometimes returns in place of plain message text.
    """
    if v is None:
        return None
    if isinstance(v, str):
        return v or None
    # TLObject or any object with a 'message' or 'text' attribute
    for attr in ("message", "text"):
        val = getattr(v, attr, None)
        if isinstance(val, str):
            return val or None
    # Last resort — stringify
    try:
        s = str(v)
        return s if s not in ("None", "") else None
    except Exception:
        return None


def _extract_user_status(entity) -> Optional[str]:
    """
    Extract human-readable online/last-seen status from a Telegram entity.
    Returns: "online", "recently", "last_week", "last_month", "long_ago",
             "never", "within_X_seconds/minutes/hours/days", or None for non-users.
    """
    from telethon.tl.types import (
        UserStatusOnline, UserStatusOffline, UserStatusRecently,
        UserStatusLastWeek, UserStatusLastMonth, UserStatusEmpty,
    )
    from datetime import datetime, timezone

    status = getattr(entity, "status", None)
    if status is None:
        return None

    if isinstance(status, UserStatusOnline):
        return "online"
    elif isinstance(status, UserStatusOffline):
        # was_online is a datetime
        was = getattr(status, "was_online", None)
        if was:
            if was.tzinfo is None:
                was = was.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            diff = int((now - was).total_seconds())
            if diff < 60:
                return f"last seen {diff}s ago"
            elif diff < 3600:
                return f"last seen {diff // 60}m ago"
            elif diff < 86400:
                return f"last seen {diff // 3600}h ago"
            elif diff < 86400 * 7:
                return f"last seen {diff // 86400}d ago"
            else:
                return "last seen long ago"
        return "offline"
    elif isinstance(status, UserStatusRecently):
        return "last seen recently"
    elif isinstance(status, UserStatusLastWeek):
        return "last seen last week"
    elif isinstance(status, UserStatusLastMonth):
        return "last seen last month"
    elif isinstance(status, UserStatusEmpty):
        return None
    return None


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
                name = acc.get("name", "").strip()
                phone = acc.get("phone", "").strip()
                display_name = acc.get("display_name", "").strip()

                # Match by any name variant or phone
                match_keys = {name, phone, display_name}
                match_keys.discard("")

                if account_name in match_keys:
                    # Try all keys the client might be stored under
                    for key in list(match_keys) + [
                        phone.replace("+", ""),
                        phone.lstrip("+"),
                    ]:
                        if key and key in user_clients:
                            return user_clients[key]
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"MongoDB lookup failed: {e}")

    # 3. Partial match on phone digits
    clean = account_name.replace("+", "").replace(" ", "").replace(".", "")
    if clean:
        for key, client in user_clients.items():
            key_clean = str(key).replace("+", "").replace(" ", "")
            if clean and len(clean) >= 5 and (clean in key_clean or key_clean in clean):
                return client

    # 4. If account_name looks like a display name (not a phone), try all clients
    #    and find which one's get_me() matches — expensive but reliable fallback
    if not account_name.startswith("+") and len(user_clients) <= 5:
        for key, client in user_clients.items():
            if client and client.is_connected():
                try:
                    me = await client.get_me()
                    fn = str(getattr(me, "first_name", "") or "")
                    ln = str(getattr(me, "last_name", "") or "")
                    full = f"{fn} {ln}".strip()
                    uname = str(getattr(me, "username", "") or "")
                    if account_name in (full, uname, fn, f"@{uname}"):
                        return client
                except Exception:
                    pass

    # 5. Single account — return it regardless
    if len(user_clients) == 1:
        return next(iter(user_clients.values()))

    # 6. Return first connected client as last resort
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
    JWT accepted via Authorization header OR ?token= query param (for <img> tags).
    """
    client = await _resolve_client(user_id, account_name)
    if not client:
        raise HTTPException(status_code=404, detail="No active client")

    try:
        try:
            entity = await client.get_entity(entity_id)
        except Exception:
            if entity_id > 0:
                try:
                    entity = await client.get_entity(-entity_id)
                except Exception:
                    raise HTTPException(status_code=404, detail="Entity not found")
            else:
                raise HTTPException(status_code=404, detail="Entity not found")

        photo_bytes = await client.download_profile_photo(entity, file=bytes)

        if not photo_bytes:
            raise HTTPException(status_code=404, detail="No profile photo")

        return Response(
            content=photo_bytes,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"Profile photo fetch failed for entity {entity_id}: {e}")
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
            # Extract sender name for groups (name of who sent the last msg)
            last_sender_name = None
            if dialog.message and (dialog.is_group or (dialog.is_channel and getattr(entity, "megagroup", False))):
                try:
                    sender = await dialog.message.get_sender()
                    if sender:
                        fn = _safe_str(getattr(sender, "first_name", "")) or ""
                        ln = _safe_str(getattr(sender, "last_name", "")) or ""
                        last_sender_name = f"{fn} {ln}".strip() or _safe_str(getattr(sender, "title", ""))
                except Exception:
                    pass

            last_message = None
            if dialog.message:
                last_message = {
                    "id": dialog.message.id,
                    "text": _safe_str(dialog.message.message),
                    "date": dialog.message.date.isoformat() if dialog.message.date else None,
                    "out": dialog.message.out,
                    "media_type": _extract_media_info(dialog.message).get("type")
                    if dialog.message.media else None,
                    "sender_name": last_sender_name,
                }

            # Detect "Saved Messages" — when dialog entity is the user themselves
            is_saved_messages = False
            try:
                from telethon.tl.types import User
                if isinstance(entity, User) and getattr(entity, "is_self", False):
                    is_saved_messages = True
            except Exception:
                pass

            # Robust photo detection for all entity types:
            # - User/Bot: UserProfilePhoto has photo_id
            # - Chat/Channel: ChatPhoto has photo_small (different type)
            # - Empty: UserProfilePhotoEmpty / ChatPhotoEmpty (no real photo)
            entity_photo = getattr(entity, "photo", None)
            has_photo = False
            if entity_photo is not None:
                photo_type = type(entity_photo).__name__
                # Any non-empty photo type counts
                has_photo = "Empty" not in photo_type and photo_type not in ("NoneType",)

            # Check muted status
            is_muted = False
            try:
                notify = getattr(dialog, "notify_settings", None)
                if notify:
                    mute_until = getattr(notify, "mute_until", None)
                    is_muted = mute_until is not None and mute_until > 0
            except Exception:
                pass

            dialogs.append({
                "id": dialog.id,
                "name": "Saved Messages" if is_saved_messages else dialog.name,
                "title": "Saved Messages" if is_saved_messages else dialog.title,
                "is_group": dialog.is_group or getattr(entity, "megagroup", False),
                "is_channel": dialog.is_channel and not getattr(entity, "megagroup", False),
                "is_user": dialog.is_user,
                "is_saved_messages": is_saved_messages,
                "unread_count": dialog.unread_count,
                "unread_mentions": getattr(dialog, "unread_mentions_count", 0) or 0,
                "last_message": last_message,
                "pinned": dialog.pinned,
                "muted": is_muted,
                "has_photo": has_photo and not is_saved_messages,
                "entity_id": dialog.id,
                "status": _extract_user_status(entity) if dialog.is_user and not is_saved_messages else None,
                "is_bot": bool(getattr(entity, "bot", False)) if dialog.is_user else False,
                "verified": bool(getattr(entity, "verified", False)),
                "participants_count": getattr(entity, "participants_count", None),
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
                        reply["text"] = _safe_str(replied.message)
                        reply["sender_id"] = replied.sender_id
                        if replied.media:
                            info = _extract_media_info(replied)
                            reply["media_type"] = info.get("type") if info else None
                except Exception:
                    pass

            # Sender name — coerce to plain string
            sender_name = None
            if message.sender_id:
                try:
                    sender = await message.get_sender()
                    if sender:
                        fn = str(getattr(sender, "first_name", "") or "")
                        ln = str(getattr(sender, "last_name", "") or "")
                        title = str(getattr(sender, "title", "") or "")
                        sender_name = f"{fn} {ln}".strip() or title or None
                except Exception:
                    pass

            messages.append({
                "id": message.id,
                "text": _safe_str(message.message),
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
# ── User status ───────────────────────────────────────────────────────────────

@router.get("/status/{account_name}/{entity_id}")
async def get_user_status(
    account_name: str,
    entity_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """
    Get real-time online/last-seen status for a user.
    Only works for private chats (users) — groups/channels return null.
    """
    client = await _resolve_client(user_id, account_name)
    if not client:
        raise HTTPException(status_code=404, detail="No active client")

    try:
        try:
            entity = await client.get_entity(entity_id)
        except Exception:
            if entity_id > 0:
                try:
                    entity = await client.get_entity(-entity_id)
                except Exception:
                    raise HTTPException(status_code=404, detail="Entity not found")
            else:
                raise HTTPException(status_code=404, detail="Entity not found")

        status = _extract_user_status(entity)
        is_online = status == "online"

        return {
            "entity_id": entity_id,
            "status": status,
            "is_online": is_online,
            "username": getattr(entity, "username", None),
            "first_name": _safe_str(getattr(entity, "first_name", None)),
            "last_name": _safe_str(getattr(entity, "last_name", None)),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"Status fetch failed for {entity_id}: {e}")
        raise HTTPException(status_code=404, detail="Status unavailable")

@router.get("/folders/{account_name}")
async def get_folders(
    account_name: str,
    user_id: int = Depends(get_current_user_id),
):
    """
    Fetch all Telegram chat folders (dialog filters) for an account.
    These are the real folders the user created in Telegram.
    """
    client = await _resolve_client(user_id, account_name)
    if not client:
        return []

    try:
        from telethon.tl.functions.messages import GetDialogFiltersRequest
        from telethon.tl.types import DialogFilter, DialogFilterDefault

        result = await client(GetDialogFiltersRequest())
        folders = []

        for f in result.filters:
            if isinstance(f, DialogFilterDefault):
                # "All Chats" default folder
                folders.append({
                    "id": 0,
                    "title": "All Chats",
                    "emoji": None,
                    "is_default": True,
                    "contacts": False,
                    "non_contacts": False,
                    "groups": False,
                    "broadcasts": False,
                    "bots": False,
                    "exclude_muted": False,
                    "exclude_read": False,
                    "exclude_archived": False,
                    "included_peers": [],
                    "excluded_peers": [],
                })
            if isinstance(f, DialogFilter):
                # Build list of included peer IDs
                included = []
                for peer in getattr(f, "include_peers", []):
                    pid = getattr(peer, "channel_id", None) or \
                          getattr(peer, "chat_id", None) or \
                          getattr(peer, "user_id", None)
                    if pid:
                        included.append(int(pid))

                excluded = []
                for peer in getattr(f, "exclude_peers", []):
                    pid = getattr(peer, "channel_id", None) or \
                          getattr(peer, "chat_id", None) or \
                          getattr(peer, "user_id", None)
                    if pid:
                        excluded.append(int(pid))

                # title can be a TextWithEntities object — extract plain text
                raw_title = f.title
                if hasattr(raw_title, "text"):
                    title_str = str(raw_title.text or "")
                else:
                    title_str = str(raw_title or "")

                folders.append({
                    "id": f.id,
                    "title": title_str,
                    "emoji": getattr(f, "emoticon", None),
                    "is_default": False,
                    "contacts": getattr(f, "contacts", False),
                    "non_contacts": getattr(f, "non_contacts", False),
                    "groups": getattr(f, "groups", False),
                    "broadcasts": getattr(f, "broadcasts", False),
                    "bots": getattr(f, "bots", False),
                    "exclude_muted": getattr(f, "exclude_muted", False),
                    "exclude_read": getattr(f, "exclude_read", False),
                    "exclude_archived": getattr(f, "exclude_archived", False),
                    "included_peers": included,
                    "excluded_peers": excluded,
                })

        return folders
    except Exception as e:
        logger.error(f"Error fetching folders for {account_name}: {e}")
        return []


@router.post("/folders/{account_name}")
async def create_folder(
    account_name: str,
    payload: Dict[str, Any],
    user_id: int = Depends(get_current_user_id),
):
    """Create or update a chat folder on Telegram."""
    client = await _resolve_client(user_id, account_name)
    if not client:
        raise HTTPException(status_code=404, detail="No active client")

    try:
        from telethon.tl.functions.messages import UpdateDialogFilterRequest
        from telethon.tl.types import DialogFilter, TextWithEntities
        import random

        folder_id = int(payload.get("id") or random.randint(2, 255))
        title_str = str(payload.get("title", "New Folder"))
        emoticon = payload.get("emoji") or None

        # Telethon 1.41+ requires TextWithEntities for title
        title_obj = TextWithEntities(text=title_str, entities=[])

        dialog_filter = DialogFilter(
            id=folder_id,
            title=title_obj,
            emoticon=emoticon,
            contacts=bool(payload.get("contacts", False)) or None,
            non_contacts=bool(payload.get("non_contacts", False)) or None,
            groups=bool(payload.get("groups", False)) or None,
            broadcasts=bool(payload.get("broadcasts", False)) or None,
            bots=bool(payload.get("bots", False)) or None,
            exclude_muted=bool(payload.get("exclude_muted", False)) or None,
            exclude_read=bool(payload.get("exclude_read", False)) or None,
            exclude_archived=bool(payload.get("exclude_archived", False)) or None,
            include_peers=[],
            exclude_peers=[],
            pinned_peers=[],
        )

        await client(UpdateDialogFilterRequest(id=folder_id, filter=dialog_filter))
        return {"status": "success", "id": folder_id, "title": title_str}
    except Exception as e:
        logger.error(f"Error creating folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/folders/{account_name}/presets")
async def create_preset_folders(
    account_name: str,
    user_id: int = Depends(get_current_user_id),
):
    """
    Create ALL preset folders at once.
    Each preset is created as a separate Telegram dialog filter.
    """
    client = await _resolve_client(user_id, account_name)
    if not client:
        raise HTTPException(status_code=404, detail="No active client")

    try:
        from telethon.tl.functions.messages import UpdateDialogFilterRequest
        from telethon.tl.types import DialogFilter, TextWithEntities

        presets = [
            {"id": 2, "title": "Personal",  "contacts": True,  "non_contacts": False, "groups": False, "broadcasts": False, "bots": False, "exclude_muted": False, "exclude_read": False, "exclude_archived": False},
            {"id": 3, "title": "Groups",    "contacts": False, "non_contacts": False, "groups": True,  "broadcasts": False, "bots": False, "exclude_muted": False, "exclude_read": False, "exclude_archived": False},
            {"id": 4, "title": "Channels",  "contacts": False, "non_contacts": False, "groups": False, "broadcasts": True,  "bots": False, "exclude_muted": False, "exclude_read": False, "exclude_archived": False},
            {"id": 5, "title": "Bots",      "contacts": False, "non_contacts": False, "groups": False, "broadcasts": False, "bots": True,  "exclude_muted": False, "exclude_read": False, "exclude_archived": False},
            {"id": 6, "title": "Unread",    "contacts": True,  "non_contacts": True,  "groups": True,  "broadcasts": True,  "bots": True,  "exclude_muted": False, "exclude_read": True,  "exclude_archived": True},
        ]

        created = []
        failed = []
        for p in presets:
            try:
                title_obj = TextWithEntities(text=p["title"], entities=[])
                df = DialogFilter(
                    id=p["id"],
                    title=title_obj,
                    emoticon=None,
                    contacts=p["contacts"] or None,
                    non_contacts=p["non_contacts"] or None,
                    groups=p["groups"] or None,
                    broadcasts=p["broadcasts"] or None,
                    bots=p["bots"] or None,
                    exclude_muted=p["exclude_muted"] or None,
                    exclude_read=p["exclude_read"] or None,
                    exclude_archived=p["exclude_archived"] or None,
                    include_peers=[],
                    exclude_peers=[],
                    pinned_peers=[],
                )
                await client(UpdateDialogFilterRequest(id=p["id"], filter=df))
                created.append(p["title"])
            except Exception as e:
                logger.warning(f"Failed to create preset '{p['title']}': {e}")
                failed.append({"title": p["title"], "error": str(e)})

        # Admin folder — chats where user is admin
        try:
            admin_peers = []
            from telethon.utils import get_input_peer
            async for dialog in client.iter_dialogs(limit=300):
                entity = dialog.entity
                if getattr(entity, "creator", False) or getattr(entity, "admin_rights", None):
                    try:
                        admin_peers.append(get_input_peer(entity))
                    except Exception:
                        pass

            if admin_peers:
                title_obj = TextWithEntities(text="Admin", entities=[])
                admin_df = DialogFilter(
                    id=7,
                    title=title_obj,
                    emoticon=None,
                    contacts=None,
                    non_contacts=None,
                    groups=None,
                    broadcasts=None,
                    bots=None,
                    exclude_muted=None,
                    exclude_read=None,
                    exclude_archived=None,
                    include_peers=admin_peers[:100],
                    exclude_peers=[],
                    pinned_peers=[],
                )
                await client(UpdateDialogFilterRequest(id=7, filter=admin_df))
                created.append("Admin")
        except Exception as e:
            logger.warning(f"Failed to create Admin folder: {e}")
            failed.append({"title": "Admin", "error": str(e)})

        return {"status": "success", "created": created, "failed": failed}
    except Exception as e:
        logger.error(f"Error creating preset folders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/folders/{account_name}/{folder_id}")
async def delete_folder(
    account_name: str,
    folder_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Delete a chat folder."""
    client = await _resolve_client(user_id, account_name)
    if not client:
        raise HTTPException(status_code=404, detail="No active client")

    try:
        from telethon.tl.functions.messages import UpdateDialogFilterRequest
        await client(UpdateDialogFilterRequest(id=folder_id))
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error deleting folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))
