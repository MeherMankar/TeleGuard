import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from bson import ObjectId
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pymongo.errors import DuplicateKeyError
from starlette.requests import Request
from starlette.responses import Response

import backend.auth.jwt as jwt_auth
from backend.api.auth_router import logout
from backend.auth.jwt import (
    BOT_TOKEN,
    SECRET_KEY,
    consume_telegram_init_data,
    validate_telegram_init_data,
)
from backend.auth.telegram_auth_manager import TelegramAuthManager
from teleguard.core.config import SecurityConfig
from teleguard.core.exceptions import ConfigurationError
from teleguard.core.mongo_database import mongodb


def _signed_init_data(user: dict, auth_date: int | None = None) -> str:
    params = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "user": json.dumps(user, separators=(",", ":")),
    }
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )
    secret_key = hmac.new(
        b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256
    ).digest()
    signature = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return urlencode({**params, "hash": signature})


def test_telegram_init_data_rejects_mock_hash():
    init_data = urlencode({"user": json.dumps({"id": 123}), "hash": "mock_hash"})

    assert validate_telegram_init_data(init_data) is None


def test_telegram_init_data_accepts_valid_signature():
    user = {"id": 123, "first_name": "Test"}

    assert validate_telegram_init_data(_signed_init_data(user)) == user


@pytest.mark.parametrize(
    "auth_date",
    [int(time.time()) - 25 * 60 * 60, int(time.time()) + 60],
)
def test_telegram_init_data_rejects_stale_or_future_auth_date(auth_date):
    assert (
        validate_telegram_init_data(_signed_init_data({"id": 123}, auth_date)) is None
    )


def test_telegram_init_data_requires_auth_date():
    params = {"user": json.dumps({"id": 123}, separators=(",", ":"))}
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )
    secret_key = hmac.new(
        b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256
    ).digest()
    signature = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    assert validate_telegram_init_data(urlencode({**params, "hash": signature})) is None


@pytest.mark.asyncio
async def test_telegram_init_data_can_only_be_consumed_once(monkeypatch):
    class ReplayCollection:
        def __init__(self):
            self.used_ids = set()

        async def insert_one(self, document):
            if document["_id"] in self.used_ids:
                raise DuplicateKeyError("Duplicate Telegram init data")
            self.used_ids.add(document["_id"])

    monkeypatch.setattr(
        jwt_auth.mongodb,
        "db",
        SimpleNamespace(telegram_init_data_replays=ReplayCollection()),
    )
    init_data = _signed_init_data({"id": 123})

    assert await consume_telegram_init_data(init_data)
    assert not await consume_telegram_init_data(init_data)


def test_jwt_secret_is_not_the_previous_fallback():
    assert SECRET_KEY != "teleguard_super_secret_jwt_key_change_in_production"
    assert len(SECRET_KEY) >= 32


def test_jwt_secret_must_meet_minimum_length():
    with pytest.raises(ConfigurationError, match="JWT_SECRET"):
        SecurityConfig(jwt_secret="too-short")


def test_login_session_is_only_available_to_its_owner():
    manager = object.__new__(TelegramAuthManager)
    manager.pending_logins = {
        "session": {"user_id": 1, "client": object(), "status": "pending"}
    }

    with pytest.raises(ValueError, match="Invalid or expired session_id"):
        manager._get_login_data("session", user_id=2)

    assert manager._get_login_data("session", user_id=1)["user_id"] == 1


@pytest.mark.asyncio
async def test_revoked_access_token_is_rejected(monkeypatch):
    class RevokedTokens:
        def __init__(self):
            self.documents = {}

        async def find_one(self, query):
            return self.documents.get(query["_id"])

        async def update_one(self, query, update, upsert=False):
            self.documents.setdefault(
                query["_id"],
                {"_id": query["_id"], **update["$setOnInsert"]},
            )

    collection = RevokedTokens()
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(revoked_tokens=collection),
    )
    token = jwt_auth.create_access_token({"user_id": 123})
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [],
            "server": ("test", 80),
            "client": ("test", 1),
            "scheme": "http",
        }
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    assert await jwt_auth.get_current_user_id(request, credentials) == 123
    assert await jwt_auth.revoke_access_token(token)
    with pytest.raises(HTTPException) as error:
        await jwt_auth.get_current_user_id(request, credentials)
    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_cookie_token(monkeypatch):
    class RevokedTokens:
        def __init__(self):
            self.documents = {}

        async def find_one(self, query):
            return self.documents.get(query["_id"])

        async def update_one(self, query, update, upsert=False):
            self.documents.setdefault(
                query["_id"],
                {"_id": query["_id"], **update["$setOnInsert"]},
            )

    collection = RevokedTokens()
    monkeypatch.setattr(mongodb, "db", SimpleNamespace(revoked_tokens=collection))
    token = jwt_auth.create_access_token({"user_id": 123})
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/logout",
            "query_string": b"",
            "headers": [(b"cookie", f"access_token={token}".encode())],
            "server": ("test", 80),
            "client": ("test", 1),
            "scheme": "http",
        }
    )
    response = Response()

    assert await logout(request, response) == {"status": "success"}
    assert "access_token=" in response.headers["set-cookie"]
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    auth_request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [],
            "server": ("test", 80),
            "client": ("test", 1),
            "scheme": "http",
        }
    )
    with pytest.raises(HTTPException) as error:
        await jwt_auth.get_current_user_id(auth_request, credentials)
    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_twofa_password_storage_reads_and_removes_encrypted_field(monkeypatch):
    from teleguard.utils import crypto_utils

    class Accounts:
        def __init__(self):
            self.account = {
                "_id": ObjectId(),
                "user_id": 123,
                "phone": "+123456789",
            }

        async def find_one(self, query):
            if (
                query.get("_id") == self.account["_id"]
                and query.get("user_id") == self.account["user_id"]
            ) or (
                query.get("phone") == self.account["phone"]
                and query.get("user_id") == self.account["user_id"]
            ):
                return self.account.copy()
            return None

        async def update_one(self, query, update):
            if query.get("_id") != self.account["_id"]:
                return SimpleNamespace(matched_count=0)
            self.account.update(update.get("$set", {}))
            for key in update.get("$unset", {}):
                self.account.pop(key, None)
            return SimpleNamespace(matched_count=1)

    accounts = Accounts()
    monkeypatch.setattr(mongodb, "db", SimpleNamespace(accounts=accounts))
    monkeypatch.setattr(
        crypto_utils.DataEncryption,
        "encrypt_field",
        staticmethod(lambda value: f"encrypted:{value}"),
    )
    monkeypatch.setattr(
        crypto_utils.DataEncryption,
        "decrypt_field",
        staticmethod(lambda value: value.removeprefix("encrypted:")),
    )

    account_id = str(accounts.account["_id"])
    await mongodb.store_2fa_password(123, account_id, "secret")
    assert accounts.account["twofa_password_enc"] == "encrypted:secret"
    assert await mongodb.get_2fa_password(123, account_id) == "secret"
    assert await mongodb.get_2fa_password_by_phone(123, "+123456789") == "secret"
    assert await mongodb.remove_2fa_password(123, account_id)
    assert "twofa_password_enc" not in accounts.account
