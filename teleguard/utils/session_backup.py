"""Session backup system - MongoDB temp storage + GitHub persistence
Developed by:
- @Meher_Mankar
- @Gutkesh
GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import asyncio
import base64
import binascii
import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from cryptography.fernet import InvalidToken

from ..core.config import FERNET, config
from ..core.mongo_database import mongodb
from .crypto_utils import DataEncryption

logger = logging.getLogger(__name__)


class TelegramBackup:
    """Handles backup operations to Telegram channels"""

    def __init__(self, bot_client):
        self.bot_client = bot_client
        self.backup_channel = os.environ.get("TELEGRAM_BACKUP_CHANNEL")

    async def delete_old_backups(self, backup_type: str) -> bool:
        """Delete old backup files using stored message IDs"""
        try:
            if not self.backup_channel:
                return False
            channel_id = self.backup_channel
            if isinstance(channel_id, str) and channel_id.startswith("-"):
                channel_id = int(channel_id)
            retention_count = int(os.environ.get("BACKUP_RETENTION_COUNT", "1"))
            backup_records = (
                await mongodb.db.backup_messages.find({"backup_type": backup_type})
                .sort("timestamp", -1)
                .to_list(length=None)
            )
            # Keep only the most recent ones, delete the rest
            if len(backup_records) >= retention_count:
                to_delete = backup_records[retention_count:]
                deleted_count = 0
                for record in to_delete:
                    try:
                        try:
                            await self.bot_client.edit_message(
                                channel_id, record["message_id"], ""
                            )
                        except Exception:
                            await self.bot_client.delete_messages(
                                channel_id, record["message_id"]
                            )
                        await mongodb.db.backup_messages.delete_one(
                            {"_id": record["_id"]}
                        )
                        deleted_count += 1
                        logger.info(
                            f"Deleted old {backup_type} backup (ID: {
                                record['message_id']})"
                        )
                    except Exception as del_error:
                        logger.warning(
                            f"Failed to delete message {
                                record['message_id']}: {del_error}"
                        )
                        await mongodb.db.backup_messages.delete_one(
                            {"_id": record["_id"]}
                        )
                return deleted_count > 0
            return False
        except Exception as e:
            logger.error(f"Failed to delete old backups: {e}")
            return False

    async def send_file(
        self, file_path: str, caption: str, backup_type: str = None
    ) -> bool:
        """Send file to Telegram backup channel and delete old backups"""
        try:
            if not self.backup_channel:
                logger.warning("TELEGRAM_BACKUP_CHANNEL not configured")
                return False
            if backup_type:
                await self.delete_old_backups(backup_type)
            # Convert channel ID to integer if it's a string
            channel_id = self.backup_channel
            if isinstance(channel_id, str) and channel_id.startswith("-"):
                channel_id = int(channel_id)
            message = await self.bot_client.send_file(
                channel_id, file_path, caption=caption
            )
            # Store message ID for future cleanup
            if backup_type and message:
                await mongodb.db.backup_messages.insert_one(
                    {
                        "backup_type": backup_type,
                        "message_id": message.id,
                        "timestamp": datetime.now(timezone.utc),
                        "caption": caption,
                    }
                )
            logger.info(f"File sent to Telegram backup channel: {caption}")
            return True
        except Exception as e:
            logger.error(f"Failed to send file to Telegram: {e}")
            return False


class SessionBackupManager:
    """Back up encrypted Telegram sessions to a private GitHub repository."""

    def __init__(self):
        self.enabled = config.security.session_backup_enabled
        self.github_branch = config.backup.github_backup_branch
        if self.enabled:
            repository = config.backup.github_repo
            self.github_token = config.backup.github_token
            if not repository:
                raise ValueError(
                    "GITHUB_REPO is required when session backups are enabled"
                )
            if not self.github_token:
                raise ValueError(
                    "GITHUB_TOKEN is required when session backups are enabled"
                )
            if FERNET is None:
                raise ValueError("FERNET_KEY is required for GitHub session backups")
            owner, name = self._parse_repository(repository)
            self.repository = f"{owner}/{name}"
            self.api_url = f"https://api.github.com/repos/{self.repository}"
            self.headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.github_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        else:
            self.repository = None
            self.github_token = None
            self.api_url = None
            self.headers = None

    @staticmethod
    def _parse_repository(repository: str) -> tuple[str, str]:
        """Return owner/name from a GitHub URL, SSH URL, or owner/name."""
        value = repository.strip()
        if value.startswith("git@github.com:"):
            value = value.removeprefix("git@github.com:")
        elif value.startswith("https://"):
            parsed = urlparse(value)
            if parsed.hostname != "github.com" or parsed.username or parsed.password:
                raise ValueError("GITHUB_REPO must refer to a repository on github.com")
            value = parsed.path.strip("/")
        value = value.removesuffix(".git")
        parts = value.split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError(
                "GITHUB_REPO must be owner/repository or a GitHub repository URL"
            )
        if not all(
            part.replace("-", "").replace("_", "").replace(".", "").isalnum()
            for part in parts
        ):
            raise ValueError(
                "GITHUB_REPO contains invalid owner or repository characters"
            )
        return parts[0], parts[1]

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, str]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        allow_status: tuple = (),
    ) -> Tuple[int, Dict[str, Any]]:
        if not self.api_url or self.headers is None:
            raise RuntimeError("GitHub backup client is not configured")
        url = f"{self.api_url}/{endpoint}"
        if params:
            url = f"{url}?{urlencode(params)}"
        data = json.dumps(json_body).encode("utf-8") if json_body is not None else None
        headers = self.headers
        if json_body is not None:
            headers = {**headers, "Content-Type": "application/json"}
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                status = response.status
                body = response.read()
        except HTTPError as error:
            status = error.code
            body = error.read()
        if not 200 <= status < 300 and status not in allow_status:
            details = body.decode("utf-8", errors="replace")[:500]
            raise RuntimeError(
                f"GitHub API {method} {endpoint} failed with HTTP {status}: {details}"
            )
        return status, json.loads(body) if body else {}

    def _ensure_private_branch(self) -> None:
        _, repository = self._request("GET", "")
        if not repository.get("private"):
            raise ValueError("The GitHub session-backup repository must be private")

        encoded_branch = quote(self.github_branch, safe="")
        ref_endpoint = f"git/ref/heads/{encoded_branch}"
        status, _ = self._request("GET", ref_endpoint, allow_status=(404,))
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
                    "message": "Initialize encrypted session backups",
                    "tree": tree["sha"],
                },
            )
            source_sha = commit["sha"]
        else:
            source_sha = source_ref["object"]["sha"]
        self._request(
            "POST",
            "git/refs",
            json_body={
                "ref": f"refs/heads/{self.github_branch}",
                "sha": source_sha,
            },
        )

    def _put_file(
        self,
        path: str,
        content: bytes,
        compare_plaintext: Optional[bytes] = None,
    ) -> bool:
        """Create or update a GitHub file; skip a commit if its contents match."""
        encoded_path = quote(path, safe="/")
        endpoint = f"contents/{encoded_path}"
        status, remote_file = self._request(
            "GET",
            endpoint,
            params={"ref": self.github_branch},
            allow_status=(404,),
        )
        current_sha = None
        if status == 200:
            current_sha = remote_file.get("sha")
            remote_content = remote_file.get("content")
            if compare_plaintext is not None and remote_content:
                if FERNET is None:
                    raise ValueError("Fernet encryption is unavailable")
                try:
                    remote_ciphertext = base64.b64decode(remote_content)
                    if FERNET.decrypt(remote_ciphertext) == compare_plaintext:
                        return False
                except (InvalidToken, binascii.Error, ValueError):
                    logger.warning(
                        "Existing GitHub session file could not be decrypted: %s",
                        path,
                    )

        git_blob = b"blob " + str(len(content)).encode() + b"\0" + content
        if current_sha == hashlib.sha1(git_blob).hexdigest():
            return False

        payload = {
            "message": f"Update session backup: {path}",
            "content": base64.b64encode(content).decode("ascii"),
            "branch": self.github_branch,
        }
        if current_sha:
            payload["sha"] = current_sha
        self._request("PUT", endpoint, json_body=payload)
        return True

    async def push_sessions_batch(self) -> bool:
        """Encrypt and push all account sessions to the configured private repo."""
        if not self.enabled:
            logger.info("Session backup disabled")
            return False
        try:
            if FERNET is None:
                raise ValueError("Fernet encryption is unavailable")
            accounts = await mongodb.db.accounts.find(
                {
                    "$or": [
                        {"session_string": {"$exists": True, "$nin": [None, ""]}},
                        {"session_string_enc": {"$exists": True, "$nin": [None, ""]}},
                    ]
                }
            ).to_list(length=None)
            files = {}
            plaintext_sessions = {}
            manifest_sessions = []
            for account in accounts:
                account_id = str(account.get("_id", ""))
                if not account_id or not all(
                    character.isalnum() or character in "_-" for character in account_id
                ):
                    raise ValueError("Account has an invalid database ID")
                decrypted = DataEncryption.decrypt_account_data(account)
                session_string = decrypted.get("session_string")
                if not isinstance(session_string, str) or not session_string:
                    continue
                if (
                    "session_string_enc" in account
                    and session_string == account["session_string_enc"]
                ):
                    raise ValueError(
                        f"Could not decrypt session for account {account_id}; "
                        "check FERNET_KEY"
                    )

                encrypted_session = FERNET.encrypt(session_string.encode("utf-8"))
                file_path = f"sessions/{account_id}.enc"
                files[file_path] = encrypted_session
                plaintext_sessions[file_path] = session_string.encode("utf-8")
                manifest_sessions.append(
                    {
                        "account_id": account_id,
                        "file": file_path,
                        "sha256": hashlib.sha256(encrypted_session).hexdigest(),
                    }
                )

            if not files:
                logger.info("No account sessions found for GitHub backup")
                return True

            manifest = json.dumps(
                {
                    "version": 1,
                    "sessions": sorted(
                        manifest_sessions, key=lambda session: session["account_id"]
                    ),
                },
                indent=2,
                sort_keys=True,
            ).encode("utf-8")
            files["manifests/sessions.json"] = manifest

            await asyncio.to_thread(self._ensure_private_branch)
            updated_files = 0
            for path, content in files.items():
                updated = await asyncio.to_thread(
                    self._put_file, path, content, plaintext_sessions.get(path)
                )
                updated_files += int(updated)
            logger.info(
                "GitHub session backup complete: %d account sessions, %d files updated",
                len(manifest_sessions),
                updated_files,
            )
            return True
        except Exception as e:
            logger.error("Failed to push sessions to GitHub: %s", e)
            return False

    async def push_session_files_to_telegram(self, bot_client) -> bool:
        """Backs up encrypted session files to Telegram."""
        if not self.enabled:
            return False
        logger.info("Starting session files backup to Telegram.")
        telegram_backup = TelegramBackup(bot_client)
        try:
            accounts = await mongodb.db.accounts.find(
                {
                    "user_id": {"$exists": True},
                    "$or": [
                        {"session_string_enc": {"$exists": True, "$ne": ""}},
                        {"session_string": {"$exists": True, "$ne": ""}},
                    ],
                }
            ).to_list(length=None)
            # Decrypt accounts for processing
            accounts = [DataEncryption.decrypt_account_data(acc) for acc in accounts]
            if not accounts:
                logger.info("No session files to backup")
                return True
            session_files_data = {
                "sessions": [],
                "backup_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            for account in accounts:
                # Encrypt session string
                encrypted_session = FERNET.encrypt(account["session_string"].encode())
                session_files_data["sessions"].append(
                    {
                        "account_id": str(account["_id"]),
                        "user_id": account["user_id"],
                        "name": account["name"],
                        "encrypted_session": encrypted_session.decode(),
                        "created_at": account.get("created_at", ""),
                    }
                )
            sessions_json = json.dumps(session_files_data, indent=2)
            encrypted_sessions = FERNET.encrypt(sessions_json.encode())
            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, suffix=".sessions.enc"
            ) as temp_file:
                temp_file.write(encrypted_sessions)
                temp_file_path = temp_file.name
            caption = f"Encrypted Session Files Backup\nAccounts: {
                len(accounts)}\nTimestamp: {
                datetime.now(
                    timezone.utc).isoformat()}"
            success = await telegram_backup.send_file(
                temp_file_path, caption, "session files"
            )
            os.remove(temp_file_path)
            return success
        except Exception as e:
            logger.error(f"Failed to backup session files to Telegram: {e}")
            return False

    async def push_user_settings_to_telegram(self, bot_client) -> bool:
        """Backs up user settings to Telegram."""
        if not self.enabled:
            return False
        logger.info("Starting user settings backup to Telegram.")
        telegram_backup = TelegramBackup(bot_client)
        try:
            encrypted_users = await mongodb.db.users.find({}).to_list(length=None)
            encrypted_accounts = await mongodb.db.accounts.find({}).to_list(length=None)
            # Decrypt data before backup
            users = [DataEncryption.decrypt_user_data(user) for user in encrypted_users]
            accounts = [
                DataEncryption.decrypt_account_data(acc) for acc in encrypted_accounts
            ]
            # Convert ObjectId to string for JSON serialization
            for user in users:
                user["_id"] = str(user["_id"])
            for account in accounts:
                account["_id"] = str(account["_id"])
            settings_data = {
                "users": users,
                "accounts": accounts,
                "backup_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            settings_json = json.dumps(settings_data, indent=2)
            encrypted_settings = FERNET.encrypt(settings_json.encode())
            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, suffix=".json.enc"
            ) as temp_file:
                temp_file.write(encrypted_settings)
                temp_file_path = temp_file.name
            caption = f"Encrypted User Settings Backup\nTimestamp: {
                datetime.now(
                    timezone.utc).isoformat()}"
            success = await telegram_backup.send_file(
                temp_file_path, caption, "user settings"
            )
            os.remove(temp_file_path)
            return success
        except Exception as e:
            logger.error(f"Failed to backup user settings to Telegram: {e}")
            return False

    async def push_user_ids_to_telegram(self, bot_client) -> bool:
        """Backs up user IDs to Telegram."""
        if not self.enabled:
            return False
        logger.info("Starting user IDs backup to Telegram.")
        telegram_backup = TelegramBackup(bot_client)
        try:
            users = await mongodb.db.users.find({}, {"telegram_id": 1}).to_list(
                length=None
            )
            encrypted_accounts = await mongodb.db.accounts.find(
                {}, {"name_enc": 1, "username_enc": 1, "user_id": 1}
            ).to_list(length=None)
            # Decrypt account data for processing
            accounts = []
            for enc_acc in encrypted_accounts:
                decrypted_acc = DataEncryption.decrypt_account_data(enc_acc)
                accounts.append(
                    {
                        "name": decrypted_acc.get("name"),
                        "username": decrypted_acc.get("username"),
                        "user_id": enc_acc.get("user_id"),
                    }
                )
            user_map = {user["telegram_id"]: [] for user in users}
            for acc in accounts:
                if acc.get("user_id") in user_map:
                    user_map[acc["user_id"]].append(
                        {"name": acc.get("name"), "username": acc.get("username")}
                    )
            user_ids_data = [
                {"telegram_id": uid, "accounts": accs} for uid, accs in user_map.items()
            ]
            user_ids_json = json.dumps(user_ids_data, indent=2)
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".json"
            ) as temp_file:
                temp_file.write(user_ids_json)
                temp_file_path = temp_file.name
            caption = (
                f"User IDs Backup\nTimestamp: {datetime.now(timezone.utc).isoformat()}"
            )
            success = await telegram_backup.send_file(
                temp_file_path, caption, "user ids"
            )
            os.remove(temp_file_path)
            return success
        except Exception as e:
            logger.error(f"Failed to backup user IDs to Telegram: {e}")
            return False
