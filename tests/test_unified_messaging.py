from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from teleguard.core.mongo_database import mongodb
from teleguard.handlers.unified_messaging import UnifiedMessagingSystem


def test_otp_destroyer_stops_duplicate_service_message_forward(monkeypatch):
    protection_manager = SimpleNamespace(
        _is_login_code=lambda text: "login code" in text.lower(),
        _has_active_otp_auth_flow=lambda _user_id, _phone: False,
    )
    manager = object.__new__(UnifiedMessagingSystem)
    manager.bot_manager = SimpleNamespace(protection_manager=protection_manager)
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(
            accounts=SimpleNamespace(
                find_one=AsyncMock(
                    return_value={
                        "phone": "+15551234567",
                        "otp_destroyer_enabled": True,
                        "otp_forward_enabled": False,
                    }
                )
            )
        ),
    )

    check = manager._should_forward_telegram_service_message(
        123,
        "primary",
        "Login code: 54268. Do not give this code to anyone.",
    )
    with pytest.raises(StopIteration) as result:
        check.send(None)

    assert result.value.value is False


def test_active_auth_flow_can_receive_its_own_login_code(monkeypatch):
    protection_manager = SimpleNamespace(
        _is_login_code=lambda text: "login code" in text.lower(),
        _has_active_otp_auth_flow=lambda _user_id, _phone: True,
    )
    manager = object.__new__(UnifiedMessagingSystem)
    manager.bot_manager = SimpleNamespace(protection_manager=protection_manager)
    monkeypatch.setattr(
        mongodb,
        "db",
        SimpleNamespace(
            accounts=SimpleNamespace(
                find_one=AsyncMock(
                    return_value={
                        "phone": "+15551234567",
                        "otp_destroyer_enabled": True,
                    }
                )
            )
        ),
    )

    check = manager._should_forward_telegram_service_message(
        123, "primary", "Login code: 54268."
    )
    with pytest.raises(StopIteration) as result:
        check.send(None)

    assert result.value.value is True
