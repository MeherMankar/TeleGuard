import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from teleguard.handlers.spam_appeal_handler import SpamAppealHandler


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


def test_appeal_without_active_accounts_does_not_disable_protection(monkeypatch):
    cursor = SimpleNamespace(to_list=AsyncMock(return_value=[]))
    accounts = SimpleNamespace(find=lambda _query: cursor)
    monkeypatch.setattr(
        "teleguard.core.mongo_database.mongodb",
        SimpleNamespace(db=SimpleNamespace(accounts=accounts)),
    )
    handler = object.__new__(SpamAppealHandler)
    handler._disable_session_protection = AsyncMock()
    event = SimpleNamespace(
        sender_id=123,
        reply=AsyncMock(),
        pattern_match=SimpleNamespace(group=lambda _index: None),
    )

    asyncio.run(handler._appeal_command_handler(event))

    handler._disable_session_protection.assert_not_awaited()
    event.reply.assert_awaited_once()
