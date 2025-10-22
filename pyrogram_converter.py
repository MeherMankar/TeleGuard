#!/usr/bin/env python3
"""Proper Pyrogram to Telethon session converter"""

import base64
import struct
import asyncio
from telethon import TelegramClient
from telethon.sessions import MemorySession

async def convert_pyrogram_to_telethon_working(pyrogram_session: str, api_id: int, api_hash: str):
    """Convert Pyrogram session to working Telethon session"""
    try:
        # Decode the Pyrogram session
        padding = 4 - len(pyrogram_session) % 4
        if padding != 4:
            pyrogram_session += "=" * padding
            
        session_data = base64.urlsafe_b64decode(pyrogram_session)
        
        # Extract Pyrogram session components
        dc_id = struct.unpack('<B', session_data[0:1])[0]
        api_id_pyro = struct.unpack('<I', session_data[1:5])[0]
        test_mode = struct.unpack('<?', session_data[5:6])[0]
        auth_key = session_data[6:262]  # 256 bytes
        user_id = struct.unpack('<Q', session_data[262:270])[0]
        is_bot = struct.unpack('<?', session_data[270:271])[0]
        
        print(f"Pyrogram session info:")
        print(f"  DC: {dc_id}")
        print(f"  API ID: {api_id_pyro}")
        print(f"  User ID: {user_id}")
        print(f"  Is Bot: {is_bot}")
        print(f"  Test Mode: {test_mode}")
        
        # Map DC to server addresses
        dc_servers = {
            1: ("149.154.175.53", 443),
            2: ("149.154.167.51", 443), 
            3: ("149.154.175.100", 443),
            4: ("149.154.167.91", 443),
            5: ("91.108.56.130", 443)
        }
        
        if dc_id not in dc_servers:
            dc_id = 2
            
        server_address, port = dc_servers[dc_id]
        
        # Create a Telethon client with MemorySession
        client = TelegramClient(MemorySession(), api_id, api_hash)
        
        # Manually set the session data
        client.session.set_dc(dc_id, server_address, port)
        client.session.auth_key = auth_key
        
        # Connect and test
        await client.connect()
        
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"✅ Successfully converted session!")
            print(f"Account: {me.first_name} {me.last_name or ''} ({me.phone})")
            
            # Get the Telethon session string
            telethon_session = client.session.save()
            await client.disconnect()
            
            return telethon_session, {
                "phone": me.phone,
                "name": f"{me.first_name or ''} {me.last_name or ''}".strip() or f"User_{me.id}",
                "user_id": me.id,
                "username": me.username
            }
        else:
            await client.disconnect()
            return None, "Session not authorized"
            
    except Exception as e:
        print(f"Conversion error: {e}")
        return None, str(e)

async def test_conversion():
    """Test the conversion with your session"""
    session_string = "AgA-i3IAgO2hJh_qaQx7nJtOgXUJYyuzbpum8Ex9GhyVytVaT5Wda_bgpk1zqSiVf-59G93dXCno6-tvWbgxKXWghhVu3DGyijvnixREHGIaFdNsNKftFBDwwOafe2oi9Z5j9vwQmA7eqK8qvGdD9-1JB22Fc3B4eR_F4EgIer1CfEsBrlV-OYgrTGwmEiZOP9_8nUN0uHyMJTuMtm5g3sWscaChMOpbs0z9WwZpXrVlEaQMGrHmRSEKWecXdDLO-pEO-v_EeLxjAl7vKlPoBrYYM7Ku3higxBmcrZMddvWNcMzOZY_bMb6dpvAi9ZOoQ1p7LNcasZhhz_ndfixgDR3iSAE2FwAAAAHjdA-PAA"
    
    # You'll need to provide your actual API credentials
    api_id = 1921728000  # Replace with your API ID
    api_hash = "your_api_hash_here"  # Replace with your API hash
    
    print("Converting Pyrogram session to Telethon...")
    
    telethon_session, result = await convert_pyrogram_to_telethon_working(session_string, api_id, api_hash)
    
    if telethon_session:
        print(f"\n✅ Conversion successful!")
        print(f"Telethon session string: {telethon_session}")
        print(f"Account info: {result}")
        
        # Test the converted session
        from telethon.sessions import StringSession
        test_client = TelegramClient(StringSession(telethon_session), api_id, api_hash)
        await test_client.connect()
        
        if await test_client.is_user_authorized():
            print("✅ Converted session works with Telethon!")
        else:
            print("❌ Converted session not authorized")
            
        await test_client.disconnect()
        
    else:
        print(f"❌ Conversion failed: {result}")

if __name__ == "__main__":
    asyncio.run(test_conversion())