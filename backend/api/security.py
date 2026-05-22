import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.jwt import get_current_user_id
from teleguard.sync.session_destroyer_db import SessionDestroyerDB

router = APIRouter(prefix="/security", tags=["Security"])
logger = logging.getLogger(__name__)


class ToggleSettingsRequest(BaseModel):
    enabled: bool


class TrustedHashRequest(BaseModel):
    account_id: str
    session_hash: int


@router.get("/settings")
async def get_settings(user_id: int = Depends(get_current_user_id)):
    try:
        settings = await SessionDestroyerDB.get_settings(user_id)
        stats = await SessionDestroyerDB.get_stats(user_id)
        settings.pop("_id", None)
        return {"settings": settings, "stats": stats}
    except Exception as e:
        logger.error(f"Error fetching security settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/settings")
async def update_settings(payload: ToggleSettingsRequest, user_id: int = Depends(get_current_user_id)):
    """Toggle Session Destroyer. Also notifies the running bot instance."""
    try:
        await SessionDestroyerDB.update_settings(user_id, payload.enabled)

        # Notify bot's session destroyer to reload settings in real-time
        try:
            from teleguard.core.bot_manager import bot_manager
            if bot_manager and hasattr(bot_manager, "protection_manager") and bot_manager.protection_manager:
                await bot_manager.protection_manager.toggle_session_destroyer(user_id, payload.enabled)
                logger.info(f"Session destroyer toggled to {payload.enabled} for user {user_id}")
        except Exception as e:
            logger.warning(f"Could not reload session destroyer in bot: {e}")

        return {"status": "success", "enabled": payload.enabled}
    except Exception as e:
        logger.error(f"Error updating security settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/logs", response_model=List[Dict[str, Any]])
async def get_logs(limit: int = 15, user_id: int = Depends(get_current_user_id)):
    try:
        logs = await SessionDestroyerDB.get_logs(user_id, limit)
        for log in logs:
            log.pop("_id", None)
            if log.get("timestamp"):
                log["timestamp"] = log["timestamp"].isoformat()
        return logs
    except Exception as e:
        logger.error(f"Error fetching security logs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/trusted/{account_id}", response_model=List[int])
async def get_trusted_sessions(account_id: str, user_id: int = Depends(get_current_user_id)):
    try:
        hashes = await SessionDestroyerDB.get_trusted_sessions(user_id, account_id)
        return list(hashes)
    except Exception as e:
        logger.error(f"Error fetching trusted sessions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/trusted/add")
async def add_trusted_session(payload: TrustedHashRequest, user_id: int = Depends(get_current_user_id)):
    try:
        await SessionDestroyerDB.add_trusted_hash(user_id, payload.account_id, payload.session_hash)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error adding trusted session: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/trusted/remove")
async def remove_trusted_session(payload: TrustedHashRequest, user_id: int = Depends(get_current_user_id)):
    try:
        current = await SessionDestroyerDB.get_trusted_sessions(user_id, payload.account_id)
        if payload.session_hash in current:
            current.discard(payload.session_hash)
            await SessionDestroyerDB.save_trusted_sessions(user_id, payload.account_id, list(current))
            return {"status": "success"}
        return {"status": "not_found"}
    except Exception as e:
        logger.error(f"Error removing trusted session: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── OTP Destroyer per-account controls ──────────────────────────────────────

class OTPDestroyerRequest(BaseModel):
    account_id: str
    enabled: bool


class TempPassthroughRequest(BaseModel):
    account_id: str


@router.post("/otp-destroyer/toggle")
async def toggle_otp_destroyer(payload: OTPDestroyerRequest, user_id: int = Depends(get_current_user_id)):
    """
    Toggle OTP Destroyer for a specific account.
    Calls protection_manager.toggle_destroyer() on the running bot immediately.
    """
    try:
        from teleguard.core.bot_manager import bot_manager
        if not bot_manager or not hasattr(bot_manager, "protection_manager") or not bot_manager.protection_manager:
            raise HTTPException(status_code=503, detail="Protection manager not initialized")

        success, message = await bot_manager.protection_manager.toggle_destroyer(
            user_id, payload.account_id, payload.enabled
        )
        if success:
            # Push real-time event to webapp
            from backend.notifier import notify
            await notify(user_id, {
                "type": "otp_destroyer_toggled",
                "account_id": payload.account_id,
                "enabled": payload.enabled,
            })
            return {"status": "success", "message": message, "enabled": payload.enabled}
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling OTP destroyer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/otp-destroyer/temp-passthrough")
async def enable_temp_passthrough(payload: TempPassthroughRequest, user_id: int = Depends(get_current_user_id)):
    """
    Enable 5-minute temporary OTP passthrough for an account.
    Useful when you need to receive an OTP while destroyer is active.
    """
    try:
        from teleguard.core.bot_manager import bot_manager
        if not bot_manager or not hasattr(bot_manager, "protection_manager") or not bot_manager.protection_manager:
            raise HTTPException(status_code=503, detail="Protection manager not initialized")

        success, message = await bot_manager.protection_manager.enable_temp_passthrough(
            user_id, payload.account_id
        )
        if success:
            from backend.notifier import notify
            await notify(user_id, {
                "type": "otp_temp_passthrough",
                "account_id": payload.account_id,
                "duration_seconds": 300,
            })
            return {"status": "success", "message": message}
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling temp passthrough: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/otp-destroyer/disable-temp")
async def disable_destroyer_temp(payload: TempPassthroughRequest, user_id: int = Depends(get_current_user_id)):
    """Temporarily disable OTP Destroyer for 5 minutes."""
    try:
        from teleguard.core.bot_manager import bot_manager
        if not bot_manager or not hasattr(bot_manager, "protection_manager") or not bot_manager.protection_manager:
            raise HTTPException(status_code=503, detail="Protection manager not initialized")

        success, message = await bot_manager.protection_manager.disable_destroyer_temp(
            user_id, payload.account_id
        )
        if success:
            return {"status": "success", "message": message}
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling destroyer temp: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
