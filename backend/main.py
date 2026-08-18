"""
TeleGuard FastAPI Backend
Runs as an asyncio task inside the bot process — shares the same event loop,
same bot_manager singleton, and same MongoDB connection.

Bot↔Webapp sync:
- Accounts added via bot are stored encrypted in MongoDB → webapp reads them via /api/accounts/list
- Accounts added via webapp are stored encrypted in MongoDB AND bot_manager.start_user_client()
  is called immediately → bot uses them without restart
- WebSocket /ws/events pushes real-time events to the webapp
"""

import logging
import os
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt, JWTError

from backend.api.auth_router import router as auth_router
from backend.api.accounts import router as accounts_router
from backend.api.sessions import router as sessions_router
from backend.api.security import router as security_router
from backend.api.messaging import router as messaging_router
from backend.api.auto_reply import router as auto_reply_router
from backend.api.analytics import router as analytics_router
from backend.api.proxies import router as proxies_router
from backend.api.chats import router as chats_router
from backend.api.spam import router as spam_router
from backend.api.privacy import router as privacy_router
from backend.websocket.manager import manager as ws_manager
from backend.auth.jwt import SECRET_KEY, ALGORITHM

logger = logging.getLogger(__name__)

app = FastAPI(
    title="TeleGuard Dashboard API",
    version="2.0.0",
    description="TeleGuard backend — bot and webapp share the same process and MongoDB",
)

# CORS — allow the frontend dev server and production domain
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:4173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production via ALLOWED_ORIGINS
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all API routers under /api prefix
app.include_router(auth_router, prefix="/api")
app.include_router(accounts_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(security_router, prefix="/api")
app.include_router(messaging_router, prefix="/api")
app.include_router(auto_reply_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(proxies_router, prefix="/api")
app.include_router(chats_router, prefix="/api")
app.include_router(spam_router, prefix="/api")
app.include_router(privacy_router, prefix="/api")


@app.api_route("/health", methods=["GET", "HEAD"])
@app.api_route("/", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "healthy", "service": "teleguard", "timestamp": time.time()}


@app.get("/ip")
async def ip_status():
    try:
        from teleguard.core.session_guardian import get_guardian
        guardian = get_guardian()
        if guardian:
            return {
                "current_ip": guardian.current_ip,
                "ip_changes": guardian.ip_change_count,
                "stability": (
                    "high" if guardian.ip_change_count < 3
                    else "medium" if guardian.ip_change_count < 10
                    else "low"
                ),
                "last_check": guardian.last_ip_check,
            }
    except Exception:
        pass
    return {"status": "guardian_not_initialized"}


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket, token: Optional[str] = Query(None)):
    """
    Authenticated WebSocket for real-time dashboard events.
    Events pushed by the bot: account_added, account_removed, session_revoked,
    new_message, security_alert, automation_log, otp_event.
    """
    user_id = None
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("user_id")
        except JWTError:
            pass

    if not user_id:
        await websocket.close(code=4001)
        return

    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        ws_manager.disconnect(user_id, websocket)


async def start_api_server():
    """Start uvicorn as an asyncio task inside the bot process."""
    port = int(os.getenv("PORT", 8080))
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    logger.info(f"Starting FastAPI server on port {port}")
    await server.serve()
