import asyncio
from types import SimpleNamespace

import pytest

from teleguard.core.messaging import MessagingManager
from teleguard.handlers.message_handlers import MessageHandlers


class Client:
    def __init__(self, connected):
        self.connected = connected

    def is_connected(self):
        return self.connected


def test_message_uses_only_the_selected_account_client():
    selected_client = Client(connected=False)
    other_client = Client(connected=True)
    manager = object.__new__(MessagingManager)
    manager.user_clients = {
        123: {
            "selected": selected_client,
            "other": other_client,
        }
    }

    client = asyncio.run(manager._get_best_client(123, "selected", "@recipient"))

    assert client is None


def test_message_returns_the_selected_account_client_when_connected():
    selected_client = Client(connected=True)
    manager = object.__new__(MessagingManager)
    manager.user_clients = {123: {"selected": selected_client}}

    client = asyncio.run(manager._get_best_client(123, "selected", "@recipient"))

    assert client is selected_client


@pytest.mark.asyncio
async def test_reply_handler_accepts_media_message_without_raw_text(monkeypatch):
    bot_manager = SimpleNamespace(
        pending_actions={},
        pending_fresh_sessions={},
    )
    handler = object.__new__(MessageHandlers)
    handler.bot_manager = bot_manager
    handler.pending_actions = bot_manager.pending_actions

    async def is_admin_group_message(_user_id, _chat_id):
        return False

    handler._is_admin_group_message = is_admin_group_message

    event = SimpleNamespace(
        sender_id=6121637257,
        chat_id=-100123,
        raw_text=None,
        text="",
    )

    await handler._handle_user_reply(event)
