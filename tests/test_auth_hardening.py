import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest

from backend.auth.jwt import BOT_TOKEN, SECRET_KEY, validate_telegram_init_data
from backend.auth.telegram_auth_manager import TelegramAuthManager
from teleguard.core.config import SecurityConfig
from teleguard.core.exceptions import ConfigurationError


def _signed_init_data(user: dict) -> str:
    params = {"user": json.dumps(user, separators=(",", ":"))}
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(params.items()))
    secret_key = hmac.new(
        b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256
    ).digest()
    signature = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return urlencode({**params, "hash": signature})


def test_telegram_init_data_rejects_mock_hash():
    init_data = urlencode(
        {"user": json.dumps({"id": 123}), "hash": "mock_hash"}
    )

    assert validate_telegram_init_data(init_data) is None


def test_telegram_init_data_accepts_valid_signature():
    user = {"id": 123, "first_name": "Test"}

    assert validate_telegram_init_data(_signed_init_data(user)) == user


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
