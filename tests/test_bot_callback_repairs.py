import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from teleguard.handlers.backup_restore import BackupRestore
from teleguard.handlers.command_handlers import CommandHandlers
from teleguard.handlers.menu_modules.menu_handlers import MenuHandlers
from teleguard.handlers.security_dashboard import SecurityDashboard
from teleguard.handlers.session_operations_handler import SessionOperationsHandler
from teleguard.handlers.spam_filters_handler import SpamFiltersHandler


class HandlerCaptureBot:
    def __init__(self):
        self.handlers = []
        self.send_message = AsyncMock()

    def on(self, builder):
        def register(handler):
            self.handlers.append((builder, handler))
            return handler

        return register


def _handler_by_name(bot, name):
    return next(handler for _, handler in bot.handlers if handler.__name__ == name)


def test_appeal_command_emits_registered_account_callback(monkeypatch):
    account_id = "account-id"
    cursor = SimpleNamespace(
        to_list=AsyncMock(return_value=[{"_id": account_id, "name": "Primary"}])
    )
    monkeypatch.setattr(
        "teleguard.handlers.command_handlers.mongodb",
        SimpleNamespace(db=SimpleNamespace(accounts=SimpleNamespace(find=Mock(return_value=cursor)))),
    )
    handler = object.__new__(CommandHandlers)
    event = SimpleNamespace(sender_id=7, reply=AsyncMock())

    asyncio.run(handler._handle_appeal(event))

    buttons = event.reply.await_args.kwargs["buttons"]
    assert buttons[0][0].data == f"appeal_account_id:{account_id}".encode()


def test_max_users_input_persists_a_value_within_existing_cap(monkeypatch):
    temp_data = SimpleNamespace(
        find_one=AsyncMock(return_value={"field": "max_users"}),
        delete_one=AsyncMock(),
        update_one=AsyncMock(),
    )
    spam_config = SimpleNamespace(update_one=AsyncMock())
    monkeypatch.setattr(
        "teleguard.handlers.spam_filters_handler.mongodb",
        SimpleNamespace(db=SimpleNamespace(temp_data=temp_data, spam_config=spam_config)),
    )
    handler = object.__new__(SpamFiltersHandler)
    handler.bot = HandlerCaptureBot()
    handler.user_clients = {}
    handler._register_settings_handlers()
    handler._register_message_handler()
    event = SimpleNamespace(
        sender_id=7,
        is_private=True,
        raw_text="350",
        reply=AsyncMock(),
    )

    asyncio.run(_handler_by_name(handler.bot, "handle_filter_inputs")(event))

    spam_config.update_one.assert_awaited_once_with(
        {"user_id": 7}, {"$set": {"max_users": 350}}, upsert=True
    )
    temp_data.delete_one.assert_awaited_once_with(
        {"user_id": 7, "type": "max_users_wait"}
    )
    event.reply.assert_awaited_once_with("✅ Maximum users per campaign set to 350.")


def test_set_max_users_button_starts_the_input_flow(monkeypatch):
    temp_data = SimpleNamespace(update_one=AsyncMock())
    monkeypatch.setattr(
        "teleguard.handlers.spam_filters_handler.mongodb",
        SimpleNamespace(db=SimpleNamespace(temp_data=temp_data)),
    )
    handler = object.__new__(SpamFiltersHandler)
    handler.bot = HandlerCaptureBot()
    handler.user_clients = {}
    handler._register_settings_handlers()
    event = SimpleNamespace(sender_id=7, answer=AsyncMock())

    asyncio.run(_handler_by_name(handler.bot, "set_max_users")(event))

    temp_data.update_one.assert_awaited_once_with(
        {"user_id": 7, "type": "max_users_wait"},
        {"$set": {"field": "max_users"}},
        upsert=True,
    )
    handler.bot.send_message.assert_awaited_once_with(
        7, "Send the maximum users per campaign (1-500), or /cancel:"
    )


def test_max_users_input_rejects_values_above_existing_cap(monkeypatch):
    temp_data = SimpleNamespace(
        find_one=AsyncMock(return_value={"field": "max_users"}),
        delete_one=AsyncMock(),
    )
    spam_config = SimpleNamespace(update_one=AsyncMock())
    monkeypatch.setattr(
        "teleguard.handlers.spam_filters_handler.mongodb",
        SimpleNamespace(db=SimpleNamespace(temp_data=temp_data, spam_config=spam_config)),
    )
    handler = object.__new__(SpamFiltersHandler)
    handler.bot = HandlerCaptureBot()
    handler.user_clients = {}
    handler._register_message_handler()
    event = SimpleNamespace(
        sender_id=7,
        is_private=True,
        raw_text="501",
        reply=AsyncMock(),
    )

    asyncio.run(_handler_by_name(handler.bot, "handle_filter_inputs")(event))

    spam_config.update_one.assert_not_awaited()
    temp_data.delete_one.assert_not_awaited()
    event.reply.assert_awaited_once_with("Value must be between 1 and 500.")


def test_security_alerts_show_only_high_and_medium_events(monkeypatch):
    monitor = SimpleNamespace(
        get_security_report=AsyncMock(
            return_value={
                "recent_events": [
                    {
                        "severity": "high",
                        "timestamp": datetime(2026, 1, 1, 12, 0),
                        "event_type": "new_login",
                        "details": {"activity": "Unrecognized login"},
                    },
                    {"severity": "low", "event_type": "routine_check"},
                ]
            }
        )
    )
    monkeypatch.setattr(
        "teleguard.handlers.security_dashboard.security_monitor", monitor
    )
    handler = object.__new__(SecurityDashboard)
    event = SimpleNamespace(sender_id=7, edit=AsyncMock(), answer=AsyncMock())

    asyncio.run(handler._show_security_alerts(event))

    text = event.edit.await_args.args[0]
    assert "[HIGH]" in text
    assert "Unrecognized login" in text
    assert "routine_check" not in text


def test_backup_restore_rejects_backup_from_another_user():
    with pytest.raises(ValueError, match="different Telegram account"):
        BackupRestore._validate_backup(
            {"version": "2.0", "user_id": 99, "accounts": []}, user_id=7
        )


def test_backup_menu_exposes_restore_action():
    handler = object.__new__(BackupRestore)
    event = SimpleNamespace(answer=AsyncMock(), edit=AsyncMock())

    asyncio.run(handler._show_backup_menu(event))

    event.answer.assert_awaited_once()
    buttons = event.edit.await_args.kwargs["buttons"]
    callback_data = [button.data for row in buttons for button in row]
    assert b"backup_restore" in callback_data


def test_restore_skips_existing_accounts_before_applying_account_limit(monkeypatch):
    cursor = SimpleNamespace(
        to_list=AsyncMock(return_value=[{"phone": "+15550000000", "name": "Primary"}])
    )
    accounts = SimpleNamespace(find=Mock(return_value=cursor), insert_one=AsyncMock())
    monkeypatch.setattr(
        "teleguard.handlers.backup_restore.mongodb",
        SimpleNamespace(db=SimpleNamespace(accounts=accounts)),
    )
    monkeypatch.setattr("teleguard.handlers.backup_restore.MAX_ACCOUNTS", 1)
    handler = object.__new__(BackupRestore)

    result = asyncio.run(
        handler._restore_accounts(
            7,
            [
                {
                    "phone": "+15550000000",
                    "name": "Primary",
                    "session_string": "not-used-for-existing-account",
                    "is_active": True,
                }
            ],
        )
    )

    assert result == {"restored": 0, "skipped": 1, "failed": 0}
    accounts.insert_one.assert_not_awaited()


def test_restore_does_not_report_disconnected_account_as_restored(monkeypatch):
    cursor = SimpleNamespace(to_list=AsyncMock(return_value=[]))
    accounts = SimpleNamespace(
        find=Mock(return_value=cursor),
        insert_one=AsyncMock(return_value=SimpleNamespace(inserted_id="new-account")),
        update_one=AsyncMock(),
    )
    monkeypatch.setattr(
        "teleguard.handlers.backup_restore.mongodb",
        SimpleNamespace(db=SimpleNamespace(accounts=accounts)),
    )
    monkeypatch.setattr("teleguard.handlers.backup_restore.MAX_ACCOUNTS", 1)
    monkeypatch.setattr(
        "teleguard.handlers.backup_restore.DataEncryption.encrypt_account_data",
        lambda value: value,
    )
    manager = SimpleNamespace(
        start_user_client=AsyncMock(),
        user_clients={},
    )
    handler = object.__new__(BackupRestore)
    handler.bot_manager = manager

    result = asyncio.run(
        handler._restore_accounts(
            7,
            [
                {
                    "phone": "+15550000000",
                    "name": "Primary",
                    "session_string": "a" * 100,
                    "is_active": True,
                }
            ],
        )
    )

    assert result == {"restored": 0, "skipped": 0, "failed": 1}
    accounts.update_one.assert_awaited_once_with(
        {"_id": "new-account", "user_id": 7},
        {"$set": {"is_active": False, "reauth_required": True}},
    )


def test_old_bulk_action_callbacks_are_explicitly_disabled():
    bot = HandlerCaptureBot()
    handler = SessionOperationsHandler(
        SimpleNamespace(bot=bot, user_clients={})
    )
    handler.register_handlers()
    event = SimpleNamespace(answer=AsyncMock())

    asyncio.run(
        _handler_by_name(bot, "disabled_bulk_operation")(event)
    )

    event.answer.assert_awaited_once_with(
        "This bulk or data-collection action is unavailable.",
        alert=True,
    )


def test_session_maintenance_only_offers_confirmed_cleanup(monkeypatch):
    account_id = "0123456789abcdef01234567"
    monkeypatch.setattr(
        "teleguard.handlers.session_operations_handler.mongodb",
        SimpleNamespace(
            db=SimpleNamespace(
                accounts=SimpleNamespace(
                    find_one=AsyncMock(return_value={"name": "Primary"})
                )
            )
        ),
    )
    handler = object.__new__(SessionOperationsHandler)
    event = SimpleNamespace(answer=AsyncMock(), edit=AsyncMock())

    asyncio.run(handler._show_bulk_operations(event, 7, account_id))

    buttons = event.edit.await_args.kwargs["buttons"]
    callback_data = [button.data for row in buttons for button in row]
    assert f"auto_cleanup:{account_id}".encode() in callback_data
    assert not any(
        callback.startswith(
            (
                b"bulk_subscribe:",
                b"bulk_messages:",
                b"extract_members:",
                b"scrape_messages:",
                b"monitor_keywords:",
            )
        )
        for callback in callback_data
    )


def test_analytics_menu_has_working_details_and_export_actions(monkeypatch):
    account_id = "0123456789abcdef01234567"
    monkeypatch.setattr(
        "teleguard.handlers.session_operations_handler.mongodb",
        SimpleNamespace(
            db=SimpleNamespace(
                accounts=SimpleNamespace(
                    find_one=AsyncMock(return_value={"name": "Primary"})
                )
            )
        ),
    )
    handler = object.__new__(SessionOperationsHandler)
    handler._get_session_analytics = AsyncMock(
        return_value={
            "total_dialogs": 2,
            "channels": 1,
            "groups": 0,
            "private_chats": 1,
            "bots": 0,
            "has_2fa": None,
            "active_sessions": "Unknown",
            "is_premium": False,
            "is_verified": False,
            "managed_since": "Not recorded",
        }
    )
    event = SimpleNamespace(answer=AsyncMock(), edit=AsyncMock())

    asyncio.run(handler._show_session_analytics(event, 7, account_id))

    buttons = event.edit.await_args.kwargs["buttons"]
    callback_data = [button.data for row in buttons for button in row]
    assert f"detailed_stats:{account_id}".encode() in callback_data
    assert f"export_analytics:{account_id}".encode() in callback_data
    assert not any(callback.startswith(b"config_analytics:") for callback in callback_data)


def test_session_analytics_uses_live_authorization_and_2fa_values():
    client = AsyncMock(
        side_effect=[
            SimpleNamespace(authorizations=[object(), object()]),
            SimpleNamespace(has_password=True),
        ]
    )
    client.is_connected = Mock(return_value=True)
    client.get_me = AsyncMock(
        return_value=SimpleNamespace(premium=True, verified=False)
    )
    client.get_dialogs = AsyncMock(return_value=[])
    handler = object.__new__(SessionOperationsHandler)
    handler.user_clients = {7: {"Primary": client}}

    analytics = asyncio.run(
        handler._get_session_analytics(
            7, {"name": "Primary", "created_at": 1_700_000_000}
        )
    )

    assert analytics["active_sessions"] == 2
    assert analytics["has_2fa"] is True
    assert analytics["is_premium"] is True
    assert "messages_sent" not in analytics
    assert "messages_received" not in analytics


def test_account_and_protection_menus_link_to_backup_and_security(monkeypatch):
    cursor = SimpleNamespace(to_list=AsyncMock(return_value=[]))
    monkeypatch.setattr(
        "teleguard.handlers.menu_modules.menu_handlers.mongodb",
        SimpleNamespace(db=SimpleNamespace(accounts=SimpleNamespace(find=Mock(return_value=cursor)))),
    )
    handlers = MenuHandlers(SimpleNamespace(bot=SimpleNamespace(), account_manager=None))
    handlers._render_menu = AsyncMock()
    event = SimpleNamespace(sender_id=7, message_id=1)

    asyncio.run(handlers.handle_account_settings(event))
    account_buttons = handlers._render_menu.await_args.args[3]
    account_callbacks = [
        button.data for row in account_buttons for button in row
    ]
    assert b"backup_menu" in account_callbacks

    handlers._render_menu.reset_mock()
    asyncio.run(handlers.handle_otp_manager(event))
    protection_buttons = handlers._render_menu.await_args.args[3]
    protection_callbacks = [
        button.data for row in protection_buttons for button in row
    ]
    assert b"security_dashboard" in protection_callbacks
