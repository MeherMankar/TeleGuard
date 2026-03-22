"""Session utilities for import/export operations"""

import json
import logging
import base64
import struct

from telethon import TelegramClient
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)


def get_supported_formats():
    """Get list of supported session formats"""
    return [
        "telethon_string",
        "telethon_file",
        "pyrogram_string",
        "pyrogram_file",
        "json_session",
        "custom_json",
    ]


def detect_session_type(session_data):
    """Detect session type from data"""
    if isinstance(session_data, str):
        if session_data.startswith("{") and session_data.endswith("}"):
            return "json_session"
        elif len(session_data) > 100 and session_data.isalnum():
            return "telethon_string"
        elif len(session_data) < 100 and session_data.isalnum():
            return "pyrogram_string"
    return "unknown"


async def validate_session(session_string, api_id, api_hash):
    """Validate session string by testing connection"""
    try:
        # Create temporary client to test session
        temp_client = TelegramClient(StringSession(session_string), api_id, api_hash)

        await temp_client.connect()

        if not await temp_client.is_user_authorized():
            await temp_client.disconnect()
            return False, "Session not authorized"

        # Get user info
        me = await temp_client.get_me()
        await temp_client.disconnect()

        return True, {
            "phone": me.phone,
            "name": f"{me.first_name or ''} {me.last_name or ''}".strip()
            or me.username
            or "Unknown",
            "session_type": "telethon_string",
            "telethon_session": session_string,
        }

    except Exception as e:
        logger.error(f"Session validation error: {e}")
        return False, str(e)


async def extract_session_from_file(file_path, api_id, api_hash):
    """Extract session string from various file formats"""
    try:
        if file_path.endswith(".session"):
            # SQLite session file
            return await _extract_from_sqlite(file_path, api_id, api_hash)
        elif file_path.endswith(".txt"):
            # Text file with session string
            with open(file_path, "r", encoding="utf-8") as f:
                session_string = f.read().strip()
            return True, session_string, "Text file"
        elif file_path.endswith(".json"):
            # JSON session file
            return await _extract_from_json(file_path)
        else:
            return False, None, "Unsupported file format"

    except Exception as e:
        logger.error(f"File extraction error: {e}")
        return False, None, str(e)


async def _extract_from_sqlite(file_path, api_id, api_hash):
    """Extract session from SQLite .session file"""
    try:
        # Create temporary client with the session file
        temp_client = TelegramClient(file_path, api_id, api_hash)
        await temp_client.connect()

        if not await temp_client.is_user_authorized():
            await temp_client.disconnect()
            return False, None, "Session file not authorized"

        # Convert to string session
        session_string = temp_client.session.save()
        await temp_client.disconnect()

        return True, session_string, "SQLite session file"

    except Exception as e:
        logger.error(f"SQLite extraction error: {e}")
        return False, None, str(e)


async def _extract_from_json(file_path):
    """Extract session from JSON file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            if "session_string" in data:
                return True, data["session_string"], "JSON with session_string"
            elif "auth_key" in data and "dc_id" in data:
                # Try to reconstruct session from auth_key and dc_id
                return False, None, "JSON auth_key format not supported yet"
        elif isinstance(data, str):
            # JSON file contains just a session string
            return True, data, "JSON string"

        return False, None, "Unsupported JSON format"

    except Exception as e:
        logger.error(f"JSON extraction error: {e}")
        return False, None, str(e)


async def convert_pyrogram_to_telethon(pyrogram_session: str, api_id: int, api_hash: str):
    """Convert Pyrogram session string to Telethon format"""
    try:
        # Decode base64 Pyrogram session
        decoded = base64.urlsafe_b64decode(pyrogram_session + "===")
        
        # Pyrogram session format: dc_id (1 byte) + auth_key (256 bytes)
        if len(decoded) < 257:
            return None, "Invalid Pyrogram session length"
        
        dc_id = decoded[0]
        auth_key = decoded[1:257]
        
        logger.info(f"Pyrogram session decoded: DC {dc_id}, auth_key length {len(auth_key)}")
        
        # DC server mapping
        dc_servers = {
            1: ('149.154.175.53', 443),
            2: ('149.154.167.51', 443),
            3: ('149.154.175.100', 443),
            4: ('149.154.167.91', 443),
            5: ('91.108.56.130', 443),
        }
        
        server, port = dc_servers.get(dc_id, ('149.154.175.53', 443))
        
        # Create Telethon StringSession format manually
        # Format: 1 byte version + data center info + auth key
        server_bytes = server.encode('ascii')
        
        # Pack session data according to Telethon's format
        session_data = struct.pack('>B', 1)  # version = 1
        session_data += struct.pack('>B', dc_id)  # dc_id
        session_data += struct.pack('>H', len(server_bytes))  # server address length (2 bytes)
        session_data += server_bytes  # server address
        session_data += struct.pack('>H', port)  # port (2 bytes)
        session_data += auth_key  # auth_key (256 bytes)
        
        # Encode to base64 for StringSession
        telethon_string = base64.urlsafe_b64encode(session_data).decode('ascii').rstrip('=')
        
        logger.info(f"Telethon session created: length {len(telethon_string)}, DC {dc_id}")
        logger.info(f"Successfully converted Pyrogram session to Telethon (DC: {dc_id})")
        return telethon_string, "Conversion successful"
        
    except Exception as e:
        logger.error(f"Pyrogram conversion failed: {e}", exc_info=True)
        return None, f"Conversion error: {str(e)}"
