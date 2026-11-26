import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pymongo.errors import DuplicateKeyError

from teleguard.core.config import config
from teleguard.core.mongo_database import mongodb

logger = logging.getLogger(__name__)

SECRET_KEY = config.security.jwt_secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
TELEGRAM_INIT_DATA_MAX_AGE_SECONDS = 24 * 60 * 60
TELEGRAM_INIT_DATA_FUTURE_SKEW_SECONDS = 30

# auto_error=False so we can also accept token via query param
security_bearer = HTTPBearer(auto_error=False)

BOT_TOKEN = config.telegram.bot_token if hasattr(config, "telegram") else None


def validate_telegram_init_data(init_data: str) -> Optional[Dict[str, Any]]:
    """Validates Telegram WebApp initData."""
    try:
        if not BOT_TOKEN:
            logger.error("BOT_TOKEN not set")
            return None

        params = dict(parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in params:
            return None

        received_hash = params.pop("hash")
        auth_date = int(params["auth_date"])
        current_time = time.time()
        if (
            auth_date <= 0
            or auth_date > current_time + TELEGRAM_INIT_DATA_FUTURE_SKEW_SECONDS
            or current_time - auth_date > TELEGRAM_INIT_DATA_MAX_AGE_SECONDS
        ):
            return None

        data_check_list = sorted([f"{k}={v}" for k, v in params.items()])
        data_check_string = "\n".join(data_check_list)

        secret_key = hmac.new(
            b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256
        ).digest()
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        if hmac.compare_digest(calculated_hash, received_hash):
            user_data = params.get("user")
            if user_data:
                parsed_user = json.loads(user_data)
                return parsed_user if isinstance(parsed_user, dict) else None
        return None
    except Exception as e:
        logger.error(f"Error validating Telegram init data: {e}")
        return None


async def consume_telegram_init_data(init_data: str) -> bool:
    """Atomically mark verified Telegram init data as used until it expires."""
    params = dict(parse_qsl(init_data, keep_blank_values=True))
    signed_hash = params.get("hash")
    try:
        auth_date = int(params["auth_date"])
    except (KeyError, ValueError):
        return False
    if not signed_hash:
        return False
    current_time = time.time()
    if (
        auth_date <= 0
        or auth_date > current_time + TELEGRAM_INIT_DATA_FUTURE_SKEW_SECONDS
        or current_time - auth_date > TELEGRAM_INIT_DATA_MAX_AGE_SECONDS
    ):
        return False

    replay_id = hashlib.sha256(signed_hash.encode("utf-8")).hexdigest()
    expires_at = datetime.fromtimestamp(
        auth_date + TELEGRAM_INIT_DATA_MAX_AGE_SECONDS, timezone.utc
    )
    try:
        await mongodb.db.telegram_init_data_replays.insert_one(
            {"_id": replay_id, "expires_at": expires_at}
        )
    except DuplicateKeyError:
        return False
    return True


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = time.time() + (ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    to_encode.update({"exp": expire, "jti": uuid.uuid4().hex})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def revoke_access_token(token: str) -> bool:
    """Persist a token revocation until its expiration time."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return False

    token_id = payload.get("jti")
    expires_at = payload.get("exp")
    if not token_id or not expires_at:
        return False

    await mongodb.db.revoked_tokens.update_one(
        {"_id": token_id},
        {
            "$setOnInsert": {
                "expires_at": datetime.fromtimestamp(float(expires_at), timezone.utc)
            }
        },
        upsert=True,
    )
    return True


async def get_current_user_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
) -> int:
    """
    Extract user_id from JWT.  Accepts the token from the Authorization header
    or the secure HTTP-only access_token cookie.
    """
    token: Optional[str] = None

    # 1. Authorization header (preferred)
    if credentials and credentials.credentials:
        token = credentials.credentials

    # 2. HTTP-only cookie fallback (used by browser image/media requests)
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(
                status_code=401, detail="Invalid token: user_id missing"
            )
        token_id = payload.get("jti")
        if not token_id:
            raise HTTPException(status_code=401, detail="Invalid token: token ID missing")
        try:
            revoked = await mongodb.db.revoked_tokens.find_one({"_id": token_id})
        except Exception as exc:
            logger.exception("Could not check token revocation")
            raise HTTPException(
                status_code=503, detail="Authentication service unavailable"
            ) from exc
        if revoked:
            raise HTTPException(status_code=401, detail="Access token revoked")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
