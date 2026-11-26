import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from teleguard.handlers import auto_reply_handler
from teleguard.services.messaging_stats import MessagingStats


class Client:
    def __init__(self):
        self.handlers = []
        self.removed_handlers = []

    def is_connected(self):
        return True

    def on(self, _event_builder):
        def register(handler):
            self.handlers.append(handler)
            return handler

        return register

    def remove_event_handler(self, handler):
        self.removed_handlers.append(handler)
        if handler in self.handlers:
            self.handlers.remove(handler)


def _handler_for_client(client):
    handler = object.__new__(auto_reply_handler.AutoReplyHandler)
    handler.bot_manager = SimpleNamespace(claim_auto_reply=lambda _event: True)
    handler.user_clients = {123: {"personal": client}}
    handler.handled_clients = set()
    handler._client_handlers = {}
    handler.user_keywords = {}
    handler.pending_actions = {123: {"action": "add_keyword", "step": "message"}}
    handler.analytics = handler._new_analytics()
    handler.user_analytics = {}
    handler.last_toggle_time = {}
    handler._last_toggle_prune_at = 0.0
    handler.last_reply_time = {}
    handler._last_reply_prune_at = 0.0
    return handler


def test_replacing_client_removes_handler_from_original_client_and_cleanup_clears_state():
    original_client = Client()
    replacement_client = Client()
    handler = _handler_for_client(original_client)

    handler._setup_client_handler(123, "personal", original_client)
    old_callback = original_client.handlers[0]
    handler._setup_client_handler(123, "personal", replacement_client)

    assert original_client.removed_handlers == [old_callback]
    assert not original_client.handlers
    assert len(replacement_client.handlers) == 1
    replacement_callback = replacement_client.handlers[0]

    asyncio.run(handler.force_cleanup_user_handlers(123))

    assert replacement_client.removed_handlers == [replacement_callback]
    assert not replacement_client.handlers
    assert 123 not in handler.pending_actions


def test_reply_cooldown_cache_prunes_expired_entries():
    handler = object.__new__(auto_reply_handler.AutoReplyHandler)
    handler.last_reply_time = {
        ("old-client", 1): 1.0,
        ("active-client", 2): 9.0,
    }
    handler._last_reply_prune_at = 0.0

    handler._prune_reply_cooldowns(10.0)

    assert handler.last_reply_time == {("active-client", 2): 9.0}


def test_toggle_cooldown_cache_prunes_expired_entries():
    handler = object.__new__(auto_reply_handler.AutoReplyHandler)
    handler.last_toggle_time = {
        "deleted-account": 1.0,
        "active-account": 9.0,
    }
    handler._last_toggle_prune_at = 0.0

    handler._prune_toggle_cooldowns(10.0)

    assert handler.last_toggle_time == {"active-account": 9.0}


def test_keyword_matching_handles_punctuation_without_partial_word_matches():
    matches = auto_reply_handler.AutoReplyHandler._keyword_matches

    assert matches("#support", "need #support now")
    assert matches("hi!", "say hi!")
    assert not matches("hi!", "say hi!there")


def test_keyword_normalization_handles_legacy_dotted_mongo_paths():
    normalized = auto_reply_handler.AutoReplyHandler._normalize_keyword_map(
        {"company": {"com": "Company reply"}}
    )

    assert normalized == {"company.com": "Company reply"}


def test_keyword_callback_token_fits_telegram_limit_for_long_keywords():
    is_valid = auto_reply_handler.AutoReplyHandler._is_valid_keyword

    assert is_valid("company.com")
    assert is_valid("x" * 46)
    assert is_valid("x" * 1000)
    assert not is_valid("cash$flow")
    token = auto_reply_handler.AutoReplyHandler._keyword_callback_token("x" * 1000)
    callback_data = (
        auto_reply_handler.DELETE_KEYWORD_HASH_CALLBACK_PREFIX + token
    )
    assert len(callback_data.encode("utf-8")) <= 64
    limit_check = auto_reply_handler.AutoReplyHandler._would_exceed_keyword_limit
    assert not limit_check(
        {f"keyword-{i}": "reply" for i in range(49)}, ["another-keyword"]
    )
    assert limit_check(
        {f"keyword-{i}": "reply" for i in range(50)}, ["another-keyword"]
    )
    assert not limit_check(
        {f"keyword-{i}": "reply" for i in range(50)}, ["keyword-1"]
    )


@pytest.mark.asyncio
async def test_long_keyword_can_be_removed_using_compact_callback_token():
    keyword = "x" * 1000
    handler = object.__new__(auto_reply_handler.AutoReplyHandler)
    handler._get_user_keywords = AsyncMock(return_value={keyword: "reply"})
    handler._remove_user_keyword = AsyncMock()
    event = SimpleNamespace(edit=AsyncMock())
    callback_data = (
        auto_reply_handler.DELETE_KEYWORD_HASH_CALLBACK_PREFIX
        + handler._keyword_callback_token(keyword)
    )

    await handler._handle_delete_keyword(event, 123, callback_data)

    handler._remove_user_keyword.assert_awaited_once_with(123, keyword)


@pytest.mark.asyncio
async def test_remove_keyword_menu_paginates_legacy_large_keyword_sets():
    handler = object.__new__(auto_reply_handler.AutoReplyHandler)
    handler._get_user_keywords = AsyncMock(
        return_value={f"keyword-{i}": "reply" for i in range(45)}
    )
    event = SimpleNamespace(edit=AsyncMock())

    await handler._handle_remove_keyword_menu(event, 123, offset=40)

    buttons = event.edit.await_args.kwargs["buttons"]
    assert len(buttons) == 7


@pytest.mark.asyncio
async def test_auto_reply_metrics_are_scoped_to_the_requesting_user():
    handler = object.__new__(auto_reply_handler.AutoReplyHandler)
    handler.user_analytics = {
        111: {
            "total_messages": 8,
            "auto_replies_sent": 4,
            "unmatched_queries": 0,
            "keyword_hits": {"secret-keyword": 4},
        },
        222: {
            "total_messages": 2,
            "auto_replies_sent": 1,
            "unmatched_queries": 1,
            "keyword_hits": {"public-keyword": 1},
        },
    }
    event = SimpleNamespace(edit=AsyncMock())

    await handler._handle_analytics(event, 222)

    rendered = event.edit.await_args.args[0]
    assert "public-keyword" in rendered
    assert "secret-keyword" not in rendered
    assert "2" in rendered


@pytest.mark.asyncio
async def test_keyword_reply_sends_literal_configured_text(monkeypatch):
    client = Client()
    handler = _handler_for_client(client)
    handler.pending_actions.clear()
    handler._get_user_keywords = AsyncMock(return_value={"hello": "<b>& reply"})
    handler._get_contact_type = AsyncMock(return_value="general")
    account_collection = SimpleNamespace(
        find_one=AsyncMock(return_value={"_id": "account-id"})
    )
    settings_collection = SimpleNamespace(
        find_one=AsyncMock(return_value={"keyword_replies_enabled": True})
    )
    monkeypatch.setattr(
        auto_reply_handler,
        "mongodb",
        SimpleNamespace(
            db=SimpleNamespace(
                accounts=account_collection,
                auto_reply_settings=settings_collection,
            )
        ),
    )
    monkeypatch.setattr(
        auto_reply_handler,
        "DataEncryption",
        SimpleNamespace(
            encrypt_field=lambda value: value,
            decrypt_account_data=lambda _account: {"auto_reply_enabled": True},
        ),
    )
    monkeypatch.setattr(
        MessagingStats, "record_auto_reply", AsyncMock(return_value=None)
    )
    event = SimpleNamespace(
        message=SimpleNamespace(text="hello"),
        sender_id=456,
        id=789,
        client=client,
        chat_id=456,
        get_sender=AsyncMock(return_value=SimpleNamespace(bot=False, username=None)),
        reply=AsyncMock(),
    )
    handler._setup_client_handler(123, "personal", client)

    await client.handlers[0](event)

    event.reply.assert_awaited_once_with("<b>& reply", parse_mode=None)
    assert handler.user_analytics[123]["auto_replies_sent"] == 1


@pytest.mark.asyncio
async def test_non_text_message_does_not_break_keyword_input(monkeypatch):
    registered = []

    class Bot:
        def on(self, _event_builder):
            def register(callback):
                registered.append(callback)
                return callback

            return register

    handler = object.__new__(auto_reply_handler.AutoReplyHandler)
    handler.bot = Bot()
    handler.pending_actions = {
        123: {"action": "add_keyword", "step": "keyword"}
    }
    handler.setup_text_handler()
    event = SimpleNamespace(
        sender_id=123,
        message=SimpleNamespace(text=None),
        reply=AsyncMock(),
    )

    await registered[-1](event)

    assert handler.pending_actions[123]["step"] == "keyword"
    event.reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_keyword_input_rejects_additions_over_the_user_limit():
    registered = []

    class Bot:
        def on(self, _event_builder):
            def register(callback):
                registered.append(callback)
                return callback

            return register

    handler = object.__new__(auto_reply_handler.AutoReplyHandler)
    handler.bot = Bot()
    handler.pending_actions = {
        123: {"action": "add_keyword", "step": "keyword"}
    }
    handler._get_user_keywords = AsyncMock(
        return_value={f"existing-{i}": "reply" for i in range(50)}
    )
    handler.setup_text_handler()
    event = SimpleNamespace(
        sender_id=123,
        message=SimpleNamespace(text="another keyword"),
        reply=AsyncMock(),
    )

    await registered[-1](event)

    assert handler.pending_actions[123]["step"] == "keyword"
    assert "up to 50" in event.reply.await_args.args[0]


@pytest.mark.asyncio
async def test_global_auto_reply_disable_removes_encrypted_and_legacy_flags(monkeypatch):
    accounts = SimpleNamespace(update_many=AsyncMock())
    monkeypatch.setattr(
        auto_reply_handler,
        "mongodb",
        SimpleNamespace(db=SimpleNamespace(accounts=accounts)),
    )
    handler = object.__new__(auto_reply_handler.AutoReplyHandler)

    await handler._disable_user_auto_reply(123)

    accounts.update_many.assert_awaited_once_with(
        {"user_id": 123},
        {
            "$unset": {
                "auto_reply_enabled_enc": "",
                "auto_reply_enabled": "",
            }
        },
    )


@pytest.mark.asyncio
async def test_reenabling_auto_reply_registers_handler_after_cleanup(monkeypatch):
    client = Client()
    handler = _handler_for_client(client)
    accounts = SimpleNamespace(
        find_one=AsyncMock(
            return_value={"_id": "account-id", "name_enc": "personal"}
        ),
        update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)),
        find=lambda _query: SimpleNamespace(
            to_list=AsyncMock(
                return_value=[
                    {"_id": "account-id", "name_enc": "personal"}
                ]
            )
        ),
    )
    monkeypatch.setattr(
        auto_reply_handler,
        "mongodb",
        SimpleNamespace(db=SimpleNamespace(accounts=accounts)),
    )
    monkeypatch.setattr(
        auto_reply_handler,
        "DataEncryption",
        SimpleNamespace(
            encrypt_field=lambda value: value,
            decrypt_account_data=lambda _account: {
                "name": "personal",
                "auto_reply_enabled": False,
            },
        ),
    )
    event = SimpleNamespace(answer=AsyncMock(), edit=AsyncMock())

    await handler._handle_toggle_account(
        event, 123, "auto_reply:toggle_account:personal"
    )

    assert len(client.handlers) == 1
    event.answer.assert_awaited_once_with("Auto-reply 🟢 enabled for personal!")
