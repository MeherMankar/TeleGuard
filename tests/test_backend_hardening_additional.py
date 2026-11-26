import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
from starlette.websockets import WebSocketDisconnect

from backend.api import accounts, messaging
from backend.api.account_client_resolver import resolve_account_client
from backend.auth.telegram_auth_manager import (
    LoginCapacityError,
    TelegramAuthManager,
)
from teleguard.core.mongo_database import MongoDB
from teleguard.core.otp_protection import otp_expiry_fields
from teleguard.core.proxy_manager import ProxyManager
from teleguard.sync import session_destroyer_db
from teleguard.sync.session_destroyer_db import SessionDestroyerDB
from backend import main as backend_main


def test_account_client_resolution_requires_unique_exact_alias():
    primary = object()
    clients = {
        "Main Account": primary,
        "+1 555 123 4567": primary,
        "Secondary": object(),
    }

    assert resolve_account_client(clients, "mainaccount") is primary
    assert resolve_account_client(clients, "main") is None


def test_account_client_resolution_rejects_ambiguous_normalized_aliases():
    with pytest.raises(ValueError, match="more than one"):
        resolve_account_client(
            {
                "Main Account": object(),
                "MainAccount": object(),
            },
            "main account",
        )


@pytest.mark.asyncio
async def test_account_list_redacts_otp_audit_values_and_caps_history(monkeypatch):
    class Cursor:
        async def to_list(self, length=None):
            return [document]

    class Accounts:
        def find(self, query, projection):
            assert query == {"user_id": 123}
            assert projection["session_string_enc"] == 0
            assert projection["twofa_password_enc"] == 0
            return Cursor()

    document = {
        "_id": ObjectId(),
        "user_id": 123,
        "name": "primary",
        "twofa_password_hash": "hashed-secret",
        "audit_log": [
            {
                "action": "otp_forwarded",
                "code": str(index),
                "details": {"otp_code": str(index)},
            }
            for index in range(205)
        ],
    }
    monkeypatch.setattr(accounts.mongodb, "db", SimpleNamespace(accounts=Accounts()))

    result = await accounts.list_accounts(user_id=123)

    assert len(result[0]["audit_log"]) == 200
    assert "twofa_password_hash" not in result[0]
    assert all(
        "code" not in entry and "otp_code" not in entry["details"]
        for entry in result[0]["audit_log"]
    )


def test_otp_expiry_fields_include_ttl_datetime():
    expiry = int(time.time()) + 60

    fields = otp_expiry_fields(expiry)

    assert fields["expires_at"] == expiry
    assert fields["expires_at_dt"].timestamp() == expiry


@pytest.mark.asyncio
async def test_account_audit_writer_redacts_nested_secrets_and_caps_entries(monkeypatch):
    collection = SimpleNamespace(update_one=AsyncMock())
    database = MongoDB()
    database.db = SimpleNamespace(accounts=collection)

    await database.append_account_audit_log(
        {"user_id": 123},
        {"action": "otp", "details": {"code": "12345", "safe": "value"}},
    )

    update = collection.update_one.await_args.args[1]
    audit_entry = update["$push"]["audit_log"]["$each"][0]
    assert audit_entry == {"action": "otp", "details": {"safe": "value"}}
    assert update["$push"]["audit_log"]["$slice"] == -200


@pytest.mark.asyncio
async def test_account_audit_migration_redacts_legacy_nested_secrets():
    document = {
        "_id": ObjectId(),
        "audit_log": [
            {"action": "otp", "details": {"code": "12345", "safe": "value"}}
        ],
    }

    class Cursor:
        def __aiter__(self):
            self.returned = False
            return self

        async def __anext__(self):
            if self.returned:
                raise StopAsyncIteration
            self.returned = True
            return document

    accounts_collection = SimpleNamespace(
        find=Mock(return_value=Cursor()),
        update_one=AsyncMock(),
    )
    database = MongoDB()
    database.client = object()
    database.db = SimpleNamespace(accounts=accounts_collection)

    await database._migrate_account_audit_logs()

    update = accounts_collection.update_one.await_args.args[1]
    assert update["$set"]["audit_log"] == [
        {"action": "otp", "details": {"safe": "value"}}
    ]


@pytest.mark.asyncio
async def test_login_attempt_rate_limit_and_absolute_qr_expiry():
    manager = TelegramAuthManager()
    for _ in range(5):
        await manager._reserve_login_slot(123)
        await manager._release_login_slot(123)

    with pytest.raises(LoginCapacityError, match="Too many login attempts"):
        await manager._reserve_login_slot(123)

    created_at = time.monotonic() - 10
    manager.pending_logins["qr"] = {
        "user_id": 456,
        "client": object(),
        "status": "pending",
        "created_at_monotonic": created_at,
    }

    assert await manager.get_qr_status(456, "qr") == {"status": "pending"}
    assert manager.pending_logins["qr"]["created_at_monotonic"] == created_at


@pytest.mark.asyncio
async def test_failed_qr_sessions_still_count_toward_global_memory_cap():
    manager = TelegramAuthManager()
    manager.pending_logins = {
        str(index): {"user_id": index, "status": "failed"}
        for index in range(200)
    }

    with pytest.raises(LoginCapacityError, match="capacity"):
        await manager._reserve_login_slot(999)


@pytest.mark.asyncio
async def test_proxy_resolution_rejects_non_public_addresses():
    with pytest.raises(ValueError, match="public IP"):
        await ProxyManager.resolve_public_proxy_server("127.0.0.1", 443)
    with pytest.raises(ValueError, match="public IP"):
        await ProxyManager.resolve_public_proxy_server("169.254.10.2", 443)

    assert await ProxyManager.resolve_public_proxy_server("8.8.8.8", 443) == "8.8.8.8"


@pytest.mark.asyncio
async def test_mongodb_disconnect_clears_client_for_reconnect():
    client = SimpleNamespace(close=Mock())
    database = MongoDB()
    database.client = client
    database.db = object()

    await database.disconnect()

    client.close.assert_called_once_with()
    assert database.client is None
    assert database.db is None


@pytest.mark.asyncio
async def test_mongodb_refuses_startup_when_otp_ttl_index_cannot_be_created():
    class Collection:
        def __init__(self, name):
            self.name = name

        async def create_index(self, *_args, **_kwargs):
            if self.name == "otp_protections":
                raise RuntimeError("index unavailable")

    class Database:
        def __getattr__(self, name):
            return Collection(name)

    database = MongoDB()
    database.db = Database()

    with pytest.raises(RuntimeError, match="MongoDB index initialization failed"):
        await database._create_indexes()


@pytest.mark.asyncio
async def test_messaging_stats_reports_unavailable_manager(monkeypatch):
    monkeypatch.setattr(messaging, "_get_bot_manager", lambda: None)

    with pytest.raises(HTTPException) as error:
        await messaging.get_stats(user_id=123)

    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_account_remove_api_delegates_to_complete_logout_path(monkeypatch):
    account_id = ObjectId()
    accounts_collection = SimpleNamespace(
        find_one=AsyncMock(
            return_value={
                "_id": account_id,
                "user_id": 123,
                "name": "primary",
            }
        ),
        delete_one=AsyncMock(),
    )
    manager = SimpleNamespace(
        remove_account_by_id=AsyncMock(return_value=(True, "removed"))
    )
    monkeypatch.setattr(accounts.mongodb, "db", SimpleNamespace(accounts=accounts_collection))
    monkeypatch.setattr(accounts, "_get_bot_manager", lambda: manager)
    monkeypatch.setattr(
        accounts.ws_manager, "send_personal_message", AsyncMock()
    )

    result = await accounts.remove_account(str(account_id), user_id=123)

    assert result == {"status": "success"}
    manager.remove_account_by_id.assert_awaited_once_with(123, str(account_id))
    accounts_collection.delete_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_websocket_closes_after_token_is_revoked(monkeypatch):
    websocket = SimpleNamespace(
        headers={"origin": "http://localhost:5173"},
        cookies={"access_token": "token"},
        receive_text=AsyncMock(
            side_effect=["ping", WebSocketDisconnect(code=1000)]
        ),
        send_text=AsyncMock(),
        close=AsyncMock(),
    )
    monkeypatch.setattr(backend_main, "ALLOWED_ORIGINS", ["http://localhost:5173"])
    monkeypatch.setattr(
        backend_main,
        "_decode_websocket_identity",
        AsyncMock(side_effect=[(123, "jti"), None]),
    )
    monkeypatch.setattr(backend_main.ws_manager, "connect", AsyncMock())
    monkeypatch.setattr(backend_main.ws_manager, "disconnect", Mock())
    monkeypatch.setattr(
        backend_main,
        "time",
        SimpleNamespace(monotonic=Mock(side_effect=[100.0, 131.0])),
    )

    await backend_main.websocket_events(websocket)

    websocket.close.assert_awaited_once_with(code=4001)
    assert backend_main._decode_websocket_identity.await_count == 2
    backend_main.ws_manager.disconnect.assert_called_once_with(123, websocket)


@pytest.mark.asyncio
async def test_session_destruction_log_storage_failure_is_reported(monkeypatch):
    collection = SimpleNamespace(insert_one=AsyncMock(side_effect=RuntimeError("db down")))
    monkeypatch.setattr(
        session_destroyer_db,
        "mongodb",
        SimpleNamespace(db=SimpleNamespace(session_destroyer_logs=collection)),
    )

    with pytest.raises(RuntimeError, match="db down"):
        await SessionDestroyerDB.log_destruction(123, "account", {})


@pytest.mark.asyncio
async def test_trusted_session_hash_insert_handles_duplicate_concurrent_creation(
    monkeypatch,
):
    collection = SimpleNamespace(
        update_one=AsyncMock(side_effect=[DuplicateKeyError("race"), None])
    )
    monkeypatch.setattr(
        session_destroyer_db,
        "mongodb",
        SimpleNamespace(db=SimpleNamespace(trusted_sessions=collection)),
    )

    await SessionDestroyerDB.add_trusted_hash(123, "account", 456)

    assert collection.update_one.await_count == 2
    _, bounded_update = collection.update_one.await_args.args[:2]
    assert "$slice" in bounded_update["$push"]["hashes"]
