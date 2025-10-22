#!/usr/bin/env python3
"""Test the new fresh Pyrogram session"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from teleguard.utils.session_utils import validate_string_session
from teleguard.core.config import config

async def test_new_session():
    session_string = "AgA-i3IAUx3gyV6fvigeaksmnCljeXp7r4yVshzrdBcks6d1WTVMkIqB3Hms7ZkpZPlqztnKZbTo7-s0WZhBetaeh3TCbBBWzQlmkue-zzAh7URMjvvtSFgmze_KCAvGtF7aQEsxmsJxdBjTJoeJih-V4rIAKVnxxMhhAj-NpLwVM-yTzDMieOaB7sQaZggvL7vGRRJv5WYn5HH94YVakK6h7chi--wDmizVlnle3oa_DGkvQlCyPMd0mjTj-dkDy8mjxhIWk4qDUtWFrd3yfan6SE4up2ZDEcSrDafUvtSi0_NB7oMLF0x8AtYWyozlOQTidMFc-EcCebQq3-4U_jj8WaGzgAAAAAHjdA-PAA"
    
    print("Testing new Pyrogram session...")
    
    success, result = await validate_string_session(
        session_string, 
        config.telegram.api_id, 
        config.telegram.api_hash
    )
    
    if success:
        print("SUCCESS: Session validation successful!")
        print(f"Account: {result['name']} ({result['phone']})")
        print(f"Session type: {result['session_type']}")
        if 'converted_session' in result:
            print(f"Converted session: {result['converted_session'][:50]}...")
    else:
        print("FAILED: Session validation failed!")
        print(f"Error: {result}")

if __name__ == "__main__":
    asyncio.run(test_new_session())