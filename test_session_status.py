#!/usr/bin/env python3
"""Test if the Pyrogram session is still valid"""

import asyncio
import base64
import struct
from telethon import TelegramClient
from telethon.sessions import MemorySession

async def test_session_validity():
    session_string = "AgA-i3IAgO2hJh_qaQx7nJtOgXUJYyuzbpum8Ex9GhyVytVaT5Wda_bgpk1zqSiVf-59G93dXCno6-tvWbgxKXWghhVu3DGyijvnixREHGIaFdNsNKftFBDwwOafe2oi9Z5j9vwQmA7eqK8qvGdD9-1JB22Fc3B4eR_F4EgIer1CfEsBrlV-OYgrTGwmEiZOP9_8nUN0uHyMJTuMtm5g3sWscaChMOpbs0z9WwZpXrVlEaQMGrHmRSEKWecXdDLO-pEO-v_EeLxjAl7vKlPoBrYYM7Ku3higxBmcrZMddvWNcMzOZY_bMb6dpvAi9ZOoQ1p7LNcasZhhz_ndfixgDR3iSAE2FwAAAAHjdA-PAA"
    
    # Decode session
    padding = 4 - len(session_string) % 4
    if padding != 4:
        session_string += "=" * padding
        
    session_data = base64.urlsafe_b64decode(session_string)
    
    # Extract components
    dc_id = struct.unpack('<B', session_data[0:1])[0]
    api_id_pyro = struct.unpack('<I', session_data[1:5])[0]
    auth_key = session_data[6:262]
    
    print(f"Testing session validity...")
    print(f"DC: {dc_id}, API ID: {api_id_pyro}")
    
    # Use any API hash - it shouldn't matter for existing sessions
    api_hash = "dummy_hash_for_existing_session"
    
    try:
        # Create client
        client = TelegramClient(MemorySession(), api_id_pyro, api_hash)
        
        # Set session data
        dc_servers = {
            1: ("149.154.175.53", 443),
            2: ("149.154.167.51", 443), 
            3: ("149.154.175.100", 443),
            4: ("149.154.167.91", 443),
            5: ("91.108.56.130", 443)
        }
        
        server_address, port = dc_servers.get(dc_id, ("149.154.167.51", 443))
        client.session.set_dc(dc_id, server_address, port)
        client.session.auth_key = auth_key
        
        # Connect
        await client.connect()
        print("Connected to Telegram")
        
        # Check authorization
        is_authorized = await client.is_user_authorized()
        print(f"Session authorized: {is_authorized}")
        
        if is_authorized:
            try:
                me = await client.get_me()
                print(f"Account: {me.first_name} {me.last_name or ''} ({me.phone})")
                print("Session is VALID and working!")
            except Exception as e:
                print(f"Error getting user info: {e}")
        else:
            print("Session has EXPIRED or been REVOKED")
            print("You need to re-login with phone number")
            
        await client.disconnect()
        
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(test_session_validity())