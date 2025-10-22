#!/usr/bin/env python3
"""Debug MemorySession save method"""

import base64
import struct
from telethon.sessions import MemorySession

def debug_memory_session():
    session_string = "AgA-i3IAUx3gyV6fvigeaksmnCljeXp7r4yVshzrdBcks6d1WTVMkIqB3Hms7ZkpZPlqztnKZbTo7-s0WZhBetaeh3TCbBBWzQlmkue-zzAh7URMjvvtSFgmze_KCAvGtF7aQEsxmsJxdBjTJoeJih-V4rIAKVnxxMhhAj-NpLwVM-yTzDMieOaB7sQaZggvL7vGRRJv5WYn5HH94YVakK6h7chi--wDmizVlnle3oa_DGkvQlCyPMd0mjTj-dkDy8mjxhIWk4qDUtWFrd3yfan6SE4up2ZDEcSrDafUvtSi0_NB7oMLF0x8AtYWyozlOQTidMFc-EcCebQq3-4U_jj8WaGzgAAAAAHjdA-PAA"
    
    # Decode session
    padding = 4 - len(session_string) % 4
    if padding != 4:
        session_string += "=" * padding
        
    session_data = base64.urlsafe_b64decode(session_string)
    
    # Extract components
    dc_id = struct.unpack('<B', session_data[0:1])[0]
    auth_key = session_data[6:262]
    
    print(f"DC ID: {dc_id}")
    print(f"Auth key length: {len(auth_key)}")
    
    # Create MemorySession
    session = MemorySession()
    print(f"Empty session save: {session.save()}")
    
    # Set DC
    session.set_dc(dc_id, "149.154.167.51", 443)
    print(f"After set_dc save: {session.save()}")
    
    # Set auth key
    session.auth_key = auth_key
    print(f"After auth_key save: {session.save()}")
    
    # Check if session has required data
    print(f"Session DC: {session.dc_id}")
    print(f"Session server: {session.server_address}")
    print(f"Session port: {session.port}")
    print(f"Session auth_key: {session.auth_key is not None}")

if __name__ == "__main__":
    debug_memory_session()