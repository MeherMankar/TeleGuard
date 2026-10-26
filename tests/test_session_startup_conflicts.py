from teleguard.core.bot_manager import BotManager


def test_duplicate_auth_key_error_is_detected_as_deployment_overlap():
    assert BotManager._is_duplicate_session_error("AUTH_KEY_DUPLICATED")
    assert BotManager._is_duplicate_session_error(
        "Authorization key used from two different IP addresses simultaneously"
    )
    assert not BotManager._is_duplicate_session_error("AUTH_KEY_UNREGISTERED")
