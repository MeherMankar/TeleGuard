"""Mirror MongoDB user and account records to a public GitHub repository."""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from bson import json_util
from cryptography.fernet import InvalidToken

from ..core.config import FERNET, config
from ..core.mongo_database import mongodb
from .session_backup import SessionBackupManager

logger = logging.getLogger(__name__)


class GitHubDataMirror:
    """Publish encrypted MongoDB snapshots without exposing record identifiers."""

    root_path = "teleguard-data/v1"

    def __init__(self):
        backup = config.backup
        self.enabled = backup.github_data_mirror_enabled
        self.branch = backup.github_data_branch
        self._sync_lock = asyncio.Lock()
        self._key = (
            config.security.fernet_key.encode("utf-8")
            if config.security.fernet_key
            else None
        )

        if not self.enabled:
            self.repository = None
            self.api_url = None
            self.headers = None
            return

        if not backup.github_data_repo:
            raise ValueError("GITHUB_DATA_REPO is required for the GitHub data mirror")
        token = backup.github_data_token
        if not token:
            raise ValueError(
                "GITHUB_DATA_TOKEN is required for the GitHub data mirror"
            )
        if FERNET is None or self._key is None:
            raise ValueError("FERNET_KEY is required for the GitHub data mirror")

        owner, repository = SessionBackupManager._parse_repository(
            backup.github_data_repo
        )
        self.repository = f"{owner}/{repository}"
        self.api_url = f"https://api.github.com/repos/{self.repository}"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {backup.github_data_token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "TeleGuard-data-mirror",
        }
        assert self.headers is not None
        self.headers["Authorization"] = f"Bearer {token}"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _opaque_id(self, record_type: str, identifier: Any) -> str:
        if self._key is None:
            raise ValueError("FERNET_KEY is required to create opaque record IDs")
        message = f"{record_type}:{identifier}".encode("utf-8")
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, str]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        allow_status: Tuple[int, ...] = (),
    ) -> Tuple[int, Any]:
        if not self.api_url or self.headers is None:
            raise RuntimeError("GitHub data mirror is not configured")
        url = f"{self.api_url}/{endpoint}"
        if params:
            url = f"{url}?{urlencode(params)}"
        body = json.dumps(json_body).encode("utf-8") if json_body is not None else None
        headers = self.headers
        if json_body is not None:
            headers = {**headers, "Content-Type": "application/json"}
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                status = response.status
                response_body = response.read()
        except HTTPError as error:
            status = error.code
            response_body = error.read()

        if not 200 <= status < 300 and status not in allow_status:
            raise RuntimeError(
                f"GitHub data mirror request failed with HTTP {status}"
            )
        return status, json.loads(response_body) if response_body else {}

    def _ensure_public_branch(self) -> None:
        _, repository = self._request("GET", "")
        if repository.get("private") is not False:
            raise ValueError("GITHUB_DATA_REPO must be a public repository")

        branch_ref = f"git/ref/heads/{quote(self.branch, safe='')}"
        status, _ = self._request("GET", branch_ref, allow_status=(404,))
        if status == 200:
            return

        default_branch = repository.get("default_branch")
        if default_branch:
            status, source_ref = self._request(
                "GET",
                f"git/ref/heads/{quote(default_branch, safe='')}",
                allow_status=(404,),
            )
        else:
            status = 404

        if status == 404:
            _, tree = self._request("POST", "git/trees", json_body={"tree": []})
            _, commit = self._request(
                "POST",
                "git/commits",
                json_body={
                    "message": "Initialize encrypted TeleGuard data mirror",
                    "tree": tree["sha"],
                },
            )
            source_sha = commit["sha"]
        else:
            source_sha = source_ref["object"]["sha"]

        self._request(
            "POST",
            "git/refs",
            json_body={"ref": f"refs/heads/{self.branch}", "sha": source_sha},
        )

    def _get_file(self, path: str) -> Tuple[int, Dict[str, Any]]:
        return self._request(
            "GET",
            f"contents/{quote(path, safe='/')}",
            params={"ref": self.branch},
            allow_status=(404,),
        )

    def _write_file(
        self,
        path: str,
        content: bytes,
        *,
        encrypted_plaintext: Optional[bytes] = None,
    ) -> bool:
        status, remote = self._get_file(path)
        current_sha = remote.get("sha") if status == 200 else None
        if current_sha:
            if encrypted_plaintext is not None and FERNET is not None:
                encoded = remote.get("content")
                if encoded:
                    try:
                        envelope = json.loads(base64.b64decode(encoded))
                        old_plaintext = FERNET.decrypt(
                            envelope["encrypted_data"].encode("ascii")
                        )
                        if old_plaintext == encrypted_plaintext:
                            return False
                    except (
                        InvalidToken,
                        KeyError,
                        TypeError,
                        ValueError,
                        json.JSONDecodeError,
                    ):
                        logger.warning(
                            "Existing encrypted GitHub record could not be verified"
                        )
            elif current_sha == self._git_blob_sha(content):
                return False

        payload = {
            "message": f"Update encrypted TeleGuard record: {path}",
            "content": base64.b64encode(content).decode("ascii"),
            "branch": self.branch,
        }
        if current_sha:
            payload["sha"] = current_sha
        self._request(
            "PUT",
            f"contents/{quote(path, safe='/')}",
            json_body=payload,
        )
        return True

    @staticmethod
    def _git_blob_sha(content: bytes) -> str:
        blob = b"blob " + str(len(content)).encode("ascii") + b"\0" + content
        return hashlib.sha1(blob).hexdigest()

    def _delete_file(self, path: str) -> bool:
        status, remote = self._get_file(path)
        if status == 404:
            return False
        self._request(
            "DELETE",
            f"contents/{quote(path, safe='/')}",
            json_body={
                "message": f"Remove stale encrypted TeleGuard record: {path}",
                "sha": remote["sha"],
                "branch": self.branch,
            },
        )
        return True

    def _read_manifest(self) -> Optional[Dict[str, Any]]:
        status, remote = self._get_file(f"{self.root_path}/index.json")
        if status == 404:
            return None
        try:
            manifest = json.loads(base64.b64decode(remote["content"]))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("GitHub data mirror index is invalid") from error
        if not isinstance(manifest, dict):
            raise ValueError("GitHub data mirror index is invalid")
        if manifest.get("schema_version") not in (1, 2):
            raise ValueError("Unsupported GitHub data mirror index version")
        if not isinstance(manifest.get("records"), dict):
            raise ValueError("GitHub data mirror index records are invalid")
        return manifest

    def _record_fingerprint(
        self, record_type: str, record_id: str, plaintext: bytes
    ) -> str:
        if self._key is None:
            raise ValueError("FERNET_KEY is required to fingerprint mirror records")
        message = (
            b"record:"
            + record_type.encode("utf-8")
            + b":"
            + record_id.encode("ascii")
            + b":"
            + plaintext
        )
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def _prepare_records(
        self, record_type: str, documents: Iterable[Dict[str, Any]]
    ) -> Dict[str, Tuple[bytes, bytes]]:
        if FERNET is None:
            raise ValueError("FERNET_KEY is required for the GitHub data mirror")

        records = {}
        for document in documents:
            identifier = (
                document.get("telegram_id")
                if record_type == "users"
                else document.get("_id")
            )
            if identifier is None:
                raise ValueError(f"{record_type} record is missing its identifier")
            record_id = self._opaque_id(record_type, identifier)
            plaintext = json_util.dumps(
                document, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            envelope = {
                "schema_version": 1,
                "type": f"{record_type[:-1]}_data",
                "encrypted": True,
                "updated_at": self._now(),
                "encrypted_data": FERNET.encrypt(plaintext).decode("ascii"),
            }
            records[record_id] = (
                json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                ),
                plaintext,
            )
        return records

    def _sync_snapshot(
        self, users: Iterable[Dict[str, Any]], accounts: Iterable[Dict[str, Any]]
    ) -> Dict[str, int]:
        user_records = self._prepare_records("users", users)
        account_records = self._prepare_records("accounts", accounts)
        previous = self._read_manifest()

        previous_records = (previous or {}).get("records", {})
        if not isinstance(previous_records, dict):
            raise ValueError("GitHub data mirror index records are invalid")
        previous_fingerprints = (previous or {}).get("fingerprints", {})
        if not isinstance(previous_fingerprints, dict):
            raise ValueError("GitHub data mirror index fingerprints are invalid")

        updated_count = 0
        current_records = {"users": user_records, "accounts": account_records}
        fingerprints = {}
        for record_type, records in current_records.items():
            old_fingerprints = previous_fingerprints.get(record_type, {})
            if not isinstance(old_fingerprints, dict):
                raise ValueError("GitHub data mirror index fingerprints are invalid")
            fingerprints[record_type] = {}
            for record_id, (content, plaintext) in records.items():
                fingerprint = self._record_fingerprint(
                    record_type, record_id, plaintext
                )
                fingerprints[record_type][record_id] = fingerprint
                if old_fingerprints.get(record_id) == fingerprint:
                    continue
                path = f"{self.root_path}/{record_type}/{record_id}.json"
                updated_count += int(
                    self._write_file(
                        path, content, encrypted_plaintext=plaintext
                    )
                )

        deleted_count = 0
        for record_type, records in current_records.items():
            old_ids = previous_records.get(record_type, [])
            if not isinstance(old_ids, list):
                raise ValueError("GitHub data mirror index record list is invalid")
            current_ids = set(records)
            for old_id in old_ids:
                if (
                    isinstance(old_id, str)
                    and len(old_id) == 64
                    and all(character in "0123456789abcdef" for character in old_id)
                    and old_id not in current_ids
                ):
                    path = f"{self.root_path}/{record_type}/{old_id}.json"
                    deleted_count += int(self._delete_file(path))

        manifest = {
            "schema_version": 2,
            "encryption": "Fernet",
            "updated_at": (
                self._now()
                if updated_count or deleted_count or previous is None
                else previous.get("updated_at", self._now())
            ),
            "counts": {
                "users": len(user_records),
                "accounts": len(account_records),
            },
            "records": {
                record_type: sorted(records)
                for record_type, records in current_records.items()
            },
            "fingerprints": fingerprints,
        }
        manifest_content = json.dumps(
            manifest, indent=2, sort_keys=True
        ).encode("utf-8")
        self._write_file(f"{self.root_path}/index.json", manifest_content)
        return {
            "users": len(user_records),
            "accounts": len(account_records),
            "updated": updated_count,
            "deleted": deleted_count,
        }

    async def sync(self) -> Dict[str, int]:
        if not self.enabled:
            return {"users": 0, "accounts": 0, "updated": 0, "deleted": 0}
        async with self._sync_lock:
            database = mongodb.db
            if database is None:
                raise RuntimeError(
                    "MongoDB is not initialized for the GitHub data mirror"
                )
            users = await database.users.find({}).to_list(length=None)
            accounts = await database.accounts.find({}).to_list(length=None)
            try:
                result = await asyncio.to_thread(
                    self._sync_with_repository, users, accounts
                )
            except Exception:
                logger.exception("GitHub encrypted database mirror failed")
                raise
            logger.info(
                "GitHub encrypted database mirror complete: "
                "%d users, %d accounts, %d files updated, %d records deleted",
                result["users"],
                result["accounts"],
                result["updated"],
                result["deleted"],
            )
            return result

    def _sync_with_repository(
        self, users: Iterable[Dict[str, Any]], accounts: Iterable[Dict[str, Any]]
    ) -> Dict[str, int]:
        self._ensure_public_branch()
        return self._sync_snapshot(users, accounts)
