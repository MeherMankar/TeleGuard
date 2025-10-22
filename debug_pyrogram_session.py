#!/usr/bin/env python3
"""Debug Pyrogram session conversion in detail"""

import asyncio
import base64
import struct
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from telethon import TelegramClient
from telethon.sessions import MemorySession
from teleguard.core.config import config

async def debug_pyrogram_session():
    """Debug the Pyrogram session in detail"""
    
    session_string = "AgA-i3IAgO2hJh_qaQx7nJtOgXUJYyuzbpum8Ex9GhyVytVaT5Wda_bgpk1zqSiVf-59G93dXCno6-tvWbgxKXWghhVu3DGyijvnixREHGIaFdNsNKftFBDwwOafe2oi9Z5j9vwQmA7eqK8qvGdD9-1JB22Fc3B4eR_F4EgIer1CfEsBrlV-OYgrTGwmEiZOP9_8nUN0uHyMJTuMtm5g3sWscaChMOpbs0z9WwZpXrVlEaQMGrHmRSEKWecXdDLO-pEO-v_EeLxjAl7vKlPoBrYYM7Ku3higxBmcrZMddvWNcMzOZY_bMb6dpvAi9ZOoQ1p7LNcasZhhz_ndfixgDR3iSAE2FwAAAAHjdA-PAA"
    
    print("Debugging Pyrogram session...")
    
    try:
        # Decode the session
        padding = 4 - len(session_string) % 4
        if padding != 4:
            session_string += "=" * padding
            
        session_data = base64.urlsafe_b64decode(session_string)
        print(f"Session data length: {len(session_data)}")
        
        # Extract components
        dc_id = struct.unpack('<B', session_data[0:1])[0]
        api_id_pyro = struct.unpack('<I', session_data[1:5])[0]
        test_mode = struct.unpack('<?', session_data[5:6])[0]
        auth_key = session_data[6:262]
        user_id = struct.unpack('<Q', session_data[262:270])[0]
        is_bot = struct.unpack('<?', session_data[270:271])[0]
        
        print(f"DC ID: {dc_id}")
        print(f"API ID (from session): {api_id_pyro}")
        print(f"API ID (config): {config.telegram.api_id}")
        print(f"User ID: {user_id}")
        print(f"Is Bot: {is_bot}")
        print(f"Test Mode: {test_mode}")
        print(f"Auth Key Length: {len(auth_key)}")
        print(f"Auth Key Valid: {auth_key != b'\\x00' * 256}")
        
        # Check if API IDs match
        if api_id_pyro != config.telegram.api_id:
            print(f"⚠️  WARNING: API ID mismatch!")
            print(f"   Session API ID: {api_id_pyro}")
            print(f"   Config API ID: {config.telegram.api_id}")
            print("   This session was created with different API credentials.")
            print("   You need to use the same API_ID and API_HASH that were used to create this session.")
            return
        
        # Map DC to server
        dc_servers = {
            1: ("149.154.175.53", 443),
            2: ("149.154.167.51", 443), 
            3: ("149.154.175.100", 443),
            4: ("149.154.167.91", 443),
            5: ("91.108.56.130", 443)
        }
        
        server_address, port = dc_servers.get(dc_id, ("149.154.167.51", 443))
        print(f"Server: {server_address}:{port}")
        
        # Try to create Telethon client
        print("\\nTesting with Telethon...")
        client = TelegramClient(MemorySession(), config.telegram.api_id, config.telegram.api_hash)
        
        # Set session data
        client.session.set_dc(dc_id, server_address, port)
        client.session.auth_key = auth_key
        
        # Connect
        await client.connect()
        print("✅ Connected to Telegram")
        
        # Check authorization
        try:
            is_authorized = await client.is_user_authorized()
            print(f"Authorized: {is_authorized}")
            
            if is_authorized:
                me = await client.get_me()
                print(f"✅ Account: {me.first_name} {me.last_name or ''} ({me.phone})")
                
                # Get Telethon session string
                telethon_session = client.session.save()
                print(f"✅ Telethon session created: {telethon_session[:50]}...")
                
            else:
                print("❌ Session not authorized - may have expired or been revoked")
                
        except Exception as auth_error:
            print(f"❌ Authorization check failed: {auth_error}")
            
        await client.disconnect()
        
    except Exception as e:
        print(f"❌ Debug error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_pyrogram_session())