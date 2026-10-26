from types import SimpleNamespace

from teleguard.handlers.menu_modules.menu_handlers import MenuHandlers


def test_otp_coverage_excludes_accounts_with_active_temporary_bypass():
    accounts = [
        {"_id": "protected", "otp_destroyer_enabled": True},
        {"_id": "bypassed", "otp_destroyer_enabled": True},
        {"_id": "unprotected", "otp_destroyer_enabled": False},
    ]

    assert MenuHandlers._otp_coverage(accounts, {"bypassed"}) == 33


def test_temporary_bypass_requires_valid_unexpired_flag():
    now = 1000

    assert MenuHandlers._is_temp_bypass_active(
        {"otp_temp_passthrough": True, "temp_passthrough_expiry": "1001"}, now
    )
    assert not MenuHandlers._is_temp_bypass_active(
        {"otp_temp_passthrough": True, "temp_passthrough_expiry": "1000"}, now
    )
    assert not MenuHandlers._is_temp_bypass_active(
        {"otp_temp_passthrough": True, "temp_passthrough_expiry": "invalid"}, now
    )
    assert not MenuHandlers._is_temp_bypass_active(
        {"otp_temp_passthrough": False, "temp_passthrough_expiry": "1001"}, now
    )


def test_cleanup_account_must_be_active_and_connected():
    connected_client = SimpleNamespace(is_connected=lambda: True)
    disconnected_client = SimpleNamespace(is_connected=lambda: False)
    manager = SimpleNamespace(
        account_manager=SimpleNamespace(
            user_clients={
                7: {
                    "connected": connected_client,
                    "disconnected": disconnected_client,
                }
            }
        )
    )
    handlers = MenuHandlers(manager)

    assert handlers._is_cleanup_account_available(
        7, {"name": "connected", "is_active": True}
    )
    assert not handlers._is_cleanup_account_available(
        7, {"name": "disconnected", "is_active": True}
    )
    assert not handlers._is_cleanup_account_available(
        7, {"name": "connected", "is_active": False}
    )
