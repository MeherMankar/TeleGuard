"""Security API for shared user settings and account-scoped session protection.

Session Destroyer state is stored per Telegram account through ProtectionStorage,
so bot and webapp changes are visible to the same watcher.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from bson import ObjectId
from bson.errors import InvalidId

from backend.auth.jwt import get_current_user_id
from teleguard.core.mongo_database import mongodb
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
    account_id: str
    enabled: bool


class AccountSessionRequest(BaseModel):
    account_id: str


class TrustedHashRequest(AccountSessionRequest):
    session_hash: int


async def _require_owned_account(user_id: int, account_id: str):
    try:
        mongo_account_id = ObjectId(account_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="Invalid account ID")
    account = await mongodb.db.accounts.find_one(
        {"_id": mongo_account_id, "user_id": user_id, "is_active": True}
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


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

        account_settings = await mongodb.db.session_destroyer_account_settings.find(
            {"user_id": user_id}
        ).to_list(length=None)
        for account_setting in account_settings:
            allow_next_until = account_setting.get("allow_next_until")
            if isinstance(allow_next_until, str):
                try:
                    allow_next_until = datetime.fromisoformat(allow_next_until)
                except ValueError:
                    allow_next_until = None
            if allow_next_until and allow_next_until.tzinfo is None:
                allow_next_until = allow_next_until.replace(tzinfo=timezone.utc)
            if (
                account_setting.get("allow_next")
                and allow_next_until
                and datetime.now(timezone.utc) > allow_next_until
            ):
                await ProtectionStorage.update_account_settings(
                    user_id,
                    account_setting["account_id"],
                    {"allow_next": False, "allow_next_until": None},
                )
                account_setting["allow_next"] = False
        return {
            "settings": {
                "session_destroyer_enabled": False,
                "otp_destroyer_enabled": settings.get("otp_destroyer_enabled", False),
                "allow_next": False,
                "last_check": settings.get("last_check"),
                "pause_until": settings.get("pause_until"),
                "trusted_hashes_count": 0,
                "session_destroyer_accounts": [
                    {
                        "account_id": row["account_id"],
                        "enabled": bool(row.get("enabled")),
                        "allow_next": bool(row.get("allow_next")),
                        "trusted_hashes_count": len(row.get("trusted_hashes", [])),
                    }
                    for row in account_settings
                ],
            },
            "stats": {
                "destroyed_count": destroyed_count,
                "otp_destroyed": stats.get("otp_destroyed", 0),
                "last_threat": stats.get("last_threat"),
            },
            # Legacy field for frontend compatibility
            "enabled": False,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching security settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/settings")
async def update_session_destroyer(
    payload: ToggleSessionDestroyerRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Toggle Session Destroyer for one owned account."""
    try:
        await _require_owned_account(user_id, payload.account_id)
        bot_manager = _get_bot_manager()
        protection_manager = getattr(bot_manager, "protection_manager", None)
        if protection_manager:
            await protection_manager.toggle_session_destroyer(
                user_id, payload.enabled, payload.account_id
            )
        else:
            current = await ProtectionStorage.get_account_settings(
                user_id, payload.account_id
            )
            changes = {"enabled": payload.enabled}
            if payload.enabled and not current.get("enabled"):
                changes.update(
                    {
                        "enabled_at": datetime.now(timezone.utc),
                        "allow_next": False,
                        "allow_next_until": None,
                    }
                )
            await ProtectionStorage.update_account_settings(
                user_id, payload.account_id, changes
            )
            if not payload.enabled:
                await mongodb.db.session_destroyer_pending.delete_many(
                    {"user_id": user_id, "account_id": payload.account_id}
                )

        return {
            "status": "success",
            "enabled": payload.enabled,
            "account_id": payload.account_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling session destroyer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/session-destroyer/allow-next")
async def allow_next_login(
    payload: AccountSessionRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Allow the next new login to be trusted automatically.
    Use this when you're about to log in on a new device and don't want
    Session Destroyer to kill it.
    """
    try:
        await _require_owned_account(user_id, payload.account_id)
        from datetime import datetime, timezone, timedelta

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        await ProtectionStorage.update_account_settings(
            user_id,
            payload.account_id,
            {"allow_next": True, "allow_next_until": expires_at},
        )
        return {
            "status": "success",
            "message": "Next login for this account will be kept for 5 minutes",
        }
    except HTTPException:
        raise
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching security logs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Trusted sessions ──────────────────────────────────────────────────────────


@router.get("/trusted")
async def get_trusted_sessions(user_id: int = Depends(get_current_user_id)):
    """Get protected session hashes grouped by account."""
    try:
        rows = await mongodb.db.session_destroyer_account_settings.find(
            {"user_id": user_id}
        ).to_list(length=None)
        return [
            {
                "account_id": row["account_id"],
                "hashes": row.get("trusted_hashes", []),
            }
            for row in rows
        ]
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
        await _require_owned_account(user_id, payload.account_id)
        await ProtectionStorage.add_account_trusted_hash(
            user_id, payload.account_id, payload.session_hash
        )
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding trusted session: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/trusted/remove")
async def remove_trusted_session(
    payload: TrustedHashRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Mark a session hash untrusted so Session Destroyer can act on it."""
    try:
        await _require_owned_account(user_id, payload.account_id)
        await ProtectionStorage.add_account_untrusted_hash(
            user_id, payload.account_id, payload.session_hash
        )
        await mongodb.db.session_destroyer_pending.delete_many(
            {
                "user_id": user_id,
                "account_id": payload.account_id,
                "hash": payload.session_hash,
            }
        )
        settings = await ProtectionStorage.get_account_settings(
            user_id, payload.account_id
        )
        if not settings.get("enabled", False):
            return {"status": "success", "terminated": False}
        bot_manager = _get_bot_manager()
        if (
            bot_manager
            and getattr(bot_manager, "protection_manager", None)
        ):
            await bot_manager.protection_manager.session_destroyer.terminate_session(
                user_id, payload.account_id, payload.session_hash
            )
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing trusted session: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/trusted/sync")
async def sync_trusted_sessions(
    payload: AccountSessionRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Sync all current Telegram sessions as trusted.
    Useful after enabling Session Destroyer if you have existing sessions
    you want to keep.
    """
    try:
        await _require_owned_account(user_id, payload.account_id)
        bot_manager = _get_bot_manager()
        if not bot_manager:
            raise HTTPException(status_code=503, detail="Bot not running")

        user_clients = bot_manager.user_clients.get(user_id, {})
        account = await _require_owned_account(user_id, payload.account_id)
        from teleguard.utils.crypto_utils import DataEncryption
        account_data = DataEncryption.decrypt_account_data(account)
        account_name = (
            account_data.get("name")
            or account_data.get("phone")
            or account_data.get("display_name")
        )
        client = user_clients.get(account_name)
        if not client:
            raise HTTPException(status_code=404, detail="No connected client")

        if hasattr(bot_manager, "protection_manager") and bot_manager.protection_manager:
            count = await bot_manager.protection_manager.session_destroyer.sync_trusted_sessions(
                user_id, client, payload.account_id
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

        if payload.enabled:
            try:
                await bot_manager.ensure_existing_sessions_loaded()
            except Exception:
                logger.exception(
                    "Could not load saved accounts before enabling OTP Destroyer"
                )
                raise HTTPException(
                    status_code=503,
                    detail="Saved account sessions are unavailable; OTP Destroyer was not enabled.",
                )

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
