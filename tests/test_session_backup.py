import base64
import hashlib

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


def test_creates_configured_branch_from_repository_default(monkeypatch):
    manager = object.__new__(SessionBackupManager)
    manager.github_branch = "backups"
    calls = []

    def request(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        if endpoint == "":
            return 200, {"private": True, "default_branch": "main"}
        if endpoint == "git/ref/heads/backups":
            return 404, {}
        if endpoint == "git/ref/heads/main":
            return 200, {"object": {"sha": "commit-sha"}}
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
            return 200, {"private": True}
        if endpoint == "git/ref/heads/backups":
            return 404, {}
        if endpoint == "git/trees":
            return 201, {"sha": "tree-sha"}
        if endpoint == "git/commits":
            return 201, {"sha": "commit-sha"}
        return 201, {}

    monkeypatch.setattr(manager, "_request", request)

    manager._ensure_private_branch()

    assert calls == [
        ("GET", ""),
        ("GET", "git/ref/heads/backups"),
        ("POST", "git/trees"),
        ("POST", "git/commits"),
        ("POST", "git/refs"),
    ]


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
