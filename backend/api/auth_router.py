import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from backend.auth.jwt import validate_telegram_init_data, create_access_token
from teleguard.core.mongo_database import mongodb

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    initData: str


@router.post("/login")
async def login(payload: LoginRequest):
    """Validate Telegram WebApp initData and return JWT."""
    try:
        user_info = validate_telegram_init_data(payload.initData)
        if not user_info:
            raise HTTPException(status_code=401, detail="Invalid Telegram initialization data")

        telegram_id = user_info.get("id")
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Telegram ID missing")

        # Create user if not exists
        user_doc = await mongodb.db.users.find_one({"telegram_id": telegram_id})
        if not user_doc:
            await mongodb.create_user(
                telegram_id=telegram_id,
                first_name=user_info.get("first_name", ""),
                last_name=user_info.get("last_name", ""),
                username=user_info.get("username", ""),
            )

        token = create_access_token({"user_id": telegram_id})
        return {
            "token": token,
            "user": {
                "id": telegram_id,
                "first_name": user_info.get("first_name"),
                "last_name": user_info.get("last_name"),
                "username": user_info.get("username"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/dev-login")
async def dev_login():
    """Dev-only login — returns JWT for test user. Disabled in production."""
    import os
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise HTTPException(status_code=404, detail="Not found")

    test_user_id = 6121637257
    token = create_access_token({"user_id": test_user_id})
    return {
        "token": token,
        "user": {
            "id": test_user_id,
            "first_name": "Dev",
            "last_name": "User",
            "username": "devuser",
        },
    }
