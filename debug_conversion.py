#!/usr/bin/env python3
"""Debug the conversion process"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from teleguard.utils.session_utils import convert_pyrogram_to_telethon
from teleguard.core.config import config

async def debug_conversion():
    session_string = "AgA-i3IAUx3gyV6fvigeaksmnCljeXp7r4yVshzrdBcks6d1WTVMkIqB3Hms7ZkpZPlqztnKZbTo7-s0WZhBetaeh3TCbBBWzQlmkue-zzAh7URMjvvtSFgmze_KCAvGtF7aQEsxmsJxdBjTJoeJih-V4rIAKVnxxMhhAj-NpLwVM-yTzDMieOaB7sQaZggvL7vGRRJv5WYn5HH94YVakK6h7chi--wDmizVlnle3oa_DGkvQlCyPMd0mjTj-dkDy8mjxhIWk4qDUtWFrd3yfan6SE4up2ZDEcSrDafUvtSi0_NB7oMLF0x8AtYWyozlOQTidMFc-EcCebQq3-4U_jj8WaGzgAAAAAHjdA-PAA"
    
    print("Testing Pyrogram conversion...")
    
    converted_session, result = await convert_pyrogram_to_telethon(
        session_string, 
        config.telegram.api_id, 
        config.telegram.api_hash
    )
    
    print(f"Converted session: {converted_session}")
    print(f"Result: {result}")
    print(f"Result type: {type(result)}")
    
    if converted_session:
        print("SUCCESS: Conversion worked!")
        print(f"Telethon session: {converted_session[:50]}...")
    else:
        print("FAILED: Conversion failed")

if __name__ == "__main__":
    asyncio.run(debug_conversion())