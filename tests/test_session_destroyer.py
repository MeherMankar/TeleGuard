import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from teleguard.core.session_destroyer import (
    SessionDestroyer,
    _initial_trusted_hashes,
    _session_existed_when_protection_enabled,
)
from teleguard.core.mongo_database import mongodb
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
    account = {"_id": "account", "user_id": 123, "name": "primary"}
    accounts = SimpleNamespace(
        find=lambda _query: SimpleNamespace(
            to_list=AsyncMock(return_value=[account])
        )
    )
    pending = SimpleNamespace(delete_many=AsyncMock())
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(accounts=accounts, session_destroyer_pending=pending),
    )
    menu = object.__new__(ProtectionMenu)
    menu.bot_manager = SimpleNamespace(get_client=lambda _user_id, _account: client)
    return menu, pending


def test_trust_action_only_updates_a_live_owned_session(monkeypatch):
    authorization = SimpleNamespace(hash=456, current=False)
    menu, pending = make_protection_menu(monkeypatch, [authorization])
    add_trusted = AsyncMock()
    monkeypatch.setattr(ProtectionStorage, "add_trusted_hash", add_trusted)

    updated = asyncio.run(menu.set_session_trust(123, 456, True))

    assert updated
    add_trusted.assert_awaited_once_with(123, 456)
    pending.delete_many.assert_awaited_once_with({"user_id": 123, "hash": 456})


def test_unknown_session_hash_cannot_be_trusted(monkeypatch):
    menu, _pending = make_protection_menu(monkeypatch, [])
    add_trusted = AsyncMock()
    monkeypatch.setattr(ProtectionStorage, "add_trusted_hash", add_trusted)

    updated = asyncio.run(menu.set_session_trust(123, 456, True))

    assert not updated
    add_trusted.assert_not_awaited()


def test_untrust_action_removes_only_the_selected_hash(monkeypatch):
    authorization = SimpleNamespace(hash=456, current=False)
    menu, pending = make_protection_menu(monkeypatch, [authorization])
    mark_untrusted = AsyncMock()
    monkeypatch.setattr(ProtectionStorage, "add_untrusted_hash", mark_untrusted)

    updated = asyncio.run(menu.set_session_trust(123, 456, False))

    assert updated
    mark_untrusted.assert_awaited_once_with(123, 456)
    pending.delete_many.assert_awaited_once_with({"user_id": 123, "hash": 456})


def test_sync_trusted_sessions_does_not_override_explicit_untrust(monkeypatch):
    authorizations = [
        SimpleNamespace(hash=456),
        SimpleNamespace(hash=789),
    ]
    client = SessionClient(authorizations)
    destroyer = object.__new__(SessionDestroyer)
    get_settings = AsyncMock(
        return_value={
            "trusted_hashes": [456],
            "untrusted_hashes": [456],
        }
    )
    update_settings = AsyncMock()
    monkeypatch.setattr(ProtectionStorage, "get_settings", get_settings)
    monkeypatch.setattr(ProtectionStorage, "update_settings", update_settings)

    synced = asyncio.run(destroyer.sync_trusted_sessions(123, client))

    assert synced == 1
    update_settings.assert_awaited_once_with(
        123, {"trusted_hashes": [789]}
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
        "session_destroyer_enabled": True,
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
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(session_destroyer_pending=pending),
    )
    monkeypatch.setattr(
        ProtectionStorage,
        "get_settings",
        AsyncMock(return_value=settings),
    )
    monkeypatch.setattr(ProtectionStorage, "update_settings", AsyncMock())
    monkeypatch.setattr(ProtectionStorage, "add_destroyed_hash", AsyncMock())
    monkeypatch.setattr(
        SessionDestroyerDB, "log_destruction", AsyncMock()
    )

    destroyer = object.__new__(SessionDestroyer)
    destroyer.bot_manager = SimpleNamespace(user_clients={123: {"primary": client}})
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
    asyncio.run(destroyer._watcher_loop(123))

    assert client.reset_hashes == [session_hash]


def test_current_session_cannot_be_untrusted(monkeypatch):
    authorization = SimpleNamespace(hash=456, current=True)
    menu, _pending = make_protection_menu(monkeypatch, [authorization])
    get_settings = AsyncMock(return_value={"trusted_hashes": [456]})
    update_settings = AsyncMock()
    monkeypatch.setattr(ProtectionStorage, "get_settings", get_settings)
    monkeypatch.setattr(ProtectionStorage, "update_settings", update_settings)

    updated = asyncio.run(menu.set_session_trust(123, 456, False))

    assert not updated
    update_settings.assert_not_awaited()
