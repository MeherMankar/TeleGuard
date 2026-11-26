import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from jose import jwt as jose_jwt
from starlette.requests import Request

from backend import main as backend_main
from backend.api import messaging
from backend.api.messaging import SendMessageRequest
from backend.auth.jwt import create_access_token
from teleguard.core.mongo_database import mongodb
from teleguard.core import bot_manager as bot_manager_module


@pytest.mark.asyncio
async def test_health_endpoint_requires_mongodb_and_started_bot(monkeypatch):
    monkeypatch.setattr(backend_main.mongodb, "client", None)
    monkeypatch.setattr(bot_manager_module, "bot_manager", None)

    response = await backend_main.health_check()

    assert response.status_code == 503
    assert json.loads(response.body)["checks"] == {"mongodb": False, "bot": False}


@pytest.mark.asyncio
async def test_health_endpoint_is_ready_when_mongodb_and_bot_are_ready(monkeypatch):
    client = SimpleNamespace(admin=SimpleNamespace(command=AsyncMock()))
    bot = SimpleNamespace(startup_complete=True, is_running=True)
    monkeypatch.setattr(backend_main.mongodb, "client", client)
    monkeypatch.setattr(bot_manager_module, "bot_manager", bot)

    response = await backend_main.health_check()

    assert response.status_code == 200
    assert json.loads(response.body)["checks"] == {"mongodb": True, "bot": True}


@pytest.mark.asyncio
async def test_send_message_preserves_failed_send_client_error(monkeypatch):
    manager = SimpleNamespace(
        messaging_manager=SimpleNamespace(send_message=AsyncMock(return_value=False))
    )
    monkeypatch.setattr(messaging, "_get_bot_manager", lambda: manager)

    with pytest.raises(HTTPException) as error:
        await messaging.send_message(
            SendMessageRequest(
                account_name="primary",
                target="@example",
                message="test",
            ),
            user_id=123,
        )

    assert error.value.status_code == 400
    assert error.value.detail == "Failed to send message"


@pytest.mark.asyncio
async def test_cookie_authenticated_mutation_rejects_untrusted_origin():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/messaging/send",
            "query_string": b"",
            "headers": [
                (b"cookie", b"access_token=token"),
                (b"origin", b"https://untrusted.example"),
            ],
            "server": ("test", 80),
            "client": ("test", 1),
            "scheme": "http",
        }
    )

    response = await backend_main.require_allowed_cookie_origin(
        request, AsyncMock()
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_request_body_middleware_limits_streamed_bodies():
    messages = [
        {"type": "http.request", "body": b"12345", "more_body": False}
    ]
    sent = []

    async def receive():
        return messages.pop(0)

    async def send(message):
        sent.append(message)

    async def consume_body(_scope, limited_receive, _send):
        await limited_receive()

    middleware = backend_main.RequestBodyLimitMiddleware(
        consume_body,
        upload_limit=4,
        request_limit=4,
    )
    await middleware(
        {"type": "http", "path": "/api/messaging/send-file", "headers": []},
        receive,
        send,
    )

    assert sent[0]["status"] == 413


@pytest.mark.asyncio
async def test_websocket_rejects_untrusted_origin():
    websocket = SimpleNamespace(
        headers={"origin": "https://untrusted.example"},
        cookies={},
        close=AsyncMock(),
    )

    await backend_main.websocket_events(websocket)

    websocket.close.assert_awaited_once_with(code=1008)


@pytest.mark.asyncio
async def test_websocket_rejects_revoked_access_token(monkeypatch):
    token = create_access_token({"user_id": 123})
    token_id = jose_jwt.decode(
        token,
        backend_main.SECRET_KEY,
        algorithms=[backend_main.ALGORITHM],
    )["jti"]
    websocket = SimpleNamespace(
        headers={"origin": "http://localhost:5173"},
        cookies={"access_token": token},
        close=AsyncMock(),
    )
    collection = SimpleNamespace(
        find_one=AsyncMock(return_value={"_id": token_id})
    )
    monkeypatch.setattr(mongodb, "db", SimpleNamespace(revoked_tokens=collection))
    monkeypatch.setattr(
        backend_main, "ALLOWED_ORIGINS", ["http://localhost:5173"]
    )

    await backend_main.websocket_events(websocket)

    collection.find_one.assert_awaited_once_with({"_id": token_id})
    websocket.close.assert_awaited_once_with(code=4001)


@pytest.mark.asyncio
async def test_api_server_signals_only_after_server_is_ready(monkeypatch):
    class Server:
        def __init__(self, _config):
            self.started = False
            self.should_exit = False

        async def serve(self):
            self.started = True

    monkeypatch.setattr(backend_main.uvicorn, "Config", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(backend_main.uvicorn, "Server", Server)
    startup_event = asyncio.Event()

    await backend_main.start_api_server(startup_event)

    assert startup_event.is_set()
    assert backend_main.api_server is None


@pytest.mark.asyncio
async def test_api_server_startup_failure_is_propagated(monkeypatch):
    class Server:
        def __init__(self, _config):
            self.started = False
            self.should_exit = False

        async def serve(self):
            raise OSError("port already in use")

    monkeypatch.setattr(backend_main.uvicorn, "Config", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(backend_main.uvicorn, "Server", Server)

    with pytest.raises(OSError, match="port already in use"):
        await backend_main.start_api_server(asyncio.Event())

    assert backend_main.api_server is None
