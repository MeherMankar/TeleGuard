#!/usr/bin/env python3
"""Run backup system tests"""

import sys
import subprocess
import os

def run_tests():
    """Run backup system tests"""
    print("Running TeleGuard Backup System Tests...")
    
    # Set PYTHONPATH to include project root
    project_root = os.path.dirname(os.path.abspath(__file__))
    env = os.environ.copy()
    env['PYTHONPATH'] = project_root
    
    # Run tests
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/sync/", 
        "-v", 
        "--tb=short"
    ]
    
    try:
        result = subprocess.run(cmd, env=env, cwd=project_root)
        return result.returncode == 0
    except FileNotFoundError:
        print("pytest not found. Install with: pip install pytest pytest-asyncio")
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)