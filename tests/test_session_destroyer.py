import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend.api import security
from teleguard.core.session_destroyer import (
    SessionDestroyer,
    _initial_trusted_hashes,
    _session_existed_when_protection_enabled,
)
from teleguard.core.protection_manager import ProtectionManager
from teleguard.core.mongo_database import MongoDB, mongodb
from teleguard.handlers.protection_menu import ProtectionMenu
from teleguard.services.protection_storage import ProtectionStorage
from teleguard.sync.session_destroyer_db import SessionDestroyerDB


def test_recently_used_old_session_is_trusted_after_restart():
    enabled_at = datetime.now(timezone.utc)
    auth = SimpleNamespace(
        date_created=enabled_at - timedelta(days=30),
        date_active=enabled_at + timedelta(days=1),
    )

    assert _session_existed_when_protection_enabled(auth, enabled_at)


def test_session_created_after_protection_was_enabled_is_not_trusted():
    enabled_at = datetime.now(timezone.utc)
    auth = SimpleNamespace(date_created=enabled_at + timedelta(seconds=1))

    assert not _session_existed_when_protection_enabled(auth, enabled_at)


def test_session_without_creation_timestamp_is_trusted_safely():
    enabled_at = datetime.now(timezone.utc)
    auth = SimpleNamespace(date_active=enabled_at + timedelta(days=1))

    assert _session_existed_when_protection_enabled(auth, enabled_at)


def test_watchers_are_independent_per_account():
    async def scenario():
        destroyer = object.__new__(SessionDestroyer)
        destroyer.active_watchers = {}
        destroyer._lock = asyncio.Lock()
        destroyer.is_shutdown = False
        blocker = asyncio.Event()

        async def hold_watcher(_user_id, _account_id):
            await blocker.wait()

        destroyer._watcher_loop = hold_watcher
        await destroyer.start_watcher(123, "account-a")
        await destroyer.start_watcher(123, "account-b")

        assert set(destroyer.active_watchers) == {
            (123, "account-a"),
            (123, "account-b"),
        }

        await destroyer.stop_watcher(123, "account-a")
        assert set(destroyer.active_watchers) == {(123, "account-b")}
        await destroyer.stop_all()

    asyncio.run(scenario())


def test_enabling_destroyer_starts_only_the_selected_account(monkeypatch):
    account_id = "507f1f77bcf86cd799439011"
    account = {
        "_id": __import__("bson").ObjectId(account_id),
        "user_id": 123,
        "name": "primary",
        "is_active": True,
    }
    client = SimpleNamespace(is_connected=lambda: True)
    accounts = SimpleNamespace(find_one=AsyncMock(return_value=account))
    monkeypatch.setattr(mongodb, "db", SimpleNamespace(accounts=accounts))
    monkeypatch.setattr(
        ProtectionStorage,
        "get_account_settings",
        AsyncMock(return_value={"enabled": False}),
    )
    update_settings = AsyncMock()
    monkeypatch.setattr(ProtectionStorage, "update_account_settings", update_settings)
    sync = AsyncMock()
    start = AsyncMock()
    manager = object.__new__(ProtectionManager)
    manager.bot_manager = SimpleNamespace(user_clients={123: {"primary": client}})
    manager.session_destroyer = SimpleNamespace(
        sync_trusted_sessions=sync,
        start_watcher=start,
    )
    from teleguard.utils.crypto_utils import DataEncryption
    monkeypatch.setattr(DataEncryption, "decrypt_account_data", lambda doc: doc)

    asyncio.run(manager.toggle_session_destroyer(123, True, account_id))

    assert update_settings.await_args.args[:2] == (123, account_id)
    assert update_settings.await_args.args[2]["enabled"] is True
    sync.assert_awaited_once_with(123, client, account_id)
    start.assert_awaited_once_with(123, account_id)


def test_account_trust_write_is_scoped_to_account(monkeypatch):
    account_id = "507f1f77bcf86cd799439011"
    update_one = AsyncMock()
    collection = SimpleNamespace(update_one=update_one)
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(session_destroyer_account_settings=collection),
    )
    monkeypatch.setattr(
        ProtectionStorage,
        "get_account_settings",
        AsyncMock(return_value={"trusted_hashes": []}),
    )

    asyncio.run(ProtectionStorage.add_account_trusted_hash(123, account_id, 456))

    assert update_one.await_args.args[0] == {
        "user_id": 123,
        "account_id": account_id,
    }
    assert update_one.await_args.args[1]["$addToSet"] == {"trusted_hashes": 456}


def test_security_api_toggle_passes_selected_account(monkeypatch):
    account_id = "507f1f77bcf86cd799439011"
    toggle = AsyncMock()
    monkeypatch.setattr(security, "_require_owned_account", AsyncMock(return_value={}))
    monkeypatch.setattr(
        security,
        "_get_bot_manager",
        lambda: SimpleNamespace(protection_manager=SimpleNamespace(
            toggle_session_destroyer=toggle
        )),
    )

    response = asyncio.run(
        security.update_session_destroyer(
            security.ToggleSessionDestroyerRequest(
                account_id=account_id,
                enabled=True,
            ),
            user_id=123,
        )
    )

    assert response["account_id"] == account_id
    toggle.assert_awaited_once_with(123, True, account_id)


def test_security_api_rejects_accounts_not_owned_by_user(monkeypatch):
    account_id = "507f1f77bcf86cd799439011"
    find_one = AsyncMock(return_value=None)
    monkeypatch.setattr(mongodb, "db", SimpleNamespace(accounts=SimpleNamespace(
        find_one=find_one
    )))

    with pytest.raises(HTTPException) as error:
        asyncio.run(security._require_owned_account(123, account_id))

    assert error.value.status_code == 404
    assert find_one.await_args.args[0]["user_id"] == 123


def test_legacy_global_setting_migrates_and_is_disabled(monkeypatch):
    database = object.__new__(MongoDB)
    database._create_mock_db()
    db = database.db
    account_id = __import__("bson").ObjectId("507f1f77bcf86cd799439011")
    asyncio.run(
        db.accounts.insert_one(
            {"_id": account_id, "user_id": 123, "is_active": True}
        )
    )
    asyncio.run(
        db.protection_settings.insert_one(
            {"user_id": 123, "session_destroyer_enabled": True}
        )
    )
    asyncio.run(
        db.session_destroyer_settings.insert_one({"user_id": 123, "enabled": True})
    )
    monkeypatch.setattr(mongodb, "db", db)

    active = asyncio.run(ProtectionStorage.get_all_active_session_destroyers())

    assert len(active) == 1
    assert active[0]["account_id"] == str(account_id)
    assert active[0]["enabled"] is True
    assert asyncio.run(
        db.protection_settings.find_one({"user_id": 123})
    )["session_destroyer_enabled"] is False
    assert asyncio.run(
        db.session_destroyer_settings.find_one({"user_id": 123})
    )["enabled"] is False


def test_duplicate_destruction_does_not_increment_stats_twice(monkeypatch):
    database = object.__new__(MongoDB)
    database._create_mock_db()
    db = database.db
    monkeypatch.setattr(mongodb, "db", db)
    account_id = "507f1f77bcf86cd799439011"

    asyncio.run(ProtectionStorage.add_account_destroyed_hash(123, account_id, 456))
    asyncio.run(ProtectionStorage.add_account_destroyed_hash(123, account_id, 456))

    account_settings = asyncio.run(
        db.session_destroyer_account_settings.find_one(
            {"user_id": 123, "account_id": account_id}
        )
    )
    user_settings = asyncio.run(db.protection_settings.find_one({"user_id": 123}))
    assert account_settings["stats"]["sessions_destroyed"] == 1
    assert user_settings["stats"]["sessions_destroyed"] == 1


def test_first_run_does_not_retrust_explicitly_untrusted_old_session():
    enabled_at = datetime.now(timezone.utc)
    authorization = SimpleNamespace(
        hash=456,
        date_created=enabled_at - timedelta(days=1),
    )

    trusted_hashes = _initial_trusted_hashes(
        [authorization],
        enabled_at,
        pending_hashes=set(),
        trusted_hashes={456},
        untrusted_hashes={456},
    )

    assert 456 not in trusted_hashes


def test_first_run_still_trusts_other_preexisting_sessions():
    enabled_at = datetime.now(timezone.utc)
    authorization = SimpleNamespace(
        hash=789,
        date_created=enabled_at - timedelta(days=1),
    )

    trusted_hashes = _initial_trusted_hashes(
        [authorization],
        enabled_at,
        pending_hashes=set(),
        trusted_hashes=set(),
        untrusted_hashes={456},
    )

    assert 789 in trusted_hashes


class SessionClient:
    def __init__(self, authorizations):
        self.authorizations = authorizations

    def is_connected(self):
        return True

    async def __call__(self, _request):
        return SimpleNamespace(authorizations=self.authorizations)


def make_protection_menu(monkeypatch, authorizations):
    client = SessionClient(authorizations)
    account_id = "507f1f77bcf86cd799439011"
    account = {
        "_id": __import__("bson").ObjectId(account_id),
        "user_id": 123,
        "name": "primary",
        "is_active": True,
    }
    accounts = SimpleNamespace(
        find=lambda _query: SimpleNamespace(
            to_list=AsyncMock(return_value=[account])
        ),
        find_one=AsyncMock(return_value=account),
    )
    pending = SimpleNamespace(delete_many=AsyncMock())
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(accounts=accounts, session_destroyer_pending=pending),
    )
    menu = object.__new__(ProtectionMenu)
    menu.bot_manager = SimpleNamespace(get_client=lambda _user_id, _account: client)
    return menu, pending, account_id


def test_trust_action_only_updates_a_live_owned_session(monkeypatch):
    authorization = SimpleNamespace(hash=456, current=False)
    menu, pending, account_id = make_protection_menu(monkeypatch, [authorization])
    add_trusted = AsyncMock()
    monkeypatch.setattr(ProtectionStorage, "add_account_trusted_hash", add_trusted)

    updated = asyncio.run(menu.set_session_trust(123, account_id, 456, True))

    assert updated
    add_trusted.assert_awaited_once_with(123, account_id, 456)
    pending.delete_many.assert_awaited_once_with(
        {"user_id": 123, "account_id": account_id, "hash": 456}
    )


def test_unknown_session_hash_cannot_be_trusted(monkeypatch):
    menu, _pending, account_id = make_protection_menu(monkeypatch, [])
    add_trusted = AsyncMock()
    monkeypatch.setattr(ProtectionStorage, "add_account_trusted_hash", add_trusted)

    updated = asyncio.run(menu.set_session_trust(123, account_id, 456, True))

    assert not updated
    add_trusted.assert_not_awaited()


def test_untrust_action_removes_only_the_selected_hash(monkeypatch):
    authorization = SimpleNamespace(hash=456, current=False)
    menu, pending, account_id = make_protection_menu(monkeypatch, [authorization])
    mark_untrusted = AsyncMock()
    monkeypatch.setattr(ProtectionStorage, "add_account_untrusted_hash", mark_untrusted)
    get_settings = AsyncMock(return_value={"enabled": False})
    monkeypatch.setattr(ProtectionStorage, "get_account_settings", get_settings)

    updated = asyncio.run(menu.set_session_trust(123, account_id, 456, False))

    assert updated
    mark_untrusted.assert_awaited_once_with(123, account_id, 456)
    get_settings.assert_awaited_once_with(123, account_id)
    pending.delete_many.assert_awaited_once_with(
        {"user_id": 123, "account_id": account_id, "hash": 456}
    )


def test_sync_trusted_sessions_does_not_override_explicit_untrust(monkeypatch):
    authorizations = [
        SimpleNamespace(hash=456),
        SimpleNamespace(hash=789),
    ]
    client = SessionClient(authorizations)
    destroyer = object.__new__(SessionDestroyer)
    account_id = "507f1f77bcf86cd799439011"
    get_settings = AsyncMock(
        return_value={"trusted_hashes": [456], "untrusted_hashes": [456]}
    )
    update_settings = AsyncMock()
    monkeypatch.setattr(ProtectionStorage, "get_account_settings", get_settings)
    monkeypatch.setattr(ProtectionStorage, "update_account_settings", update_settings)

    synced = asyncio.run(destroyer.sync_trusted_sessions(123, client, account_id))

    assert synced == 1
    update_settings.assert_awaited_once_with(
        123, account_id, {"trusted_hashes": [789]}
    )


def test_watcher_terminates_explicitly_untrusted_session_on_first_run(monkeypatch):
    session_hash = 456
    enabled_at = datetime.now(timezone.utc) - timedelta(days=1)
    authorization = SimpleNamespace(
        hash=session_hash,
        current=False,
        date_created=enabled_at - timedelta(days=1),
        device_model="Untrusted device",
        ip="127.0.0.1",
        platform="Test",
        app_version="1",
        country="Test",
    )
    settings = {
        "enabled": True,
        "enabled_at": enabled_at,
        "trusted_hashes": [session_hash],
        "untrusted_hashes": [session_hash],
        "destroyed_hashes": [],
        "allow_next": True,
    }

    class Client:
        def __init__(self):
            self.reset_hashes = []

        def is_connected(self):
            return True

        async def __call__(self, request):
            if request.__class__.__name__ == "GetAuthorizationsRequest":
                return SimpleNamespace(authorizations=[authorization])
            self.reset_hashes.append(request.hash)

    client = Client()

    class Cursor:
        async def to_list(self, _length=None):
            return []

    pending = SimpleNamespace(
        find=lambda _query: Cursor(),
        update_one=AsyncMock(),
        delete_one=AsyncMock(),
        delete_many=AsyncMock(),
    )
    account_id = "507f1f77bcf86cd799439011"
    account = {
        "_id": __import__("bson").ObjectId(account_id),
        "user_id": 123,
        "name": "primary",
    }
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(
            accounts=SimpleNamespace(find_one=AsyncMock(return_value=account)),
            session_destroyer_pending=pending,
        ),
    )
    monkeypatch.setattr(
        ProtectionStorage,
        "get_account_settings",
        AsyncMock(return_value=settings),
    )
    monkeypatch.setattr(ProtectionStorage, "update_account_settings", AsyncMock())
    monkeypatch.setattr(ProtectionStorage, "add_account_destroyed_hash", AsyncMock())
    monkeypatch.setattr(
        SessionDestroyerDB, "log_destruction", AsyncMock()
    )

    destroyer = object.__new__(SessionDestroyer)
    destroyer.bot_manager = SimpleNamespace(user_clients={123: {"primary": client}})
    destroyer._get_account_client = lambda _user_id, _account: client
    destroyer.notifier = SimpleNamespace(notify_session_destroyed=AsyncMock())
    destroyer.is_shutdown = False

    original_sleep = asyncio.sleep
    sleep_calls = 0

    async def stop_after_one_detection_cycle(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls == 3:
            destroyer.is_shutdown = True
        await original_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", stop_after_one_detection_cycle)
    asyncio.run(destroyer._watcher_loop(123, account_id))

    assert client.reset_hashes == [session_hash]


def test_current_session_cannot_be_untrusted(monkeypatch):
    authorization = SimpleNamespace(hash=456, current=True)
    menu, _pending, account_id = make_protection_menu(monkeypatch, [authorization])
    get_settings = AsyncMock(return_value={"trusted_hashes": [456]})
    update_settings = AsyncMock()
    monkeypatch.setattr(ProtectionStorage, "get_account_settings", get_settings)
    monkeypatch.setattr(ProtectionStorage, "update_account_settings", update_settings)

    updated = asyncio.run(menu.set_session_trust(123, account_id, 456, False))

    assert not updated
    update_settings.assert_not_awaited()


def test_immediate_termination_never_revokes_current_session(monkeypatch):
    authorization = SimpleNamespace(hash=456, current=True)
    client = SessionClient([authorization])
    destroyer = object.__new__(SessionDestroyer)
    destroyer.bot_manager = SimpleNamespace(user_clients={123: {"primary": client}})
    account_id = "507f1f77bcf86cd799439011"
    account = {
        "_id": __import__("bson").ObjectId(account_id),
        "user_id": 123,
        "name": "primary",
    }
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(accounts=SimpleNamespace(find_one=AsyncMock(return_value=account))),
    )
    destroyer._get_account_client = lambda _user_id, _account: client

    monkeypatch.setattr(
        ProtectionStorage,
        "get_account_settings",
        AsyncMock(return_value={"enabled": True}),
    )
    add_trusted = AsyncMock()
    monkeypatch.setattr(ProtectionStorage, "add_account_trusted_hash", add_trusted)

    terminated = asyncio.run(destroyer.terminate_session(123, account_id, 456))

    assert not terminated
    add_trusted.assert_awaited_once_with(123, account_id, 456)
