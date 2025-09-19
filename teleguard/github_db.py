"""
GitHub JSON Database Client for TeleGuard

A production-ready implementation that uses GitHub repository as a JSON database
with safe concurrent access, encryption support, and conflict resolution.
"""

import base64
import json
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple, Union
from urllib.parse import quote

import requests
from cryptography.fernet import Fernet


class GitHubDBError(Exception):
    """Base exception for GitHub DB operations"""

    pass


class RateLimitError(GitHubDBError):
    """Raised when GitHub API rate limit is exceeded"""

    pass


class ConflictError(GitHubDBError):
    """Raised when there's a conflict during update"""

    pass


class PermissionError(GitHubDBError):
    """Raised when GitHub API returns permission error"""

    pass


@dataclass
class RateLimit:
    """GitHub API rate limit information"""

    limit: int
    remaining: int
    reset_time: int

    @property
    def reset_in_seconds(self) -> int:
        return max(0, self.reset_time - int(time.time()))


class GitHubJSONDB:
    """
    GitHub-based JSON database client with safe concurrent access.

    Features:
    - Optimistic concurrency control using SHA
    - Automatic retry with exponential backoff
    - Optional Fernet encryption
    - Deep merge conflict resolution
    - Rate limit handling
    """

    def __init__(
        self,
        owner: str,
        repo: str,
        token: str,
        branch: str = "db-live",
        write_allowed: bool = False,
        base_url: str = "https://api.github.com",
    ):
        """
        Initialize GitHub JSON DB client.

        Args:
            owner: GitHub repository owner
            repo: GitHub repository name
            token: GitHub personal access token
            branch: Branch to use for database files
            write_allowed: Whether write operations are allowed
            base_url: GitHub API base URL
        """
        self.owner = owner
        self.repo = repo
        self.token = token
        self.branch = branch
        self.write_allowed = write_allowed
        self.base_url = base_url.rstrip("/")

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "TeleGuard-GitHubDB/1.0",
            }
        )

    def _get_rate_limit(self) -> RateLimit:
        """Get current rate limit status"""
        response = self.session.get(f"{self.base_url}/rate_limit")
        if response.status_code == 200:
            data = response.json()
            core = data["resources"]["core"]
            return RateLimit(
                limit=core["limit"],
                remaining=core["remaining"],
                reset_time=core["reset"],
            )
        return RateLimit(5000, 5000, int(time.time()) + 3600)

    def _create_branch_if_not_exists(self):
        """Create database branch if it doesn't exist"""
        print(f"Checking if branch {self.branch} exists in {self.owner}/{self.repo}")

        # Check if branch exists
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/branches/{self.branch}"
        response = self._make_request("GET", url)

        if response.status_code == 200:
            print(f"Branch {self.branch} already exists")
            return  # Branch exists

        if response.status_code != 404:
            raise GitHubDBError(
                f"Failed to check branch: {response.status_code} {response.text}"
            )

        print(f"Branch {self.branch} does not exist, creating it...")

        # Get default branch SHA
        repo_url = f"{self.base_url}/repos/{self.owner}/{self.repo}"
        repo_response = self._make_request("GET", repo_url)

        if repo_response.status_code != 200:
            raise GitHubDBError(
                f"Failed to get repo info: {repo_response.status_code} {repo_response.text}"
            )

        repo_data = repo_response.json()
        default_branch = repo_data["default_branch"]
        print(f"Default branch: {default_branch}")

        # Get default branch SHA
        ref_url = f"{self.base_url}/repos/{self.owner}/{self.repo}/git/refs/heads/{default_branch}"
        ref_response = self._make_request("GET", ref_url)

        if ref_response.status_code != 200:
            raise GitHubDBError(
                f"Failed to get default branch SHA: {ref_response.status_code} {ref_response.text}"
            )

        base_sha = ref_response.json()["object"]["sha"]
        print(f"Base SHA: {base_sha}")

        # Create new branch
        create_ref_url = f"{self.base_url}/repos/{self.owner}/{self.repo}/git/refs"
        create_payload = {"ref": f"refs/heads/{self.branch}", "sha": base_sha}

        print(f"Creating branch with payload: {create_payload}")
        create_response = self._make_request(
            "POST", create_ref_url, json=create_payload
        )

        if create_response.status_code != 201:
            print(
                f"Branch creation failed: {create_response.status_code} {create_response.text}"
            )
            raise GitHubDBError(
                f"Failed to create branch: {create_response.status_code} {create_response.text}"
            )

        print(f"Branch {self.branch} created successfully")

        # Create initial database structure
        initial_data = {
            "created_at": int(time.time()),
            "version": "1.0",
            "description": "TeleGuard Database",
        }

        print("Creating initial database structure...")
        self.put_json(
            "db/metadata.json",
            initial_data,
            f"Initialize {self.branch} database branch",
        )
        print("Database initialization complete")

    def _wait_for_rate_limit(self, retry_after: Optional[int] = None):
        """Wait for rate limit reset with jitter"""
        if retry_after:
            wait_time = retry_after
        else:
            rate_limit = self._get_rate_limit()
            wait_time = rate_limit.reset_in_seconds

        # Add jitter to avoid thundering herd
        jitter = random.uniform(0.1, 0.3) * wait_time
        total_wait = min(wait_time + jitter, 300)  # Max 5 minutes

        print(f"Rate limit exceeded, waiting {total_wait:.1f} seconds...")
        time.sleep(total_wait)

    def _make_request(
        self, method: str, url: str, max_retries: int = 5, **kwargs
    ) -> requests.Response:
        """Make HTTP request with retry logic and rate limit handling"""
        for attempt in range(max_retries):
            try:
                response = self.session.request(method, url, **kwargs)

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        self._wait_for_rate_limit(int(retry_after))
                    else:
                        self._wait_for_rate_limit()
                    continue

                # Handle other errors
                if response.status_code == 403:
                    if "rate limit" in response.text.lower():
                        self._wait_for_rate_limit()
                        continue
                    else:
                        raise PermissionError(f"Permission denied: {response.text}")

                if response.status_code >= 500:
                    if attempt < max_retries - 1:
                        wait_time = (2**attempt) + random.uniform(0, 1)
                        time.sleep(wait_time)
                        continue

                return response

            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    time.sleep(wait_time)
                    continue
                raise GitHubDBError(f"Request failed after {max_retries} attempts: {e}")

        raise GitHubDBError(f"Request failed after {max_retries} attempts")

    def get_json(
        self, path: str, decrypt_with_fernet: Optional[Fernet] = None
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Get JSON object from GitHub repository.

        Args:
            path: File path in repository (e.g., 'db/user_settings.json')
            decrypt_with_fernet: Optional Fernet instance for decryption

        Returns:
            Tuple of (json_object, sha). Returns ({}, None) if file doesn't exist.
        """
        encoded_path = quote(path, safe="/")
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/contents/{encoded_path}"

        params = {"ref": self.branch}
        response = self._make_request("GET", url, params=params)

        if response.status_code == 404:
            return {}, None

        if response.status_code != 200:
            raise GitHubDBError(
                f"Failed to get {path}: {response.status_code} {response.text}"
            )

        data = response.json()
        content = base64.b64decode(data["content"]).decode("utf-8")

        # Decrypt if needed
        if decrypt_with_fernet:
            try:
                content = decrypt_with_fernet.decrypt(content.encode()).decode("utf-8")
            except Exception as e:
                raise GitHubDBError(f"Failed to decrypt {path}: {e}")

        try:
            json_obj = json.loads(content)
        except json.JSONDecodeError as e:
            raise GitHubDBError(f"Invalid JSON in {path}: {e}")

        return json_obj, data["sha"]

    def put_json(
        self,
        path: str,
        obj: Dict[str, Any],
        commit_message: str,
        sha: Optional[str] = None,
        encrypt_with_fernet: Optional[Fernet] = None,
    ) -> str:
        """
        Put JSON object to GitHub repository.

        Args:
            path: File path in repository
            obj: JSON object to store
            commit_message: Git commit message
            sha: Current file SHA for optimistic locking (None for new files)
            encrypt_with_fernet: Optional Fernet instance for encryption

        Returns:
            New SHA of the file
        """
        if not self.write_allowed:
            raise GitHubDBError(
                "Write operations not allowed. Set DB_WRITE_ALLOWED=true"
            )

        # Create branch on first write if needed
        try:
            self._create_branch_if_not_exists()
        except Exception as e:
            print(f"Warning: Could not create branch {self.branch}: {e}")
            # Continue anyway, maybe branch exists

        # Serialize JSON
        content = json.dumps(obj, indent=2, sort_keys=True)

        # Encrypt if needed
        if encrypt_with_fernet:
            content = encrypt_with_fernet.encrypt(content.encode()).decode()

        # Encode content
        encoded_content = base64.b64encode(content.encode()).decode()

        encoded_path = quote(path, safe="/")
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/contents/{encoded_path}"

        payload = {
            "message": commit_message,
            "content": encoded_content,
            "branch": self.branch,
        }

        if sha:
            payload["sha"] = sha

        response = self._make_request("PUT", url, json=payload)

        if response.status_code in (409, 422):
            raise ConflictError(f"Conflict updating {path}: {response.text}")

        if response.status_code not in (200, 201):
            raise GitHubDBError(
                f"Failed to put {path}: {response.status_code} {response.text}"
            )

        return response.json()["content"]["sha"]

    def _deep_merge(
        self, base: Dict[str, Any], incoming: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Deep merge two dictionaries, with incoming taking precedence.

        Args:
            base: Base dictionary
            incoming: Incoming changes

        Returns:
            Merged dictionary
        """
        result = base.copy()

        for key, value in incoming.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

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
        Safely update JSON file with conflict resolution.

        Args:
            path: File path in repository
            modify_func: Function that takes current object and returns modified object
            commit_message: Git commit message
            max_retries: Maximum number of retry attempts
            encrypt_with_fernet: Optional Fernet instance for encryption
            merge_strategy: Conflict resolution strategy ('deep_merge', 'incoming_wins', 'latest_wins')

        Returns:
            New SHA of the file
        """
        if not self.write_allowed:
            raise GitHubDBError(
                "Write operations not allowed. Set DB_WRITE_ALLOWED=true"
            )

        for attempt in range(max_retries):
            try:
                # Get current state
                current_obj, current_sha = self.get_json(path, encrypt_with_fernet)

                # Apply modifications
                modified_obj = modify_func(current_obj.copy())

                # Try to update
                return self.put_json(
                    path, modified_obj, commit_message, current_sha, encrypt_with_fernet
                )

            except ConflictError:
                if attempt >= max_retries - 1:
                    raise

                # Handle conflict based on strategy
                if merge_strategy == "latest_wins":
                    # Just retry with latest version
                    continue
                elif merge_strategy == "incoming_wins":
                    # Force update (get latest SHA and overwrite)
                    _, latest_sha = self.get_json(path, decrypt_with_fernet)
                    modified_obj = modify_func({})  # Start fresh
                    return self.put_json(
                        path,
                        modified_obj,
                        commit_message,
                        latest_sha,
                        encrypt_with_fernet,
                    )
                elif merge_strategy == "deep_merge":
                    # Get latest version and merge changes
                    latest_obj, latest_sha = self.get_json(path, encrypt_with_fernet)
                    our_changes = modify_func(current_obj.copy())
                    merged_obj = self._deep_merge(latest_obj, our_changes)
                    return self.put_json(
                        path,
                        merged_obj,
                        commit_message,
                        latest_sha,
                        encrypt_with_fernet,
                    )

                # Wait before retry
                wait_time = (2**attempt) + random.uniform(0, 1)
                time.sleep(wait_time)

        raise GitHubDBError(f"Failed to update {path} after {max_retries} attempts")

    def create_lock(self, resource: str, ttl: int = 300) -> bool:
        """
        Create a simple lock using GitHub files (best effort only).

        WARNING: This is not a distributed lock! Use only for coordination hints.
        GitHub API doesn't provide atomic operations, so this can have race conditions.

        Args:
            resource: Resource name to lock
            ttl: Lock TTL in seconds

        Returns:
            True if lock acquired, False otherwise
        """
        if not self.write_allowed:
            return False

        lock_path = f"locks/{resource}.lock"
        lock_data = {
            "locked_at": int(time.time()),
            "ttl": ttl,
            "owner": f"teleguard-{os.getpid()}",
        }

        try:
            # Check if lock exists and is valid
            current_lock, sha = self.get_json(lock_path)
            if current_lock:
                locked_at = current_lock.get("locked_at", 0)
                lock_ttl = current_lock.get("ttl", 300)
                if time.time() - locked_at < lock_ttl:
                    return False  # Lock still valid

            # Try to acquire lock
            self.put_json(lock_path, lock_data, f"Acquire lock for {resource}", sha)
            return True

        except (ConflictError, GitHubDBError):
            return False

    def release_lock(self, resource: str) -> bool:
        """
        Release a lock (best effort only).

        Args:
            resource: Resource name to unlock

        Returns:
            True if lock released, False otherwise
        """
        if not self.write_allowed:
            return False

        lock_path = f"locks/{resource}.lock"

        try:
            current_lock, sha = self.get_json(lock_path)
            if not current_lock:
                return True  # No lock exists

            # Delete lock file by putting empty content
            self.put_json(lock_path, {}, f"Release lock for {resource}", sha)
            return True

        except (ConflictError, GitHubDBError):
            return False


# Example usage and testing
if __name__ == "__main__":
    import os

    from cryptography.fernet import Fernet

    # Example configuration
    db = GitHubJSONDB(
        owner=os.getenv("DB_GITHUB_OWNER", "your_owner"),
        repo=os.getenv("DB_GITHUB_REPO", "your_repo"),
        token=os.getenv("GITHUB_TOKEN", "your_token_here"),
        branch=os.getenv("DB_GITHUB_BRANCH", "db-live"),
        write_allowed=os.getenv("DB_WRITE_ALLOWED", "false").lower() == "true",
    )

    # Example 1: Read a file
    print("=== Reading user_settings.json ===")
    settings, sha = db.get_json("db/user_settings.json")
    print(f"Current settings: {settings}")
    print(f"SHA: {sha}")

    # Example 2: Safe update
    if db.write_allowed:
        print("\n=== Safe update example ===")

        def add_user(current_data):
            users = current_data.setdefault("users", {})
            users["123456"] = {"name": "Test User", "created_at": int(time.time())}
            return current_data

        try:
            new_sha = db.safe_update_json(
                "db/user_settings.json", add_user, "Add test user via GitHub DB"
            )
            print(f"Updated successfully, new SHA: {new_sha}")
        except Exception as e:
            print(f"Update failed: {e}")

    # Example 3: Encryption
    if os.getenv("FERNET_KEY"):
        print("\n=== Encryption example ===")
        fernet = Fernet(os.getenv("FERNET_KEY").encode())

        # Write encrypted data
        if db.write_allowed:
            secret_data = {"api_key": "secret123", "password": "hidden"}
            db.put_json(
                "db/secrets.json.enc",
                secret_data,
                "Store encrypted secrets",
                encrypt_with_fernet=fernet,
            )

        # Read encrypted data
        decrypted_data, _ = db.get_json(
            "db/secrets.json.enc", decrypt_with_fernet=fernet
        )
        print(f"Decrypted data: {decrypted_data}")

    # Example 4: Lock usage (demonstration only)
    print("\n=== Lock example ===")
    if db.create_lock("user_settings", ttl=60):
        print("Lock acquired!")
        time.sleep(1)
        db.release_lock("user_settings")
        print("Lock released!")
    else:
        print("Failed to acquire lock")
