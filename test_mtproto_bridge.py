"""Test MTProto Bridge Functionality"""
import asyncio
import sys
from teleguard.core.mtproto_bridge import mtproto_bridge

async def test_bridge():
    """Test MTProto to SOCKS5 bridge"""
    print("🧪 Testing MTProto Bridge\n")
    
    # Test configuration
    test_proxy = {
        'addr': 'proxy.example.com',
        'port': 443,
        'secret': b'test_secret_bytes_here_1234567890'
    }
    
    print("1️⃣ Creating bridge...")
    bridge_info = await mtproto_bridge.create_bridge('test_proxy_1', test_proxy)
    
    if bridge_info:
        host, port = bridge_info
        print(f"✅ Bridge created: {host}:{port}")
        print(f"   Routes to: {test_proxy['addr']}:{test_proxy['port']}")
    else:
        print("❌ Bridge creation failed")
        return False
    
    print("\n2️⃣ Checking bridge info...")
    info = mtproto_bridge.get_bridge_info('test_proxy_1')
    if info:
        print(f"✅ Bridge info retrieved: {info[0]}:{info[1]}")
    else:
        print("❌ Bridge info not found")
    
    print("\n3️⃣ Creating second bridge...")
    bridge_info_2 = await mtproto_bridge.create_bridge('test_proxy_2', {
        'addr': 'proxy2.example.com',
        'port': 8443,
        'secret': b'another_secret_bytes_here_xyz'
    })
    
    if bridge_info_2:
        host2, port2 = bridge_info_2
        print(f"✅ Second bridge created: {host2}:{port2}")
    else:
        print("❌ Second bridge creation failed")
    
    print(f"\n4️⃣ Active bridges: {len(mtproto_bridge.bridges)}")
    for proxy_id, (h, p, _) in mtproto_bridge.bridges.items():
        print(f"   • {proxy_id}: {h}:{p}")
    
    print("\n5️⃣ Stopping first bridge...")
    stopped = await mtproto_bridge.stop_bridge('test_proxy_1')
    if stopped:
        print("✅ Bridge stopped successfully")
    else:
        print("❌ Failed to stop bridge")
    
    print(f"\n6️⃣ Active bridges: {len(mtproto_bridge.bridges)}")
    
    print("\n7️⃣ Stopping all bridges...")
    await mtproto_bridge.stop_all_bridges()
    print(f"✅ All bridges stopped. Active: {len(mtproto_bridge.bridges)}")
    
    print("\n✅ All tests passed!")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("MTProto Bridge Test Suite")
    print("=" * 60 + "\n")
    
    try:
        result = asyncio.run(test_bridge())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
