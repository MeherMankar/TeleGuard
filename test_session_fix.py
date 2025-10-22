#!/usr/bin/env python3
"""Test session validation with the provided session string"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from teleguard.utils.session_utils import validate_string_session, detect_session_type
from teleguard.core.config import config

async def test_session():
    session_string = "AgA-i3IAgO2hJh_qaQx7nJtOgXUJYyuzbpum8Ex9GhyVytVaT5Wda_bgpk1zqSiVf-59G93dXCno6-tvWbgxKXWghhVu3DGyijvnixREHGIaFdNsNKftFBDwwOafe2oi9Z5j9vwQmA7eqK8qvGdD9-1JB22Fc3B4eR_F4EgIer1CfEsBrlV-OYgrTGwmEiZOP9_8nUN0uHyMJTuMtm5g3sWscaChMOpbs0z9WwZpXrVlEaQMGrHmRSEKWecXdDLO-pEO-v_EeLxjAl7vKlPoBrYYM7Ku3higxBmcrZMddvWNcMzOZY_bMb6dpvAi9ZOoQ1p7LNcasZhhz_ndfixgDR3iSAE2FwAAAAHjdA-PAA"
    
    print(f"Testing session string...")
    print(f"Length: {len(session_string)}")
    print(f"Type: {type(session_string)}")
    
    # Detect session type
    session_type = detect_session_type(session_string)
    print(f"Detected type: {session_type}")
    
    # Test validation
    try:
        success, result = await validate_string_session(
            session_string, 
            config.telegram.api_id, 
            config.telegram.api_hash
        )
        
        if success:
            print("Session validation successful!")
            print(f"Account info: {result}")
        else:
            print("Session validation failed!")
            print(f"Error: {result}")
            
    except Exception as e:
        print(f"Validation error: {e}")

if __name__ == "__main__":
    asyncio.run(test_session())