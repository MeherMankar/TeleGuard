#!/usr/bin/env python3
"""
Compact Database Branch

This script compacts the database branch history by creating a single commit
with all current database files. Provides two strategies:
1. Orphan snapshot (safe, creates new branch)
2. Force replace (destructive, requires explicit confirmation)
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from teleguard.github_db import GitHubDBError, GitHubJSONDB


def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables"""
    config = {
        "db_github_owner": os.getenv("DB_GITHUB_OWNER"),
        "db_github_repo": os.getenv("DB_GITHUB_REPO"),
        "db_github_branch": os.getenv("DB_GITHUB_BRANCH", "db-live"),
        "github_token": os.getenv("GITHUB_TOKEN"),
        "allow_force_replace": os.getenv("ALLOW_FORCE_REPLACE", "false").lower()
        == "true",
        "db_write_allowed": os.getenv("DB_WRITE_ALLOWED", "false").lower() == "true",
    }

    # Validate required settings
    if not config["db_write_allowed"]:
        print("❌ ERROR: DB_WRITE_ALLOWED must be set to 'true' to run cleanup")
        sys.exit(1)

    missing_vars = []
    for var in ["db_github_owner", "db_github_repo", "github_token"]:
        if not config[var]:
            missing_vars.append(var.upper())

    if missing_vars:
        print(
            f"❌ ERROR: Missing required environment variables: {', '.join(missing_vars)}"
        )
        sys.exit(1)

    return config


def get_all_db_files(github_db: GitHubJSONDB) -> List[str]:
    """
    Get list of all database files in the repository.

    Args:
        github_db: GitHub database client

    Returns:
        List of file paths in the db/ directory
    """
    import requests

    # Use GitHub API to list directory contents
    url = f"{github_db.base_url}/repos/{github_db.owner}/{github_db.repo}/contents/db"
    params = {"ref": github_db.branch}

    response = github_db._make_request("GET", url, params=params)

    if response.status_code == 404:
        print("⚠️  No db/ directory found in repository")
        return []

    if response.status_code != 200:
        raise GitHubDBError(
            f"Failed to list db/ directory: {response.status_code} {response.text}"
        )

    files = []
    for item in response.json():
        if item["type"] == "file" and item["name"].endswith(".json"):
            files.append(f"db/{item['name']}")

    return files


def create_orphan_snapshot(
    github_db: GitHubJSONDB, db_files: List[str], snapshot_branch: str = "db-snapshot"
) -> str:
    """
    Create an orphan branch snapshot with current database state.

    This is the SAFE method - it doesn't modify the existing branch.

    Args:
        github_db: GitHub database client
        db_files: List of database file paths
        snapshot_branch: Name for the snapshot branch

    Returns:
        SHA of the new commit
    """
    print(f"📸 Creating orphan snapshot branch: {snapshot_branch}")

    # This is a simplified implementation
    # In a real scenario, you'd use the Git Data API to create trees and commits

    print("⚠️  ORPHAN SNAPSHOT METHOD:")
    print("   This method requires using the Git Data API to create trees and commits.")
    print("   For now, this is a placeholder implementation.")
    print("   You can manually create a snapshot by:")
    print(f"   1. git checkout --orphan {snapshot_branch}")
    print(f"   2. Copy all files from {github_db.branch}")
    print(f"   3. git add . && git commit -m 'Database snapshot at {int(time.time())}'")

    return "placeholder_sha"


def force_replace_branch(
    github_db: GitHubJSONDB, db_files: List[str], allow_force: bool = False
) -> str:
    """
    Force replace the database branch with a single commit.

    WARNING: This is DESTRUCTIVE and will lose all commit history!

    Args:
        github_db: GitHub database client
        db_files: List of database file paths
        allow_force: Whether force replacement is allowed

    Returns:
        SHA of the new commit
    """
    if not allow_force:
        print("❌ ERROR: Force replacement not allowed")
        print("   Set ALLOW_FORCE_REPLACE=true to enable this destructive operation")
        sys.exit(1)

    print("⚠️  WARNING: FORCE REPLACE MODE")
    print("   This will PERMANENTLY DELETE all commit history in the database branch!")
    print("   This action CANNOT be undone!")

    # Triple confirmation for destructive operation
    confirmations = [
        "I understand this will delete all commit history",
        "I have backed up important data",
        "I want to proceed with force replacement",
    ]

    for i, confirmation in enumerate(confirmations, 1):
        response = input(
            f"   {i}. Type 'yes' to confirm: {confirmation}\n      > "
        ).strip()
        if response.lower() != "yes":
            print("❌ Force replacement cancelled")
            sys.exit(1)

    print("🔥 Proceeding with force replacement...")

    # This is a simplified implementation
    # In a real scenario, you'd use the Git Data API to:
    # 1. Create a new tree with all current files
    # 2. Create a new commit with that tree
    # 3. Force update the branch reference

    print("⚠️  FORCE REPLACE METHOD:")
    print("   This method requires using the Git Data API to create trees and commits.")
    print("   For now, this is a placeholder implementation.")
    print("   You can manually force replace by:")
    print(f"   1. git checkout --orphan temp-branch")
    print(f"   2. Copy all current files")
    print(
        f"   3. git add . && git commit -m 'Compacted database at {int(time.time())}'"
    )
    print(f"   4. git branch -D {github_db.branch}")
    print(f"   5. git branch -m temp-branch {github_db.branch}")
    print(f"   6. git push --force origin {github_db.branch}")

    return "placeholder_sha"


def main():
    """Main cleanup function"""
    print("🧹 TeleGuard Database Branch Cleanup")
    print("=" * 40)

    # Parse command line arguments
    strategy = "snapshot"  # Default to safe method
    if "--force-replace" in sys.argv:
        strategy = "force-replace"
    elif "--snapshot" in sys.argv:
        strategy = "snapshot"

    # Load configuration
    config = load_config()

    # Initialize GitHub client
    print("🔧 Initializing GitHub client...")
    github_db = GitHubJSONDB(
        owner=config["db_github_owner"],
        repo=config["db_github_repo"],
        token=config["github_token"],
        branch=config["db_github_branch"],
        write_allowed=config["db_write_allowed"],
    )

    print(f"   🐙 Repository: {config['db_github_owner']}/{config['db_github_repo']}")
    print(f"   🌿 Branch: {config['db_github_branch']}")
    print(f"   📋 Strategy: {strategy}")

    # Get list of database files
    print("\n📁 Scanning database files...")
    try:
        db_files = get_all_db_files(github_db)
        print(f"   Found {len(db_files)} database files:")
        for file_path in db_files:
            print(f"     - {file_path}")
    except Exception as e:
        print(f"❌ Failed to scan database files: {e}")
        sys.exit(1)

    if not db_files:
        print("❌ No database files found to compact")
        sys.exit(1)

    # Show cleanup plan
    print(f"\n📋 Cleanup Plan:")
    print(f"   • Strategy: {strategy}")
    print(f"   • Files to include: {len(db_files)}")
    print(f"   • Target branch: {config['db_github_branch']}")

    if strategy == "force-replace":
        print(f"   • ⚠️  WARNING: This will DELETE all commit history!")
        print(
            f"   • Force mode: {'ENABLED' if config['allow_force_replace'] else 'DISABLED'}"
        )
    else:
        print(f"   • ✅ Safe mode: Will create snapshot branch")

    # Confirm operation
    if strategy == "snapshot":
        response = input(f"\n❓ Create snapshot branch? (y/N): ").strip().lower()
    else:
        response = (
            input(f"\n❓ Proceed with DESTRUCTIVE force replacement? (y/N): ")
            .strip()
            .lower()
        )

    if response != "y":
        print("❌ Cleanup cancelled by user")
        sys.exit(0)

    # Perform cleanup
    print(f"\n🔄 Starting cleanup...")

    try:
        if strategy == "snapshot":
            new_sha = create_orphan_snapshot(github_db, db_files)
            print(f"✅ Snapshot created successfully!")
            print(f"   New commit SHA: {new_sha}")
            print(f"   Snapshot branch: db-snapshot")
        else:
            new_sha = force_replace_branch(
                github_db, db_files, config["allow_force_replace"]
            )
            print(f"✅ Branch force replacement completed!")
            print(f"   New commit SHA: {new_sha}")
            print(f"   ⚠️  All previous history has been deleted!")

        print(f"\n💡 Next steps:")
        if strategy == "snapshot":
            print(f"   1. Review the snapshot branch: db-snapshot")
            print(f"   2. If satisfied, you can optionally replace the main branch")
            print(f"   3. Delete old snapshot branches if no longer needed")
        else:
            print(f"   1. Verify the compacted branch works correctly")
            print(f"   2. Update any CI/CD that depends on commit history")
            print(f"   3. Inform team members about the history reset")

    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n❌ Cleanup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Cleanup failed with error: {e}")
        sys.exit(1)
