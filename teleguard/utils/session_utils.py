"""Session utilities for import/export operations"""

import json
import logging

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
