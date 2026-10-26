import asyncio

from teleguard.core.messaging import MessagingManager


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
