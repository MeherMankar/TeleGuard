import base64
import io
import json
from types import SimpleNamespace
from urllib.error import HTTPError

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
    instance.repository = "owner/database"
    instance.headers = {}

    def private_repo_request(method, endpoint, **_kwargs):
        assert (method, endpoint) == ("GET", "")
        return 200, {"private": True}

    monkeypatch.setattr(instance, "_request", private_repo_request)

    with pytest.raises(ValueError, match="must be a public repository"):
        instance._ensure_public_branch()


def test_repository_root_request_omits_trailing_slash(mirror, monkeypatch):
    instance, _ = mirror
    instance.api_url = "https://api.github.com/repos/owner/database"
    instance.headers = {}
    requested_urls = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout):
        assert timeout == 30
        requested_urls.append(request.full_url)
        return Response()

    monkeypatch.setattr(github_data_mirror, "urlopen", fake_urlopen)

    assert instance._request("GET", "") == (200, {})
    assert requested_urls == ["https://api.github.com/repos/owner/database"]


def test_missing_public_repository_is_created_and_branch_initialized(
    mirror, monkeypatch
):
    instance, _ = mirror
    instance.api_url = "https://api.github.com/repos/owner/database"
    instance.repository = "owner/database"
    instance.branch = "main"
    instance.headers = {}
    calls = []

    def request(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        if endpoint == "" and method == "GET":
            return 404, {}
        if endpoint == "/user":
            return 200, {"login": "owner"}
        if endpoint == "/user/repos":
            assert kwargs["json_body"] == {
                "name": "database",
                "private": False,
                "auto_init": False,
            }
            return 201, {"full_name": "owner/database", "private": False}
        if endpoint == "git/ref/heads/main":
            return 404, {}
        if endpoint == "git/trees":
            return 201, {"sha": "tree-sha"}
        if endpoint == "git/commits":
            return 201, {"sha": "commit-sha"}
        if endpoint == "git/refs":
            return 201, {}
        raise AssertionError(f"Unexpected request: {method} {endpoint}")

    monkeypatch.setattr(instance, "_request", request)

    instance._ensure_public_branch()

    assert [call[:2] for call in calls] == [
        ("GET", ""),
        ("GET", "/user"),
        ("POST", "/user/repos"),
        ("GET", "git/ref/heads/main"),
        ("POST", "git/trees"),
        ("POST", "git/commits"),
        ("POST", "git/refs"),
    ]


def test_creates_repository_readme_with_mirror_status_when_missing(
    mirror, monkeypatch
):
    instance, _ = mirror
    instance.branch = "main"
    writes = []
    monkeypatch.setattr(instance, "_get_file", lambda _path: (404, {}))
    monkeypatch.setattr(instance, "_now", lambda: "2026-11-27T00:00:00+00:00")

    def request(method, endpoint, **kwargs):
        writes.append((method, endpoint, kwargs["json_body"]))
        return 201, {}

    monkeypatch.setattr(instance, "_request", request)

    instance._update_readme(
        {"users": 2, "accounts": 1, "updated": 3, "deleted": 0}
    )

    assert len(writes) == 1
    method, endpoint, payload = writes[0]
    assert (method, endpoint) == ("PUT", "contents/README.md")
    assert payload["branch"] == "main"
    readme = base64.b64decode(payload["content"]).decode("utf-8")
    assert "Encrypted Data Mirror" in readme
    assert "Last mirror update: `2026-11-27T00:00:00+00:00`" in readme
    assert "- User records: 2" in readme
    assert "- Account records: 1" in readme


def test_updates_managed_readme_status_preserving_custom_content(mirror, monkeypatch):
    instance, _ = mirror
    instance.branch = "main"
    previous_readme = (
        "# My repository notes\n\nKeep this text.\n\n"
        "<!-- teleguard-data-mirror-status:start -->\n"
        "## Mirror status\n\n"
        "- Last mirror update: `old`\n"
        "- User records: 1\n"
        "- Account records: 1\n"
        "<!-- teleguard-data-mirror-status:end -->\n"
    )
    remote = {
        "sha": "existing-readme",
        "content": base64.b64encode(previous_readme.encode("utf-8")).decode("ascii"),
    }
    monkeypatch.setattr(instance, "_get_file", lambda _path: (200, remote))
    monkeypatch.setattr(instance, "_now", lambda: "2026-11-27T00:00:00+00:00")
    payloads = []

    def request(method, endpoint, **kwargs):
        assert (method, endpoint) == ("PUT", "contents/README.md")
        payloads.append(kwargs["json_body"])
        return 200, {}

    monkeypatch.setattr(instance, "_request", request)

    instance._update_readme(
        {"users": 2, "accounts": 3, "updated": 1, "deleted": 0}
    )

    assert len(payloads) == 1
    assert payloads[0]["sha"] == "existing-readme"
    updated_readme = base64.b64decode(payloads[0]["content"]).decode("utf-8")
    assert "# My repository notes\n\nKeep this text." in updated_readme
    assert "- User records: 2" in updated_readme
    assert "- Account records: 3" in updated_readme
    assert "- Last mirror update: `2026-11-27T00:00:00+00:00`" in updated_readme


def test_does_not_commit_readme_when_mirror_data_is_unchanged(mirror, monkeypatch):
    instance, _ = mirror
    current_readme = (
        "<!-- teleguard-data-mirror-status:start -->\n"
        "## Mirror status\n\n"
        "- Last mirror update: `previous`\n"
        "- User records: 2\n"
        "- Account records: 1\n"
        "<!-- teleguard-data-mirror-status:end -->\n"
    )
    monkeypatch.setattr(
        instance,
        "_get_file",
        lambda _path: (
            200,
            {
                "sha": "readme-sha",
                "content": base64.b64encode(current_readme.encode()).decode("ascii"),
            },
        ),
    )

    def unexpected_request(*args, **kwargs):
        raise AssertionError(f"Unexpected write: {args} {kwargs}")

    monkeypatch.setattr(instance, "_request", unexpected_request)

    instance._update_readme(
        {"users": 2, "accounts": 1, "updated": 0, "deleted": 0}
    )


def test_sync_updates_readme_after_snapshot(mirror, monkeypatch):
    instance, _ = mirror
    calls = []
    snapshot = {"users": 1, "accounts": 2, "updated": 2, "deleted": 0}
    monkeypatch.setattr(
        instance, "_ensure_public_branch", lambda: calls.append("branch")
    )
    monkeypatch.setattr(
        instance,
        "_sync_snapshot",
        lambda users, accounts: calls.append((users, accounts)) or snapshot,
    )
    monkeypatch.setattr(
        instance, "_update_readme", lambda result: calls.append(("readme", result))
    )

    result = instance._sync_with_repository([], [])

    assert calls == ["branch", ([], []), ("readme", snapshot)]
    assert result == snapshot


def test_repository_404_reports_configuration_and_access_guidance(mirror, monkeypatch):
    instance, _ = mirror
    instance.api_url = "https://api.github.com/repos/owner/database"
    instance.repository = "owner/database"
    instance.headers = {}

    def missing_repository(*args, **kwargs):
        raise HTTPError(
            instance.api_url,
            404,
            "Not Found",
            {},
            io.BytesIO(b'{"message":"Not Found"}'),
        )

    monkeypatch.setattr(github_data_mirror, "urlopen", missing_repository)

    with pytest.raises(RuntimeError, match="owner/database") as error:
        instance._request("GET", "")

    assert "GITHUB_DATA_REPO" in str(error.value)
    assert "GITHUB_DATA_TOKEN" in str(error.value)


def test_github_backup_configuration_ignores_legacy_fallback_variables(monkeypatch):
    variables = (
        "GITHUB_DATA_MIRROR_ENABLED",
        "GITHUB_DATA_REPO",
        "GITHUB_DATA_TOKEN",
        "GITHUB_DATA_BRANCH",
        "SESSION_BACKUP_GITHUB_REPO",
        "SESSION_BACKUP_GITHUB_TOKEN",
        "DB_GITHUB_TOKEN",
        "DB_GITHUB_OWNER",
        "DB_GITHUB_REPO",
        "DB_GITHUB_BRANCH",
        "USE_GITHUB_DB",
        "DB_WRITE_ALLOWED",
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
    monkeypatch.setenv("GITHUB_REPO", "owner/legacy")
    monkeypatch.setenv("GITHUB_TOKEN", "legacy-token")

    backup = ConfigManager.__new__(ConfigManager)._load_backup_config()

    assert backup.github_data_mirror_enabled is False
    assert backup.github_data_repo is None
    assert backup.github_data_token is None
    assert backup.github_data_branch == "main"
    assert backup.session_backup_github_repo is None
    assert backup.session_backup_github_token is None


def test_github_backup_configuration_reads_dedicated_variables(monkeypatch):
    variables = (
        "GITHUB_DATA_MIRROR_ENABLED",
        "GITHUB_DATA_REPO",
        "GITHUB_DATA_TOKEN",
        "GITHUB_DATA_BRANCH",
        "SESSION_BACKUP_GITHUB_REPO",
        "SESSION_BACKUP_GITHUB_TOKEN",
    )
    for variable in variables:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("GITHUB_DATA_MIRROR_ENABLED", "true")
    monkeypatch.setenv("GITHUB_DATA_REPO", "owner/database")
    monkeypatch.setenv("GITHUB_DATA_TOKEN", "mirror-token")
    monkeypatch.setenv("GITHUB_DATA_BRANCH", "data")
    monkeypatch.setenv("SESSION_BACKUP_GITHUB_REPO", "owner/private-sessions")
    monkeypatch.setenv("SESSION_BACKUP_GITHUB_TOKEN", "session-token")

    backup = ConfigManager.__new__(ConfigManager)._load_backup_config()

    assert backup.github_data_mirror_enabled is True
    assert backup.github_data_repo == "owner/database"
    assert backup.github_data_token == "mirror-token"
    assert backup.github_data_branch == "data"
    assert backup.session_backup_github_repo == "owner/private-sessions"
    assert backup.session_backup_github_token == "session-token"


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
