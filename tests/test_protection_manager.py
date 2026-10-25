import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bson import ObjectId

from teleguard.core.protection_manager import ProtectionManager
from teleguard.core.mongo_database import mongodb
from teleguard.services.protection_storage import ProtectionStorage


class Event:
    def __init__(self, message_text, client):
        self.message = SimpleNamespace(message=message_text)
        self.client = client
        self.deleted = False

    async def delete(self):
        self.deleted = True


class Client:
    def __init__(self, error=None):
        self.error = error
        self.requests = []

    async def __call__(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error


class Bot:
    def __init__(self):
        self.messages = []

    async def send_message(self, user_id, message):
        self.messages.append((user_id, message))


def make_manager(monkeypatch, message_text, client, *, account_overrides=None):
    account = {
        "_id": "account-id",
        "phone": "+15551234567",
        "otp_destroyer_enabled": True,
        "otp_forward_enabled": False,
    }
    account.update(account_overrides or {})

    manager = object.__new__(ProtectionManager)
    manager.bot = Bot()
    manager.bot_manager = SimpleNamespace(pending_fresh_sessions={})
    manager.processed_otps = set()
    manager.sent_notifications = set()
    manager.fresh_session_otps = set()
    manager.temp_passthrough = {}
    manager.last_cleanup = time.time()
    manager.notifier = SimpleNamespace(
        notify_otp_destroyed=AsyncMock()
    )
    manager._find_account_for_message = AsyncMock(
        return_value=(123, "primary", account)
    )
    event = Event(message_text, client)

    monkeypatch.setattr(
        ProtectionStorage,
        "get_settings",
        AsyncMock(return_value={"pause_until": None}),
    )
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(
            otp_protections=SimpleNamespace(find_one=AsyncMock(return_value=None)),
            accounts=SimpleNamespace(update_one=AsyncMock()),
        ),
    )
    monkeypatch.setattr(
        ProtectionStorage, "increment_otp_stats", AsyncMock()
    )
    return manager, event


def test_unextractable_otp_is_not_deleted(monkeypatch):
    client = Client()
    manager, event = make_manager(
        monkeypatch, "Login code could not be read", client
    )

    asyncio.run(manager._handle_otp_message(event))

    assert not event.deleted
    assert not client.requests
    assert manager.bot.messages
    assert "left intact" in manager.bot.messages[0][1]


def test_allowlist_lookup_failure_leaves_otp_intact(monkeypatch):
    client = Client()
    manager, event = make_manager(
        monkeypatch, "Login code: 12345", client
    )
    mongodb.db.otp_protections.find_one.side_effect = RuntimeError("database unavailable")

    asyncio.run(manager._handle_otp_message(event))

    assert not event.deleted
    assert not client.requests
    assert not manager.processed_otps
    assert manager.bot.messages
    assert "left intact" in manager.bot.messages[0][1]


def test_allowlisted_otp_is_not_invalidated_or_deleted(monkeypatch):
    client = Client()
    manager, event = make_manager(
        monkeypatch, "Login code: 12345", client
    )
    mongodb.db.otp_protections.find_one.return_value = {"reason": "account_addition"}

    asyncio.run(manager._handle_otp_message(event))

    assert not event.deleted
    assert not client.requests


def test_invalidation_failure_leaves_otp_intact(monkeypatch):
    client = Client(error=RuntimeError("Telegram unavailable"))
    manager, event = make_manager(
        monkeypatch, "Login code: 12345", client
    )

    asyncio.run(manager._handle_otp_message(event))

    assert not event.deleted
    assert len(client.requests) == 1
    assert not manager.processed_otps
    assert manager.bot.messages
    assert "left intact" in manager.bot.messages[0][1]


def test_successful_invalidation_deletes_and_records_otp(monkeypatch):
    client = Client()
    manager, event = make_manager(
        monkeypatch, "Login code: 12345", client
    )

    asyncio.run(manager._handle_otp_message(event))

    assert event.deleted
    assert len(client.requests) == 1
    ProtectionStorage.increment_otp_stats.assert_awaited_once_with(123)
    manager.notifier.notify_otp_destroyed.assert_awaited_once()


def test_expired_temp_bypass_restores_saved_account_settings(monkeypatch):
    account_id = ObjectId()
    expiry = time.time() - 1
    account = {
        "_id": account_id,
        "user_id": 123,
        "otp_temp_passthrough": True,
        "temp_passthrough_expiry": expiry,
        "otp_temp_original_destroyer_state": True,
        "otp_temp_original_forward_state": False,
    }
    accounts = SimpleNamespace(
        find_one=AsyncMock(return_value=account),
        update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)),
    )
    monkeypatch.setattr(mongodb, "db", SimpleNamespace(accounts=accounts))
    manager = object.__new__(ProtectionManager)
    manager.bot = Bot()
    manager._temp_bypass_tasks = {}

    asyncio.run(manager._expire_temp_bypass(123, str(account_id), expiry))

    accounts.update_one.assert_awaited_once()
    _, update = accounts.update_one.await_args.args
    assert update["$set"] == {
        "otp_destroyer_enabled": True,
        "otp_forward_enabled": False,
    }
    assert "otp_temp_passthrough" in update["$unset"]
