#!/usr/bin/env python3
"""
Selenium Setup Script for TeleGuard Captcha Bypass
Automatically installs and configures Selenium dependencies
"""

import subprocess
import sys
import os
import platform
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        if e.stdout:
            print(f"Output: {e.stdout}")
        if e.stderr:
            print(f"Error: {e.stderr}")
        return False

def install_python_packages():
    """Install required Python packages"""
    packages = [
        "selenium>=4.15.0",
        "webdriver-manager>=4.0.0",
        "beautifulsoup4>=4.12.0"
    ]
    
    for package in packages:
        if not run_command(f"{sys.executable} -m pip install {package}", f"Installing {package}"):
            return False
    return True

def install_chrome():
    """Install Chrome browser based on OS"""
    system = platform.system().lower()
    
    if system == "windows":
        print("🌐 Please install Chrome manually from: https://www.google.com/chrome/")
        print("   The script cannot auto-install Chrome on Windows")
        return True
    
    elif system == "linux":
        # Try different package managers
        commands = [
            "sudo apt-get update && sudo apt-get install -y google-chrome-stable",
            "sudo yum install -y google-chrome-stable",
            "sudo dnf install -y google-chrome-stable"
        ]
        
        for cmd in commands:
            if run_command(cmd, "Installing Chrome on Linux"):
                return True
        
        print("❌ Could not install Chrome automatically")
        print("   Please install Chrome manually for your Linux distribution")
        return False
    
    elif system == "darwin":  # macOS
        if run_command("brew install --cask google-chrome", "Installing Chrome via Homebrew"):
            return True
        else:
            print("🌐 Please install Chrome manually from: https://www.google.com/chrome/")
            print("   Or install Homebrew first: https://brew.sh/")
            return True
    
    return True

def test_selenium_setup():
    """Test if Selenium is working properly"""
    print("🧪 Testing Selenium setup...")
    
    test_code = '''
import sys
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.get("https://www.google.com")
    title = driver.title
    driver.quit()
    
    print(f"✅ Selenium test successful! Page title: {title}")
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Selenium test failed: {e}")
    sys.exit(1)
'''
    
    try:
        result = subprocess.run([sys.executable, "-c", test_code], 
                              capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✅ Selenium is working correctly!")
            return True
        else:
            print(f"❌ Selenium test failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Selenium test timed out")
        return False
    except Exception as e:
        print(f"❌ Error running Selenium test: {e}")
        return False

def main():
    """Main setup function"""
    print("🤖 TeleGuard Selenium Setup Script")
    print("=" * 40)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        return False
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Install Python packages
    if not install_python_packages():
        print("❌ Failed to install Python packages")
        return False
    
    # Install Chrome
    print("\n🌐 Setting up Chrome browser...")
    install_chrome()
    
    # Test setup
    print("\n🧪 Testing Selenium configuration...")
    if test_selenium_setup():
        print("\n🎉 Selenium setup completed successfully!")
        print("\n📋 Next steps:")
        print("   1. Restart your TeleGuard bot")
        print("   2. Try the /check_selenium command")
        print("   3. Use /appeal to test captcha bypass")
        return True
    else:
        print("\n❌ Setup completed but tests failed")
        print("\n🛠️ Troubleshooting:")
        print("   1. Restart your terminal/IDE")
        print("   2. Check if Chrome is installed")
        print("   3. Try running: pip install --upgrade selenium webdriver-manager")
        print("   4. Use /check_selenium command for detailed diagnosis")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)