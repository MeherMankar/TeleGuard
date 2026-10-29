from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from teleguard.core.mongo_database import mongodb
from teleguard.handlers.dm_reply_handler import DMReplyHandler
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
