import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telethon.tl.functions.contacts import AddContactRequest, ImportContactsRequest

from teleguard.core.contact_models import Contact
from teleguard.core.contact_sync import ContactSync


def test_sync_to_telegram_uses_add_contact_request_for_username(monkeypatch):
    contact = Contact(
        user_id=456,
        first_name="Alex",
        last_name="Example",
        username="alex",
        managed_by_account="account",
    )
    monkeypatch.setattr(
        "teleguard.core.contact_sync.ContactDB.get_all_contacts",
        AsyncMock(return_value=[contact]),
    )
    client = AsyncMock()
    client.side_effect = [SimpleNamespace(users=[]), SimpleNamespace()]
    client.get_entity.return_value = SimpleNamespace(id=456)

    result = asyncio.run(ContactSync.sync_to_telegram(client, "account"))

    assert result["success"] is True
    assert result["added"] == 1
    request = client.await_args_list[1].args[0]
    assert isinstance(request, AddContactRequest)
    assert request.first_name == "Alex"
    assert request.last_name == "Example"


def test_sync_to_telegram_imports_phone_contacts(monkeypatch):
    contact = Contact(
        user_id=456,
        first_name="Alex",
        phone="+15551234567",
        managed_by_account="account",
    )
    monkeypatch.setattr(
        "teleguard.core.contact_sync.ContactDB.get_all_contacts",
        AsyncMock(return_value=[contact]),
    )
    client = AsyncMock()
    client.side_effect = [
        SimpleNamespace(users=[]),
        SimpleNamespace(users=[SimpleNamespace(id=456)]),
    ]

    result = asyncio.run(ContactSync.sync_to_telegram(client, "account"))

    assert result["success"] is True
    assert result["added"] == 1
    assert isinstance(client.await_args_list[1].args[0], ImportContactsRequest)
