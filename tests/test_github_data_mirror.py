import base64
import json
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

import teleguard.utils.github_data_mirror as github_data_mirror
from teleguard.core.config import ConfigManager
from teleguard.utils.github_data_mirror import GitHubDataMirror


@pytest.fixture
def mirror(monkeypatch):
    key = Fernet.generate_key()
    cipher = Fernet(key)
    monkeypatch.setattr(github_data_mirror, "FERNET", cipher)

    instance = object.__new__(GitHubDataMirror)
    instance._key = key
    instance.root_path = "teleguard-data/v1"
    return instance, cipher


def test_prepare_records_encrypts_documents_and_uses_opaque_ids(mirror):
    instance, cipher = mirror
    user = {
        "telegram_id": 123456789,
        "phone": "+15555550123",
        "session": "private-session-value",
    }

    records = instance._prepare_records("users", [user])

    assert len(records) == 1
    record_id, (content, _) = next(iter(records.items()))
    assert len(record_id) == 64
    assert record_id != str(user["telegram_id"])
    envelope = json.loads(content)
    assert envelope["encrypted"] is True
    decrypted = json.loads(cipher.decrypt(envelope["encrypted_data"]))
    assert decrypted["telegram_id"] == 123456789
    assert b"+15555550123" not in content
    assert b"private-session-value" not in content


def test_public_mirror_rejects_private_repositories(mirror, monkeypatch):
    instance, _ = mirror
    instance.api_url = "https://api.github.com/repos/owner/database"
    instance.headers = {}
    def private_repo_request(method, endpoint):
        assert (method, endpoint) == ("GET", "")
        return 200, {"private": True}

    monkeypatch.setattr(instance, "_request", private_repo_request)

    with pytest.raises(ValueError, match="must be a public repository"):
        instance._ensure_public_branch()


def test_legacy_db_github_variables_configure_encrypted_mirror(monkeypatch):
    variables = (
        "GITHUB_DATA_MIRROR_ENABLED",
        "GITHUB_DATA_REPO",
        "GITHUB_DATA_TOKEN",
        "GITHUB_DATA_BRANCH",
        "DB_GITHUB_TOKEN",
        "GITHUB_REPO",
        "GITHUB_TOKEN",
    )
    for variable in variables:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("GITHUB_DATA_MIRROR_ENABLED", "")
    monkeypatch.setenv("USE_GITHUB_DB", "true")
    monkeypatch.setenv("DB_WRITE_ALLOWED", "true")
    monkeypatch.setenv("DB_GITHUB_OWNER", "owner")
    monkeypatch.setenv("DB_GITHUB_REPO", "database")
    monkeypatch.setenv("DB_GITHUB_BRANCH", "db-live")
    monkeypatch.setenv("DB_GITHUB_TOKEN", "mirror-token")

    backup = ConfigManager.__new__(ConfigManager)._load_backup_config()

    assert backup.github_data_mirror_enabled is True
    assert backup.github_data_repo == "owner/database"
    assert backup.github_data_branch == "db-live"
    assert backup.github_data_token == "mirror-token"


def test_legacy_mirror_requires_both_opt_in_flags(monkeypatch):
    monkeypatch.delenv("GITHUB_DATA_MIRROR_ENABLED", raising=False)
    monkeypatch.setenv("USE_GITHUB_DB", "true")
    monkeypatch.setenv("DB_WRITE_ALLOWED", "false")

    backup = ConfigManager.__new__(ConfigManager)._load_backup_config()

    assert backup.github_data_mirror_enabled is False


def test_explicit_mirror_setting_overrides_legacy_enablement(monkeypatch):
    monkeypatch.setenv("USE_GITHUB_DB", "true")
    monkeypatch.setenv("DB_WRITE_ALLOWED", "true")
    monkeypatch.setenv("GITHUB_DATA_MIRROR_ENABLED", "false")

    backup = ConfigManager.__new__(ConfigManager)._load_backup_config()

    assert backup.github_data_mirror_enabled is False


def test_mirror_uses_configured_token_for_github_api(monkeypatch):
    key = Fernet.generate_key().decode("ascii")
    backup = SimpleNamespace(
        github_data_mirror_enabled=True,
        github_data_branch="db-live",
        github_data_repo="owner/database",
        github_data_token="mirror-token",
    )
    monkeypatch.setattr(
        github_data_mirror,
        "config",
        SimpleNamespace(
            backup=backup,
            security=SimpleNamespace(fernet_key=key),
        ),
    )
    monkeypatch.setattr(github_data_mirror, "FERNET", Fernet(key.encode("ascii")))

    instance = GitHubDataMirror()
    assert instance.headers is not None

    assert instance.headers["Authorization"] == "Bearer mirror-token"


def test_write_file_skips_record_with_unchanged_plaintext(mirror, monkeypatch):
    instance, cipher = mirror
    plaintext = b'{"telegram_id":123}'
    envelope = {
        "encrypted_data": cipher.encrypt(plaintext).decode("ascii"),
    }
    remote_content = base64.b64encode(json.dumps(envelope).encode()).decode("ascii")
    def get_file(path):
        assert path.endswith(".json")
        return 200, {"sha": "existing-sha", "content": remote_content}

    monkeypatch.setattr(instance, "_get_file", get_file)

    def unexpected_request(method, endpoint, **kwargs):
        raise AssertionError(
            f"Unexpected request: {method} {endpoint} {kwargs}"
        )

    monkeypatch.setattr(instance, "_request", unexpected_request)

    assert (
        instance._write_file(
            "teleguard-data/v1/users/opaque.json",
            b"new ciphertext",
            encrypted_plaintext=plaintext,
        )
        is False
    )


def test_sync_snapshot_cleans_stale_files_and_publishes_safe_index(
    mirror, monkeypatch
):
    instance, _ = mirror
    stale_id = "a" * 64
    monkeypatch.setattr(
        instance,
        "_read_manifest",
        lambda: {
            "updated_at": "old-time",
            "records": {"users": [stale_id], "accounts": []},
        },
    )
    written = {}
    deleted = []

    def write_file(path, content, *, encrypted_plaintext=None):
        written[path] = (content, encrypted_plaintext)
        return True

    monkeypatch.setattr(instance, "_write_file", write_file)

    def delete_file(path):
        deleted.append(path)
        return True

    monkeypatch.setattr(instance, "_delete_file", delete_file)

    result = instance._sync_snapshot(
        [{"telegram_id": 123456789, "phone": "+15555550123"}],
        [{"_id": "account-object-id", "session": "private-session-value"}],
    )

    index_path = "teleguard-data/v1/index.json"
    index = json.loads(written[index_path][0])
    assert result == {"users": 1, "accounts": 1, "updated": 2, "deleted": 1}
    assert deleted == [f"teleguard-data/v1/users/{stale_id}.json"]
    assert index["counts"] == {"users": 1, "accounts": 1}
    assert all(
        len(record_id) == 64
        for values in index["records"].values()
        for record_id in values
    )
    assert b"123456789" not in written[index_path][0]
    assert b"+15555550123" not in written[index_path][0]
    assert b"private-session-value" not in written[index_path][0]
    assert b"account-object-id" not in written[index_path][0]


def test_sync_snapshot_skips_unchanged_records_using_keyed_fingerprints(
    mirror, monkeypatch
):
    instance, _ = mirror
    user = {"telegram_id": 123456789, "phone": "+15555550123"}
    records = instance._prepare_records("users", [user])
    record_id, (_, plaintext) = next(iter(records.items()))
    fingerprint = instance._record_fingerprint("users", record_id, plaintext)
    monkeypatch.setattr(
        instance,
        "_read_manifest",
        lambda: {
            "schema_version": 2,
            "updated_at": "previous-time",
            "records": {"users": [record_id], "accounts": []},
            "fingerprints": {
                "users": {record_id: fingerprint},
                "accounts": {},
            },
        },
    )
    written = []

    def write_file(path, content, *, encrypted_plaintext=None):
        written.append((path, content, encrypted_plaintext))
        return False

    monkeypatch.setattr(instance, "_write_file", write_file)

    def delete_file(path):
        assert path.startswith(instance.root_path)
        return False

    monkeypatch.setattr(instance, "_delete_file", delete_file)

    result = instance._sync_snapshot([user], [])

    assert result == {"users": 1, "accounts": 0, "updated": 0, "deleted": 0}
    assert [path for path, _, _ in written] == ["teleguard-data/v1/index.json"]


def test_read_manifest_rejects_non_object_json(mirror, monkeypatch):
    instance, _ = mirror
    content = base64.b64encode(b"[]").decode("ascii")
    def get_file(path):
        assert path.endswith("/index.json")
        return 200, {"content": content}

    monkeypatch.setattr(instance, "_get_file", get_file)

    with pytest.raises(ValueError, match="index is invalid"):
        instance._read_manifest()
