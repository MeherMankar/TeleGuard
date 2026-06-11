import hmac
import hashlib
import time
import json
import logging
from typing import Dict, Any, Optional
from urllib.parse import parse_qsl
from jose import jwt, JWTError
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from teleguard.core.config import config

logger = logging.getLogger(__name__)

SECRET_KEY = (
    config.security.jwt_secret
    if hasattr(config, "security") and hasattr(config.security, "jwt_secret")
    else "teleguard_super_secret_jwt_key_change_in_production"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week

# auto_error=False so we can also accept token via query param
security_bearer = HTTPBearer(auto_error=False)

BOT_TOKEN = config.telegram.bot_token if hasattr(config, "telegram") else None


def validate_telegram_init_data(init_data: str) -> Optional[Dict[str, Any]]:
    """Validates Telegram WebApp initData."""
    try:
        if not BOT_TOKEN:
            logger.error("BOT_TOKEN not set")
            return None

        params = dict(parse_qsl(init_data))
        if "hash" not in params:
            return None

        received_hash = params.pop("hash")

        # Dev bypass
        if received_hash == "mock_hash":
            user_data = params.get("user")
            if user_data:
                return json.loads(user_data)

        data_check_list = sorted([f"{k}={v}" for k, v in params.items()])
        data_check_string = "\n".join(data_check_list)

        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        if hmac.compare_digest(calculated_hash, received_hash):
            user_data = params.get("user")
            if user_data:
                return json.loads(user_data)
        return None
    except Exception as e:
        logger.error(f"Error validating Telegram init data: {e}")
        return None


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = time.time() + (ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
) -> int:
    """
    Extract user_id from JWT.  Accepts the token from two places:
      1. Authorization: Bearer <token>  — standard API calls
      2. ?token=<jwt>                   — used by <img src> for photo proxying
         (browsers don't send Authorization headers with image requests)
    """
    token: Optional[str] = None

    # 1. Authorization header (preferred)
    if credentials and credentials.credentials:
        token = credentials.credentials

    # 2. Query param fallback
    if not token:
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token: user_id missing")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
