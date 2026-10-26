import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from teleguard.core.session_destroyer import _session_existed_when_protection_enabled
from teleguard.core.mongo_database import mongodb
from teleguard.handlers.protection_menu import ProtectionMenu
from teleguard.services.protection_storage import ProtectionStorage


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
    menu, _pending = make_protection_menu(monkeypatch, [authorization])
    get_settings = AsyncMock(return_value={"trusted_hashes": [456, 789]})
    update_settings = AsyncMock()
    monkeypatch.setattr(ProtectionStorage, "get_settings", get_settings)
    monkeypatch.setattr(ProtectionStorage, "update_settings", update_settings)

    updated = asyncio.run(menu.set_session_trust(123, 456, False))

    assert updated
    update_settings.assert_awaited_once_with(123, {"trusted_hashes": [789]})


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
