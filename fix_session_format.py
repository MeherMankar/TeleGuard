#!/usr/bin/env python3
"""Fix session format by understanding Telethon's StringSession structure"""

import base64
import struct
from telethon.sessions import StringSession

def analyze_telethon_format():
    """Analyze how Telethon StringSession works"""
    
    # Create a dummy session to see the format
    try:
        # Let's see what an empty StringSession looks like
        empty_session = StringSession()
        print(f"Empty StringSession: {empty_session}")
        
        # Try to understand the format by looking at Telethon source
        # StringSession expects: dc_id, server_address, port, auth_key in a specific format
        
        # The correct format based on Telethon source code:
        # It uses struct.pack to create the session data
        
        return True
    except Exception as e:
        print(f"Analysis error: {e}")
        return False

def create_proper_telethon_session(dc_id, server_address, port, auth_key):
    """Create a proper Telethon session string"""
    try:
        # Based on Telethon's StringSession.save() method
        # The format is: dc_id (1 byte) + server_address (variable) + port (2 bytes) + auth_key (256 bytes)
        
        # But we need to follow Telethon's exact format
        # Looking at the source, it uses a specific packing method
        
        # Create session data in the format Telethon expects
        session_data = struct.pack('<B', dc_id)  # DC ID
        
        # Server address needs to be null-terminated and padded
        server_bytes = server_address.encode('ascii')
        session_data += server_bytes + b'\x00'
        
        session_data += struct.pack('<H', port)  # Port
        session_data += auth_key  # Auth key
        
        # Encode to base64
        session_string = base64.urlsafe_b64encode(session_data).decode('ascii')
        
        return session_string
        
    except Exception as e:
        print(f"Session creation error: {e}")
        return None

def test_session_creation():
    """Test creating a session in the correct format"""
    
    # Test data from the Pyrogram session
    dc_id = 2
    server_address = "149.154.167.51"
    port = 443
    
    # Dummy auth key for testing (256 bytes)
    auth_key = b'A' * 256
    
    session_string = create_proper_telethon_session(dc_id, server_address, port, auth_key)
    
    if session_string:
        print(f"Created session: {session_string[:50]}...")
        
        try:
            test_session = StringSession(session_string)
            print("StringSession creation successful!")
            return True
        except Exception as e:
            print(f"StringSession creation failed: {e}")
            return False
    
    return False

if __name__ == "__main__":
    print("Analyzing Telethon StringSession format...")
    analyze_telethon_format()
    print("\nTesting session creation...")
    test_session_creation()