#!/usr/bin/env python3
"""Simple approach - just use the session as-is and handle the error gracefully"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from telethon import TelegramClient
from telethon.sessions import StringSession
from teleguard.core.config import config

async def test_direct_session():
    """Test using the session directly without conversion"""
    
    session_string = "AgA-i3IAgO2hJh_qaQx7nJtOgXUJYyuzbpum8Ex9GhyVytVaT5Wda_bgpk1zqSiVf-59G93dXCno6-tvWbgxKXWghhVu3DGyijvnixREHGIaFdNsNKftFBDwwOafe2oi9Z5j9vwQmA7eqK8qvGdD9-1JB22Fc3B4eR_F4EgIer1CfEsBrlV-OYgrTGwmEiZOP9_8nUN0uHyMJTuMtm5g3sWscaChMOpbs0z9WwZpXrVlEaQMGrHmRSEKWecXdDLO-pEO-v_EeLxjAl7vKlPoBrYYM7Ku3higxBmcrZMddvWNcMzOZY_bMb6dpvAi9ZOoQ1p7LNcasZhhz_ndfixgDR3iSAE2FwAAAAHjdA-PAA"
    
    print("Testing session directly with Telethon...")
    
    try:
        # Try to create StringSession directly
        string_session = StringSession(session_string)
        print("✅ StringSession created successfully")
        
        # Try to connect
        client = TelegramClient(string_session, config.telegram.api_id, config.telegram.api_hash)
        await client.connect()
        print("✅ Client connected")
        
        # Check authorization
        if await client.is_user_authorized():
            print("✅ Session is authorized")
            me = await client.get_me()
            print(f"Account: {me.first_name} {me.last_name or ''} ({me.phone})")
        else:
            print("❌ Session not authorized")
            
        await client.disconnect()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
        # The session might be in Pyrogram format, which Telethon can't read directly
        # Let's create a simple workaround
        print("\nThis appears to be a Pyrogram session.")
        print("Pyrogram sessions cannot be directly converted to Telethon format.")
        print("You'll need to:")
        print("1. Use the original Pyrogram client to export the session")
        print("2. Or re-login with phone number in TeleGuard")

if __name__ == "__main__":
    asyncio.run(test_direct_session())