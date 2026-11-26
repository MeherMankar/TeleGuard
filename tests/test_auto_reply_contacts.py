import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from teleguard.handlers import auto_reply_handler


def test_contact_type_lookup_uses_saved_contact_fields_and_account_scope(monkeypatch):
    contacts = SimpleNamespace(
        find_one=AsyncMock(return_value={"type": "family"})
    )
    monkeypatch.setattr(
        auto_reply_handler,
        "mongodb",
        SimpleNamespace(db=SimpleNamespace(contacts=contacts)),
    )
    handler = object.__new__(auto_reply_handler.AutoReplyHandler)

    contact_type = asyncio.run(handler._get_contact_type(456, "personal"))

    assert contact_type == "family"
    contacts.find_one.assert_awaited_once_with(
        {"user_id": 456, "managed_by_account": "personal"}
    )


def test_contact_type_lookup_supports_contact_tags(monkeypatch):
    contacts = SimpleNamespace(
        find_one=AsyncMock(return_value={"tags": ["friend", "Work"]})
    )
    monkeypatch.setattr(
        auto_reply_handler,
        "mongodb",
        SimpleNamespace(db=SimpleNamespace(contacts=contacts)),
    )
    handler = object.__new__(auto_reply_handler.AutoReplyHandler)

    assert asyncio.run(handler._get_contact_type(456, "personal")) == "work"
