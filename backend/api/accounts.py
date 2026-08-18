"""
Accounts API — full bot↔webapp sync.

Account storage contract (IMPORTANT):
- Accounts stored in MongoDB use PLAIN fields: phone, name, session_string, is_active
  This is the same format the bot uses (mongodb.create_account) and what
  bot_manager._load_existing_sessions() reads on restart.
- DataEncryption is only used to READ accounts that were added by the bot via
  its own encrypted format (legacy accounts). New accounts from webapp are plain.
- user_id in JWT == telegram_id of the dashboard owner == user_id stored on accounts
"""

import logging
import time
from typing import List, Dict, Any, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.jwt import get_current_user_id
from backend.auth.telegram_auth_manager import telegram_auth_manager
from backend.websocket.manager import manager as ws_manager
from teleguard.core.mongo_database import mongodb
from teleguard.utils.crypto_utils import DataEncryption
from teleguard.core.client_manager import get_client_manager

router = APIRouter(prefix="/accounts", tags=["Accounts"])
logger = logging.getLogger(__name__)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_bot_manager():
    """Safely get the global bot_manager singleton."""
    try:
        from teleguard.core.bot_manager import bot_manager
        return bot_manager
    except Exception:
        return None


async def _save_and_start_account(user_id: int, phone: str, session_string: str, telegram_user, session_id: str = None) -> dict:
    """
    Save account using EXACTLY the same format as the bot's /add command
    (mongodb.create_account with plain fields, no encryption), then register
    the client with bot_manager so it survives restarts.
    """
    # Build display name the same way the bot does
    first_name = str(getattr(telegram_user, "first_name", "") or "").strip()
    last_name = str(getattr(telegram_user, "last_name", "") or "").strip()
    display_name = f"{first_name} {last_name}".strip()
    username = getattr(telegram_user, "username", None)
    tg_id = getattr(telegram_user, "id", None)

    # Ensure we always have a meaningful name — never store "." or empty string
    if not display_name or display_name in (".", " ", ""):
        if username:
            display_name = f"@{username}"
        elif phone:
            display_name = phone
        else:
            display_name = f"User {tg_id or 'Unknown'}"

    # Save using plain fields — same as mongodb.create_account()
    # This is what bot_manager._load_existing_sessions() reads on restart
    account_data = {
        "user_id": user_id,
        "phone": phone,
        "name": display_name,
        "display_name": display_name,
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "session_string": session_string,   # plain field — bot reads this directly
        "is_active": True,
        "otp_destroyer_enabled": False,
        "added_via": "webapp",
        "fast_import": False,
    }
    if tg_id:
        account_data["telegram_id"] = tg_id

    # Upsert — encrypt session_string before writing
    await mongodb.db.accounts.update_one(
        {"user_id": user_id, "phone": phone},
        {"$set": DataEncryption.encrypt_account_data(account_data)},
        upsert=True,
    )
    logger.info(f"Saved webapp account: {display_name} ({phone}) for user {user_id}")

    # Register with bot_manager using add_user_account() — this sets up
    # OTP handler, auto-reply handler, DM handler, activity simulator, etc.
    # It also means the account will be loaded on next restart.
    bot_manager = _get_bot_manager()
    if bot_manager:
        # Try to reuse existing auth client to avoid a second login notification
        existing_client = None
        if session_id:
            existing_client = telegram_auth_manager.get_connected_client(session_id)

        if existing_client and existing_client.is_connected():
            try:
                # Register the already-connected client directly
                if user_id not in bot_manager.user_clients:
                    bot_manager.user_clients[user_id] = {}
                bot_manager.user_clients[user_id][display_name] = existing_client

                # Set up all handlers the same way add_user_account() does
                if hasattr(bot_manager, "protection_manager") and bot_manager.protection_manager:
                    try:
                        bot_manager.protection_manager.register_handler_for_client(
                            user_id, display_name, existing_client
                        )
                    except Exception as e:
                        logger.warning(f"Protection handler setup: {e}")

                    # If Session Destroyer is already active, trust this account's
                    # pre-existing sessions so the watcher doesn't destroy them.
                    try:
                        await bot_manager.protection_manager.session_destroyer.sync_trusted_for_new_client(
                            user_id, existing_client
                        )
                    except Exception as sd_err:
                        logger.warning(f"Session Destroyer pre-trust sync failed for {display_name}: {sd_err}")

                if hasattr(bot_manager, "auto_reply_handler") and bot_manager.auto_reply_handler:
                    try:
                        await bot_manager.auto_reply_handler.setup_new_client_handler(
                            user_id, display_name, existing_client
                        )
                    except Exception as e:
                        logger.warning(f"Auto-reply handler setup: {e}")

                if hasattr(bot_manager, "dm_reply_handler") and bot_manager.dm_reply_handler:
                    try:
                        await bot_manager.dm_reply_handler.setup_new_client_handler(
                            user_id, display_name, existing_client
                        )
                    except Exception as e:
                        logger.warning(f"DM reply handler setup: {e}")

                logger.info(f"Registered existing client for {display_name} — no new session")
            except Exception as e:
                logger.warning(f"Direct client registration failed, falling back: {e}")
                try:
                    await bot_manager.add_user_account(user_id, display_name, session_string)
                except Exception as e2:
                    logger.warning(f"add_user_account also failed: {e2}")
        else:
            # No existing client (QR edge case, or client was disconnected)
            # Use add_user_account which sets up all handlers properly
            try:
                await bot_manager.add_user_account(user_id, display_name, session_string)
                logger.info(f"Started new client for {display_name} via add_user_account")
            except Exception as e:
                logger.warning(f"Could not start client immediately (will load on restart): {e}")

    # Push real-time event to webapp
    await ws_manager.send_personal_message(
        {"type": "account_added", "phone": phone, "name": display_name},
        user_id,
    )

    return {"status": "success", "message": "Account added successfully", "name": display_name}


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("/list", response_model=List[Dict[str, Any]])
async def list_accounts(user_id: int = Depends(get_current_user_id)):
    """
    List all accounts for this user.
    Works for accounts added via bot AND via webapp — both use the same MongoDB collection.
    """
    try:
        cursor = mongodb.db.accounts.find({"user_id": user_id})
        docs = await cursor.to_list(length=200)

        result = []
        for doc in docs:
            try:
                decrypted = DataEncryption.decrypt_account_data(doc)
                decrypted["id"] = str(doc["_id"])
                decrypted.pop("_id", None)
                # Remove sensitive fields before sending to frontend
                decrypted.pop("session_string", None)
                decrypted.pop("api_hash", None)
                decrypted.pop("twofa_password", None)
                # Normalise user_id type
                if "user_id" in decrypted:
                    decrypted["user_id"] = int(decrypted["user_id"])
                # Ensure boolean fields are present for the frontend
                decrypted.setdefault("otp_destroyer_enabled", False)
                decrypted.setdefault("otp_forward_enabled", False)
                decrypted.setdefault("is_active", True)
                # Ensure name always has a usable value (falls back to phone)
                if not decrypted.get("name"):
                    decrypted["name"] = decrypted.get("phone", str(doc["_id"]))
                result.append(decrypted)
            except Exception as e:
                logger.error(f"Failed to decrypt account {doc.get('_id')}: {e}")
        return result
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status")
async def get_accounts_status(user_id: int = Depends(get_current_user_id)):
    """Connection status for each account — checks live bot_manager clients."""
    bot_manager = _get_bot_manager()
    client_manager = get_client_manager()
    status_map = {}

    try:
        cursor = mongodb.db.accounts.find({"user_id": user_id})
        docs = await cursor.to_list(length=200)

        for doc in docs:
            try:
                decrypted = DataEncryption.decrypt_account_data(doc)
                name = decrypted.get("name") or decrypted.get("phone")
                if not name:
                    continue

                is_connected = False

                # Check bot_manager user_clients first (most reliable)
                if bot_manager:
                    user_clients = bot_manager.user_clients.get(user_id, {})
                    client = user_clients.get(name)
                    if client:
                        try:
                            is_connected = client.is_connected() and await client.is_user_authorized()
                        except Exception:
                            is_connected = client.is_connected()

                # Fallback: check client_manager
                if not is_connected and client_manager:
                    client = client_manager.clients.get(f"{user_id}_{name}")
                    if client:
                        is_connected = client.is_connected()

                status_map[name] = {
                    "connected": is_connected,
                    "phone": decrypted.get("phone"),
                    "name": name,
                    "active": decrypted.get("is_active", True),
                }
            except Exception as e:
                logger.error(f"Error checking status for account: {e}")

        return status_map
    except Exception as e:
        logger.error(f"Error getting accounts status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/toggle-reply")
async def toggle_reply(payload: Dict[str, Any], user_id: int = Depends(get_current_user_id)):
    """Toggle auto-reply for an account."""
    account_name = payload.get("name")
    if not account_name:
        raise HTTPException(status_code=400, detail="Account name required")

    try:
        # Find by encrypted name or plain name
        doc = await mongodb.db.accounts.find_one({
            "user_id": user_id,
            "name_enc": DataEncryption.encrypt_field(account_name),
        })
        if not doc:
            doc = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
        if not doc:
            raise HTTPException(status_code=404, detail="Account not found")

        decrypted = DataEncryption.decrypt_account_data(doc)
        current = decrypted.get("auto_reply_enabled", False)
        new_status = not current

        if "name_enc" in doc:
            await mongodb.db.accounts.update_one(
                {"_id": doc["_id"]},
                {"$set": {"auto_reply_enabled_enc": DataEncryption.encrypt_field(new_status)}},
            )
        else:
            await mongodb.db.accounts.update_one(
                {"_id": doc["_id"]},
                {"$set": {"auto_reply_enabled": new_status}},
            )

        # Notify bot's auto_reply_handler to reload
        bot_manager = _get_bot_manager()
        if bot_manager and hasattr(bot_manager, "auto_reply_handler"):
            try:
                await bot_manager.auto_reply_handler.load_user_keywords(user_id)
            except Exception:
                pass

        return {"status": "success", "auto_reply_enabled": new_status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling auto-reply: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── Telegram Native Auth (phone → OTP → 2FA → account saved + bot started) ─

class SendCodeRequest(BaseModel):
    phone: str


class VerifyCodeRequest(BaseModel):
    session_id: str
    code: str


class VerifyPasswordRequest(BaseModel):
    session_id: str
    password: str


@router.post("/send-code")
async def send_code(req: SendCodeRequest, user_id: int = Depends(get_current_user_id)):
    """Step 1: Send OTP to phone number."""
    try:
        session_id, phone_code_hash = await telegram_auth_manager.start_phone_login(req.phone)
        return {"session_id": session_id, "phone_code_hash": phone_code_hash}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error sending code: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-code")
async def verify_code(req: VerifyCodeRequest, user_id: int = Depends(get_current_user_id)):
    """Step 2: Verify OTP. Returns success or requires_2fa."""
    try:
        res = await telegram_auth_manager.verify_code(req.session_id, req.code)
        if res.get("status") == "success":
            phone = telegram_auth_manager.pending_logins.get(req.session_id, {}).get("phone", "")
            await _save_and_start_account(user_id, phone, res["session"], res["user"], session_id=req.session_id)
            await telegram_auth_manager.finish_login(req.session_id, keep_client=True)
            return {"status": "success"}
        elif res.get("status") == "requires_2fa":
            return {"status": "requires_2fa"}
        raise HTTPException(status_code=400, detail="Unexpected auth state")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying code: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify-password")
async def verify_password(req: VerifyPasswordRequest, user_id: int = Depends(get_current_user_id)):
    """Step 3 (optional): Verify 2FA password."""
    try:
        res = await telegram_auth_manager.verify_password(req.session_id, req.password)
        if res.get("status") == "success":
            phone = telegram_auth_manager.pending_logins.get(req.session_id, {}).get("phone", "")
            await _save_and_start_account(user_id, phone, res["session"], res["user"], session_id=req.session_id)
            await telegram_auth_manager.finish_login(req.session_id, keep_client=True)
            return {"status": "success"}
        raise HTTPException(status_code=400, detail="Unexpected auth state")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/qr-login")
async def qr_login(user_id: int = Depends(get_current_user_id)):
    """Start QR login — returns session_id and QR URL."""
    try:
        return await telegram_auth_manager.start_qr_login()
    except Exception as e:
        logger.error(f"Error starting QR login: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/qr-status/{session_id}")
async def qr_status(session_id: str, user_id: int = Depends(get_current_user_id)):
    """Poll QR login status. Returns success, requires_2fa, failed, or pending."""
    try:
        res = await telegram_auth_manager.get_qr_status(session_id)
        if res.get("status") == "success":
            tg_user = res.get("user")
            phone = getattr(tg_user, "phone", "") or ""
            await _save_and_start_account(user_id, phone, res["session"], tg_user, session_id=session_id)
            await telegram_auth_manager.finish_login(session_id, keep_client=True)
            return {"status": "success"}
        return res
    except Exception as e:
        logger.error(f"Error getting QR status: {e}")
        raise HTTPException(status_code=400, detail=str(e))


class QRPasswordRequest(BaseModel):
    session_id: str
    password: str


@router.post("/qr-password")
async def qr_password(req: QRPasswordRequest, user_id: int = Depends(get_current_user_id)):
    """Submit 2FA password after QR scan when 2FA is enabled."""
    try:
        res = await telegram_auth_manager.verify_qr_password(req.session_id, req.password)
        if res.get("status") == "success":
            tg_user = res.get("user")
            phone = getattr(tg_user, "phone", "") or ""
            await _save_and_start_account(user_id, phone, res["session"], tg_user, session_id=req.session_id)
            await telegram_auth_manager.finish_login(req.session_id, keep_client=True)
            return {"status": "success"}
        raise HTTPException(status_code=400, detail="Unexpected state")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error verifying QR 2FA password: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/remove/{account_id}")
async def remove_account(account_id: str, user_id: int = Depends(get_current_user_id)):
    """Remove an account from bot and database."""
    try:
        doc = await mongodb.db.accounts.find_one({
            "_id": ObjectId(account_id),
            "user_id": user_id,
        })
        if not doc:
            raise HTTPException(status_code=404, detail="Account not found")

        decrypted = DataEncryption.decrypt_account_data(doc)
        name = decrypted.get("name") or decrypted.get("phone")

        # Disconnect from bot_manager
        bot_manager = _get_bot_manager()
        if bot_manager and name:
            user_clients = bot_manager.user_clients.get(user_id, {})
            client = user_clients.pop(name, None)
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass

        await mongodb.db.accounts.delete_one({"_id": ObjectId(account_id), "user_id": user_id})

        await ws_manager.send_personal_message(
            {"type": "account_removed", "account_id": account_id, "name": name},
            user_id,
        )
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing account: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── Profile info endpoint ────────────────────────────────────────────────────

@router.get("/profile/{account_name}")
async def get_profile(account_name: str, user_id: int = Depends(get_current_user_id)):
    """
    Fetch real profile info for an account directly from Telegram.
    Returns: id, first_name, last_name, username, phone, bio, dc_id, photo_url
    """
    bot_manager = _get_bot_manager()
    if not bot_manager:
        raise HTTPException(status_code=503, detail="Bot manager not initialized")

    # Resolve client
    user_clients = bot_manager.user_clients.get(user_id, {})
    client = user_clients.get(account_name)
    if not client:
        # Try phone / partial match
        clean = account_name.replace("+", "").replace(" ", "")
        for key, c in user_clients.items():
            if clean in str(key).replace("+", "").replace(" ", ""):
                client = c
                break
    if not client:
        if len(user_clients) == 1:
            client = next(iter(user_clients.values()))

    if not client:
        raise HTTPException(status_code=404, detail=f"No active client for '{account_name}'")

    try:
        me = await client.get_me()
        if not me:
            raise HTTPException(status_code=404, detail="Could not fetch profile")

        # Get full user info (includes bio)
        from telethon.tl.functions.users import GetFullUserRequest
        full = await client(GetFullUserRequest(me))
        bio = ""
        try:
            bio = full.full_user.about or ""
        except Exception:
            pass

        # Robust photo check — works for User, UserProfilePhoto, ChatPhoto etc.
        entity_photo = getattr(me, "photo", None)
        has_photo = (
            entity_photo is not None and
            "Empty" not in type(entity_photo).__name__
        )

        return {
            "id": me.id,
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
            "username": me.username or "",
            "phone": me.phone or "",
            "bio": bio,
            "dc_id": getattr(me, "photo", None) and getattr(me.photo, "dc_id", None),
            "premium": getattr(me, "premium", False),
            "verified": getattr(me, "verified", False),
            "has_photo": has_photo,
            "account_name": account_name,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching profile for {account_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class UpdateProfileRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    username: Optional[str] = None


@router.patch("/profile/{account_name}")
async def update_profile(
    account_name: str,
    payload: UpdateProfileRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Update Telegram profile fields: first_name, last_name, bio, username.
    Only supplied (non-None) fields are changed.
    """
    bot_manager = _get_bot_manager()
    if not bot_manager:
        raise HTTPException(status_code=503, detail="Bot not running")

    user_clients = bot_manager.user_clients.get(user_id, {})
    client = user_clients.get(account_name)
    if not client:
        clean = account_name.replace("+", "").replace(" ", "")
        for key, c in user_clients.items():
            if clean in str(key).replace("+", "").replace(" ", ""):
                client = c
                break
    if not client:
        if len(user_clients) == 1:
            client = next(iter(user_clients.values()))
    if not client:
        raise HTTPException(status_code=404, detail=f"No active client for '{account_name}'")

    try:
        from telethon import functions as tl_functions

        # Update name / bio
        if payload.first_name is not None or payload.last_name is not None or payload.bio is not None:
            me = await client.get_me()
            await client(tl_functions.account.UpdateProfileRequest(
                first_name=payload.first_name if payload.first_name is not None else (me.first_name or ""),
                last_name=payload.last_name if payload.last_name is not None else (me.last_name or ""),
                about=payload.bio if payload.bio is not None else "",
            ))

        # Update username
        if payload.username is not None:
            clean_username = payload.username.lstrip("@").strip()
            await client(tl_functions.account.UpdateUsernameRequest(username=clean_username))

        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error updating profile for {account_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh-names")
async def refresh_account_names(user_id: int = Depends(get_current_user_id)):
    """
    Refresh display names for all accounts by fetching real data from Telegram.
    Fixes accounts stored with '.' or blank names.
    """
    bot_manager = _get_bot_manager()
    updated = []
    skipped = []

    try:
        cursor = mongodb.db.accounts.find({"user_id": user_id})
        docs = await cursor.to_list(length=200)

        for doc in docs:
            try:
                # Find the live client for this account
                acc_id = str(doc["_id"])
                phone = doc.get("phone", "")
                current_name = doc.get("name", "")

                # Skip if name is already meaningful
                if current_name and current_name not in (".", "", " ") and len(current_name) > 1:
                    skipped.append(current_name)
                    continue

                # Find client
                client = None
                if bot_manager:
                    for key, c in bot_manager.user_clients.get(user_id, {}).items():
                        if phone and (phone in str(key) or str(key) in phone.replace("+", "")):
                            client = c
                            break
                    if not client and bot_manager.user_clients.get(user_id):
                        # Try all clients
                        for key, c in bot_manager.user_clients.get(user_id, {}).items():
                            if c and c.is_connected():
                                try:
                                    me = await c.get_me()
                                    if str(getattr(me, "phone", "")).endswith(phone.lstrip("+")[-8:]):
                                        client = c
                                        break
                                except Exception:
                                    pass

                if not client:
                    skipped.append(f"{phone} (no client)")
                    continue

                me = await client.get_me()
                fn = str(getattr(me, "first_name", "") or "").strip()
                ln = str(getattr(me, "last_name", "") or "").strip()
                uname = getattr(me, "username", None)
                new_name = f"{fn} {ln}".strip()
                if not new_name or new_name in (".", ""):
                    new_name = f"@{uname}" if uname else phone

                await mongodb.db.accounts.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {
                        "name": new_name,
                        "display_name": new_name,
                        "first_name": fn,
                        "last_name": ln,
                        "username": uname,
                    }}
                )
                updated.append(f"{phone} → {new_name}")
                logger.info(f"Refreshed account name: {phone} → {new_name}")

            except Exception as e:
                logger.warning(f"Failed to refresh name for {doc.get('phone')}: {e}")

        return {"status": "success", "updated": updated, "skipped": skipped}
    except Exception as e:
        logger.error(f"Error refreshing account names: {e}")
        raise HTTPException(status_code=500, detail=str(e))
