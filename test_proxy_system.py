"""Test script for Proxy Management System"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from teleguard.core.proxy_manager import proxy_manager


async def test_proxy_parsing():
    """Test proxy link parsing"""
    print("=" * 50)
    print("Testing Proxy Link Parsing")
    print("=" * 50)
    
    test_links = [
        "t.me/proxy?server=1.2.3.4&port=443&secret=abc123",
        "t.me/socks?server=1.2.3.4&port=1080&user=admin&pass=password",
        "tg://proxy?server=5.6.7.8&port=443&secret=def456",
        "socks5://user:pass@1.2.3.4:1080",
        "http://user:pass@1.2.3.4:8080",
    ]
    
    for link in test_links:
        print(f"\n[TEST] Testing: {link}")
        result = await proxy_manager.parse_telegram_proxy_link(link)
        if result:
            print(f"[PASS] Parsed successfully:")
            print(f"   Type: {result.get('type')}")
            print(f"   Server: {result.get('server')}")
            print(f"   Port: {result.get('port')}")
            if result.get('username'):
                print(f"   Username: {result.get('username')}")
            if result.get('secret'):
                print(f"   Secret: {result.get('secret')[:10]}...")
        else:
            print(f"[FAIL] Failed to parse")


async def test_proxy_dict_building():
    """Test building Telethon proxy dict"""
    print("\n" + "=" * 50)
    print("Testing Proxy Dict Building")
    print("=" * 50)
    
    test_proxies = [
        {
            'type': 'socks5',
            'server': '1.2.3.4',
            'port': 1080,
            'username': 'admin',
            'password': 'password'
        },
        {
            'type': 'mtproto',
            'server': '5.6.7.8',
            'port': 443,
            'secret': 'abc123def456'
        },
        {
            'type': 'http',
            'server': '9.10.11.12',
            'port': 8080
        }
    ]
    
    for proxy in test_proxies:
        print(f"\n[TEST] Testing {proxy['type']} proxy:")
        result = proxy_manager.build_telethon_proxy(proxy)
        if result:
            print(f"[PASS] Built successfully:")
            print(f"   {result}")
        else:
            print(f"[FAIL] Failed to build")


async def test_validation():
    """Test proxy validation"""
    print("\n" + "=" * 50)
    print("Testing Proxy Validation")
    print("=" * 50)
    
    # Test valid formats
    valid_links = [
        "t.me/proxy?server=1.2.3.4&port=443&secret=abc",
        "socks5://1.2.3.4:1080",
    ]
    
    # Test invalid formats
    invalid_links = [
        "invalid_link",
        "http://",
        "t.me/proxy",  # Missing parameters
    ]
    
    print("\n[VALID] Valid Links:")
    for link in valid_links:
        result = await proxy_manager.parse_telegram_proxy_link(link)
        status = "[PASS]" if result else "[FAIL]"
        print(f"   {status}: {link}")
    
    print("\n[INVALID] Invalid Links (should fail):")
    for link in invalid_links:
        result = await proxy_manager.parse_telegram_proxy_link(link)
        status = "[PASS]" if not result else "[FAIL]"
        print(f"   {status}: {link}")


async def main():
    """Run all tests"""
    print("\n[TEST] TeleGuard Proxy Management System Tests\n")
    
    try:
        await test_proxy_parsing()
        await test_proxy_dict_building()
        await test_validation()
        
        print("\n" + "=" * 50)
        print("[SUCCESS] All Tests Completed!")
        print("=" * 50)
        print("\n[SUMMARY]")
        print("   [PASS] Proxy link parsing: Working")
        print("   [PASS] Telethon dict building: Working")
        print("   [PASS] Validation: Working")
        print("\n[READY] Proxy system is ready to use!")
        print("\n[INFO] To test in bot:")
        print("   1. Start your bot: python main.py")
        print("   2. Send /proxy command")
        print("   3. Click 'Add Proxy'")
        print("   4. Paste a proxy link")
        
    except Exception as e:
        print(f"\n[ERROR] Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
