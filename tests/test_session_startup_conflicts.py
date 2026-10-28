from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from teleguard.core.bot_manager import BotManager
from teleguard.utils.account_invalidation import AccountInvalidationHandler


def test_duplicate_auth_key_error_is_detected_as_deployment_overlap():
    assert BotManager._is_duplicate_session_error("AUTH_KEY_DUPLICATED")
    assert BotManager._is_duplicate_session_error(
        "Authorization key used from two different IP addresses simultaneously"
    )
    assert not BotManager._is_duplicate_session_error("AUTH_KEY_UNREGISTERED")


def test_duplicate_auth_key_does_not_remove_account():
    manager = SimpleNamespace(
        bot=None,
        _schedule_session_retry=Mock(),
        _notify_user_session_conflict=AsyncMock(),
    )
    handler = AccountInvalidationHandler(manager)
    handler._remove_invalidated_account = AsyncMock(return_value=True)
    handler._send_invalidation_notification = AsyncMock()

    coroutine = handler.handle_account_invalidation(
        1,
        "account",
        "+10000000000",
        "406 AUTH_KEY_DUPLICATED: authorization key used from different IP addresses simultaneously",
    )
    with pytest.raises(StopIteration):
        coroutine.send(None)

    handler._remove_invalidated_account.assert_not_awaited()
    handler._send_invalidation_notification.assert_not_awaited()
    manager._schedule_session_retry.assert_called_once_with(1, "account")
    manager._notify_user_session_conflict.assert_awaited_once()
