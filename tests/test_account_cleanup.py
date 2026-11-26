import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bson import ObjectId

from teleguard.core.bot_manager import BotManager
from teleguard.core.mongo_database import mongodb


def test_account_cleanup_requires_both_plain_and_encrypted_sessions_to_be_missing():
    query = BotManager._accounts_missing_session_query()

    assert query == {
        "$and": [
            {
                "$or": [
                    {"session_string": {"$exists": False}},
                    {"session_string": {"$in": [None, "", False]}},
                ]
            },
            {
                "$or": [
                    {"session_string_enc": {"$exists": False}},
                    {"session_string_enc": {"$in": [None, "", False]}},
                ]
            },
        ]
    }


def _create_account_removal_manager(monkeypatch, logout_error=None):
    account_id = ObjectId()
    account = {
        "_id": account_id,
        "user_id": 123,
        "name": "primary",
        "phone": "+15551234567",
        "session_string": "session",
    }

    class Accounts:
        def __init__(self):
            self.deleted = False

        async def find_one(self, query):
            assert query == {"_id": account_id, "user_id": 123}
            return account

        async def delete_one(self, query):
            assert query == {"_id": account_id, "user_id": 123}
            self.deleted = True
            return SimpleNamespace(deleted_count=1)

    class CleanupCollection:
        def __init__(self):
            self.queries = []

        async def delete_many(self, _query):
            self.queries.append(_query)
            return SimpleNamespace(deleted_count=1)

    class Client:
        def __init__(self):
            self.logged_out = False
            self.disconnected = False

        def is_connected(self):
            return not self.disconnected

        async def __call__(self, _request):
            if logout_error:
                raise logout_error
            self.logged_out = True

        async def disconnect(self):
            self.disconnected = True

    accounts = Accounts()
    client = Client()
    otp_protections = CleanupCollection()
    manager = object.__new__(BotManager)
    manager.user_clients = {123: {"primary": client, "+15551234567": client}}
    manager._client_tg_ids = {}
    manager.activity_simulator = None
    manager.session_monitor = None
    manager.protection_manager = None
    manager.fullclient_manager = None
    manager.bot = None

    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(
            accounts=accounts,
            session_destroyer_account_settings=CleanupCollection(),
            trusted_sessions=CleanupCollection(),
            session_destroyer_logs=CleanupCollection(),
            session_destroyer_pending=CleanupCollection(),
            otp_protections=otp_protections,
            topic_mappings=CleanupCollection(),
        ),
    )
    monkeypatch.setattr(
        "teleguard.core.bot_manager.BotLogger.log_account_removed",
        AsyncMock(),
    )
    return manager, client, accounts, otp_protections, account_id


def test_account_removal_logs_out_before_deleting_and_clears_client_aliases(monkeypatch):
    manager, client, accounts, otp_protections, account_id = (
        _create_account_removal_manager(monkeypatch)
    )

    success, message = asyncio.run(manager.remove_account_by_id(123, str(account_id)))

    assert success
    assert "logout" in message
    assert client.logged_out
    assert client.disconnected
    assert accounts.deleted
    assert manager.user_clients[123] == {}
    assert otp_protections.queries == [
        {"phone": "+15551234567", "user_id": 123}
    ]


def test_account_removal_does_not_delete_when_telegram_logout_fails(monkeypatch):
    manager, client, accounts, _otp_protections, account_id = (
        _create_account_removal_manager(
            monkeypatch, logout_error=RuntimeError("Telegram unavailable")
        )
    )

    success, message = asyncio.run(manager.remove_account_by_id(123, str(account_id)))

    assert not success
    assert "logout failed" in message.lower()
    assert client.disconnected
    assert not accounts.deleted
