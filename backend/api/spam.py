"""
SpamMaster API — exposes legitimate tools via REST.

Legitimate tools (wired here):
  • Contact Scraper  — extract member list from a group/channel
  • Username Checker — find available usernames based on a base word

Abuse tools (message flooding, raids, mass-invite) remain bot-only and
require the in-bot ToS acceptance flow.
"""

import asyncio
import logging
import random
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.jwt import get_current_user_id
from teleguard.core.mongo_database import mongodb

router = APIRouter(prefix="/spam", tags=["SpamMaster"])
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_bot_manager():
    try:
        from teleguard.core.bot_manager import bot_manager
        return bot_manager
    except Exception:
        return None


async def _get_client(user_id: int, account_name: str):
    bm = _get_bot_manager()
    if not bm:
        return None
    return bm.user_clients.get(user_id, {}).get(account_name)


# ── Contact Scraper ───────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    account_name: str
    target: str          # @group, t.me/group, or group ID
    limit: int = 2000


@router.post("/scrape-members")
async def scrape_members(
    payload: ScrapeRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Extract member list from a public group or channel.
    Returns a list of members with id, username, first/last name, and phone (if visible).
    """
    client = await _get_client(user_id, payload.account_name)
    if not client:
        raise HTTPException(status_code=404, detail="Account not connected — start the bot first")

    try:
        entity = await client.get_entity(payload.target)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not resolve target: {e}")

    try:
        members = []
        async for participant in client.iter_participants(entity, limit=min(payload.limit, 5000)):
            if participant.bot:
                continue
            members.append({
                "id": participant.id,
                "username": participant.username,
                "first_name": participant.first_name or "",
                "last_name": participant.last_name or "",
                "phone": participant.phone,
            })
            if len(members) % 200 == 0:
                await asyncio.sleep(1)

        return {
            "target": payload.target,
            "count": len(members),
            "members": members,
        }
    except Exception as e:
        logger.error(f"Scrape error for {payload.target}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Username Checker ──────────────────────────────────────────────────────────

class UsernameCheckRequest(BaseModel):
    account_name: str
    base: str        # e.g. "coolname" → tries coolname1, coolname2 …
    count: int = 50  # how many variants to check


@router.post("/check-usernames")
async def check_usernames(
    payload: UsernameCheckRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Check username availability for a given base word.
    Returns up to `count` available usernames.
    """
    client = await _get_client(user_id, payload.account_name)
    if not client:
        raise HTTPException(status_code=404, detail="Account not connected — start the bot first")

    base = payload.base.strip().lower()
    if not base.isalnum() or len(base) < 2:
        raise HTTPException(status_code=400, detail="Base must be alphanumeric, min 2 chars")

    available: List[str] = []
    checked = 0
    variants = [f"{base}{random.randint(1, 9999)}" for _ in range(min(payload.count * 3, 300))]
    # De-duplicate
    seen = set()
    unique_variants = [v for v in variants if not (v in seen or seen.add(v))]  # type: ignore[func-returns-value]

    try:
        for username in unique_variants:
            if len(available) >= payload.count:
                break
            try:
                await client.get_entity(username)
                # Entity found → username is taken
            except Exception:
                # Not found → available
                available.append(username)
            checked += 1
            if checked % 10 == 0:
                await asyncio.sleep(1)

        return {
            "base": base,
            "checked": checked,
            "available_count": len(available),
            "available": available,
        }
    except Exception as e:
        logger.error(f"Username check error for base={base}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
