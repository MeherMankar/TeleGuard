#!/usr/bin/env python3
"""
TeleGuard Setup Script

Quick setup script for TeleGuard installation and configuration.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(cmd, check=True):
    """Run shell command"""
    try:
        result = subprocess.run(
            cmd, shell=True, check=check, capture_output=True, text=True
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr


def check_python_version():
    """Check Python version"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")
    return True


def install_dependencies():
    """Install required dependencies"""
    print("📦 Installing dependencies...")
    success, stdout, stderr = run_command("pip install -r config/requirements.txt")
    if success:
        print("✅ Dependencies installed")
        return True
    else:
        print(f"❌ Failed to install dependencies: {stderr}")
        return False


def setup_config():
    """Setup configuration files"""
    print("⚙️ Setting up configuration...")

    # Copy .env.example to .env if not exists
    env_example = Path("config/.env.example")
    env_file = Path("config/.env")

    if env_example.exists() and not env_file.exists():
        shutil.copy(env_example, env_file)
        print("✅ Created config/.env from template")
        print("⚠️ Please edit config/.env with your credentials")
        return True
    elif env_file.exists():
        print("✅ Configuration file already exists")
        return True
    else:
        print("❌ No configuration template found")
        return False


def create_directories():
    """Create necessary directories"""
    print("📁 Creating directories...")

    dirs = ["logs", "data", "backups", "temp"]
    for dir_name in dirs:
        Path(dir_name).mkdir(exist_ok=True)

    print("✅ Directories created")
    return True


def run_tests():
    """Run basic tests"""
    print("🧪 Running tests...")
    success, stdout, stderr = run_command("python tests/test_otp_destroyer.py")
    if success:
        print("✅ Tests passed")
        return True
    else:
        print(f"⚠️ Some tests failed: {stderr}")
        return False


def main():
    """Main setup function"""
    print("🛡️ TeleGuard Setup")
    print("=" * 30)

    steps = [
        ("Checking Python version", check_python_version),
        ("Installing dependencies", install_dependencies),
        ("Setting up configuration", setup_config),
        ("Creating directories", create_directories),
        ("Running tests", run_tests),
    ]

    for step_name, step_func in steps:
        print(f"\n{step_name}...")
        if not step_func():
            print(f"❌ Setup failed at: {step_name}")
            return False

    print("\n🎉 Setup completed successfully!")
    print("\nNext steps:")
    print("1. Edit config/.env with your API credentials")
    print("2. Run: python main.py")
    print("3. Add your first account and enable OTP Destroyer")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
