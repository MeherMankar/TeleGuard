from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from telethon.errors import FloodWaitError

import teleguard.core.bot_manager as bot_manager_module
from teleguard.core.bot_manager import BotManager


@pytest.mark.asyncio
async def test_bot_client_reuses_a_stable_session(monkeypatch):
    manager = object.__new__(BotManager)
    manager._start_bot_with_retry = AsyncMock()
    manager._on_session_load_interaction = AsyncMock()
    client = SimpleNamespace(add_event_handler=Mock())
    create_client = Mock(return_value=client)
    monkeypatch.setattr(bot_manager_module, "TelegramClient", create_client)
    monkeypatch.setattr(
        "teleguard.core.device_snooper.DeviceSnooper.get_spoofed_device_params",
        staticmethod(lambda: {}),
    )

    await manager._initialize_bot_client()

    assert create_client.call_args.args[0] == "teleguard_bot"


@pytest.mark.asyncio
async def test_bot_start_waits_for_full_telegram_flood_wait(monkeypatch):
    manager = object.__new__(BotManager)
    manager.bot = SimpleNamespace(
        start=AsyncMock(side_effect=[FloodWaitError(None, capture=451), None])
    )
    sleep = AsyncMock()
    monkeypatch.setattr(bot_manager_module.asyncio, "sleep", sleep)

    await manager._start_bot_with_retry()

    sleep.assert_awaited_once_with(451)
    assert manager.bot.start.await_count == 2
