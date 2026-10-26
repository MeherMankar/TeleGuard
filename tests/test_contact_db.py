import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from teleguard.core import contact_db


def test_update_contact_succeeds_when_record_matches_without_changes(monkeypatch):
    contacts = SimpleNamespace(
        update_one=AsyncMock(
            return_value=SimpleNamespace(matched_count=1, modified_count=0)
        )
    )
    monkeypatch.setattr(
        contact_db,
        "mongodb",
        SimpleNamespace(db=SimpleNamespace(contacts=contacts)),
    )

    result = asyncio.run(
        contact_db.ContactDB.update_contact(456, "account", {"notes": "same"})
    )

    assert result is True
