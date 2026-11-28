import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from bson import ObjectId

from teleguard.handlers.command_handlers import CommandHandlers
from teleguard.handlers.spam_appeal_handler import SpamAppealHandler


class HandlerCaptureBot:
    def __init__(self):
        self.handlers = []

    def on(self, builder):
        def register(handler):
            self.handlers.append((builder, handler))
            return handler

        return register


def test_session_protection_bypass_uses_wall_clock_timestamp(monkeypatch):
    accounts = SimpleNamespace(update_many=AsyncMock())
    monkeypatch.setattr(
        "teleguard.core.mongo_database.mongodb",
        SimpleNamespace(db=SimpleNamespace(accounts=accounts)),
    )
    monkeypatch.setattr("teleguard.handlers.spam_appeal_handler.time.time", lambda: 1000)
    handler = object.__new__(SpamAppealHandler)

    asyncio.run(handler._disable_session_protection(123))

    update = accounts.update_many.await_args.args[1]
    assert update["$set"]["protection_bypass_until"] == 2800
    assert "$unset" not in update


def test_restore_session_protection_removes_temporary_bypass(monkeypatch):
    accounts = SimpleNamespace(update_many=AsyncMock())
    monkeypatch.setattr(
        "teleguard.core.mongo_database.mongodb",
        SimpleNamespace(db=SimpleNamespace(accounts=accounts)),
    )
    handler = object.__new__(SpamAppealHandler)

    asyncio.run(handler._restore_session_protection(123))

    assert accounts.update_many.await_args.args[0] == {"user_id": 123}
    assert "protection_bypass_until" in accounts.update_many.await_args.args[1]["$unset"]


def test_appeal_command_is_registered_only_once():
    bot = HandlerCaptureBot()
    command_handler = object.__new__(CommandHandlers)
    command_handler.bot = bot
    command_handler._register_command_handlers()

    spam_handler = object.__new__(SpamAppealHandler)
    spam_handler.bot = bot
    spam_handler.register_handlers()

    appeal_handlers = [
        handler.__name__
        for _, handler in bot.handlers
        if handler.__name__ in {"_handle_appeal", "_appeal_command_handler"}
    ]

    assert appeal_handlers == ["_handle_appeal"]
    appeal_builder = next(
        builder
        for builder, handler in bot.handlers
        if handler.__name__ == "_handle_appeal"
    )
    assert appeal_builder.pattern("/appeal")
    assert appeal_builder.pattern("/appeal@mybot")
    assert not appeal_builder.pattern("/appealing")
    assert not appeal_builder.pattern("/appeal extra")


def test_appeal_selection_starts_only_the_selected_active_account(monkeypatch):
    account_id = ObjectId()
    account = {"_id": account_id, "name": "Primary", "is_active": True}
    accounts = SimpleNamespace(find_one=AsyncMock(return_value=account))
    monkeypatch.setattr(
        "teleguard.core.mongo_database.mongodb",
        SimpleNamespace(db=SimpleNamespace(accounts=accounts)),
    )
    handler = object.__new__(SpamAppealHandler)
    handler._disable_session_protection = AsyncMock()
    handler._restore_session_protection = AsyncMock()
    handler._cancel_appeal = lambda _user_id: None
    handler._start_appeal_for_account = AsyncMock()
    handler.active_appeals = {}
    handler.pending_appeals = set()
    event = SimpleNamespace(
        sender_id=123,
        data=f"appeal_account_id:{account_id}".encode(),
        answer=AsyncMock(),
        edit=AsyncMock(),
        delete=AsyncMock(),
        respond=AsyncMock(),
    )
    monkeypatch.setattr(
        "teleguard.handlers.spam_appeal_handler.asyncio.sleep", AsyncMock()
    )

    asyncio.run(handler._appeal_account_callback_handler(event))

    accounts.find_one.assert_awaited_once_with(
        {"_id": account_id, "user_id": 123, "is_active": True}
    )
    handler._disable_session_protection.assert_awaited_once_with(123)
    handler._start_appeal_for_account.assert_awaited_once_with(
        123, "Primary", "", event
    )


def test_duplicate_appeal_selection_is_rejected_without_database_access(monkeypatch):
    accounts = SimpleNamespace(find_one=AsyncMock())
    monkeypatch.setattr(
        "teleguard.core.mongo_database.mongodb",
        SimpleNamespace(db=SimpleNamespace(accounts=accounts)),
    )
    handler = object.__new__(SpamAppealHandler)
    handler.active_appeals = {123: {"state": "waiting_initial_response"}}
    handler.pending_appeals = set()
    event = SimpleNamespace(
        sender_id=123,
        data=b"appeal_account_id:0123456789abcdef01234567",
        answer=AsyncMock(),
        respond=AsyncMock(),
    )

    asyncio.run(handler._appeal_account_callback_handler(event))

    event.answer.assert_awaited_once_with(
        "An appeal is already in progress.", alert=True
    )
    accounts.find_one.assert_not_awaited()


def test_appeal_setup_failure_restores_protection_and_releases_pending_state(
    monkeypatch,
):
    account_id = ObjectId()
    accounts = SimpleNamespace(
        find_one=AsyncMock(
            return_value={
                "_id": account_id,
                "name": "Primary",
                "is_active": True,
            }
        )
    )
    monkeypatch.setattr(
        "teleguard.core.mongo_database.mongodb",
        SimpleNamespace(db=SimpleNamespace(accounts=accounts)),
    )
    handler = object.__new__(SpamAppealHandler)
    handler.active_appeals = {}
    handler.pending_appeals = set()
    handler._disable_session_protection = AsyncMock(
        side_effect=RuntimeError("database unavailable")
    )
    handler._restore_session_protection = AsyncMock()
    handler._cancel_appeal = Mock()
    handler._start_appeal_for_account = AsyncMock()
    event = SimpleNamespace(
        sender_id=123,
        data=f"appeal_account_id:{account_id}".encode(),
        answer=AsyncMock(),
        edit=AsyncMock(),
        delete=AsyncMock(),
        respond=AsyncMock(),
    )

    asyncio.run(handler._appeal_account_callback_handler(event))

    handler._restore_session_protection.assert_awaited_once_with(123)
    handler._cancel_appeal.assert_called_once_with(123)
    handler._start_appeal_for_account.assert_not_awaited()
    assert 123 not in handler.pending_appeals
    event.respond.assert_awaited_once_with("❌ Error starting appeal process.")


def test_spam_appeal_start_does_not_disable_protection_before_selection(monkeypatch):
    account = {"_id": ObjectId(), "name": "Primary", "is_active": True}
    cursor = SimpleNamespace(to_list=AsyncMock(return_value=[account]))
    accounts = SimpleNamespace(find=Mock(return_value=cursor))
    monkeypatch.setattr(
        "teleguard.core.mongo_database.mongodb",
        SimpleNamespace(db=SimpleNamespace(accounts=accounts)),
    )
    handler = object.__new__(SpamAppealHandler)
    handler._disable_session_protection = AsyncMock()
    handler._show_account_selection = AsyncMock()
    event = SimpleNamespace(
        sender_id=123,
        answer=AsyncMock(),
        respond=AsyncMock(),
    )

    asyncio.run(handler._spam_appeal_start_callback_handler(event))

    handler._disable_session_protection.assert_not_awaited()
    handler._show_account_selection.assert_awaited_once_with(event, [account])
