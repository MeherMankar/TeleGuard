"""Network and retry utilities for TeleGuard"""
import asyncio
import logging
from typing import Any, Callable
logger = logging.getLogger(__name__)
async def retry_async(fn: Callable, *args, max_attempts: int = 5, base_delay: float = 1, **kwargs) -> Any:
    """Retry async function with exponential backoff for network errors"""
    attempt = 0
    while True:
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            attempt += 1
            logger.warning("Network error on attempt %s/%s: %s", attempt, max_attempts, e)
            if attempt >= max_attempts:
                logger.exception("Max attempts reached")
                raise
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
def format_phone_number(phone) -> str:
    """Format phone number to ensure it has + prefix"""
    if not phone:
        return "Unknown"
    phone_str = str(phone).strip()
    if not phone_str.startswith("+"):
        return f"+{phone_str}"
    return phone_str

def format_display_name(account) -> str:
    """Format account display name with fallbacks"""
    if account is None:
        return "Unknown"
    def _get(k):
        if isinstance(account, dict):
            return account.get(k)
        return getattr(account, k, None)
    # Prefer stored display_name
    display = _get("display_name")
    if display and display != "Unknown":
        return display
    # Build from name components
    first = _get("first_name") or _get("first")
    last = _get("last_name") or _get("last")
    username = _get("username")
    phone = _get("phone")
    uid = _get("_id") or _get("id")
    name = " ".join(p for p in (first, last) if p)
    if name:
        base = name
    elif username:
        base = f"@{username}"
    elif phone:
        base = format_phone_number(phone)
    elif uid:
        base = f"ID:{uid}"
    else:
        base = "Unknown"
    extra = username or format_phone_number(phone) if phone else None
    if extra and str(extra) not in base:
        base = f"{base} ({extra})"
    return base
async def find_account_doc(db, account_id_or_phone):
    """Find account by ID, phone, or other identifier"""
    from bson import ObjectId
    # Try ObjectId
    try:
        oid = ObjectId(account_id_or_phone)
        doc = await db.accounts.find_one({"_id": oid})
        if doc:
            return doc, oid
    except Exception:
        pass
    # Try by phone
    doc = await db.accounts.find_one({"phone": account_id_or_phone})
    if doc:
        return doc, doc.get("_id")
    # Try by display_name
    doc = await db.accounts.find_one({"display_name": account_id_or_phone})
    if doc:
        return doc, doc.get("_id")
    return None, None

async def get_user_info_safe(client, max_retries=3):
    """Safely get user info with retries"""
    for attempt in range(max_retries):
        try:
            user_info = await client.get_me()
            if user_info:
                return user_info
            raise ValueError("No user info returned")
        except Exception as e:
            if attempt == max_retries - 1:
                raise ValueError(f"Failed to get valid user info: {e}")
            await asyncio.sleep(1)
    return None