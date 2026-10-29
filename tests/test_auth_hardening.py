import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from pymongo.errors import DuplicateKeyError

import backend.auth.jwt as jwt_auth
from backend.auth.jwt import (
    BOT_TOKEN,
    SECRET_KEY,
    consume_telegram_init_data,
    validate_telegram_init_data,
)
from backend.auth.telegram_auth_manager import TelegramAuthManager
from teleguard.core.config import SecurityConfig
from teleguard.core.exceptions import ConfigurationError


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
