import base64
import hashlib
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

import teleguard.utils.session_backup as session_backup
from teleguard.utils.session_backup import SessionBackupManager


@pytest.mark.parametrize(
    ("repository", "expected"),
    [
        ("owner/private-backup", ("owner", "private-backup")),
        ("https://github.com/owner/private-backup.git", ("owner", "private-backup")),
        ("git@github.com:owner/private-backup.git", ("owner", "private-backup")),
    ],
)
def test_parse_github_repository(repository, expected):
    assert SessionBackupManager._parse_repository(repository) == expected


def test_rejects_non_github_repository_url():
    with pytest.raises(ValueError, match="github.com"):
        SessionBackupManager._parse_repository("https://example.com/owner/repo")


def test_refuses_to_store_sessions_in_public_repository(monkeypatch):
    manager = object.__new__(SessionBackupManager)
    manager.github_branch = "backups"
    calls = []

    def request(method, endpoint, **_kwargs):
        calls.append((method, endpoint))
        return 200, {"private": False}

    monkeypatch.setattr(manager, "_request", request)

    with pytest.raises(ValueError, match="must be private"):
        manager._ensure_private_branch()
    assert calls == [("GET", "")]


def test_session_manager_uses_dedicated_private_repo_credentials(monkeypatch):
    monkeypatch.setattr(
        session_backup,
        "config",
        SimpleNamespace(
            security=SimpleNamespace(session_backup_enabled=True),
            backup=SimpleNamespace(
                github_backup_branch="backups",
                session_backup_github_repo="owner/private-session-backups",
                session_backup_github_token="private-token",
            ),
        ),
    )
    monkeypatch.setattr(session_backup, "FERNET", Fernet(Fernet.generate_key()))

    manager = SessionBackupManager()
    assert manager.headers is not None

    assert manager.repository == "owner/private-session-backups"
    assert manager.headers["Authorization"] == "Bearer private-token"


def test_repository_root_request_omits_trailing_slash(monkeypatch):
    manager = object.__new__(SessionBackupManager)
    manager.api_url = "https://api.github.com/repos/owner/session-backups"
    manager.headers = {}
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

    monkeypatch.setattr(session_backup, "urlopen", fake_urlopen)

    assert manager._request("GET", "") == (200, {})
    assert requested_urls == [
        "https://api.github.com/repos/owner/session-backups"
    ]


def test_creates_configured_branch_from_repository_default(monkeypatch):
    manager = object.__new__(SessionBackupManager)
    manager.github_branch = "backups"
    calls = []
    default_ref_checks = 0

    def request(method, endpoint, **kwargs):
        nonlocal default_ref_checks
        calls.append((method, endpoint, kwargs))
        if endpoint == "":
            return 200, {"private": True, "default_branch": "main"}
        if endpoint == "git/ref/heads/backups":
            return 404, {}
        if endpoint == "git/ref/heads/main":
            default_ref_checks += 1
            if default_ref_checks == 1:
                return 200, {"object": {"sha": "commit-sha"}}
            return 404, {}
        return 201, {}

    monkeypatch.setattr(manager, "_request", request)

    manager._ensure_private_branch()

    assert calls[-1][0:2] == ("POST", "git/refs")
    assert calls[-1][2]["json_body"] == {
        "ref": "refs/heads/backups",
        "sha": "commit-sha",
    }


def test_initializes_branch_for_empty_private_repository(monkeypatch):
    manager = object.__new__(SessionBackupManager)
    manager.github_branch = "backups"
    calls = []

    def request(method, endpoint, **_kwargs):
        calls.append((method, endpoint))
        if endpoint == "":
            return 200, {"private": True, "default_branch": "main"}
        if endpoint in (
            "git/ref/heads/backups",
            "git/ref/heads/main",
        ):
            return 409, {"message": "Git Repository is empty."}
        if endpoint == "contents/README.md":
            assert _kwargs["json_body"]["content"]
            return 201, {"commit": {"sha": "commit-sha"}}
        return 201, {}

    monkeypatch.setattr(manager, "_request", request)

    manager._ensure_private_branch()

    assert calls == [
        ("GET", ""),
        ("GET", "git/ref/heads/backups"),
        ("GET", "git/ref/heads/main"),
        ("PUT", "contents/README.md"),
        ("POST", "git/refs"),
    ]


def test_missing_private_repository_is_created_and_branch_initialized(monkeypatch):
    manager = object.__new__(SessionBackupManager)
    manager.repository = "owner/session-backups"
    manager.github_branch = "backups"
    calls = []

    def request(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        if endpoint == "" and method == "GET":
            return 404, {}
        if endpoint == "/user":
            return 200, {"login": "owner"}
        if endpoint == "/user/repos":
            assert kwargs["json_body"] == {
                "name": "session-backups",
                "private": True,
                "auto_init": False,
            }
            return 201, {
                "full_name": "owner/session-backups",
                "private": True,
                "default_branch": "main",
            }
        if endpoint == "git/ref/heads/backups":
            return 404, {}
        if endpoint == "git/ref/heads/main":
            return 404, {}
        if endpoint == "contents/README.md":
            assert method == "PUT"
            return 201, {"commit": {"sha": "commit-sha"}}
        if endpoint == "git/refs":
            return 201, {}
        raise AssertionError(f"Unexpected request: {method} {endpoint}")

    monkeypatch.setattr(manager, "_request", request)

    manager._ensure_private_branch()

    assert [call[:2] for call in calls] == [
        ("GET", ""),
        ("GET", "/user"),
        ("POST", "/user/repos"),
        ("GET", "git/ref/heads/backups"),
        ("GET", "git/ref/heads/main"),
        ("PUT", "contents/README.md"),
        ("POST", "git/refs"),
    ]


def test_creates_session_repository_readme_only_when_missing(monkeypatch):
    manager = object.__new__(SessionBackupManager)
    manager.github_branch = "backups"
    calls = []

    def request(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        if method == "GET":
            return 404, {}
        return 201, {}

    monkeypatch.setattr(manager, "_request", request)

    manager._ensure_readme()

    assert [call[:2] for call in calls] == [
        ("GET", "contents/README.md"),
        ("PUT", "contents/README.md"),
    ]
    assert calls[0][2]["params"] == {"ref": "backups"}
    assert calls[1][2]["json_body"]["branch"] == "backups"
    assert b"Encrypted Session Backups" in base64.b64decode(
        calls[1][2]["json_body"]["content"]
    )


def test_preserves_existing_session_repository_readme(monkeypatch):
    manager = object.__new__(SessionBackupManager)
    manager.github_branch = "backups"
    calls = []

    def request(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        return 200, {"sha": "existing-readme"}

    monkeypatch.setattr(manager, "_request", request)

    manager._ensure_readme()

    assert [call[:2] for call in calls] == [("GET", "contents/README.md")]


@pytest.mark.asyncio
async def test_empty_session_backup_still_initializes_repository_and_readme(
    monkeypatch,
):
    class EmptyCursor:
        async def to_list(self, length=None):
            assert length is None
            return []

    class EmptyAccounts:
        def find(self, query):
            assert "$or" in query
            return EmptyCursor()

    monkeypatch.setattr(
        session_backup.mongodb,
        "db",
        SimpleNamespace(accounts=EmptyAccounts()),
    )
    monkeypatch.setattr(session_backup, "FERNET", Fernet(Fernet.generate_key()))
    manager = object.__new__(SessionBackupManager)
    manager.enabled = True
    calls = []
    monkeypatch.setattr(
        manager, "_ensure_private_branch", lambda: calls.append("branch")
    )
    monkeypatch.setattr(
        manager, "_ensure_readme", lambda: calls.append("readme")
    )

    assert await manager.push_sessions_batch() is True
    assert calls == ["branch", "readme"]


def test_github_upload_skips_unchanged_files(monkeypatch):
    content = b"encrypted session contents"
    git_blob = b"blob " + str(len(content)).encode() + b"\0" + content
    expected_sha = hashlib.sha1(git_blob).hexdigest()

    manager = object.__new__(SessionBackupManager)
    manager.github_branch = "backups"
    calls = []

    def request(method, _endpoint, **_kwargs):
        calls.append(method)
        return (200, {"sha": expected_sha}) if method == "GET" else (200, {})

    monkeypatch.setattr(manager, "_request", request)

    assert manager._put_file("sessions/account.enc", content) is False
    assert calls == ["GET"]


def test_github_upload_skips_session_when_decrypted_content_matches(monkeypatch):
    plain_session = b"telegram-session"
    cipher = Fernet(Fernet.generate_key())
    encrypted_content = cipher.encrypt(plain_session)
    manager = object.__new__(SessionBackupManager)
    manager.github_branch = "backups"
    calls = []

    def request(method, _endpoint, **_kwargs):
        calls.append(method)
        return (
            200,
            {
                "sha": "remote-sha",
                "content": base64.b64encode(encrypted_content).decode("ascii"),
            },
        )

    monkeypatch.setattr(manager, "_request", request)
    monkeypatch.setattr(session_backup, "FERNET", cipher)

    assert (
        manager._put_file(
            "sessions/account.enc",
            cipher.encrypt(plain_session),
            compare_plaintext=plain_session,
        )
        is False
    )
    assert calls == ["GET"]


def test_github_upload_creates_file_on_configured_branch(monkeypatch):
    content = b"encrypted session contents"
    manager = object.__new__(SessionBackupManager)
    manager.github_branch = "backups"
    payload = {}

    def request(method, _endpoint, **kwargs):
        if method == "GET":
            return 404, {}
        payload.update(kwargs["json_body"])
        return 200, {}

    monkeypatch.setattr(manager, "_request", request)

    assert manager._put_file("sessions/account.enc", content) is True
    assert payload["branch"] == "backups"
    assert payload["content"] == "ZW5jcnlwdGVkIHNlc3Npb24gY29udGVudHM="
