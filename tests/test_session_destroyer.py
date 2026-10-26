from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from teleguard.core.session_destroyer import _session_existed_when_protection_enabled


def test_recently_used_old_session_is_trusted_after_restart():
    enabled_at = datetime.now(timezone.utc)
    auth = SimpleNamespace(
        date_created=enabled_at - timedelta(days=30),
        date_active=enabled_at + timedelta(days=1),
    )

    assert _session_existed_when_protection_enabled(auth, enabled_at)


def test_session_created_after_protection_was_enabled_is_not_trusted():
    enabled_at = datetime.now(timezone.utc)
    auth = SimpleNamespace(date_created=enabled_at + timedelta(seconds=1))

    assert not _session_existed_when_protection_enabled(auth, enabled_at)


def test_session_without_creation_timestamp_is_trusted_safely():
    enabled_at = datetime.now(timezone.utc)
    auth = SimpleNamespace(date_active=enabled_at + timedelta(days=1))

    assert _session_existed_when_protection_enabled(auth, enabled_at)
