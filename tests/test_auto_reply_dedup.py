from types import SimpleNamespace

from teleguard.core.bot_manager import BotManager


def test_auto_reply_claim_is_unique_per_message_and_client():
    manager = object.__new__(BotManager)
    manager._auto_reply_claims = {}
    client = object()
    event = SimpleNamespace(client=client, chat_id=456, id=789)

    assert manager.claim_auto_reply(event)
    assert not manager.claim_auto_reply(event)
    assert manager.claim_auto_reply(
        SimpleNamespace(client=client, chat_id=456, id=790)
    )
    assert manager.claim_auto_reply(
        SimpleNamespace(client=object(), chat_id=456, id=789)
    )


def test_auto_reply_claim_fails_closed_without_message_identity(caplog):
    manager = object.__new__(BotManager)
    manager._auto_reply_claims = {}

    assert not manager.claim_auto_reply(SimpleNamespace())
    assert "Cannot deduplicate auto-reply without message identity" in caplog.text
