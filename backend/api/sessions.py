import logging
import re
import time
from typing import List, Dict, Any, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.jwt import get_current_user_id
from backend.websocket.manager import manager as ws_manager
from teleguard.core.mongo_database import mongodb
from teleguard.utils.crypto_utils import DataEncryption
from teleguard.core.client_manager import get_client_manager

router = APIRouter(prefix="/sessions", tags=["Sessions"])
logger = logging.getLogger(__name__)


def _get_bot_manager():
    try:
        from teleguard.core.bot_manager import bot_manager
        return bot_manager
    except Exception:
        return None


class RevokeSessionRequest(BaseModel):
    account_id: str
    session_hash: str


class AddSessionRequest(BaseModel):
    phone: str


class ConfirmSessionRequest(BaseModel):
    phone: str
    code: Optional[str] = None
    password: Optional[str] = None


@router.get("/list", response_model=List[Dict[str, Any]])
async def list_sessions(user_id: int = Depends(get_current_user_id)):
    """List all active Telegram sessions across all user accounts."""
    client_manager = get_client_manager()
    all_sessions = []

    try:
        cursor = mongodb.db.accounts.find({"user_id": user_id})
        accounts = await cursor.to_list(length=200)

        for acc in accounts:
            try:
                decrypted = DataEncryption.decrypt_account_data(acc)
                acc_id = str(acc["_id"])
                acc_name = decrypted.get("name") or decrypted.get("phone", "Unknown")

                if client_manager:
                    success, sessions = await client_manager.list_active_sessions(user_id, acc_id)
                    if success:
                        for s in sessions:
                            s["account_id"] = acc_id
                            s["account_name"] = acc_name
                            all_sessions.append(s)
            except Exception as e:
                logger.error(f"Error fetching sessions for {acc.get('_id')}: {e}")

        return all_sessions
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/revoke")
async def revoke_session(payload: RevokeSessionRequest, user_id: int = Depends(get_current_user_id)):
    """Revoke a specific Telegram session."""
    client_manager = get_client_manager()
    if not client_manager:
        raise HTTPException(status_code=503, detail="Client manager not initialized")

    try:
        session_hash = int(payload.session_hash)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session hash")

    try:
        account = await mongodb.db.accounts.find_one({
            "_id": ObjectId(payload.account_id),
            "user_id": user_id,
        })
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        success, message = await client_manager.terminate_session(
            user_id=user_id,
            account_id=payload.account_id,
            session_hash=session_hash,
        )

        if success:
            await ws_manager.send_personal_message({
                "type": "session_revoked",
                "account_id": payload.account_id,
                "session_hash": payload.session_hash,
            }, user_id)
            return {"status": "success", "message": message}
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking session: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/add/request")
async def request_otp(payload: AddSessionRequest, user_id: int = Depends(get_current_user_id)):
    """Start adding account via phone — sends OTP via bot's auth manager."""
    bot_manager = _get_bot_manager()
    if not bot_manager or not bot_manager.auth_manager:
        raise HTTPException(status_code=503, detail="Auth manager not initialized")

    phone = payload.phone.strip()
    if not phone.startswith("+"):
        raise HTTPException(status_code=400, detail="Phone must start with + and country code")
    if not re.match(r"^\+[1-9]\d{1,14}$", phone):
        raise HTTPException(status_code=400, detail="Invalid phone number format")

    try:
        await bot_manager.auth_manager.start_auth(user_id, phone, use_otp_destroyer=False)

        # OTP protection
        try:
            await mongodb.db.otp_protections.update_one(
                {"phone": phone},
                {"$set": {
                    "phone": phone,
                    "wildcard": True,
                    "expires_at": int(time.time()) + 600,
                    "reason": "account_addition",
                    "user_id": user_id,
                }},
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"Failed to set OTP protection: {e}")

        bot_manager.pending_actions[user_id] = {
            "action": "verify_otp",
            "phone": phone,
            "otp_destroyer": False,
        }
        return {"status": "sent", "message": f"OTP sent to {phone}"}
    except Exception as e:
        bot_manager.pending_actions.pop(user_id, None)
        logger.error(f"Error starting auth: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/add/confirm")
async def confirm_otp(payload: ConfirmSessionRequest, user_id: int = Depends(get_current_user_id)):
    """Confirm OTP and optional 2FA to complete account addition via bot."""
    bot_manager = _get_bot_manager()
    if not bot_manager or not bot_manager.auth_manager:
        raise HTTPException(status_code=503, detail="Auth manager not initialized")

    if not bot_manager.auth_manager.has_pending_auth(user_id):
        raise HTTPException(status_code=400, detail="No pending auth session. Start request first.")

    phone = payload.phone.strip()
    code = payload.code
    password = payload.password

    if code:
        code = code.replace("-", "").replace(" ", "").strip().lstrip("/")

    try:
        session_string = await bot_manager.auth_manager.complete_auth(
            user_id=user_id, code=code, password=password
        )

        if session_string == "OTP_DESTROYED":
            return {"status": "destroyed", "message": "OTP destroyed"}

        # Save account encrypted (matching bot format)
        from teleguard.core.mongo_database import mongodb as db
        account_data = {
            "user_id": user_id,
            "phone": phone,
            "name": phone,
            "session_string": session_string,
            "is_active": True,
            "otp_destroyer_enabled": False,
            "added_via": "webapp_sessions",
            "created_at": int(time.time()),
        }
        encrypted = DataEncryption.encrypt_account_data(account_data)
        result = await db.db.accounts.update_one(
            {"user_id": user_id, "phone": phone},
            {"$set": encrypted},
            upsert=True,
        )

        # Start client in bot
        await bot_manager.start_user_client(user_id, phone, session_string)

        # Store 2FA if provided
        if password:
            try:
                from teleguard.core.database_manager import db_manager
                inserted_id = result.upserted_id or (
                    await db.db.accounts.find_one({"user_id": user_id, "phone": phone})
                )["_id"]
                await db_manager.store_2fa_password(user_id, str(inserted_id), password)
            except Exception as e:
                logger.warning(f"Failed to store 2FA: {e}")

        # Cleanup
        try:
            await db.db.otp_protections.delete_one({"phone": phone, "reason": "account_addition"})
        except Exception:
            pass
        bot_manager.pending_actions.pop(user_id, None)

        await ws_manager.send_personal_message(
            {"type": "account_added", "phone": phone},
            user_id,
        )
        return {"status": "success", "message": "Account added successfully"}

    except ValueError as e:
        msg = str(e)
        if "Two-factor" in msg or "password" in msg.lower():
            return {"status": "2fa_required", "message": "2FA password required"}
        raise HTTPException(status_code=400, detail=msg)
    except Exception as e:
        logger.error(f"Error completing auth: {e}")
        bot_manager.pending_actions.pop(user_id, None)
        raise HTTPException(status_code=500, detail=str(e))
