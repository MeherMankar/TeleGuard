import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telethon.errors import PhoneNumberInvalidError

from teleguard.core.messaging import MessagingManager
from teleguard.handlers.message_handlers import MessageHandlers
from teleguard.utils.network_helpers import retry_async


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


def test_invalid_phone_error_is_reported_once_and_clears_pending_action():
    user_id = 123
    handlers = object.__new__(MessageHandlers)
    handlers.pending_actions = {user_id: {"action": "add_account"}}
    handlers.auth_manager = SimpleNamespace(
        start_auth=AsyncMock(
            side_effect=PhoneNumberInvalidError(request=None)
        )
    )
    event = SimpleNamespace(reply=AsyncMock())

    asyncio.run(handlers._process_add_account(event, user_id, "+988974834xxx"))

    event.reply.assert_awaited_once()
    assert "Invalid Phone Number" in event.reply.await_args.args[0]
    assert user_id not in handlers.pending_actions


def test_phone_number_error_is_not_retried():
    request = AsyncMock(side_effect=PhoneNumberInvalidError(request=None))

    try:
        asyncio.run(retry_async(request, "+988974834xxx", base_delay=0))
    except PhoneNumberInvalidError:
        pass
    else:
        raise AssertionError("PhoneNumberInvalidError should propagate immediately")

    request.assert_awaited_once_with("+")
