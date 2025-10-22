#!/usr/bin/env python3
"""Fix API ID mismatch for Pyrogram session"""

import base64
import struct

def analyze_session_api_id():
    session_string = "AgA-i3IAgO2hJh_qaQx7nJtOgXUJYyuzbpum8Ex9GhyVytVaT5Wda_bgpk1zqSiVf-59G93dXCno6-tvWbgxKXWghhVu3DGyijvnixREHGIaFdNsNKftFBDwwOafe2oi9Z5j9vwQmA7eqK8qvGdD9-1JB22Fc3B4eR_F4EgIer1CfEsBrlV-OYgrTGwmEiZOP9_8nUN0uHyMJTuMtm5g3sWscaChMOpbs0z9WwZpXrVlEaQMGrHmRSEKWecXdDLO-pEO-v_EeLxjAl7vKlPoBrYYM7Ku3higxBmcrZMddvWNcMzOZY_bMb6dpvAi9ZOoQ1p7LNcasZhhz_ndfixgDR3iSAE2FwAAAAHjdA-PAA"
    
    # Decode session
    padding = 4 - len(session_string) % 4
    if padding != 4:
        session_string += "=" * padding
        
    session_data = base64.urlsafe_b64decode(session_string)
    
    # Extract API ID
    api_id_from_session = struct.unpack('<I', session_data[1:5])[0]
    
    print("API ID MISMATCH DETECTED")
    print("=" * 40)
    print(f"Session was created with API ID: {api_id_from_session}")
    print(f"Your config uses API ID: 22242892")
    print()
    print("SOLUTION:")
    print("You need to update your .env file to use the same API credentials")
    print("that were used to create this Pyrogram session.")
    print()
    print("Update your config/.env file:")
    print(f"API_ID={api_id_from_session}")
    print("API_HASH=your_matching_api_hash_here")
    print()
    print("Or get the correct API_HASH for API_ID 1921728000 from https://my.telegram.org")

if __name__ == "__main__":
    analyze_session_api_id()