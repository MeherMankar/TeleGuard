#!/usr/bin/env python3
"""Verify the Pyrogram session data directly"""

import base64
import struct

def verify_session():
    session_string = "AgA-i3IAUx3gyV6fvigeaksmnCljeXp7r4yVshzrdBcks6d1WTVMkIqB3Hms7ZkpZPlqztnKZbTo7-s0WZhBetaeh3TCbBBWzQlmkue-zzAh7URMjvvtSFgmze_KCAvGtF7aQEsxmsJxdBjTJoeJih-V4rIAKVnxxMhhAj-NpLwVM-yTzDMieOaB7sQaZggvL7vGRRJv5WYn5HH94YVakK6h7chi--wDmizVlnle3oa_DGkvQlCyPMd0mjTj-dkDy8mjxhIWk4qDUtWFrd3yfan6SE4up2ZDEcSrDafUvtSi0_NB7oMLF0x8AtYWyozlOQTidMFc-EcCebQq3-4U_jj8WaGzgAAAAAHjdA-PAA"
    
    print("Verifying Pyrogram session data...")
    
    # Decode session
    padding = 4 - len(session_string) % 4
    if padding != 4:
        session_string += "=" * padding
        
    session_data = base64.urlsafe_b64decode(session_string)
    print(f"Session data length: {len(session_data)}")
    
    if len(session_data) != 271:
        print("ERROR: Invalid Pyrogram session length")
        return
    
    # Extract components
    dc_id = struct.unpack('<B', session_data[0:1])[0]
    api_id = struct.unpack('<I', session_data[1:5])[0]
    test_mode = struct.unpack('<?', session_data[5:6])[0]
    auth_key = session_data[6:262]
    user_id = struct.unpack('<Q', session_data[262:270])[0]
    is_bot = struct.unpack('<?', session_data[270:271])[0]
    
    print(f"DC ID: {dc_id}")
    print(f"API ID: {api_id}")
    print(f"User ID: {user_id}")
    print(f"Is Bot: {is_bot}")
    print(f"Test Mode: {test_mode}")
    print(f"Auth Key Length: {len(auth_key)}")
    print(f"Auth Key Valid: {auth_key != b'\\x00' * 256}")
    
    # Check if auth key looks valid
    if auth_key == b'\\x00' * 256:
        print("ERROR: Auth key is all zeros - session is invalid")
    elif len(set(auth_key)) < 10:
        print("WARNING: Auth key has low entropy - may be invalid")
    else:
        print("Auth key appears valid")
    
    print(f"\\nThis session was created with API ID {api_id}")
    print("To use this session, you need the matching API_HASH for this API_ID")
    print("Or the session may have expired/been revoked by Telegram")

if __name__ == "__main__":
    verify_session()