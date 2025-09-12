#!/usr/bin/env python3
"""Development environment setup script"""
import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run command and handle errors"""
    print(f"🔧 {description}...")
    try:
        result = subprocess.run(
            cmd, shell=True, check=True, capture_output=True, text=True
        )
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e.stderr}")
        return False


def main():
    """Setup development environment"""
    print("🚀 Setting up TeleGuard development environment...")

    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        sys.exit(1)

    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # Install dependencies
    if not run_command(
        "pip install -r config/requirements.txt", "Installing dependencies"
    ):
        sys.exit(1)

    # Install pre-commit hooks
    if not run_command("pre-commit install", "Setting up pre-commit hooks"):
        print("⚠️  Pre-commit setup failed, continuing...")

    # Create necessary directories
    dirs = [".teleguard/sessions", "logs", "backups"]
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"📁 Created directory: {dir_path}")

    # Set permissions for session directory
    session_dir = Path.home() / ".teleguard" / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    print("\n🎉 Development environment setup complete!")
    print("\n📋 Next steps:")
    print("1. Copy config/.env.example to config/.env")
    print("2. Fill in your API credentials in config/.env")
    print("3. Run 'make test' to verify setup")
    print("4. Run 'python main.py' to start the bot")


if __name__ == "__main__":
    main()
