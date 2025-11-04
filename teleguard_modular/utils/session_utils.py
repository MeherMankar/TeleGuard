"""Session utilities for TeleGuard - Pyrogram to Telethon conversion"""
import base64
import struct
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)

async def convert_pyrogram_to_telethon(pyrogram_session: str, api_id: int, api_hash: str) -> tuple:
    """Convert Pyrogram session to Telethon using MemorySession"""
    try:
        from telethon.sessions import MemorySession
        
        # Decode the Pyrogram session
        padding = 4 - len(pyrogram_session) % 4
        if padding != 4:
            pyrogram_session += "=" * padding
            
        session_data = base64.urlsafe_b64decode(pyrogram_session)
        
        # Validate minimum length
        if len(session_data) < 271:
            logger.error(f"Invalid Pyrogram session length: {len(session_data)}")
            return None, "Invalid session length"
        
        # Extract Pyrogram session components
        dc_id = struct.unpack('<B', session_data[0:1])[0]
        api_id_pyro = struct.unpack('<I', session_data[1:5])[0]
        test_mode = struct.unpack('<?', session_data[5:6])[0]
        auth_key = session_data[6:262]  # 256 bytes
        user_id = struct.unpack('<Q', session_data[262:270])[0]
        is_bot = struct.unpack('<?', session_data[270:271])[0]
        
        logger.debug(f"Pyrogram session - DC: {dc_id}, API_ID: {api_id_pyro}, User: {user_id}, Bot: {is_bot}")
        
        # Validate auth_key
        if len(auth_key) != 256 or auth_key == b'\x00' * 256:
            logger.error("Invalid auth_key in Pyrogram session")
            return None, "Invalid auth key"
        
        # Map DC to server addresses
        dc_servers = {
            1: ("149.154.175.53", 443),
            2: ("149.154.167.51", 443), 
            3: ("149.154.175.100", 443),
            4: ("149.154.167.91", 443),
            5: ("91.108.56.130", 443)
        }
        
        if dc_id not in dc_servers:
            logger.warning(f"Unknown DC {dc_id}, defaulting to DC2")
            dc_id = 2
            
        server_address, port = dc_servers[dc_id]
        
        # Create Telethon StringSession directly from auth_key
        from telethon.sessions import StringSession
        from telethon.crypto import AuthKey
        
        # Create empty StringSession and set the data
        session = StringSession()
        session.set_dc(dc_id, server_address, port)
        
        # Create AuthKey object from raw bytes
        auth_key_obj = AuthKey(auth_key)
        session.auth_key = auth_key_obj
        
        # Save to get Telethon session string
        telethon_session = session.save()
        
        logger.info(f"Converted Pyrogram session to Telethon format")
        
        # Test converted session to get real account info
        if telethon_session:
            try:
                test_client = TelegramClient(StringSession(telethon_session), api_id, api_hash)
                await test_client.connect()
                
                if await test_client.is_user_authorized():
                    me = await test_client.get_me()
                    await test_client.disconnect()
                    
                    return telethon_session, {
                        "phone": f"+{me.phone}" if me.phone and not me.phone.startswith("+") else me.phone,
                        "name": f"{me.first_name or ''} {me.last_name or ''}".strip() or f"User_{me.id}",
                        "user_id": me.id,
                        "username": me.username
                    }
                else:
                    await test_client.disconnect()
                    logger.warning("Session expired - marking for reauth")
                    return None, "Session expired - marked for reauth"
            except Exception as e:
                return None, f"Failed to validate converted session: {e}"
        else:
            return None, "Failed to create Telethon session"
            
    except Exception as e:
        logger.error(f"Pyrogram to Telethon conversion error: {e}")
        return None, str(e)

async def validate_string_session(session_string: str, api_id: int, api_hash: str) -> tuple:
    """Validate session string and return account info"""
    try:
        # Decode HTML entities if present
        import html
        session_string = html.unescape(session_string)
        
        # First try as Telethon session directly
        try:
            client = TelegramClient(StringSession(session_string), api_id, api_hash)
            await client.connect()
            
            if not await client.is_user_authorized():
                await client.disconnect()
                return False, "Session not authorized"
                
            me = await client.get_me()
            await client.disconnect()
            
            return True, {
                "phone": f"+{me.phone}" if me.phone and not me.phone.startswith("+") else me.phone,
                "name": f"{me.first_name or ''} {me.last_name or ''}".strip() or f"User_{me.id}",
                "user_id": me.id,
                "username": me.username,
                "session_type": "telethon"
            }
            
        except ValueError as ve:
            if "Not a valid string" in str(ve):
                # This is likely a Pyrogram session - try to convert it
                session_type = detect_session_type(session_string)
                if session_type == "pyrogram":
                    logger.info("Detected Pyrogram session, attempting conversion...")
                    
                    converted_session, result = await convert_pyrogram_to_telethon(session_string, api_id, api_hash)
                    
                    if converted_session:
                        return True, {
                            "phone": result["phone"],
                            "name": result["name"],
                            "user_id": result["user_id"],
                            "username": result["username"],
                            "session_type": "pyrogram_converted",
                            "converted_session": converted_session
                        }
                    else:
                        return False, f"Pyrogram session conversion failed: {result}"
                else:
                    return False, f"Invalid session string format: {ve}"
            else:
                return False, f"Session validation error: {ve}"
                
        except Exception as e:
            logger.debug(f"Telethon session validation failed: {e}")
            return False, f"Session validation failed: {str(e)}"
            
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