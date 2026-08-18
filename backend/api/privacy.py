"""
Privacy & Security API

Exposes Telegram privacy settings (who can see last seen, phone, etc.)
and 2FA status for the active account.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.jwt import get_current_user_id

router = APIRouter(prefix="/privacy", tags=["Privacy"])
logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_bot_manager():
    try:
        from teleguard.core.bot_manager import bot_manager
        return bot_manager
    except Exception:
        return None


async def _resolve_client(user_id: int, account_name: str):
    bm = _get_bot_manager()
    if not bm:
        return None
    clients = bm.user_clients.get(user_id, {})
    client = clients.get(account_name)
    if not client:
        clean = account_name.replace("+", "").replace(" ", "")
        for key, c in clients.items():
            if clean in str(key).replace("+", "").replace(" ", ""):
                return c
    return client


# Telethon privacy key type → friendly name mapping
_KEY_MAP = {
    "StatusTimestamp":          "last_seen",
    "PhoneNumber":              "phone",
    "ProfilePhoto":             "profile_photo",
    "About":                    "bio",
    "Forwards":                 "forwards",
    "ChatInvite":               "groups",
    "PhoneCall":                "calls",
    "VoiceMessages":            "voice_messages",
}

_RULE_MAP = {
    "PrivacyValueAllowAll":         "everybody",
    "PrivacyValueAllowContacts":    "contacts",
    "PrivacyValueDisallowAll":      "nobody",
}

_RULE_TO_TL = {
    "everybody": "PrivacyValueAllowAll",
    "contacts":  "PrivacyValueAllowContacts",
    "nobody":    "PrivacyValueDisallowAll",
}


def _rule_label(rules) -> str:
    for rule in rules:
        name = type(rule).__name__
        label = _RULE_MAP.get(name)
        if label:
            return label
    return "unknown"


# ── GET all privacy settings ──────────────────────────────────────────────────

@router.get("/settings/{account_name}")
async def get_privacy_settings(
    account_name: str,
    user_id: int = Depends(get_current_user_id),
):
    """Return all privacy settings + 2FA status for the account."""
    client = await _resolve_client(user_id, account_name)
    if not client:
        raise HTTPException(status_code=404, detail="Account not connected")

    try:
        from telethon.tl.functions.account import GetPrivacyRequest, GetPasswordRequest
        from telethon.tl.types import (
            InputPrivacyKeyStatusTimestamp,
            InputPrivacyKeyPhoneNumber,
            InputPrivacyKeyProfilePhoto,
            InputPrivacyKeyAbout,
            InputPrivacyKeyForwards,
            InputPrivacyKeyChatInvite,
            InputPrivacyKeyPhoneCall,
            InputPrivacyKeyVoiceMessages,
        )

        keys = {
            "last_seen":      InputPrivacyKeyStatusTimestamp(),
            "phone":          InputPrivacyKeyPhoneNumber(),
            "profile_photo":  InputPrivacyKeyProfilePhoto(),
            "bio":            InputPrivacyKeyAbout(),
            "forwards":       InputPrivacyKeyForwards(),
            "groups":         InputPrivacyKeyChatInvite(),
            "calls":          InputPrivacyKeyPhoneCall(),
            "voice_messages": InputPrivacyKeyVoiceMessages(),
        }

        settings = {}
        for name, key in keys.items():
            try:
                result = await client(GetPrivacyRequest(key))
                settings[name] = _rule_label(result.rules)
            except Exception as e:
                logger.debug(f"Could not fetch privacy key {name}: {e}")
                settings[name] = "unknown"

        # 2FA status
        twofa_enabled = False
        try:
            pwd = await client(GetPasswordRequest())
            twofa_enabled = pwd.has_password
        except Exception:
            pass

        return {"settings": settings, "twofa_enabled": twofa_enabled}

    except Exception as e:
        logger.error(f"Error fetching privacy settings for {account_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── PATCH a single privacy setting ───────────────────────────────────────────

class UpdatePrivacyRequest(BaseModel):
    key: str   # last_seen | phone | profile_photo | bio | forwards | groups | calls | voice_messages
    value: str # everybody | contacts | nobody


@router.patch("/settings/{account_name}")
async def update_privacy_setting(
    account_name: str,
    payload: UpdatePrivacyRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Update a single Telegram privacy setting."""
    client = await _resolve_client(user_id, account_name)
    if not client:
        raise HTTPException(status_code=404, detail="Account not connected")

    if payload.value not in ("everybody", "contacts", "nobody"):
        raise HTTPException(status_code=400, detail="value must be everybody | contacts | nobody")

    try:
        from telethon.tl.functions.account import SetPrivacyRequest
        from telethon.tl.types import (
            InputPrivacyKeyStatusTimestamp, InputPrivacyKeyPhoneNumber,
            InputPrivacyKeyProfilePhoto, InputPrivacyKeyAbout,
            InputPrivacyKeyForwards, InputPrivacyKeyChatInvite,
            InputPrivacyKeyPhoneCall, InputPrivacyKeyVoiceMessages,
            PrivacyValueAllowAll, PrivacyValueAllowContacts, PrivacyValueDisallowAll,
        )

        key_map = {
            "last_seen":      InputPrivacyKeyStatusTimestamp(),
            "phone":          InputPrivacyKeyPhoneNumber(),
            "profile_photo":  InputPrivacyKeyProfilePhoto(),
            "bio":            InputPrivacyKeyAbout(),
            "forwards":       InputPrivacyKeyForwards(),
            "groups":         InputPrivacyKeyChatInvite(),
            "calls":          InputPrivacyKeyPhoneCall(),
            "voice_messages": InputPrivacyKeyVoiceMessages(),
        }

        rule_map = {
            "everybody": PrivacyValueAllowAll(),
            "contacts":  PrivacyValueAllowContacts(),
            "nobody":    PrivacyValueDisallowAll(),
        }

        tl_key = key_map.get(payload.key)
        if not tl_key:
            raise HTTPException(status_code=400, detail=f"Unknown privacy key: {payload.key}")

        await client(SetPrivacyRequest(
            key=tl_key,
            rules=[rule_map[payload.value]],
        ))

        return {"status": "success", "key": payload.key, "value": payload.value}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating privacy {payload.key} for {account_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
