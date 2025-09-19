"""GitHub backup operations"""

import os
import subprocess
import tempfile
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

GIT_REPO_URL = os.getenv("GITHUB_REPO")
GIT_BRANCH = os.getenv("GITHUB_BACKUP_BRANCH", "backups")
GIT_AUTHOR_NAME = "teleguard-bot"
GIT_AUTHOR_EMAIL = "noreply@teleguard.bot"

def _run(cmd, cwd=None):
    """Run shell command"""
    subprocess.check_call(cmd, shell=True, cwd=cwd)

def push_hourly_snapshot(local_snapshot_path: str):
    """Push hourly snapshot to GitHub (preserves history)"""
    if not GIT_REPO_URL:
        logger.warning("GITHUB_REPO not configured, skipping GitHub backup")
        return
    
    with tempfile.TemporaryDirectory() as tmp:
        try:
            _run(f"git clone {GIT_REPO_URL} .", cwd=tmp)
            _run(f"git checkout -B {GIT_BRANCH}", cwd=tmp)
            
            # Create snapshots directory
            snapshots_dir = os.path.join(tmp, "snapshots")
            os.makedirs(snapshots_dir, exist_ok=True)
            
            # Copy snapshot file
            dst = os.path.join(snapshots_dir, os.path.basename(local_snapshot_path))
            if os.name == 'nt':  # Windows
                _run(f'copy "{local_snapshot_path}" "{dst}"', cwd=tmp)
            else:  # Unix
                _run(f'cp "{local_snapshot_path}" "{dst}"', cwd=tmp)
            
            _run("git add -A", cwd=tmp)
            ts = datetime.utcnow().isoformat()
            _run(f'git -c user.name="{GIT_AUTHOR_NAME}" -c user.email="{GIT_AUTHOR_EMAIL}" commit -m "hourly snapshot {ts}" || echo "No changes"', cwd=tmp)
            _run(f"git push origin {GIT_BRANCH}", cwd=tmp)
            
            logger.info(f"Pushed hourly snapshot to GitHub: {os.path.basename(local_snapshot_path)}")
            
        except Exception as e:
            logger.error(f"Failed to push hourly snapshot: {e}")

def force_orphan_push_latest(local_snapshot_path: str):
    """Create orphan branch with only latest snapshot (removes history)"""
    if not GIT_REPO_URL:
        logger.warning("GITHUB_REPO not configured, skipping GitHub cleanup")
        return
    
    with tempfile.TemporaryDirectory() as tmp:
        try:
            _run("git init .", cwd=tmp)
            _run(f"git remote add origin {GIT_REPO_URL}", cwd=tmp)
            
            # Copy snapshot file
            dst = os.path.join(tmp, os.path.basename(local_snapshot_path))
            if os.name == 'nt':  # Windows
                _run(f'copy "{local_snapshot_path}" "{dst}"', cwd=tmp)
            else:  # Unix
                _run(f'cp "{local_snapshot_path}" "{dst}"', cwd=tmp)
            
            _run("git add -A", cwd=tmp)
            ts = datetime.utcnow().isoformat()
            _run(f'git -c user.name="{GIT_AUTHOR_NAME}" -c user.email="{GIT_AUTHOR_EMAIL}" commit -m "orphan snapshot {ts}"', cwd=tmp)
            _run(f"git branch -M {GIT_BRANCH}", cwd=tmp)
            _run(f"git push --force origin {GIT_BRANCH}", cwd=tmp)
            
            logger.info(f"Force pushed orphan snapshot to GitHub: {os.path.basename(local_snapshot_path)}")
            
        except Exception as e:
            logger.error(f"Failed to force push orphan snapshot: {e}")