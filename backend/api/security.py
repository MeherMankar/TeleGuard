"""
Security / Protection Manager API
==================================
Single source of truth: ALL reads and writes go through ProtectionStorage
(protection_settings collection) — the same collection the bot uses.

This ensures webapp toggles affect the running bot immediately and bot
changes are visible in the webapp.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.jwt import get_current_user_id
from teleguard.services.protection_storage import ProtectionStorage

router = APIRouter(prefix="/security", tags=["Security"])
logger = logging.getLogger(__name__)


def _get_bot_manager():
    try:
        from teleguard.core.bot_manager import bot_manager
        return bot_manager
    except Exception:
        return None


# ── Session Destroyer ─────────────────────────────────────────────────────────

class ToggleSessionDestroyerRequest(BaseModel):
    enabled: bool


@router.get("/settings")
async def get_settings(user_id: int = Depends(get_current_user_id)):
    """Get all protection settings + stats."""
    try:
        settings = await ProtectionStorage.get_settings(user_id)
        settings.pop("_id", None)

        # Auto-expire allow_next if the 5-min window has passed (survives process restarts)
        allow_next = settings.get("allow_next", False)
        if allow_next:
            allow_next_until = settings.get("allow_next_until")
            if allow_next_until:
                # Handle both datetime and string formats
                if isinstance(allow_next_until, str):
                    try:
                        allow_next_until = datetime.fromisoformat(allow_next_until)
                    except Exception:
                        allow_next_until = None
                if allow_next_until and allow_next_until.tzinfo is None:
                    allow_next_until = allow_next_until.replace(tzinfo=timezone.utc)
                if allow_next_until and datetime.now(timezone.utc) > allow_next_until:
                    # Window expired — clear it
                    await ProtectionStorage.update_settings(user_id, {
                        "allow_next": False,
                        "allow_next_until": None,
                    })
                    allow_next = False

        # Count destroyed sessions from stats sub-document
        stats = settings.get("stats", {})
        destroyed_count = stats.get("sessions_destroyed", 0)

        return {
            "settings": {
                "session_destroyer_enabled": settings.get("session_destroyer_enabled", False),
                "otp_destroyer_enabled": settings.get("otp_destroyer_enabled", False),
                "allow_next": allow_next,
                "last_check": settings.get("last_check"),
                "pause_until": settings.get("pause_until"),
                "trusted_hashes_count": len(settings.get("trusted_hashes", [])),
            },
            "stats": {
                "destroyed_count": destroyed_count,
                "otp_destroyed": stats.get("otp_destroyed", 0),
                "last_threat": stats.get("last_threat"),
            },
            # Legacy field for frontend compatibility
            "enabled": settings.get("session_destroyer_enabled", False),
        }
    except Exception as e:
        logger.error(f"Error fetching security settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/settings")
async def update_session_destroyer(
    payload: ToggleSessionDestroyerRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Toggle Session Destroyer — syncs existing sessions as trusted on enable."""
    try:
        bot_manager = _get_bot_manager()

        if payload.enabled:
            # First sync all current sessions as trusted so we don't destroy them
            if bot_manager and hasattr(bot_manager, "protection_manager") and bot_manager.protection_manager:
                await bot_manager.protection_manager.toggle_session_destroyer(user_id, True)
            else:
                # Bot not running yet — just save the setting
                await ProtectionStorage.update_settings(user_id, {
                    "session_destroyer_enabled": True
                })
        else:
            if bot_manager and hasattr(bot_manager, "protection_manager") and bot_manager.protection_manager:
                await bot_manager.protection_manager.toggle_session_destroyer(user_id, False)
            else:
                await ProtectionStorage.update_settings(user_id, {
                    "session_destroyer_enabled": False
                })

        return {"status": "success", "enabled": payload.enabled}
    except Exception as e:
        logger.error(f"Error toggling session destroyer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/session-destroyer/allow-next")
async def allow_next_login(user_id: int = Depends(get_current_user_id)):
    """
    Allow the next new login to be trusted automatically.
    Use this when you're about to log in on a new device and don't want
    Session Destroyer to kill it.
    """
    try:
        import asyncio
        from datetime import datetime, timezone, timedelta

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        await ProtectionStorage.update_settings(user_id, {
            "allow_next": True,
            "allow_next_until": expires_at,
        })

        # Best-effort in-memory auto-clear (survives the normal case)
        async def _clear():
            await asyncio.sleep(300)
            await ProtectionStorage.update_settings(user_id, {
                "allow_next": False,
                "allow_next_until": None,
            })
        asyncio.create_task(_clear())
        return {"status": "success", "message": "Next login will be trusted (5 min window)"}
    except Exception as e:
        logger.error(f"Error setting allow_next: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Security logs ─────────────────────────────────────────────────────────────

@router.get("/logs", response_model=List[Dict[str, Any]])
async def get_logs(limit: int = 15, user_id: int = Depends(get_current_user_id)):
    """Get recent session destruction logs."""
    try:
        from teleguard.sync.session_destroyer_db import SessionDestroyerDB
        logs = await SessionDestroyerDB.get_logs(user_id, limit)
        for log in logs:
            log.pop("_id", None)
            if log.get("timestamp"):
                log["timestamp"] = log["timestamp"].isoformat()
        return logs
    except Exception as e:
        logger.error(f"Error fetching security logs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Trusted sessions ──────────────────────────────────────────────────────────

class TrustedHashRequest(BaseModel):
    session_hash: int


@router.get("/trusted", response_model=List[int])
async def get_trusted_sessions(user_id: int = Depends(get_current_user_id)):
    """Get all trusted session hashes."""
    try:
        settings = await ProtectionStorage.get_settings(user_id)
        return settings.get("trusted_hashes", [])
    except Exception as e:
        logger.error(f"Error fetching trusted sessions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/trusted/add")
async def add_trusted_session(
    payload: TrustedHashRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Manually mark a session hash as trusted."""
    try:
        await ProtectionStorage.add_trusted_hash(user_id, payload.session_hash)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error adding trusted session: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/trusted/remove")
async def remove_trusted_session(
    payload: TrustedHashRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Remove a session hash from trusted list."""
    try:
        settings = await ProtectionStorage.get_settings(user_id)
        trusted = list(set(settings.get("trusted_hashes", [])))
        if payload.session_hash in trusted:
            trusted.remove(payload.session_hash)
            await ProtectionStorage.update_settings(user_id, {"trusted_hashes": trusted})
            return {"status": "success"}
        return {"status": "not_found"}
    except Exception as e:
        logger.error(f"Error removing trusted session: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/trusted/sync")
async def sync_trusted_sessions(user_id: int = Depends(get_current_user_id)):
    """
    Sync all current Telegram sessions as trusted.
    Useful after enabling Session Destroyer if you have existing sessions
    you want to keep.
    """
    try:
        bot_manager = _get_bot_manager()
        if not bot_manager:
            raise HTTPException(status_code=503, detail="Bot not running")

        user_clients = bot_manager.user_clients.get(user_id, {})
        client = next(
            (c for c in user_clients.values() if c and c.is_connected()), None
        )
        if not client:
            raise HTTPException(status_code=404, detail="No connected client")

        if hasattr(bot_manager, "protection_manager") and bot_manager.protection_manager:
            count = await bot_manager.protection_manager.session_destroyer.sync_trusted_sessions(
                user_id, client
            )
            return {"status": "success", "trusted_count": count}
        raise HTTPException(status_code=503, detail="Protection manager not initialized")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing trusted sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── OTP Destroyer per-account controls ───────────────────────────────────────

class OTPDestroyerRequest(BaseModel):
    account_id: str
    enabled: bool


class TempPassthroughRequest(BaseModel):
    account_id: str


class OTPForwardRequest(BaseModel):
    account_id: str
    enabled: bool


@router.post("/otp-destroyer/toggle")
async def toggle_otp_destroyer(
    payload: OTPDestroyerRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Toggle OTP Destroyer for a specific account — calls bot immediately."""
    try:
        bot_manager = _get_bot_manager()
        if not bot_manager or not getattr(bot_manager, "protection_manager", None):
            raise HTTPException(status_code=503, detail="Protection manager not initialized")

        success, message = await bot_manager.protection_manager.toggle_destroyer(
            user_id, payload.account_id, payload.enabled
        )
        if success:
            try:
                from backend.notifier import notify
                await notify(user_id, {
                    "type": "otp_destroyer_toggled",
                    "account_id": payload.account_id,
                    "enabled": payload.enabled,
                })
            except Exception:
                pass
            return {"status": "success", "message": message, "enabled": payload.enabled}
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling OTP destroyer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/otp-forward/toggle")
async def toggle_otp_forward(
    payload: OTPForwardRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Toggle OTP Forward for an account.
    When enabled: OTPs are forwarded to the bot chat instead of destroyed.
    Cannot be enabled when OTP Destroyer is active.
    """
    try:
        bot_manager = _get_bot_manager()
        if not bot_manager or not getattr(bot_manager, "protection_manager", None):
            raise HTTPException(status_code=503, detail="Protection manager not initialized")

        success, message = await bot_manager.protection_manager.toggle_forward(
            user_id, payload.account_id, payload.enabled
        )
        if success:
            try:
                from backend.notifier import notify
                await notify(user_id, {
                    "type": "otp_forward_toggled",
                    "account_id": payload.account_id,
                    "enabled": payload.enabled,
                })
            except Exception:
                pass
            return {"status": "success", "message": message, "enabled": payload.enabled}
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling OTP forward: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/otp-destroyer/temp-passthrough")
async def enable_temp_passthrough(
    payload: TempPassthroughRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Allow OTPs to pass through for 5 minutes while OTP Destroyer stays on.
    Use when you need to log in on a new device RIGHT NOW.
    """
    try:
        bot_manager = _get_bot_manager()
        if not bot_manager or not getattr(bot_manager, "protection_manager", None):
            raise HTTPException(status_code=503, detail="Protection manager not initialized")

        success, message = await bot_manager.protection_manager.enable_temp_passthrough(
            user_id, payload.account_id
        )
        if success:
            try:
                from backend.notifier import notify
                await notify(user_id, {
                    "type": "otp_temp_passthrough",
                    "account_id": payload.account_id,
                    "duration_seconds": 300,
                })
            except Exception:
                pass
            return {"status": "success", "message": message}
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling temp passthrough: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/otp-destroyer/disable-temp")
async def disable_destroyer_temp(
    payload: TempPassthroughRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Pause OTP Destroyer for 5 minutes.
    OTPs will be forwarded during this window.
    """
    try:
        bot_manager = _get_bot_manager()
        if not bot_manager or not getattr(bot_manager, "protection_manager", None):
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
