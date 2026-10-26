import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telethon.tl import types

from teleguard.handlers.channel_manager import ChannelManager


def test_channel_creation_rejects_invalid_type_before_connecting():
    manager = object.__new__(ChannelManager)
    manager._get_client = AsyncMock()

    result = asyncio.run(
        manager.create_channel(123, "+15551234567", "invalid", "Title")
    )

    assert result == (False, "Channel type must be 'channel' or 'group'.")
    manager._get_client.assert_not_awaited()


def test_channel_creation_rejects_empty_title_before_connecting():
    manager = object.__new__(ChannelManager)
    manager._get_client = AsyncMock()

    result = asyncio.run(
        manager.create_channel(123, "+15551234567", "channel", "  ")
    )

    assert result == (False, "Channel or group title cannot be empty.")
    manager._get_client.assert_not_awaited()


def test_delete_permission_check_awaits_get_me():
    account = SimpleNamespace(id=456)
    client = AsyncMock()
    client.get_me.return_value = account
    client.return_value = SimpleNamespace(
        participant=SimpleNamespace(
            admin_rights=SimpleNamespace(delete_messages=True)
        )
    )
    manager = object.__new__(ChannelManager)

    result = asyncio.run(
        manager._check_delete_permissions(client, SimpleNamespace(id=789))
    )

    assert result[0] is False
    client.get_me.assert_awaited_once()
    request = client.await_args.args[0]
    assert request.participant == account


def test_delete_permission_check_fails_closed_on_lookup_error():
    client = AsyncMock()
    client.get_me.side_effect = RuntimeError("Telegram unavailable")
    manager = object.__new__(ChannelManager)

    result = asyncio.run(
        manager._check_delete_permissions(client, SimpleNamespace(id=789))
    )

    assert result[0] is False
    assert "was not deleted" in result[1]
    client.assert_not_awaited()


def test_join_rejects_empty_target_before_connecting():
    manager = object.__new__(ChannelManager)
    manager._get_client = AsyncMock()

    result = asyncio.run(manager.join_channel(123, "+15551234567", "  "))

    assert result == (False, "Enter a valid channel username, link, or ID.")
    manager._get_client.assert_not_awaited()


def test_join_accepts_channel_link_with_trailing_slash_and_query():
    client = SimpleNamespace()
    manager = object.__new__(ChannelManager)
    manager._get_client = AsyncMock(return_value=client)
    manager._join_via_entity = AsyncMock(return_value=(True, "joined"))

    result = asyncio.run(
        manager.join_channel(
            123, "+15551234567", "https://t.me/example_channel/?single"
        )
    )

    assert result == (True, "joined")
    manager._join_via_entity.assert_awaited_once_with(
        client, "https://t.me/example_channel/?single"
    )


def test_get_client_reloads_a_disconnected_selected_client():
    disconnected_client = SimpleNamespace(is_connected=lambda: False)
    connected_client = SimpleNamespace(is_connected=lambda: True)
    manager = object.__new__(ChannelManager)
    manager._load_user_clients = AsyncMock(
        return_value={"+15551234567": disconnected_client}
    )
    manager._find_account_by_phone = AsyncMock(return_value={"name": "primary"})
    manager._find_client_by_account = AsyncMock(return_value=disconnected_client)
    manager._reload_account_client = AsyncMock(return_value=connected_client)

    client = asyncio.run(manager._get_client(123, "+15551234567"))

    assert client is connected_client
    manager._reload_account_client.assert_awaited_once()


def test_resolve_channel_strips_url_query_and_trailing_path():
    entity = SimpleNamespace(id=789)
    client = SimpleNamespace(get_entity=AsyncMock(return_value=entity))
    manager = object.__new__(ChannelManager)

    resolved = asyncio.run(
        manager._resolve_channel(
            client, "http://t.me/example_channel/?single"
        )
    )

    assert resolved is entity
    client.get_entity.assert_awaited_once_with("example_channel")
