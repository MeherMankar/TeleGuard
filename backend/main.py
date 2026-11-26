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

import asyncio
import logging
import os
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.api.accounts import router as accounts_router
from backend.api.analytics import router as analytics_router
from backend.api.auth_router import router as auth_router
from backend.api.auto_reply import router as auto_reply_router
from backend.api.chats import router as chats_router
from backend.api.messaging import MAX_UPLOAD_SIZE, router as messaging_router
from backend.api.privacy import router as privacy_router
from backend.api.proxies import router as proxies_router
from backend.api.security import router as security_router
from backend.api.sessions import router as sessions_router
from backend.api.spam import router as spam_router
from backend.auth.jwt import ALGORITHM, SECRET_KEY
from backend.websocket.manager import manager as ws_manager
from teleguard.core.mongo_database import mongodb

logger = logging.getLogger(__name__)
api_server: Optional[uvicorn.Server] = None


class RequestBodyTooLarge(Exception):
    pass


class RequestBodyLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        upload_limit: int = MAX_UPLOAD_SIZE + 1024 * 1024,
        request_limit: int = 2 * 1024 * 1024,
    ) -> None:
        self.app = app
        self.upload_limit = upload_limit
        self.request_limit = request_limit

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = (
            self.upload_limit
            if scope.get("path") == "/api/messaging/send-file"
            else self.request_limit
        )
        headers = dict(scope.get("headers", []))
        try:
            if int(headers.get(b"content-length", b"0")) > limit:
                await self._send_too_large(send)
                return
        except ValueError:
            pass

        received_size = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received_size
            message = await receive()
            if message["type"] == "http.request":
                received_size += len(message.get("body", b""))
                if received_size > limit:
                    raise RequestBodyTooLarge
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except RequestBodyTooLarge:
            if not response_started:
                await self._send_too_large(send)

    @staticmethod
    async def _send_too_large(send: Send) -> None:
        body = b'{"detail":"Request body too large"}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


app = FastAPI(
    title="TeleGuard Dashboard API",
    version="2.0.0",
    description="TeleGuard backend — bot and webapp share the same process and MongoDB",
)

# CORS — allow the frontend dev server and production domain
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://localhost:4173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(RequestBodyLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _origin_is_allowed(origin: Optional[str]) -> bool:
    return bool(origin and origin in ALLOWED_ORIGINS)


@app.middleware("http")
async def require_allowed_cookie_origin(request: Request, call_next):
    if (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and request.cookies.get("access_token")
        and not _origin_is_allowed(request.headers.get("origin"))
    ):
        return JSONResponse(status_code=403, content={"detail": "Origin not allowed"})
    return await call_next(request)


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
    checks = {"mongodb": False, "bot": False}
    if mongodb.client is not None:
        try:
            await mongodb.client.admin.command("ping")
            checks["mongodb"] = True
        except Exception:
            logger.exception("MongoDB readiness check failed")

    try:
        from teleguard.core.bot_manager import bot_manager

        checks["bot"] = bool(
            bot_manager and bot_manager.startup_complete and bot_manager.is_running
        )
    except Exception:
        logger.exception("Bot readiness check failed")

    ready = all(checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "healthy" if ready else "unhealthy",
            "service": "teleguard",
            "timestamp": time.time(),
            "checks": checks,
        },
    )


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
async def websocket_events(websocket: WebSocket):
    """
    Authenticated WebSocket for real-time dashboard events.
    Events pushed by the bot: account_added, account_removed, session_revoked,
    new_message, security_alert, automation_log, otp_event,
    otp_destroyer_toggled, otp_forward_toggled, otp_temp_passthrough.
    """
    if not _origin_is_allowed(websocket.headers.get("origin")):
        await websocket.close(code=1008)
        return

    user_id = None
    token = websocket.cookies.get("access_token")
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("user_id")
            token_id = payload.get("jti")
            if not token_id:
                user_id = None
            else:
                revoked = await mongodb.db.revoked_tokens.find_one(
                    {"_id": token_id}
                )
                if revoked:
                    user_id = None
        except JWTError:
            pass
        except Exception:
            logger.exception("Could not validate WebSocket token revocation")
            await websocket.close(code=1011)
            return

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


async def start_api_server(startup_event: Optional[asyncio.Event] = None):
    """Start uvicorn as an asyncio task inside the bot process."""
    global api_server
    port = int(os.getenv("PORT", 8080))
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    api_server = server
    logger.info(f"Starting FastAPI server on port {port}")
    serve_task = asyncio.create_task(server.serve())
    try:
        while not server.started:
            if serve_task.done():
                await serve_task
                raise RuntimeError("API server stopped before becoming ready")
            await asyncio.sleep(0.05)
        if startup_event:
            startup_event.set()
        await serve_task
    finally:
        if not serve_task.done():
            server.should_exit = True
            serve_task.cancel()
            await asyncio.gather(serve_task, return_exceptions=True)
        if api_server is server:
            api_server = None


def request_api_server_shutdown() -> None:
    """Ask the running Uvicorn server to exit cleanly."""
    if api_server is not None:
        api_server.should_exit = True
