import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend import main as backend_main
from backend.api import messaging
from backend.api.messaging import SendMessageRequest
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
