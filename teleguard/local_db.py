"""
Local JSON Database Client - Fallback for GitHub DB

A simple local file-based JSON database that provides the same interface
as GitHubJSONDB for seamless switching between local and GitHub storage.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from cryptography.fernet import Fernet


class LocalJSONDB:
    """
    Local file-based JSON database with the same interface as GitHubJSONDB.

    This provides a fallback when USE_GITHUB_DB=false or for local development.
    """

    def __init__(self, base_path: str = ".", write_allowed: bool = True):
        """
        Initialize local JSON DB client.

        Args:
            base_path: Base directory for database files
            write_allowed: Whether write operations are allowed
        """
        self.base_path = Path(base_path)
        self.write_allowed = write_allowed

        # Ensure base directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, path: str) -> Path:
        """Get full file path from relative path"""
        return self.base_path / path

    def _calculate_sha(self, content: str) -> str:
        """Calculate SHA hash for content (simulates GitHub SHA)"""
        return hashlib.sha1(content.encode()).hexdigest()

    def get_json(
        self, path: str, decrypt_with_fernet: Optional[Fernet] = None
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Get JSON object from local file.

        Args:
            path: File path relative to base_path
            decrypt_with_fernet: Optional Fernet instance for decryption

        Returns:
            Tuple of (json_object, sha). Returns ({}, None) if file doesn't exist.
        """
        file_path = self._get_file_path(path)

        if not file_path.exists():
            return {}, None

        try:
            content = file_path.read_text(encoding="utf-8")

            # Decrypt if needed
            if decrypt_with_fernet:
                try:
                    content = decrypt_with_fernet.decrypt(content.encode()).decode(
                        "utf-8"
                    )
                except Exception as e:
                    raise ValueError(f"Failed to decrypt {path}: {e}")

            json_obj = json.loads(content)
            sha = self._calculate_sha(content)

            return json_obj, sha

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"Failed to read {path}: {e}")

    def put_json(
        self,
        path: str,
        obj: Dict[str, Any],
        commit_message: str,
        sha: Optional[str] = None,
        encrypt_with_fernet: Optional[Fernet] = None,
    ) -> str:
        """
        Put JSON object to local file.

        Args:
            path: File path relative to base_path
            obj: JSON object to store
            commit_message: Commit message (logged but not used)
            sha: Current file SHA for optimistic locking (optional for local)
            encrypt_with_fernet: Optional Fernet instance for encryption

        Returns:
            New SHA of the file
        """
        if not self.write_allowed:
            raise PermissionError("Write operations not allowed")

        file_path = self._get_file_path(path)

        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Check SHA if provided (optimistic locking)
        if sha and file_path.exists():
            current_content = file_path.read_text(encoding="utf-8")
            current_sha = self._calculate_sha(current_content)
            if current_sha != sha:
                raise ValueError(
                    f"SHA mismatch for {path}: expected {sha}, got {current_sha}"
                )

        # Serialize JSON
        content = json.dumps(obj, indent=2, sort_keys=True)

        # Encrypt if needed
        if encrypt_with_fernet:
            content = encrypt_with_fernet.encrypt(content.encode()).decode()

        # Write file
        file_path.write_text(content, encoding="utf-8")

        # Log the operation
        print(f"LocalDB: {commit_message} -> {path}")

        return self._calculate_sha(content)

    def safe_update_json(
        self,
        path: str,
        modify_func: Callable[[Dict[str, Any]], Dict[str, Any]],
        commit_message: str,
        max_retries: int = 5,
        encrypt_with_fernet: Optional[Fernet] = None,
        merge_strategy: str = "deep_merge",
    ) -> str:
        """
        Safely update JSON file (no concurrency issues in local mode).

        Args:
            path: File path relative to base_path
            modify_func: Function that takes current object and returns modified object
            commit_message: Commit message
            max_retries: Maximum retries (not used in local mode)
            encrypt_with_fernet: Optional Fernet instance for encryption
            merge_strategy: Merge strategy (not used in local mode)

        Returns:
            New SHA of the file
        """
        if not self.write_allowed:
            raise PermissionError("Write operations not allowed")

        # Get current state
        current_obj, current_sha = self.get_json(path, decrypt_with_fernet)

        # Apply modifications
        modified_obj = modify_func(current_obj.copy())

        # Update file
        return self.put_json(
            path, modified_obj, commit_message, current_sha, encrypt_with_fernet
        )

    def create_lock(self, resource: str, ttl: int = 300) -> bool:
        """
        Create a lock file (simple file-based locking).

        Args:
            resource: Resource name to lock
            ttl: Lock TTL in seconds

        Returns:
            True if lock acquired, False otherwise
        """
        if not self.write_allowed:
            return False

        lock_path = self._get_file_path(f"locks/{resource}.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if lock exists and is valid
        if lock_path.exists():
            try:
                lock_data = json.loads(lock_path.read_text())
                locked_at = lock_data.get("locked_at", 0)
                lock_ttl = lock_data.get("ttl", 300)
                if time.time() - locked_at < lock_ttl:
                    return False  # Lock still valid
            except (json.JSONDecodeError, KeyError):
                pass  # Invalid lock file, proceed to acquire

        # Acquire lock
        lock_data = {
            "locked_at": int(time.time()),
            "ttl": ttl,
            "owner": f"teleguard-{os.getpid()}",
        }

        try:
            lock_path.write_text(json.dumps(lock_data, indent=2))
            return True
        except OSError:
            return False

    def release_lock(self, resource: str) -> bool:
        """
        Release a lock by deleting the lock file.

        Args:
            resource: Resource name to unlock

        Returns:
            True if lock released, False otherwise
        """
        if not self.write_allowed:
            return False

        lock_path = self._get_file_path(f"locks/{resource}.lock")

        try:
            if lock_path.exists():
                lock_path.unlink()
            return True
        except OSError:
            return False


# Example usage
if __name__ == "__main__":
    import tempfile

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        db = LocalJSONDB(temp_dir, write_allowed=True)

        # Test basic operations
        print("=== Testing LocalJSONDB ===")

        # Test read non-existent file
        data, sha = db.get_json("test.json")
        print(f"Non-existent file: {data}, SHA: {sha}")

        # Test write
        test_data = {"users": {"123": {"name": "Test User"}}}
        new_sha = db.put_json("test.json", test_data, "Create test file")
        print(f"Written file, SHA: {new_sha}")

        # Test read existing file
        data, sha = db.get_json("test.json")
        print(f"Read file: {data}, SHA: {sha}")

        # Test safe update
        def add_user(current):
            current.setdefault("users", {})["456"] = {"name": "Another User"}
            return current

        updated_sha = db.safe_update_json("test.json", add_user, "Add another user")
        print(f"Updated file, SHA: {updated_sha}")

        # Test final state
        final_data, final_sha = db.get_json("test.json")
        print(f"Final data: {final_data}")

        # Test locking
        print("\n=== Testing locks ===")
        if db.create_lock("test_resource", ttl=5):
            print("Lock acquired!")
            time.sleep(1)
            db.release_lock("test_resource")
            print("Lock released!")
        else:
            print("Failed to acquire lock")
