import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from backend.auth.jwt import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    consume_telegram_init_data,
    create_access_token,
    revoke_access_token,
    validate_telegram_init_data,
)
from teleguard.core.mongo_database import mongodb

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    initData: str


@router.post("/login")
async def login(payload: LoginRequest, response: Response):
    """Validate Telegram WebApp initData and return JWT."""
    try:
        user_info = validate_telegram_init_data(payload.initData)
        if not user_info:
            raise HTTPException(
                status_code=401, detail="Invalid Telegram initialization data"
            )

        if not await consume_telegram_init_data(payload.initData):
            raise HTTPException(
                status_code=401,
                detail="Telegram initialization data has already been used",
            )

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
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=os.getenv("ENVIRONMENT", "production").lower() == "production",
            samesite="none" if os.getenv("ENVIRONMENT", "production").lower() == "production" else "lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
        )
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
async def dev_login(response: Response):
    """Development-only login — returns a JWT for the test user."""
    if os.getenv("ENVIRONMENT", "production").lower() != "development":
        raise HTTPException(status_code=404, detail="Not found")

    test_user_id = 6121637257
    token = create_access_token({"user_id": test_user_id})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return {
        "token": token,
        "user": {
            "id": test_user_id,
            "first_name": "Dev",
            "last_name": "User",
            "username": "devuser",
        },
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    tokens = {request.cookies.get("access_token")}
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        tokens.add(authorization[7:].strip())

    try:
        for token in tokens - {None, ""}:
            await revoke_access_token(token)
    except Exception:
        logger.exception("Could not revoke access token during logout")
        response.status_code = 503
        response.delete_cookie(
            key="access_token",
            path="/",
            httponly=True,
            secure=os.getenv("ENVIRONMENT", "production").lower() == "production",
            samesite="none"
            if os.getenv("ENVIRONMENT", "production").lower() == "production"
            else "lax",
        )
        return {"detail": "Could not revoke access token"}

    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        secure=os.getenv("ENVIRONMENT", "production").lower() == "production",
        samesite="none"
        if os.getenv("ENVIRONMENT", "production").lower() == "production"
        else "lax",
    )
    return {"status": "success"}
