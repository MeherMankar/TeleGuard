#!/usr/bin/env python3
"""
Migrate Local Database Files to GitHub

This script migrates all local JSON database files to GitHub repository.
Requires DB_WRITE_ALLOWED=true to actually perform writes.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from teleguard.github_db import GitHubDBError, GitHubJSONDB
from teleguard.local_db import LocalJSONDB


def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables"""
    config = {
        "use_github_db": os.getenv("USE_GITHUB_DB", "false").lower() == "true",
        "db_github_owner": os.getenv("DB_GITHUB_OWNER"),
        "db_github_repo": os.getenv("DB_GITHUB_REPO"),
        "db_github_branch": os.getenv("DB_GITHUB_BRANCH", "db-live"),
        "github_token": os.getenv("GITHUB_TOKEN"),
        "db_write_allowed": os.getenv("DB_WRITE_ALLOWED", "false").lower() == "true",
        "local_db_path": os.getenv("LOCAL_DB_PATH", "."),
    }

    # Validate required settings
    if not config["db_write_allowed"]:
        print("❌ ERROR: DB_WRITE_ALLOWED must be set to 'true' to run migration")
        print("   This is a safety measure to prevent accidental writes.")
        sys.exit(1)

    if not config["use_github_db"]:
        print("❌ ERROR: USE_GITHUB_DB must be set to 'true' for migration")
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


def find_local_db_files(base_path: str) -> list[Path]:
    """Find all JSON files in the local database directory"""
    db_path = Path(base_path) / "db"
    if not db_path.exists():
        print(f"⚠️  WARNING: Local db directory not found: {db_path}")
        return []

    json_files = list(db_path.glob("*.json"))
    print(f"📁 Found {len(json_files)} JSON files in {db_path}")

    for file_path in json_files:
        print(f"   - {file_path.name} ({file_path.stat().st_size} bytes)")

    return json_files


def migrate_file(
    local_db: LocalJSONDB,
    github_db: GitHubJSONDB,
    local_file: Path,
    dry_run: bool = False,
) -> bool:
    """
    Migrate a single file from local to GitHub.

    Args:
        local_db: Local database client
        github_db: GitHub database client
        local_file: Path to local file
        dry_run: If True, don't actually write to GitHub

    Returns:
        True if migration successful, False otherwise
    """
    # Calculate relative path for GitHub
    relative_path = f"db/{local_file.name}"

    try:
        # Read from local database
        print(f"📖 Reading {local_file.name}...")
        local_data, local_sha = local_db.get_json(relative_path)

        if not local_data:
            print(f"   ⚠️  File is empty, skipping")
            return True

        # Check if file already exists in GitHub
        print(f"🔍 Checking if {relative_path} exists in GitHub...")
        github_data, github_sha = github_db.get_json(relative_path)

        if github_data:
            print(f"   ⚠️  File already exists in GitHub")

            # Compare content
            if local_data == github_data:
                print(f"   ✅ Content is identical, skipping")
                return True
            else:
                print(f"   ⚠️  Content differs between local and GitHub")
                print(
                    f"      Local keys: {list(local_data.keys()) if isinstance(local_data, dict) else 'not dict'}"
                )
                print(
                    f"      GitHub keys: {list(github_data.keys()) if isinstance(github_data, dict) else 'not dict'}"
                )

                response = (
                    input(f"      Overwrite GitHub version? (y/N): ").strip().lower()
                )
                if response != "y":
                    print(f"   ⏭️  Skipping {local_file.name}")
                    return True

        if dry_run:
            print(f"   🔄 [DRY RUN] Would upload {relative_path}")
            return True

        # Upload to GitHub
        print(f"⬆️  Uploading {relative_path} to GitHub...")
        commit_message = f"migrate: import {local_file.name} from local database"

        new_sha = github_db.put_json(
            relative_path,
            local_data,
            commit_message,
            github_sha,  # Use existing SHA if file exists
        )

        print(f"   ✅ Successfully uploaded (SHA: {new_sha[:8]}...)")
        return True

    except Exception as e:
        print(f"   ❌ Failed to migrate {local_file.name}: {e}")
        return False


def main():
    """Main migration function"""
    print("🚀 TeleGuard Database Migration: Local → GitHub")
    print("=" * 50)

    # Load configuration
    config = load_config()

    # Initialize database clients
    print("🔧 Initializing database clients...")

    local_db = LocalJSONDB(base_path=config["local_db_path"], write_allowed=True)

    github_db = GitHubJSONDB(
        owner=config["db_github_owner"],
        repo=config["db_github_repo"],
        token=config["github_token"],
        branch=config["db_github_branch"],
        write_allowed=config["db_write_allowed"],
    )

    print(f"   📁 Local DB path: {config['local_db_path']}")
    print(f"   🐙 GitHub repo: {config['db_github_owner']}/{config['db_github_repo']}")
    print(f"   🌿 GitHub branch: {config['db_github_branch']}")

    # Find local database files
    local_files = find_local_db_files(config["local_db_path"])

    if not local_files:
        print("❌ No local database files found to migrate")
        sys.exit(1)

    # Ask for confirmation
    print(f"\n📋 Migration Plan:")
    print(f"   • Migrate {len(local_files)} files to GitHub")
    print(
        f"   • Target: {config['db_github_owner']}/{config['db_github_repo']}:{config['db_github_branch']}"
    )
    print(f"   • Write mode: {'ENABLED' if config['db_write_allowed'] else 'DISABLED'}")

    # Check if this is a dry run
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print(f"   • Mode: DRY RUN (no actual writes)")

    if not dry_run:
        response = input(f"\n❓ Proceed with migration? (y/N): ").strip().lower()
        if response != "y":
            print("❌ Migration cancelled by user")
            sys.exit(0)

    # Perform migration
    print(f"\n🔄 Starting migration...")

    success_count = 0
    total_count = len(local_files)

    for local_file in local_files:
        print(f"\n📄 Processing {local_file.name}...")

        if migrate_file(local_db, github_db, local_file, dry_run):
            success_count += 1
        else:
            print(f"   ❌ Migration failed for {local_file.name}")

    # Summary
    print(f"\n📊 Migration Summary:")
    print(f"   • Total files: {total_count}")
    print(f"   • Successful: {success_count}")
    print(f"   • Failed: {total_count - success_count}")

    if success_count == total_count:
        print(f"   ✅ All files migrated successfully!")

        if not dry_run:
            print(f"\n💡 Next steps:")
            print(
                f"   1. Verify files in GitHub: https://github.com/{config['db_github_owner']}/{config['db_github_repo']}/tree/{config['db_github_branch']}/db"
            )
            print(f"   2. Test your application with USE_GITHUB_DB=true")
            print(f"   3. Consider backing up local files before switching permanently")

        sys.exit(0)
    else:
        print(f"   ⚠️  Some files failed to migrate")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n❌ Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Migration failed with error: {e}")
        sys.exit(1)
