#!/usr/bin/env python3
"""
Test Device Snooper functionality
"""

import asyncio
import logging
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'teleguard'))

from core.device_snooper import DeviceSnooper

# Mock database for testing
class MockDatabase:
    def __init__(self):
        self.device_logs = MockCollection()

class MockCollection:
    def __init__(self):
        self.data = {}
    
    async def update_one(self, filter_dict, update_dict, upsert=False):
        user_id = filter_dict['user_id']
        self.data[user_id] = update_dict['$set']
        print(f"✅ Stored device data for user {user_id}")
    
    async def find_one(self, filter_dict):
        user_id = filter_dict['user_id']
        return self.data.get(user_id)

# Mock Telegram client and authorization
class MockAuth:
    def __init__(self, device_model, platform, system_version, country="US", official_app=True):
        self.hash = 12345
        self.device_model = device_model
        self.platform = platform
        self.system_version = system_version
        self.api_id = 6
        self.app_name = "Telegram Desktop"
        self.app_version = "4.9.3"
        self.date_created = "2024-01-01"
        self.date_active = "2024-01-15"
        self.ip = "192.168.1.1"
        self.country = country
        self.region = country
        self.current = True
        self.official_app = official_app
        self.password_pending = False

class MockAuthResult:
    def __init__(self, auths):
        self.authorizations = auths

class MockClient:
    def __init__(self, auths):
        self.auths = auths
    
    async def __call__(self, request):
        return MockAuthResult(self.auths)

async def test_device_snooper():
    """Test device snooping functionality"""
    print("🧪 Testing Device Snooper...")
    
    # Setup
    db = MockDatabase()
    snooper = DeviceSnooper(db)
    
    # Test devices
    test_devices = [
        MockAuth("iPhone 15 Pro", "iOS", "iOS 17.2", "US", True),
        MockAuth("Samsung Galaxy S24", "Android", "Android 14", "US", True),
        MockAuth("MacBook Pro", "macOS", "macOS 14.2", "US", True),
        MockAuth("Windows Desktop", "Windows", "Windows NT 10.0", "US", True),
        MockAuth("Unknown Device", "Linux", "Ubuntu 22.04", "RU", False),  # Suspicious
    ]
    
    client = MockClient(test_devices)
    user_id = 123456
    
    # Test device snooping
    print("\n📱 Testing device scanning...")
    result = await snooper.snoop_device_info(client, user_id)
    
    print(f"✅ Found {result['count']} devices")
    for i, device in enumerate(result['devices'], 1):
        print(f"  {i}. {device['device_type']}: {device['device_model']}")
        print(f"     OS: {device['os_name']} {device['os_version']}")
        print(f"     Arch: {device['os_architecture']}")
    
    # Test device history
    print("\n📚 Testing device history...")
    history = await snooper.get_device_history(user_id)
    print(f"✅ Retrieved {history['count']} devices from history")
    
    # Test suspicious device detection
    print("\n⚠️ Testing suspicious device detection...")
    suspicious = await snooper.detect_suspicious_devices(user_id)
    print(f"✅ Found {len(suspicious)} suspicious devices")
    
    for item in suspicious:
        device = item['device']
        reasons = item['reasons']
        print(f"  🚨 {device['device_model']}: {', '.join(reasons)}")
    
    print("\n✅ All tests completed successfully!")

def test_os_detection():
    """Test OS detection functionality"""
    print("\n🖥️ Testing OS Detection...")
    
    db = MockDatabase()
    snooper = DeviceSnooper(db)
    
    test_cases = [
        ("Windows", "Windows NT 10.0.19045", "Dell Laptop", "Windows", "Windows 10/11", "x64", "Laptop"),
        ("macOS", "macOS 14.2", "MacBook Pro", "macOS", "macOS 14.2", "Unknown", "Laptop"),
        ("Linux", "Ubuntu 22.04 x86_64", "ThinkPad", "Linux", "Ubuntu 22.04 x86_64", "x64", "Laptop"),
        ("Android", "Android 14", "Samsung Galaxy S24", "Android", "Android 14", "Unknown", "Mobile"),
        ("iOS", "iOS 17.2", "iPhone 15 Pro", "iOS", "iOS 17.2", "Unknown", "Mobile"),
    ]
    
    for platform, system_version, device_model, expected_os, expected_version, expected_arch, expected_type in test_cases:
        result = snooper._extract_os_info(platform, system_version, device_model)
        
        print(f"  📱 {device_model}:")
        print(f"     Platform: {platform} → OS: {result['os_name']} {result['os_version']}")
        print(f"     Type: {result['device_type']}, Arch: {result['architecture']}")
        
        # Verify results
        assert result['os_name'] == expected_os, f"OS mismatch: {result['os_name']} != {expected_os}"
        assert result['device_type'] == expected_type, f"Type mismatch: {result['device_type']} != {expected_type}"
    
    print("✅ OS detection tests passed!")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Run tests
        test_os_detection()
        asyncio.run(test_device_snooper())
        
        print("\n🎉 All device snooper tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()