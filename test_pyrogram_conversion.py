#!/usr/bin/env python3
"""Test Pyrogram session conversion"""

import base64
import struct
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def convert_pyrogram_to_telethon_v2(pyrogram_session: str) -> str:
    """Convert Pyrogram session to Telethon using actual Telethon session format"""
    try:
        # Decode base64 session
        padding = 4 - len(pyrogram_session) % 4
        if padding != 4:
            pyrogram_session += "=" * padding
            
        session_data = base64.urlsafe_b64decode(pyrogram_session)
        print(f"Decoded session data length: {len(session_data)}")
        
        # Pyrogram session format: dc_id, api_id, test_mode, auth_key, user_id, is_bot
        dc_id = struct.unpack('<B', session_data[0:1])[0]
        api_id = struct.unpack('<I', session_data[1:5])[0]
        test_mode = struct.unpack('<?', session_data[5:6])[0]
        auth_key = session_data[6:262]  # 256 bytes
        user_id = struct.unpack('<Q', session_data[262:270])[0]
        is_bot = struct.unpack('<?', session_data[270:271])[0]
        
        print(f"DC: {dc_id}, API_ID: {api_id}, User: {user_id}, Bot: {is_bot}")
        
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
        
        # Create Telethon session data using the actual format
        # Telethon StringSession format is different - it's just the session data encoded
        
        # Try a simpler approach - create the session data that Telethon expects
        # This is based on Telethon's actual StringSession implementation
        
        # The format should be: dc_id + server_address + port + auth_key
        session_bytes = struct.pack('<B', dc_id)  # DC ID (1 byte)
        session_bytes += server_address.encode('utf-8')[:15].ljust(16, b'\x00')  # Server (16 bytes)
        session_bytes += struct.pack('<H', port)  # Port (2 bytes)  
        session_bytes += auth_key  # Auth key (256 bytes)
        
        # Encode to base64
        telethon_session = base64.urlsafe_b64encode(session_bytes).decode('ascii').rstrip('=')
        
        print(f"Telethon session length: {len(telethon_session)}")
        return telethon_session
        
    except Exception as e:
        print(f"Conversion error: {e}")
        return None

def test_conversion():
    session_string = "AgA-i3IAgO2hJh_qaQx7nJtOgXUJYyuzbpum8Ex9GhyVytVaT5Wda_bgpk1zqSiVf-59G93dXCno6-tvWbgxKXWghhVu3DGyijvnixREHGIaFdNsNKftFBDwwOafe2oi9Z5j9vwQmA7eqK8qvGdD9-1JB22Fc3B4eR_F4EgIer1CfEsBrlV-OYgrTGwmEiZOP9_8nUN0uHyMJTuMtm5g3sWscaChMOpbs0z9WwZpXrVlEaQMGrHmRSEKWecXdDLO-pEO-v_EeLxjAl7vKlPoBrYYM7Ku3higxBmcrZMddvWNcMzOZY_bMb6dpvAi9ZOoQ1p7LNcasZhhz_ndfixgDR3iSAE2FwAAAAHjdA-PAA"
    
    print("Testing Pyrogram to Telethon conversion...")
    result = convert_pyrogram_to_telethon_v2(session_string)
    
    if result:
        print(f"Conversion successful!")
        print(f"Original length: {len(session_string)}")
        print(f"Converted length: {len(result)}")
        
        # Test if we can create a StringSession with it
        try:
            from telethon.sessions import StringSession
            test_session = StringSession(result)
            print("StringSession creation successful!")
        except Exception as e:
            print(f"StringSession creation failed: {e}")
    else:
        print("Conversion failed")

if __name__ == "__main__":
    test_conversion()