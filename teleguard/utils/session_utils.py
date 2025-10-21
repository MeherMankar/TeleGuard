"""Session utilities for TeleGuard - Pyrogram to Telethon conversion"""
import base64
import struct
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)

def convert_pyrogram_to_telethon(pyrogram_session: str) -> str:
    """Convert Pyrogram session string to Telethon format"""
    try:
        # Decode base64 session
        session_data = base64.urlsafe_b64decode(pyrogram_session + "=" * (4 - len(pyrogram_session) % 4))
        
        # Pyrogram session format: dc_id, api_id, test_mode, auth_key, user_id, is_bot
        dc_id = struct.unpack('<B', session_data[0:1])[0]
        api_id = struct.unpack('<I', session_data[1:5])[0]
        test_mode = struct.unpack('<?', session_data[5:6])[0]
        auth_key = session_data[6:262]  # 256 bytes
        user_id = struct.unpack('<Q', session_data[262:270])[0]
        is_bot = struct.unpack('<?', session_data[270:271])[0]
        
        # Create Telethon session format
        # Telethon StringSession format: dc_id + server_address + port + auth_key
        
        # Map DC to server addresses (Telegram's production servers)
        dc_servers = {
            1: ("149.154.175.53", 443),
            2: ("149.154.167.51", 443), 
            3: ("149.154.175.100", 443),
            4: ("149.154.167.91", 443),
            5: ("91.108.56.130", 443)
        }
        
        if dc_id not in dc_servers:
            dc_id = 2  # Default to DC2
            
        server_address, port = dc_servers[dc_id]
        
        # Pack Telethon session data
        telethon_data = struct.pack('<B', dc_id)  # DC ID
        telethon_data += server_address.encode('ascii') + b'\x00' * (16 - len(server_address))  # Server (16 bytes)
        telethon_data += struct.pack('<H', port)  # Port
        telethon_data += auth_key  # Auth key (256 bytes)
        
        # Encode to base64
        telethon_session = base64.urlsafe_b64encode(telethon_data).decode('ascii').rstrip('=')
        
        return telethon_session
        
    except Exception as e:
        logger.error(f"Pyrogram to Telethon conversion error: {e}")
        return None

async def validate_string_session(session_string: str, api_id: int, api_hash: str) -> tuple:
    """Validate session string and return account info"""
    try:
        # First try as Telethon session
        try:
            client = TelegramClient(StringSession(session_string), api_id, api_hash)
            await client.connect()
            
            if not await client.is_user_authorized():
                await client.disconnect()
                return False, "Session not authorized"
                
            me = await client.get_me()
            await client.disconnect()
            
            return True, {
                "phone": me.phone,
                "name": f"{me.first_name or ''} {me.last_name or ''}".strip() or f"User_{me.id}",
                "user_id": me.id,
                "username": me.username,
                "session_type": "telethon"
            }
            
        except Exception as telethon_error:
            logger.debug(f"Telethon validation failed: {telethon_error}")
            
            # Try converting from Pyrogram format
            converted_session = convert_pyrogram_to_telethon(session_string)
            if not converted_session:
                return False, "Invalid session format (not Telethon or Pyrogram)"
                
            # Test converted session
            client = TelegramClient(StringSession(converted_session), api_id, api_hash)
            await client.connect()
            
            if not await client.is_user_authorized():
                await client.disconnect()
                return False, "Converted session not authorized"
                
            me = await client.get_me()
            await client.disconnect()
            
            return True, {
                "phone": me.phone,
                "name": f"{me.first_name or ''} {me.last_name or ''}".strip() or f"User_{me.id}",
                "user_id": me.id,
                "username": me.username,
                "session_type": "pyrogram_converted",
                "converted_session": converted_session
            }
            
    except Exception as e:
        logger.error(f"Session validation error: {e}")
        return False, f"Validation failed: {str(e)}"

def detect_session_type(session_string: str) -> str:
    """Detect if session is Pyrogram or Telethon format"""
    try:
        # Try to decode as base64
        session_data = base64.urlsafe_b64decode(session_string + "=" * (4 - len(session_string) % 4))
        
        # Pyrogram sessions are typically 271 bytes
        if len(session_data) == 271:
            return "pyrogram"
        # Telethon sessions vary but are typically different length
        elif len(session_data) > 100:
            return "telethon"
        else:
            return "unknown"
            
    except Exception:
        return "invalid"