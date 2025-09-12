"""Session backup system - MongoDB temp storage + GitHub persistence

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .crypto_utils import encrypt_session_string
from .mongo_store import (
    get_unpersisted_sessions,
    log_audit_event,
    mark_session_persisted,
    store_session_temp,
)

logger = logging.getLogger(__name__)

# Configuration
import tempfile
from pathlib import Path

default_workdir = Path.home() / ".teleguard" / "sessions_repo"
GIT_WORKDIR = os.environ.get("GIT_WORKDIR", str(default_workdir))
GPG_KEY_ID = os.environ.get("GPG_KEY_ID")


class SessionBackupManager:
    """Manages session backup to MongoDB and GitHub"""

    def __init__(self):
        self.enabled = (
            os.environ.get("SESSION_BACKUP_ENABLED", "false").lower() == "true"
        )

        if self.enabled:
            self.github_repo = os.environ.get("GITHUB_REPO")
            if not self.github_repo:
                raise ValueError(
                    "GITHUB_REPO environment variable required when SESSION_BACKUP_ENABLED=true"
                )
        else:
            self.github_repo = None

        self.workdir = Path(GIT_WORKDIR)

    def store_session(self, account_id: str, session_string: str) -> dict:
        """Store session in MongoDB temporary storage"""
        try:
            encrypted_bytes, sha256_hash = encrypt_session_string(session_string)
            result = store_session_temp(account_id, encrypted_bytes, sha256_hash)

            logger.info(f"Session stored in MongoDB for account {account_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to store session for {account_id}: {e}")
            raise

    def ensure_local_clone(self):
        """Ensure local git clone exists and is up to date"""
        if not self.workdir.exists():
            subprocess.run(
                ["/usr/bin/git", "clone", self.github_repo, str(self.workdir)],
                check=True,
                shell=False,
            )
            logger.info(f"Cloned sessions repo to {self.workdir}")
        else:
            subprocess.run(
                ["/usr/bin/git", "-C", str(self.workdir), "fetch", "origin"],
                check=True,
                shell=False,
            )
            subprocess.run(
                [
                    "/usr/bin/git",
                    "-C",
                    str(self.workdir),
                    "reset",
                    "--hard",
                    "origin/main",
                ],
                check=True,
                shell=False,
            )
            logger.info("Updated local sessions repo")

    def write_session_file(self, account_id: str, encrypted_bytes: bytes):
        """Write encrypted session to file"""
        sessions_dir = self.workdir / "sessions"
        sessions_dir.mkdir(exist_ok=True)

        file_path = sessions_dir / f"{account_id}.enc"
        with open(file_path, "wb") as f:
            f.write(encrypted_bytes)

    def build_manifest(self, sessions: list) -> dict:
        """Build manifest file for sessions"""
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "sessions": [],
        }

        for session in sessions:
            manifest["sessions"].append(
                {
                    "account_id": session["account_id"],
                    "file": f"sessions/{session['account_id']}.enc",
                    "sha256": session["sha256"],
                    "ts": session["last_updated"].isoformat(),
                }
            )

        return manifest

    def sign_manifest(self, manifest_path: Path):
        """Sign manifest with GPG"""
        if not GPG_KEY_ID:
            logger.warning("GPG_KEY_ID not set, skipping manifest signing")
            return

        try:
            subprocess.run(
                [
                    "/usr/bin/gpg",
                    "--batch",
                    "--yes",
                    "--detach-sign",
                    "--armor",
                    "--default-key",
                    GPG_KEY_ID,
                    "--output",
                    str(manifest_path) + ".sig",
                    str(manifest_path),
                ],
                check=True,
                shell=False,
            )
            logger.info("Manifest signed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to sign manifest: {e}")
            raise

    def commit_and_push(self, message: str) -> str:
        """Commit changes and push to GitHub"""
        subprocess.run(["git", "-C", str(self.workdir), "add", "."], check=True)

        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "-C", str(self.workdir), "diff", "--cached", "--quiet"],
            capture_output=True,
        )

        if result.returncode == 0:
            logger.info("No changes to commit")
            return None

        subprocess.run(
            ["git", "-C", str(self.workdir), "commit", "-m", message], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.workdir), "push", "origin", "main"], check=True
        )

        # Get commit SHA
        commit_sha = (
            subprocess.check_output(
                ["git", "-C", str(self.workdir), "rev-parse", "HEAD"]
            )
            .strip()
            .decode()
        )

        logger.info(f"Pushed sessions to GitHub, commit: {commit_sha}")
        return commit_sha

    def push_sessions_batch(self) -> bool:
        """Push unpersisted sessions to GitHub"""
        if not self.enabled:
            logger.info("Session backup disabled")
            return False

        try:
            # Get unpersisted sessions
            sessions = get_unpersisted_sessions()
            if not sessions:
                logger.info("No sessions to push")
                return True

            logger.info(f"Pushing {len(sessions)} sessions to GitHub")

            # Ensure local clone
            self.ensure_local_clone()

            # Write session files
            for session in sessions:
                self.write_session_file(session["account_id"], session["enc_blob"])

            # Build and write manifest
            manifest = self.build_manifest(sessions)
            manifest_dir = self.workdir / "manifests"
            manifest_dir.mkdir(exist_ok=True)

            manifest_path = manifest_dir / "sessions.json"
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2, sort_keys=True)

            # Sign manifest
            self.sign_manifest(manifest_path)

            # Commit and push
            commit_sha = self.commit_and_push(
                f"Session backup @ {datetime.now(timezone.utc).isoformat()}Z"
            )

            if commit_sha:
                # Mark sessions as persisted
                for session in sessions:
                    mark_session_persisted(
                        session["account_id"], commit_sha, manifest["generated_at"]
                    )

                    # Log audit event
                    log_audit_event(
                        session["account_id"],
                        "push_to_github",
                        {
                            "commit": commit_sha,
                            "manifest_version": manifest["generated_at"],
                        },
                        "scheduler",
                    )

                logger.info(f"Successfully pushed {len(sessions)} sessions")

            return True

        except Exception as e:
            logger.error(f"Failed to push sessions: {e}")
            # Log failure
            log_audit_event(
                None,
                "push_to_github",
                {
                    "error": str(e),
                    "session_count": len(sessions) if "sessions" in locals() else 0,
                },
                "scheduler",
            )
            return False

    def compact_history(self) -> bool:
        """Compact GitHub repository history"""
        if not self.enabled:
            logger.info("Session backup disabled")
            return False

        try:
            logger.info("Starting history compaction")

            # Ensure local clone
            self.ensure_local_clone()

            # Create backup branch
            ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            backup_branch = f"backup_history_{ts}"

            subprocess.run(
                ["git", "-C", str(self.workdir), "checkout", "-B", backup_branch],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(self.workdir), "push", "origin", backup_branch],
                check=True,
            )

            # Create orphan branch with current files
            subprocess.run(
                ["git", "-C", str(self.workdir), "checkout", "--orphan", "clean_main"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(self.workdir), "rm", "-rf", "."], check=True
            )

            # Re-add current files
            if (self.workdir / "sessions").exists():
                subprocess.run(
                    ["git", "-C", str(self.workdir), "add", "sessions"], check=True
                )
            if (self.workdir / "manifests").exists():
                subprocess.run(
                    ["git", "-C", str(self.workdir), "add", "manifests"], check=True
                )

            subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.workdir),
                    "commit",
                    "-m",
                    f"compact snapshot @ {ts}",
                ],
                check=True,
            )

            # Force-push to main
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.workdir),
                    "push",
                    "-f",
                    "origin",
                    "clean_main:main",
                ],
                check=True,
            )

            # Clean up local branch
            subprocess.run(
                ["git", "-C", str(self.workdir), "checkout", "main"], check=True
            )
            subprocess.run(
                ["git", "-C", str(self.workdir), "branch", "-D", "clean_main"],
                check=True,
            )

            # Log audit event
            log_audit_event(
                None,
                "compact_history",
                {"backup_branch": backup_branch, "timestamp": ts},
                "scheduler",
            )

            logger.info(f"History compacted successfully, backup: {backup_branch}")
            return True

        except Exception as e:
            logger.error(f"Failed to compact history: {e}")
            log_audit_event(None, "compact_history", {"error": str(e)}, "scheduler")
            return False
