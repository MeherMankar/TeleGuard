#!/usr/bin/env python3
"""Fix HTML-encoded sessions in database"""

import asyncio
import html
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from teleguard.core.mongo_database import init_db, mongodb

async def fix_html_sessions():
    """Fix HTML-encoded session strings in database"""
    try:
        await init_db()
        
        # Find accounts with HTML-encoded sessions
        accounts = await mongodb.db.accounts.find({}).to_list(None)
        
        fixed_count = 0
        for account in accounts:
            session_string = account.get('session_string', '')
            
            if '&lt;' in session_string or '&gt;' in session_string or '&#39;' in session_string:
                # Decode HTML entities
                decoded_session = html.unescape(session_string)
                
                # Update the account
                await mongodb.db.accounts.update_one(
                    {'_id': account['_id']},
                    {'$set': {'session_string': decoded_session}}
                )
                
                print(f"Fixed session for {account.get('name', 'Unknown')} ({account.get('phone', 'Unknown')})")
                fixed_count += 1
        
        print(f"Fixed {fixed_count} HTML-encoded sessions")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(fix_html_sessions())