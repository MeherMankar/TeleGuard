"""
Accounts API — full bot↔webapp sync.

Account storage contract:
- Bot stores accounts with encrypted fields (name_enc, phone_enc, session_string_enc, etc.)
  via DataEncryption.encrypt_account_data()
- Webapp reads them via DataEncryption.decrypt_account_data()
- Webapp adds accounts via send-code/verify-code/verify-password/qr-login
- After webapp adds an account it calls bot_manager.start_user_client() so the bot
  immediately picks it up — no restart needed.
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


async def _save_and_start_account(user_id: int, phone: str, session_string: str, telegram_user) -> dict:
    """
    Save account to MongoDB (encrypted, matching bot's format) and immediately
    start the Telethon client in bot_manager so the bot sees it without restart.
    """
    first_name = getattr(telegram_user, "first_name", "") or ""
    last_name = getattr(telegram_user, "last_name", "") or ""
    full_name = f"{first_name} {last_name}".strip() or phone
    username = getattr(telegram_user, "username", None)
    tg_id = getattr(telegram_user, "id", None)

    # Build account document — encrypt sensitive fields to match bot's format
    account_data = {
        "user_id": user_id,
        "phone": phone,
        "name": full_name,
        "username": username,
        "session_string": session_string,
        "is_active": True,
        "otp_destroyer_enabled": False,
        "added_via": "webapp",
        "created_at": int(time.time()),
    }
    if tg_id:
        account_data["telegram_id"] = tg_id

    # Encrypt to match bot's storage format
    encrypted = DataEncryption.encrypt_account_data(account_data)

    # Upsert — if account already exists (added via bot) just update session
    await mongodb.db.accounts.update_one(
        {"user_id": user_id, "phone": phone},
        {"$set": encrypted},
        upsert=True,
    )

    # Immediately start the client in bot_manager so bot sees it now
    bot_manager = _get_bot_manager()
    if bot_manager and hasattr(bot_manager, "_start_user_client"):
        try:
            await bot_manager._start_user_client(user_id, full_name, session_string)
            logger.info(f"Started client for {full_name} via webapp login")
        except Exception as e:
            logger.warning(f"Could not start client immediately: {e}")

    # Notify webapp via WebSocket
    await ws_manager.send_personal_message(
        {"type": "account_added", "phone": phone, "name": full_name},
        user_id,
    )

    return {"status": "success", "message": "Account added successfully", "name": full_name}


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
            await _save_and_start_account(user_id, phone, res["session"], res["user"])
            await telegram_auth_manager.finish_login(req.session_id)
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
            await _save_and_start_account(user_id, phone, res["session"], res["user"])
            await telegram_auth_manager.finish_login(req.session_id)
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
    """Poll QR login status. On success, saves account and starts bot client."""
    try:
        res = await telegram_auth_manager.get_qr_status(session_id)
        if res.get("status") == "success":
            tg_user = res.get("user")
            phone = getattr(tg_user, "phone", "") or ""
            await _save_and_start_account(user_id, phone, res["session"], tg_user)
            await telegram_auth_manager.finish_login(session_id)
            return {"status": "success"}
        return res
    except Exception as e:
        logger.error(f"Error getting QR status: {e}")
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
