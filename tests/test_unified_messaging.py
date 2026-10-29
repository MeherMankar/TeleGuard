from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from teleguard.core.mongo_database import mongodb
from teleguard.handlers.dm_reply_handler import DMReplyHandler
from teleguard.handlers.topic_actions_handler import TopicActionsHandler
from teleguard.handlers.unified_messaging import UnifiedMessagingSystem


def _run_immediately(coroutine):
    try:
        return coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError("Coroutine unexpectedly suspended")


def test_legacy_dm_refresh_delegates_to_unified_handler():
    unified_messaging = SimpleNamespace(setup_handlers=Mock())
    handler = object.__new__(DMReplyHandler)
    handler.bot_manager = SimpleNamespace(unified_messaging=unified_messaging)

    _run_immediately(handler.refresh_all_handlers())

    unified_messaging.setup_handlers.assert_called_once_with()


def test_unified_admin_reply_handler_is_registered_only_once():
    class RegisteringBot:
        def __init__(self):
            self.registrations = 0

        def on(self, _event):
            def register(handler):
                self.registrations += 1
                return handler

            return register

    manager = object.__new__(UnifiedMessagingSystem)
    manager.bot = RegisteringBot()
    manager._admin_reply_handler_registered = False

    manager._setup_admin_reply_handler()
    manager._setup_admin_reply_handler()

    assert manager.bot.registrations == 1


def test_otp_destroyer_stops_duplicate_service_message_forward(monkeypatch):
    protection_manager = SimpleNamespace(
        _is_login_code=lambda text: "login code" in text.lower(),
        _has_active_otp_auth_flow=lambda _user_id, _phone: False,
    )
    manager = object.__new__(UnifiedMessagingSystem)
    manager.bot_manager = SimpleNamespace(protection_manager=protection_manager)
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(
            accounts=SimpleNamespace(
                find_one=AsyncMock(
                    return_value={
                        "phone": "+15551234567",
                        "otp_destroyer_enabled": True,
                        "otp_forward_enabled": False,
                    }
                )
            )
        ),
    )

    check = manager._should_forward_telegram_service_message(
        123,
        "primary",
        "Login code: 54268. Do not give this code to anyone.",
    )
    with pytest.raises(StopIteration) as result:
        check.send(None)

    assert result.value.value is False


def test_active_auth_flow_can_receive_its_own_login_code(monkeypatch):
    protection_manager = SimpleNamespace(
        _is_login_code=lambda text: "login code" in text.lower(),
        _has_active_otp_auth_flow=lambda _user_id, _phone: True,
    )
    manager = object.__new__(UnifiedMessagingSystem)
    manager.bot_manager = SimpleNamespace(protection_manager=protection_manager)
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(
            accounts=SimpleNamespace(
                find_one=AsyncMock(
                    return_value={
                        "phone": "+15551234567",
                        "otp_destroyer_enabled": True,
                    }
                )
            )
        ),
    )

    check = manager._should_forward_telegram_service_message(
        123, "primary", "Login code: 54268."
    )
    with pytest.raises(StopIteration) as result:
        check.send(None)

    assert result.value.value is True


def test_topic_reply_does_not_fall_back_to_an_unrelated_account(monkeypatch):
    unrelated_client = SimpleNamespace(
        is_connected=Mock(return_value=True),
        get_me=AsyncMock(return_value=SimpleNamespace(id=456)),
    )
    topic_mappings = SimpleNamespace(update_many=AsyncMock())
    sender_records = SimpleNamespace(find_one=AsyncMock())
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(topic_mappings=topic_mappings, dm_senders=sender_records),
    )
    manager = object.__new__(UnifiedMessagingSystem)
    manager.bot_manager = SimpleNamespace(
        get_client_by_telegram_id=AsyncMock(return_value=None)
    )
    manager.user_clients = {999: {"unrelated": unrelated_client}}

    _run_immediately(
        manager._send_topic_reply({"user_id": 123, "account_id": 789}, "hello")
    )

    unrelated_client.get_me.assert_not_awaited()
    topic_mappings.update_many.assert_not_awaited()
    sender_records.find_one.assert_not_awaited()


@pytest.mark.parametrize(
    ("closed", "request_name"),
    [(True, "BlockRequest"), (False, "UnblockRequest")],
)
def test_topic_close_and_reopen_block_and_unblock_mapped_sender(
    monkeypatch, closed, request_name
):
    from telethon.tl.functions.contacts import BlockRequest, UnblockRequest

    client = AsyncMock()
    client.get_input_entity = AsyncMock(return_value=SimpleNamespace(user_id=456))
    mapping = {
        "admin_group_id": -1000000000123,
        "topic_id": 321,
        "account_id": 789,
        "sender_id": 456,
    }
    topic_mappings = SimpleNamespace(
        find_one=AsyncMock(return_value=mapping),
        update_one=AsyncMock(),
    )
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(topic_mappings=topic_mappings),
    )
    handler = object.__new__(TopicActionsHandler)
    handler.bot_manager = SimpleNamespace(
        get_client_by_telegram_id=AsyncMock(return_value=client)
    )

    result = _run_immediately(handler._handle_topic_closed(123, 321, closed))

    assert result is True
    topic_mappings.update_one.assert_any_await(
        {"admin_group_id": -1000000000123, "topic_id": 321},
        {"$set": {"is_closed": closed, "block_sync_pending": True}},
    )
    topic_mappings.update_one.assert_any_await(
        {"admin_group_id": -1000000000123, "topic_id": 321},
        {"$set": {"block_sync_pending": False}},
    )
    request = client.await_args.args[0]
    if request_name == "BlockRequest":
        assert isinstance(request, BlockRequest)
    else:
        assert isinstance(request, UnblockRequest)
    assert request.id.user_id == 456


def test_deleted_topic_clears_mapped_account_history_and_mapping(monkeypatch):
    from telethon.tl.functions.messages import DeleteHistoryRequest

    client = AsyncMock()
    client.get_input_entity = AsyncMock(return_value=SimpleNamespace(user_id=456))
    mapping = {
        "admin_group_id": -1000000000123,
        "topic_id": 321,
        "account_id": 789,
        "sender_id": 456,
    }
    topic_mappings = SimpleNamespace(
        find_one=AsyncMock(return_value=mapping),
        update_one=AsyncMock(),
        delete_one=AsyncMock(),
    )
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(topic_mappings=topic_mappings),
    )
    handler = object.__new__(TopicActionsHandler)
    handler.bot_manager = SimpleNamespace(
        get_client_by_telegram_id=AsyncMock(return_value=client)
    )

    _run_immediately(handler._handle_deleted_topic_messages(123, [321]))

    request = client.await_args.args[0]
    assert isinstance(request, DeleteHistoryRequest)
    assert request.peer.user_id == 456
    assert request.revoke is True
    topic_mappings.delete_one.assert_awaited_once_with(
        {"admin_group_id": -1000000000123, "topic_id": 321}
    )


def test_deleted_topic_uses_admin_log_when_root_id_is_missing(monkeypatch):
    from telethon.tl.types import ChannelAdminLogEventActionDeleteTopic

    mapping = {
        "admin_group_id": -1000000000123,
        "topic_id": 321,
        "account_id": 789,
        "sender_id": 456,
    }
    topic_mappings = SimpleNamespace(
        find_one=AsyncMock(side_effect=[None, None, mapping]),
    )
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(topic_mappings=topic_mappings),
    )
    admin_event = SimpleNamespace(
        action=ChannelAdminLogEventActionDeleteTopic(
            topic=SimpleNamespace(id=321)
        )
    )
    bot = AsyncMock(return_value=SimpleNamespace(events=[admin_event]))
    bot.get_input_entity = AsyncMock(return_value=SimpleNamespace(channel_id=123))
    handler = object.__new__(TopicActionsHandler)
    handler.bot = bot
    handler._clear_deleted_topic_history = AsyncMock()

    _run_immediately(handler._handle_deleted_topic_messages(123, [888, 889]))

    handler._clear_deleted_topic_history.assert_awaited_once_with(mapping)
    request = bot.await_args.args[0]
    assert request.events_filter.delete is True
    assert request.limit == 100


def test_offline_topic_close_is_retried_when_account_returns(monkeypatch):
    from telethon.tl.functions.contacts import BlockRequest

    mapping = {
        "admin_group_id": -1000000000123,
        "topic_id": 321,
        "account_id": 789,
        "sender_id": 456,
        "is_closed": True,
    }
    empty_cursor = SimpleNamespace(to_list=AsyncMock(return_value=[]))
    pending_cursor = SimpleNamespace(to_list=AsyncMock(return_value=[mapping]))
    topic_mappings = SimpleNamespace(
        find=Mock(side_effect=[empty_cursor, pending_cursor]),
        update_one=AsyncMock(),
    )
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(topic_mappings=topic_mappings),
    )
    client = AsyncMock()
    client.get_input_entity = AsyncMock(return_value=SimpleNamespace(user_id=456))
    handler = object.__new__(TopicActionsHandler)

    _run_immediately(handler.sync_account_topic_states(789, client))

    assert isinstance(client.await_args.args[0], BlockRequest)


def test_raw_topic_close_reopen_and_delete_updates_are_routed():
    from telethon.tl.types import (
        MessageActionTopicEdit,
        Message,
        MessageReplyHeader,
        PeerChannel,
        UpdateDeleteChannelMessages,
        UpdateEditChannelMessage,
    )

    class RegisteringBot:
        def __init__(self):
            self.handlers = []

        def on(self, event_builder):
            def register(handler):
                self.handlers.append((event_builder, handler))
                return handler

            return register

    bot = RegisteringBot()
    handler = object.__new__(TopicActionsHandler)
    handler.bot = bot
    handler._handle_topic_closed = AsyncMock()
    handler._handle_deleted_topic_messages = AsyncMock()
    handler.register_handlers()
    raw_handler = bot.handlers[0][1]

    message = Message(
        id=888,
        peer_id=PeerChannel(channel_id=123),
        reply_to=MessageReplyHeader(reply_to_top_id=321),
        action=MessageActionTopicEdit(closed=False),
    )
    _run_immediately(
        raw_handler(UpdateEditChannelMessage(message=message, pts=1, pts_count=1))
    )
    closed_message = Message(
        id=889,
        peer_id=PeerChannel(channel_id=123),
        reply_to=MessageReplyHeader(reply_to_top_id=321),
        action=MessageActionTopicEdit(closed=True),
    )
    _run_immediately(
        raw_handler(
            UpdateEditChannelMessage(
                message=closed_message, pts=2, pts_count=1
            )
        )
    )
    _run_immediately(
        raw_handler(
            UpdateDeleteChannelMessages(
                channel_id=123, messages=[321], pts=3, pts_count=1
            )
        )
    )

    assert handler._handle_topic_closed.await_args_list[0].args == (123, 321)
    assert handler._handle_topic_closed.await_args_list[0].kwargs == {
        "closed": False
    }
    assert handler._handle_topic_closed.await_args_list[1].args == (123, 321)
    assert handler._handle_topic_closed.await_args_list[1].kwargs == {
        "closed": True
    }
    handler._handle_deleted_topic_messages.assert_awaited_once_with(123, [321])
