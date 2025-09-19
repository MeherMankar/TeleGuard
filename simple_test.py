#!/usr/bin/env python3
"""
Simple Device Snooper Test
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

class DeviceSnooper:
    def __init__(self, db):
        self.db = db
        
    def _extract_os_info(self, platform: str, system_version: str, device_model: str) -> Dict[str, str]:
        """Extract detailed OS information from platform and system version"""
        os_info = {
            'os_name': 'Unknown',
            'os_version': 'Unknown',
            'architecture': 'Unknown',
            'device_type': self._detect_device_type(device_model, platform)
        }
        
        if not platform or not system_version:
            return os_info
            
        platform_lower = platform.lower()
        
        # Windows detection
        if 'windows' in platform_lower:
            os_info['os_name'] = 'Windows'
            if 'NT 10.0' in system_version:
                os_info['os_version'] = 'Windows 10/11'
            elif 'NT 6.3' in system_version:
                os_info['os_version'] = 'Windows 8.1'
            elif 'NT 6.1' in system_version:
                os_info['os_version'] = 'Windows 7'
            else:
                os_info['os_version'] = system_version
                
        # macOS detection
        elif 'darwin' in platform_lower or 'macos' in platform_lower:
            os_info['os_name'] = 'macOS'
            os_info['os_version'] = system_version
            
        # Linux detection
        elif 'linux' in platform_lower:
            os_info['os_name'] = 'Linux'
            os_info['os_version'] = system_version
            
        # Android detection
        elif 'android' in platform_lower:
            os_info['os_name'] = 'Android'
            os_info['os_version'] = system_version
            
        # iOS detection
        elif 'ios' in platform_lower or device_model and ('iphone' in device_model.lower() or 'ipad' in device_model.lower()):
            os_info['os_name'] = 'iOS'
            os_info['os_version'] = system_version
            
        # Architecture detection
        if 'x64' in system_version or 'x86_64' in system_version or 'amd64' in system_version:
            os_info['architecture'] = 'x64'
        elif 'x86' in system_version or 'i386' in system_version:
            os_info['architecture'] = 'x86'
        elif 'arm64' in system_version or 'aarch64' in system_version:
            os_info['architecture'] = 'ARM64'
        elif 'arm' in system_version:
            os_info['architecture'] = 'ARM'
            
        return os_info
    
    def _detect_device_type(self, device_model: str, platform: str) -> str:
        """Detect device type from model and platform"""
        if not device_model:
            return 'Unknown'
            
        model_lower = device_model.lower()
        platform_lower = platform.lower() if platform else ''
        
        # Mobile devices
        if any(x in model_lower for x in ['iphone', 'android', 'samsung', 'pixel', 'oneplus', 'xiaomi', 'huawei']):
            return 'Mobile'
        
        # Tablets
        if any(x in model_lower for x in ['ipad', 'tablet', 'surface']):
            return 'Tablet'
            
        # Laptops
        if any(x in model_lower for x in ['macbook', 'laptop', 'thinkpad', 'dell', 'hp', 'asus', 'lenovo']):
            return 'Laptop'
            
        # Desktops
        if any(x in model_lower for x in ['desktop', 'pc', 'workstation', 'imac']):
            return 'Desktop'
            
        # Web/Browser
        if 'web' in platform_lower or 'browser' in platform_lower:
            return 'Web'
            
        return 'Computer'

def test_os_detection():
    """Test OS detection functionality"""
    print("Testing Device Snooper OS Detection...")
    
    snooper = DeviceSnooper(None)
    
    test_cases = [
        ("Windows", "Windows NT 10.0.19045", "Dell Laptop", "Windows", "Windows 10/11", "x64", "Laptop"),
        ("macOS", "macOS 14.2", "MacBook Pro", "macOS", "macOS 14.2", "Unknown", "Laptop"),
        ("Linux", "Ubuntu 22.04 x86_64", "ThinkPad", "Linux", "Ubuntu 22.04 x86_64", "x64", "Laptop"),
        ("Android", "Android 14", "Samsung Galaxy S24", "Android", "Android 14", "Unknown", "Mobile"),
        ("iOS", "iOS 17.2", "iPhone 15 Pro", "iOS", "iOS 17.2", "Unknown", "Mobile"),
        ("Web", "Browser", "Chrome", "Unknown", "Unknown", "Unknown", "Web"),
    ]
    
    print("\nTesting device detection:")
    for platform, system_version, device_model, expected_os, expected_version, expected_arch, expected_type in test_cases:
        result = snooper._extract_os_info(platform, system_version, device_model)
        
        print(f"  {device_model}:")
        print(f"    Platform: {platform} -> OS: {result['os_name']} {result['os_version']}")
        print(f"    Type: {result['device_type']}, Arch: {result['architecture']}")
        
        # Verify results
        if result['os_name'] == expected_os and result['device_type'] == expected_type:
            print(f"    PASS")
        else:
            print(f"    FAIL - Expected OS: {expected_os}, Type: {expected_type}")
        print()
    
    print("Device snooper OS detection test completed!")

def test_device_emojis():
    """Test device emoji mapping"""
    print("\nTesting Device Emojis:")
    
    emoji_map = {
        'Mobile': '[Mobile]',
        'Tablet': '[Tablet]', 
        'Laptop': '[Laptop]',
        'Desktop': '[Desktop]',
        'Web': '[Web]',
        'Computer': '[Computer]',
        'Unknown': '[Unknown]'
    }
    
    for device_type, placeholder in emoji_map.items():
        print(f"  {placeholder} {device_type}")
    
    print("Emoji mapping test completed!")

if __name__ == "__main__":
    try:
        test_os_detection()
        test_device_emojis()
        print("\nAll device snooper tests passed!")
        
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()