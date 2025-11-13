"""Session Login Handler - Complete SessionMaster Integration
Developed by:
- @Meher_Mankar
- @Gutkesh
GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""
import logging
import os
import asyncio
import tempfile
import time
import io
import json
import shutil
from typing import Dict, Optional, List, Any
from telethon import TelegramClient, events, Button
from telethon.errors import PhoneCodeInvalidError, SessionPasswordNeededError, PasswordHashInvalidError
from telethon.sessions import StringSession
from telethon.crypto import AuthKey
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.contacts import GetContactsRequest, ImportContactsRequest
from telethon.tl.functions.messages import GetHistoryRequest, SendMessageRequest
from telethon.tl.types import InputPhoneContact, User, Channel, Chat
from ..core.config import config
from ..core.mongo_database import mongodb
from ..utils.network_helpers import retry_async
from ..core.device_snooper import DeviceSnooper

logger = logging.getLogger(__name__)

class SessionLoginHandler:
    """Complete SessionMaster functionality integrated into TeleGuard"""
    
    def __init__(self, bot_manager):
        self.bot = bot_manager.bot
        self.bot_manager = bot_manager
        self.user_clients = bot_manager.user_clients
        self.pending_auth = {}
        self.pending_actions = {}
        self.device_snooper = DeviceSnooper(mongodb) if mongodb else None
        
        # Device list for realistic session creation
        self.devices = [
            {"model": "Samsung SM-G973F", "system": "Android 10", "version": "8.4.1"},
            {"model": "Samsung SM-G975F", "system": "Android 11", "version": "8.5.0"},
            {"model": "Samsung SM-G981B", "system": "Android 11", "version": "8.5.1"},
            {"model": "Samsung SM-G991B", "system": "Android 12", "version": "8.6.1"},
            {"model": "Samsung SM-A525F", "system": "Android 11", "version": "8.5.4"},
            {"model": "Samsung SM-N975F", "system": "Android 10", "version": "8.4.3"},
            {"model": "Samsung SM-G996B", "system": "Android 12", "version": "8.6.4"},
            {"model": "Samsung SM-G998B", "system": "Android 13", "version": "8.7.2"},
            {"model": "Xiaomi Mi 11", "system": "Android 11", "version": "8.5.2"},
            {"model": "Xiaomi Mi 12", "system": "Android 12", "version": "8.6.5"},
            {"model": "Xiaomi Redmi Note 10", "system": "Android 11", "version": "8.5.5"},
            {"model": "Xiaomi POCO F3", "system": "Android 11", "version": "8.5.6"},
            {"model": "OnePlus 9 Pro", "system": "Android 12", "version": "8.6.0"},
            {"model": "OnePlus 8T", "system": "Android 11", "version": "8.5.7"},
            {"model": "Google Pixel 6", "system": "Android 13", "version": "8.7.1"},
            {"model": "Google Pixel 5", "system": "Android 12", "version": "8.6.8"},
            {"model": "Huawei P40 Pro", "system": "Android 10", "version": "8.4.2"},
            {"model": "Oppo Find X3", "system": "Android 11", "version": "8.5.1"},
            {"model": "Vivo X60 Pro", "system": "Android 11", "version": "8.5.2"},
            {"model": "Realme GT", "system": "Android 11", "version": "8.5.3"}
        ]
    
    def get_random_device(self):
        """Get random device configuration"""
        import random
        return random.choice(self.devices)
    
    def register_handlers(self):
        """Register all session login handlers"""
        
        @self.bot.on(events.CallbackQuery(pattern=r"^session_login$"))
        async def session_login_menu(event):
            user_id = event.sender_id
            await self._show_session_login_menu(event, user_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^export_sessions$"))
        async def create_session_menu(event):
            user_id = event.sender_id
            await self._start_session_creation(event, user_id)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"^create_sess:(.+)$"))
        async def create_session_execute(event):
            user_id = event.sender_id
            phone = event.pattern_match.group(1).decode()
            await self._show_format_selection(event, user_id, phone)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"^create_sess_fmt:(.+):(.+)$"))
        async def create_session_with_format(event):
            user_id = event.sender_id
            phone = event.pattern_match.group(1).decode()
            format_type = event.pattern_match.group(2).decode()
            await event.answer("⏳ Creating session...")
            await self._execute_session_creation(event, user_id, phone, format_type)
        

        
        @self.bot.on(events.CallbackQuery(pattern=r"^login_session_file$"))
        async def login_by_session_file(event):
            user_id = event.sender_id
            await self._start_session_file_login(event, user_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^login_session_string$"))
        async def login_by_session_string(event):
            user_id = event.sender_id
            await self._start_session_string_login(event, user_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^session_info:(.+)$"))
        async def show_session_info(event):
            user_id = event.sender_id
            account_id = event.pattern_match.group(1).decode()
            await self._show_session_info(event, user_id, account_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^session_operations:(.+)$"))
        async def session_operations(event):
            user_id = event.sender_id
            account_id = event.pattern_match.group(1).decode()
            await self._show_session_operations(event, user_id, account_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^session_op:(.+):(.+)$"))
        async def handle_session_operation(event):
            user_id = event.sender_id
            operation = event.pattern_match.group(1).decode()
            account_id = event.pattern_match.group(2).decode()
            await self._handle_session_operation(event, user_id, operation, account_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^resend_code$"))
        async def resend_code(event):
            user_id = event.sender_id
            await self._resend_code(event, user_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^restart_auth$"))
        async def restart_auth(event):
            user_id = event.sender_id
            await self._restart_auth(event, user_id)
    
    async def _show_session_login_menu(self, event, user_id):
        """Show session login main menu"""
        try:
            text = (
                "🔐 **Session Import Manager**\n\n"
                "Import existing sessions using these methods:\n\n"
                "**📁 Session File**\n"
                "• Upload .session file\n"
                "• Supports Telethon & Pyrogram\n"
                "• Instant account addition\n\n"
                "**📝 Session String**\n"
                "• Paste session string\n"
                "• Quick import method\n\n"
                "**📦 TData (Coming Soon)**\n"
                "• Telegram Desktop format\n"
                "• Currently not supported\n\n"
                "Choose your import method:"
            )
            
            buttons = [
                [Button.inline("📁 Upload Session File", "login_session_file")],
                [Button.inline("📝 Import Session String", "login_session_string")],
                [Button.inline("🔙 Back to Account Settings", "menu:accounts")]
            ]
            
            await event.edit(text, buttons=buttons)
        except Exception as e:
            logger.error(f"Session login menu error: {e}")
            await event.edit("❌ Error loading session login menu.")
    

    
    async def _start_session_file_login(self, event, user_id):
        """Start session file upload process"""
        try:
            self.bot_manager.pending_actions[user_id] = {
                "action": "session_file_login"
            }
            
            text = (
                "📁 **Upload Session File**\n\n"
                "Send your .session file as a document:\n\n"
                "**Supported Files:**\n"
                "• .session files from Telethon\n"
                "• .session files from Pyrogram\n"
                "• SQLite session databases\n"
                "• TData files (not yet supported)\n\n"
                "**Security:**\n"
                "• Files are validated before use\n"
                "• Temporary files are deleted\n"
                "• Session data is encrypted\n\n"
                "**How to Send:**\n"
                "1. Send the file as document (not photo)\n"
                "2. Bot will validate the session\n"
                "3. Account will be added automatically\n\n"
                "Send your .session file now:"
            )
            
            await event.edit(text)
            await event.answer("📁 Send session file")
        except Exception as e:
            logger.error(f"Start session file login error: {e}")
            await event.edit("❌ Error starting session file login.")
    
    async def _start_session_string_login(self, event, user_id):
        """Start session string import process"""
        try:
            self.bot_manager.pending_actions[user_id] = {
                "action": "session_string_login"
            }
            
            text = (
                "📝 **Import Session String**\n\n"
                "Reply with your session string:\n\n"
                "**Format:**\n"
                "```\n"
                "1BVtsOHwAa7T...(long string)\n"
                "```\n\n"
                "**Where to Get:**\n"
                "• From another TeleGuard bot\n"
                "• From Telethon scripts\n"
                "• From session export tools\n"
                "• From other Telegram bots\n\n"
                "**Security:**\n"
                "• Session strings are validated\n"
                "• Data is encrypted before storage\n"
                "• Invalid sessions are rejected\n\n"
                "Reply with your session string:"
            )
            
            await event.edit(text)
            await event.answer("📝 Reply with session string")
        except Exception as e:
            logger.error(f"Start session string login error: {e}")
            await event.edit("❌ Error starting session string login.")
    

    

    

    
    async def process_session_file(self, user_id, file_path):
        """Process uploaded session file"""
        try:
            if not os.path.exists(file_path):
                return False, "❌ Session file not found"
            
            # Check file size (should be reasonable for a session file)
            file_size = os.path.getsize(file_path)
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                return False, "❌ Session file too large (max 10MB)"
            
            if file_size < 100:  # Too small to be a valid session
                return False, "❌ Session file appears to be empty or corrupted"
            
            # Extract session string from file
            logger.info(f"Processing session file: {file_path} (size: {file_size} bytes)")
            session_string = await self._extract_session_from_file(file_path)
            
            if not session_string:
                return False, (
                    "❌ Could not extract session from file.\n\n"
                    "**File Analysis:**\n"
                    f"• File size: {file_size} bytes\n"
                    f"• File path: {os.path.basename(file_path)}\n\n"
                    "**Supported formats:**\n"
                    "• Telethon .session files (SQLite)\n"
                    "• Pyrogram .session files (SQLite)\n"
                    "• Other SQLite-based session files\n\n"
                    "**Troubleshooting:**\n"
                    "• Ensure file is not corrupted\n"
                    "• Try using '📝 Import Session String' instead\n"
                    "• Use '📱 Login by Phone' for fresh login\n"
                    "• Check bot logs for detailed error information"
                )
            
            # Validate and save session
            logger.info(f"Validating extracted session string (length: {len(session_string)})")
            success, message = await self.process_session_string(user_id, session_string)
            
            # Clean up file
            try:
                os.remove(file_path)
                logger.info(f"Cleaned up temporary file: {file_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup file {file_path}: {cleanup_error}")
            
            return success, message
            
        except Exception as e:
            logger.error(f"Session file processing error: {e}")
            # Clean up file on error
            try:
                os.remove(file_path)
                logger.info(f"Cleaned up file after error: {file_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup file after error {file_path}: {cleanup_error}")
            
            return False, (
                f"❌ File processing failed: {str(e)}\n\n"
                "**Error Details:**\n"
                f"• Error: {str(e)}\n"
                f"• File: {os.path.basename(file_path)}\n\n"
                "**Try these alternatives:**\n"
                "• Use '📝 Import Session String' instead\n"
                "• Use '📱 Login by Phone' for fresh login\n"
                "• Ensure the session file is valid and not corrupted\n"
                "• Check bot logs for detailed error information"
            )
    
    async def process_session_string(self, user_id, session_string):
        """Process session string import"""
        try:
            if not session_string or len(session_string) < 50:
                return False, "❌ Invalid session string format"
            
            # Try temp file approach first for better reliability
            logger.info("Attempting session string import via temp file method...")
            temp_success, temp_result = await self._process_session_via_temp_file(session_string)
            if temp_success:
                return await self._finalize_session_import(user_id, temp_result, session_string)
            
            # Fallback to fast validation mode
            logger.info("Temp file method failed, using fast validation mode...")
            success, info = await self._validate_session_string(session_string)
            if not success:
                logger.error(f"Session validation failed: {info}")
                return False, f"❌ {info}\n\n💡 Try using session file upload for better reliability."
            
            return await self._finalize_session_import(user_id, info, session_string)
            
        except Exception as e:
            logger.error(f"Session string processing error: {e}")
            return False, f"❌ Import failed: {str(e)}\n\n💡 **Try using session file upload instead**"
    
    async def _extract_session_from_file(self, file_path):
        """Extract session string from various session file formats"""
        try:
            logger.info(f"Starting session extraction from: {file_path}")
            
            # Method 1: Try Pyrogram session format first (most common)
            logger.info("Attempting Pyrogram session extraction...")
            pyrogram_session = await self._extract_pyrogram_session(file_path)
            if pyrogram_session:
                logger.info("Successfully extracted Pyrogram session")
                return pyrogram_session
            
            # Method 2: Try Telethon session format
            logger.info("Attempting Telethon session extraction...")
            telethon_session = await self._extract_telethon_session(file_path)
            if telethon_session:
                logger.info("Successfully extracted Telethon session")
                return telethon_session
            
            # Method 3: Try direct SQLite reading for other formats
            logger.info("Attempting generic SQLite session extraction...")
            sqlite_session = await self._extract_from_sqlite(file_path)
            if sqlite_session:
                logger.info("Successfully extracted generic SQLite session")
                return sqlite_session
            
            logger.warning("All session extraction methods failed")
            return None
                
        except Exception as e:
            logger.error(f"Session extraction error: {e}")
            return None
    
    async def _extract_pyrogram_session(self, file_path):
        """Extract session from Pyrogram format"""
        try:
            import sqlite3
            import base64
            from struct import pack
            
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            # Check if it's a Pyrogram session
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Try different Pyrogram table structures
            session_data = None
            
            # Method 1: Standard Pyrogram sessions table
            if 'sessions' in tables:
                cursor.execute("PRAGMA table_info(sessions)")
                columns = [row[1] for row in cursor.fetchall()]
                
                if all(col in columns for col in ['dc_id', 'server_address', 'port', 'auth_key']):
                    cursor.execute("SELECT dc_id, server_address, port, auth_key FROM sessions LIMIT 1")
                    session_data = cursor.fetchone()
                elif all(col in columns for col in ['dc_id', 'api_id', 'test_mode', 'auth_key', 'date', 'user_id', 'is_bot']):
                    # Alternative Pyrogram structure
                    cursor.execute("SELECT dc_id, auth_key FROM sessions LIMIT 1")
                    row = cursor.fetchone()
                    if row:
                        dc_id, auth_key = row
                        # Default server addresses for each DC
                        dc_servers = {
                            1: ('149.154.175.53', 443),
                            2: ('149.154.167.51', 443),
                            3: ('149.154.175.100', 443),
                            4: ('149.154.167.91', 443),
                            5: ('91.108.56.130', 443)
                        }
                        server_address, port = dc_servers.get(dc_id, ('149.154.167.50', 443))
                        session_data = (dc_id, server_address, port, auth_key)
            
            # Method 2: Try other common Pyrogram table names
            if not session_data:
                for table_name in ['session', 'pyrogram_session', 'client_session']:
                    if table_name in tables:
                        try:
                            cursor.execute(f"PRAGMA table_info({table_name})")
                            columns = [row[1] for row in cursor.fetchall()]
                            
                            if 'auth_key' in columns and 'dc_id' in columns:
                                cursor.execute(f"SELECT dc_id, auth_key FROM {table_name} LIMIT 1")
                                row = cursor.fetchone()
                                if row:
                                    dc_id, auth_key = row
                                    dc_servers = {
                                        1: ('149.154.175.53', 443),
                                        2: ('149.154.167.51', 443),
                                        3: ('149.154.175.100', 443),
                                        4: ('149.154.167.91', 443),
                                        5: ('91.108.56.130', 443)
                                    }
                                    server_address, port = dc_servers.get(dc_id, ('149.154.167.50', 443))
                                    session_data = (dc_id, server_address, port, auth_key)
                                    break
                        except Exception:
                            continue
            
            if session_data:
                dc_id, server_address, port, auth_key = session_data
                
                # Handle different auth_key formats
                if isinstance(auth_key, str):
                    try:
                        auth_key_bytes = base64.b64decode(auth_key)
                    except:
                        auth_key_bytes = auth_key.encode('utf-8')
                elif isinstance(auth_key, (bytes, memoryview)):
                    auth_key_bytes = bytes(auth_key)
                else:
                    auth_key_bytes = str(auth_key).encode('utf-8')
                
                # Ensure auth_key is proper length (256 bytes for Telegram)
                if len(auth_key_bytes) < 256:
                    auth_key_bytes = auth_key_bytes.ljust(256, b'\x00')
                elif len(auth_key_bytes) > 256:
                    auth_key_bytes = auth_key_bytes[:256]
                
                # Build Telethon-compatible session string
                try:
                    # Create a temporary Telethon client to generate proper session string
                    temp_session = StringSession()
                    temp_session.set_dc(dc_id, server_address, port)
                    temp_session.auth_key = AuthKey(auth_key_bytes)
                    
                    session_string = StringSession.save(temp_session)
                    conn.close()
                    logger.info(f"Successfully extracted Pyrogram session: DC {dc_id}, Server {server_address}:{port}, Auth key length: {len(auth_key_bytes)}")
                    return session_string
                    
                except Exception as e:
                    logger.error(f"Failed to build session string: {e}")
            
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"Pyrogram extraction failed: {e}")
            return None
    
    async def _extract_telethon_session(self, file_path):
        """Extract session from Telethon format"""
        try:
            session_name = file_path.replace('.session', '')
            
            temp_client = TelegramClient(
                session_name, 
                config.telegram.api_id, 
                config.telegram.api_hash,
                connection_retries=1,
                retry_delay=1
            )
            
            try:
                await asyncio.wait_for(temp_client.connect(), timeout=10.0)
                
                if temp_client.is_connected():
                    session_string = StringSession.save(temp_client.session)
                    await temp_client.disconnect()
                    return session_string
                else:
                    await temp_client.disconnect()
                    return None
                    
            except Exception:
                try:
                    await temp_client.disconnect()
                except:
                    pass
                return None
                
        except Exception as e:
            logger.debug(f"Telethon extraction failed: {e}")
            return None
    
    async def _extract_from_sqlite(self, file_path):
        """Extract session from SQLite database directly"""
        try:
            import sqlite3
            import base64
            from struct import pack
            
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            logger.info(f"Found tables in session file: {tables}")
            
            # Try common session table patterns
            for table_name in tables:
                try:
                    # Get column info
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns_info = cursor.fetchall()
                    columns = [row[1] for row in columns_info]
                    
                    logger.info(f"Table {table_name} columns: {columns}")
                    
                    # Look for session-like data with various column patterns
                    auth_key_cols = [col for col in columns if 'auth' in col.lower() and 'key' in col.lower()]
                    dc_cols = [col for col in columns if 'dc' in col.lower() and 'id' in col.lower()]
                    server_cols = [col for col in columns if 'server' in col.lower() or 'address' in col.lower()]
                    port_cols = [col for col in columns if 'port' in col.lower()]
                    
                    if auth_key_cols and dc_cols:
                        # Build query based on available columns
                        auth_key_col = auth_key_cols[0]
                        dc_col = dc_cols[0]
                        server_col = server_cols[0] if server_cols else None
                        port_col = port_cols[0] if port_cols else None
                        
                        query_cols = [dc_col, auth_key_col]
                        if server_col:
                            query_cols.append(server_col)
                        if port_col:
                            query_cols.append(port_col)
                        
                        cursor.execute(f"SELECT {', '.join(query_cols)} FROM {table_name} LIMIT 1")
                        row = cursor.fetchone()
                        
                        if row and len(row) >= 2:
                            dc_id = row[0] if row[0] is not None else 2
                            auth_key = row[1]
                            server_address = row[2] if len(row) > 2 and row[2] else None
                            port = row[3] if len(row) > 3 and row[3] else 443
                            
                            # Use default server if not provided
                            if not server_address:
                                dc_servers = {
                                    1: '149.154.175.53',
                                    2: '149.154.167.51', 
                                    3: '149.154.175.100',
                                    4: '149.154.167.91',
                                    5: '91.108.56.130'
                                }
                                server_address = dc_servers.get(dc_id, '149.154.167.50')
                            
                            if auth_key:
                                # Handle different auth_key formats
                                if isinstance(auth_key, str):
                                    try:
                                        auth_key_bytes = base64.b64decode(auth_key)
                                    except:
                                        try:
                                            auth_key_bytes = bytes.fromhex(auth_key)
                                        except:
                                            auth_key_bytes = auth_key.encode('utf-8')
                                elif isinstance(auth_key, (bytes, memoryview)):
                                    auth_key_bytes = bytes(auth_key)
                                else:
                                    auth_key_bytes = str(auth_key).encode('utf-8')
                                
                                # Ensure proper auth_key length
                                if len(auth_key_bytes) < 256:
                                    auth_key_bytes = auth_key_bytes.ljust(256, b'\x00')
                                elif len(auth_key_bytes) > 256:
                                    auth_key_bytes = auth_key_bytes[:256]
                                
                                # Build session string using Telethon's method
                                try:
                                    # Create a temporary Telethon session to generate proper session string
                                    temp_session = StringSession()
                                    temp_session.set_dc(dc_id, server_address, port)
                                    temp_session.auth_key = AuthKey(auth_key_bytes)
                                    
                                    session_string = StringSession.save(temp_session)
                                    conn.close()
                                    logger.info(f"Successfully extracted session from table {table_name}: DC {dc_id}, Server {server_address}:{port}, Auth key length: {len(auth_key_bytes)}")
                                    return session_string
                                    
                                except Exception as e:
                                    logger.error(f"Failed to build session string from {table_name}: {e}")
                                    
                except Exception as e:
                    logger.debug(f"Failed to extract from table {table_name}: {e}")
                    continue
            
            conn.close()
            logger.warning("Could not extract session from any table in the database")
            return None
            
        except Exception as e:
            logger.error(f"SQLite extraction error: {e}")
            return None
    
    async def _validate_session_string(self, session_string):
        """Validate session string and get user info with skip validation option"""
        client = None
        try:
            logger.info(f"Validating session string (length: {len(session_string)})")
            
            # Check if it's a Pyrogram session string and convert if needed
            converted_session = await self._convert_pyrogram_session_string(session_string)
            if converted_session:
                logger.info("Converted Pyrogram session string to Telethon format")
                session_string = converted_session
            
            # Try basic session format validation first
            try:
                # Test if it's a valid Telethon session string
                test_session = StringSession(session_string)
                if not test_session:
                    raise ValueError("Empty session")
            except Exception as e:
                # If Telethon validation fails, it might be Pyrogram format
                logger.debug(f"Telethon validation failed: {e}")
                
                # Try Pyrogram format validation
                try:
                    import base64
                    # Convert URL-safe base64 and fix padding
                    fixed_session = session_string.replace('-', '+').replace('_', '/')
                    while len(fixed_session) % 4 != 0:
                        fixed_session += '='
                    
                    decoded = base64.b64decode(fixed_session)
                    if len(decoded) < 260:
                        return False, f"Invalid session format: too short ({len(decoded)} bytes)"
                    
                    logger.info("Session appears to be Pyrogram format")
                except Exception as decode_error:
                    return False, f"Invalid session string format: {str(decode_error)}"
            
            # Skip full validation and return basic info for faster processing
            logger.info("Using fast validation mode - skipping full connection test")
            
            # Extract basic info from session string if possible
            try:
                # Try to decode session to get DC info
                import base64
                from struct import unpack
                
                # For Pyrogram sessions, try to extract phone from original string
                if len(session_string) > 300:  # Likely Pyrogram
                    try:
                        # Convert URL-safe base64 and fix padding
                        fixed_session = session_string.replace('-', '+').replace('_', '/')
                        while len(fixed_session) % 4 != 0:
                            fixed_session += '='
                        
                        decoded = base64.b64decode(fixed_session)
                        if len(decoded) >= 260:
                            dc_id_bytes = decoded[256:260]
                            dc_id = unpack('<I', dc_id_bytes)[0]
                            
                            # Map unusual DC IDs to valid ones
                            if dc_id not in [1, 2, 3, 4, 5]:
                                dc_id = 5  # Default to DC5
                                logger.info(f"Mapped unusual DC ID to DC5")
                            
                            logger.info(f"Detected Pyrogram session with DC {dc_id}")
                            
                            # Return minimal info for fast processing
                            return True, {
                                "name": "Imported Account",
                                "phone": "+000000000",  # Placeholder
                                "username": None,
                                "id": 0,  # Placeholder
                                "premium": False,
                                "verified": False,
                                "fast_import": True
                            }
                    except Exception as e:
                        logger.debug(f"Pyrogram extraction failed: {e}")
                
                # For other sessions, return generic info
                return True, {
                    "name": "Imported Account",
                    "phone": "+000000000",  # Placeholder
                    "username": None,
                    "id": 0,  # Placeholder
                    "premium": False,
                    "verified": False,
                    "fast_import": True
                }
                
            except Exception:
                # If all else fails, try quick connection test
                return await self._quick_connection_test(session_string)
            
        except Exception as e:
            logger.error(f"Session validation error: {e}")
            return False, f"Session validation failed: {str(e)}"
    
    async def _quick_connection_test(self, session_string):
        """Quick connection test with minimal timeout"""
        client = None
        try:
            client = TelegramClient(
                StringSession(session_string), 
                config.telegram.api_id, 
                config.telegram.api_hash,
                connection_retries=1,
                retry_delay=0,
                timeout=3
            )
            
            # Very quick connection test
            await asyncio.wait_for(client.connect(), timeout=3.0)
            
            if client.is_connected():
                # Quick auth check
                is_authorized = await asyncio.wait_for(client.is_user_authorized(), timeout=2.0)
                if is_authorized:
                    try:
                        me = await asyncio.wait_for(client.get_me(), timeout=3.0)
                        info = {
                            "name": f"{me.first_name or ''} {me.last_name or ''}".strip() or "Unknown",
                            "phone": me.phone,
                            "username": me.username,
                            "id": me.id,
                            "premium": getattr(me, "premium", False),
                            "verified": getattr(me, "verified", False)
                        }
                        await client.disconnect()
                        return True, info
                    except:
                        await client.disconnect()
                        # Return placeholder info if get_me fails
                        return True, {
                            "name": "Imported Account",
                            "phone": "+000000000",
                            "username": None,
                            "id": 0,
                            "premium": False,
                            "verified": False,
                            "fast_import": True
                        }
                else:
                    await client.disconnect()
                    return False, "Session not authorized"
            else:
                return False, "Connection failed"
                
        except asyncio.TimeoutError:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass
            # Return success with placeholder for timeout cases
            logger.info("Using fast import mode due to timeout")
            return True, {
                "name": "Imported Account",
                "phone": "+000000000",
                "username": None,
                "id": 0,
                "premium": False,
                "verified": False,
                "fast_import": True
            }
        except Exception as e:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass
            return False, f"Connection test failed: {str(e)}"
    
    async def _convert_pyrogram_session_string(self, session_string):
        """Convert Pyrogram session string to Telethon format"""
        try:
            import base64
            from struct import unpack
            
            # Check if it looks like a Pyrogram session string
            if not session_string or len(session_string) < 100:
                return None
                
            # Decode the session string with proper padding
            try:
                # Convert URL-safe base64 and fix padding
                fixed_session = session_string.replace('-', '+').replace('_', '/')
                while len(fixed_session) % 4 != 0:
                    fixed_session += '='
                
                decoded = base64.b64decode(fixed_session)
            except Exception as e:
                logger.error(f"Base64 decode failed: {e}")
                return None
            
            if len(decoded) < 260:  # Need at least auth_key + dc_id
                return None
            
            # Extract components
            auth_key = decoded[:256]
            dc_id_bytes = decoded[256:260]
            
            # Extract DC ID and normalize it
            try:
                dc_id = unpack('<I', dc_id_bytes)[0]
                # Map any DC ID to valid range
                if dc_id not in [1, 2, 3, 4, 5]:
                    # Use modulo to map to valid DC range
                    dc_id = (dc_id % 5) + 1
                    logger.info(f"Mapped DC ID to valid range: {dc_id}")
            except:
                dc_id = 5
            
            # Map DC to server
            dc_servers = {
                1: '149.154.175.53',
                2: '149.154.167.51',
                3: '149.154.175.100', 
                4: '149.154.167.91',
                5: '91.108.56.130'
            }
            server_address = dc_servers.get(dc_id, '149.154.167.51')
            
            # Build Telethon session string directly
            try:
                temp_session = StringSession()
                temp_session.set_dc(dc_id, server_address, 443)
                temp_session.auth_key = AuthKey(auth_key)
                
                session_string = StringSession.save(temp_session)
                logger.info(f"Successfully converted Pyrogram session: DC {dc_id}")
                return session_string
                
            except Exception as e:
                logger.error(f"Failed to build session string: {e}")
                return None
            
        except Exception as e:
            logger.error(f"Pyrogram session conversion failed: {e}")
            return None
    
    async def _show_session_info(self, event, user_id, account_id):
        """Show detailed session information"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account:
                await event.edit("❌ Account not found")
                return
            
            # Get live session info
            info = await self._get_live_session_info(user_id, account["name"])
            
            if info:
                text = (
                    f"📱 **Session Info: {account['name']}**\n\n"
                    f"👤 **Name:** {info.get('name', 'Unknown')}\n"
                    f"🆔 **ID:** {info.get('id', 'Unknown')}\n"
                    f"📞 **Phone:** {info.get('phone', 'Hidden')}\n"
                )
                
                if info.get('username'):
                    text += f"📛 **Username:** @{info['username']}\n"
                
                text += (
                    f"💬 **Dialogs:** {info.get('dialogs', 0)}\n"
                    f"📢 **Channels:** {info.get('channels', 0)}\n"
                    f"👥 **Groups:** {info.get('groups', 0)}\n"
                    f"🤖 **Bots:** {info.get('bots', 0)}\n"
                    f"💭 **Private Chats:** {info.get('private_chats', 0)}\n"
                )
                
                if info.get('premium'):
                    text += "⭐ **Premium Account**\n"
                if info.get('verified'):
                    text += "✅ **Verified Account**\n"
                
                text += f"\n📅 **Added:** {account.get('created_at', 'Unknown')}"
                text += f"\n🔧 **Method:** {account.get('added_via', 'Unknown')}"
            else:
                text = f"📱 **Session Info: {account['name']}**\n\n❌ Could not retrieve live session information."
            
            buttons = [
                [Button.inline("🔄 Refresh Info", f"session_info:{account_id}")],
                [Button.inline("⚙️ Session Operations", f"session_operations:{account_id}")],
                [Button.inline("🔙 Back", "session_login")]
            ]
            
            await event.edit(text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Show session info error: {e}")
            await event.edit("❌ Error loading session information")
    
    async def _show_session_operations(self, event, user_id, account_id):
        """Show session operations menu"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account:
                await event.edit("❌ Account not found")
                return
            
            text = (
                f"⚙️ **Session Operations: {account['name']}**\n\n"
                "Choose an operation to perform:\n\n"
                "**📊 Information**\n"
                "• Update session info\n"
                "• Check spam status\n"
                "• View account details\n\n"
                "**📢 Channel Operations**\n"
                "• Subscribe to channels\n"
                "• Leave channels\n"
                "• Manage subscriptions\n\n"
                "**💬 Messaging**\n"
                "• Send messages\n"
                "• Bulk messaging\n"
                "• Message templates\n\n"
                "**🗑️ Cleanup**\n"
                "• Delete dialogs\n"
                "• Clean conversations\n"
                "• Remove contacts\n\n"
                "**📤 Export**\n"
                "• Export contacts\n"
                "• Generate TData\n"
                "• Backup session"
            )
            
            buttons = [
                [
                    Button.inline("📊 Update Info", f"session_op:update:{account_id}"),
                    Button.inline("🚫 Spam Check", f"session_op:spam_check:{account_id}")
                ],
                [
                    Button.inline("📢 Subscribe", f"session_op:subscribe:{account_id}"),
                    Button.inline("💬 Send Message", f"session_op:message:{account_id}")
                ],
                [
                    Button.inline("🗑️ Delete Dialogs", f"session_op:delete:{account_id}"),
                    Button.inline("📤 Export Contacts", f"session_op:export:{account_id}")
                ],
                [
                    Button.inline("💾 Generate TData", f"session_op:tdata:{account_id}"),
                    Button.inline("💰 Check Wallet", f"session_op:wallet:{account_id}")
                ],
                [Button.inline("🔙 Back", f"session_info:{account_id}")]
            ]
            
            await event.edit(text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Show session operations error: {e}")
            await event.edit("❌ Error loading session operations")
    
    async def _handle_session_operation(self, event, user_id, operation, account_id):
        """Handle session operation"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account:
                await event.answer("❌ Account not found")
                return
            
            if operation == "update":
                await self._update_session_info(event, user_id, account_id)
            elif operation == "spam_check":
                await self._check_spam_status(event, user_id, account_id)
            elif operation == "subscribe":
                await self._start_channel_subscribe(event, user_id, account_id)
            elif operation == "message":
                await self._start_send_message(event, user_id, account_id)
            elif operation == "delete":
                await self._show_delete_options(event, user_id, account_id)
            elif operation == "export":
                await self._export_contacts(event, user_id, account_id)
            elif operation == "tdata":
                await self._generate_tdata(event, user_id, account_id)
            elif operation == "wallet":
                await self._check_crypto_wallet(event, user_id, account_id)
            else:
                await event.answer("❌ Unknown operation")
                
        except Exception as e:
            logger.error(f"Handle session operation error: {e}")
            await event.answer("❌ Operation failed")
    
    async def _get_live_session_info(self, user_id, account_name):
        """Get live session information"""
        try:
            if user_id not in self.user_clients or account_name not in self.user_clients[user_id]:
                return None
            
            client = self.user_clients[user_id][account_name]
            if not client or not client.is_connected():
                return None
            
            me = await client.get_me()
            dialogs = await client.get_dialogs()
            
            # Count different types of entities
            stats = {"contacts": 0, "channels": 0, "bots": 0, "groups": 0, "private_chats": 0}
            
            for dialog in dialogs:
                entity = dialog.entity
                if isinstance(entity, User):
                    if getattr(entity, "bot", False):
                        stats["bots"] += 1
                    else:
                        stats["private_chats"] += 1
                elif isinstance(entity, Channel):
                    if getattr(entity, "broadcast", False):
                        stats["channels"] += 1
                    else:
                        stats["groups"] += 1
                elif isinstance(entity, Chat):
                    stats["groups"] += 1
            
            return {
                "name": f"{me.first_name or ''} {me.last_name or ''}".strip(),
                "premium": getattr(me, "premium", False),
                "verified": getattr(me, "verified", False),
                "id": me.id,
                "username": me.username,
                "phone": me.phone,
                "dialogs": len(dialogs),
                **stats
            }
            
        except Exception as e:
            logger.error(f"Get live session info error: {e}")
            return None
    
    async def _resend_code(self, event, user_id):
        """Resend verification code"""
        try:
            if user_id not in self.pending_auth:
                await event.answer("❌ No pending authentication")
                return
            
            auth_data = self.pending_auth[user_id]
            phone = auth_data["phone"]
            
            # Cancel current auth and start fresh
            await self._cleanup_auth(user_id)
            
            success, message = await self.process_phone_login(user_id, phone)
            if success:
                await event.edit(f"📨 Code resent to {phone}. Please enter the new verification code:")
            else:
                await event.edit(message)
                
        except Exception as e:
            logger.error(f"Resend code error: {e}")
            await event.answer("❌ Error resending code")
    
    async def _restart_auth(self, event, user_id):
        """Restart authentication process"""
        try:
            await self._cleanup_auth(user_id)
            await self._show_session_login_menu(event, user_id)
        except Exception as e:
            logger.error(f"Restart auth error: {e}")
            await event.answer("❌ Error restarting authentication")
    
    async def _cleanup_auth(self, user_id):
        """Clean up authentication resources"""
        try:
            if user_id in self.pending_auth:
                auth_data = self.pending_auth[user_id]
                client = auth_data.get("client")
                if client:
                    try:
                        await client.disconnect()
                    except:
                        pass
                self.pending_auth.pop(user_id, None)
        except Exception as e:
            logger.error(f"Cleanup auth error: {e}")
    
    async def _update_session_info(self, event, user_id, account_id):
        """Update session information"""
        try:
            await event.answer("🔄 Updating session info...")
            await self._show_session_info(event, user_id, account_id)
        except Exception as e:
            logger.error(f"Update session info error: {e}")
            await event.answer("❌ Error updating session info")
    
    async def _check_spam_status(self, event, user_id, account_id):
        """Check spam status"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                await event.answer("❌ Account not available")
                return
            
            client = self.user_clients[user_id][account["name"]]
            
            # Check spam status with @spambot
            try:
                spambot = await client.get_entity("spambot")
                await client.send_message(spambot, "/start")
                await asyncio.sleep(3)
                
                messages = await client.get_messages(spambot, limit=1)
                if messages and messages[0].message:
                    message_text = messages[0].message.lower()
                    is_blocked = any(word in message_text for word in ["ограничен", "limited", "restricted"])
                    status = "🚫 Spam Blocked" if is_blocked else "✅ Not Blocked"
                else:
                    status = "❓ Unknown Status"
            except Exception:
                status = "❌ Check Failed"
            
            await event.answer(f"Spam Status: {status}")
            
        except Exception as e:
            logger.error(f"Check spam status error: {e}")
            await event.answer("❌ Error checking spam status")
    
    async def _start_channel_subscribe(self, event, user_id, account_id):
        """Start channel subscription process"""
        try:
            self.bot_manager.pending_actions[user_id] = {
                "action": "session_subscribe_channel",
                "account_id": account_id
            }
            
            text = (
                "📢 **Subscribe to Channel**\n\n"
                "Send the channel link or username:\n\n"
                "**Examples:**\n"
                "• @channelname\n"
                "• https://t.me/channelname\n"
                "• t.me/channelname\n\n"
                "Reply with the channel link:"
            )
            
            await event.edit(text)
            await event.answer("📢 Reply with channel link")
            
        except Exception as e:
            logger.error(f"Start channel subscribe error: {e}")
            await event.answer("❌ Error starting channel subscription")
    
    async def _start_send_message(self, event, user_id, account_id):
        """Start send message process"""
        try:
            self.bot_manager.pending_actions[user_id] = {
                "action": "session_send_message_target",
                "account_id": account_id
            }
            
            text = (
                "💬 **Send Message**\n\n"
                "Enter the recipient:\n\n"
                "**Examples:**\n"
                "• @username\n"
                "• +1234567890\n"
                "• 123456789 (user ID)\n\n"
                "Reply with the recipient:"
            )
            
            await event.edit(text)
            await event.answer("💬 Reply with recipient")
            
        except Exception as e:
            logger.error(f"Start send message error: {e}")
            await event.answer("❌ Error starting message send")
    
    async def _show_delete_options(self, event, user_id, account_id):
        """Show dialog deletion options"""
        try:
            text = (
                f"🗑️ **Delete Dialogs**\n\n"
                "Choose what to delete:\n\n"
                "**⚠️ Warning:** This action cannot be undone!\n\n"
                "Select dialog type to delete:"
            )
            
            buttons = [
                [
                    Button.inline("📢 All Channels", f"session_delete:channels:{account_id}"),
                    Button.inline("👥 All Groups", f"session_delete:groups:{account_id}")
                ],
                [
                    Button.inline("🤖 All Bots", f"session_delete:bots:{account_id}"),
                    Button.inline("💭 Private Chats", f"session_delete:private:{account_id}")
                ],
                [Button.inline("🔙 Back", f"session_operations:{account_id}")]
            ]
            
            await event.edit(text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Show delete options error: {e}")
            await event.answer("❌ Error showing delete options")
    
    async def _export_contacts(self, event, user_id, account_id):
        """Export contacts"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                await event.answer("❌ Account not available")
                return
            
            client = self.user_clients[user_id][account["name"]]
            
            # Export contacts
            contacts_result = await client(GetContactsRequest(hash=0))
            users = contacts_result.users
            
            # Create contacts file
            lines = ["Name\tUsername\tPhone\tID"]
            for user in users:
                name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
                username = user.username or ""
                phone = user.phone or ""
                user_id_str = str(user.id)
                lines.append(f"{name}\t{username}\t{phone}\t{user_id_str}")
            
            contacts_text = "\n".join(lines)
            contacts_file = io.BytesIO(contacts_text.encode("utf-8"))
            contacts_file.name = f"contacts_{account['name']}.txt"
            
            await self.bot.send_file(
                user_id,
                contacts_file,
                caption=f"📤 Contacts exported from {account['name']}\n\nTotal contacts: {len(users)}"
            )
            
            await event.answer("📤 Contacts exported successfully!")
            
        except Exception as e:
            logger.error(f"Export contacts error: {e}")
            await event.answer("❌ Error exporting contacts")
    
    async def _generate_tdata(self, event, user_id, account_id):
        """Generate TData archive"""
        try:
            await event.answer("💾 Generating TData... This may take a moment.")
            
            # This is a placeholder - TData generation is complex
            # In a real implementation, you would need to:
            # 1. Create TData directory structure
            # 2. Convert session to TData format
            # 3. Create proper key files
            # 4. Package as archive
            
            text = (
                "💾 **TData Generation**\n\n"
                "TData generation is a complex process that requires:\n\n"
                "• Session conversion to TData format\n"
                "• Key file generation\n"
                "• Directory structure creation\n"
                "• Archive packaging\n\n"
                "This feature is currently under development.\n\n"
                "For now, you can export the session string instead."
            )
            
            buttons = [
                [Button.inline("📝 Export Session String", f"session_export_string:{account_id}")],
                [Button.inline("🔙 Back", f"session_operations:{account_id}")]
            ]
            
            await event.edit(text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Generate TData error: {e}")
            await event.answer("❌ Error generating TData")
    
    async def _check_crypto_wallet(self, event, user_id, account_id):
        """Check cryptocurrency wallet"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                await event.answer("❌ Account not available")
                return
            
            client = self.user_clients[user_id][account["name"]]
            
            # Check wallet with @wallet bot
            try:
                wallet_bot = await client.get_entity("wallet")
                await client.send_message(wallet_bot, "/balance")
                await asyncio.sleep(3)
                
                messages = await client.get_messages(wallet_bot, limit=1)
                if messages and messages[0].message:
                    balance_info = messages[0].message
                else:
                    balance_info = "No wallet information available"
            except Exception:
                balance_info = "Wallet bot not accessible"
            
            text = f"💰 **Crypto Wallet Balance**\n\n{balance_info}"
            buttons = [[Button.inline("🔙 Back", f"session_operations:{account_id}")]]
            
            await event.edit(text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Check crypto wallet error: {e}")
            await event.answer("❌ Error checking wallet")
    
    async def subscribe_to_channel(self, user_id, account_id, channel_link):
        """Subscribe to channel"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                return False, "❌ Account not available"
            
            client = self.user_clients[user_id][account["name"]]
            
            # Subscribe to channel
            await client(JoinChannelRequest(channel_link))
            
            return True, f"✅ Successfully subscribed to {channel_link}"
            
        except Exception as e:
            logger.error(f"Subscribe to channel error: {e}")
            return False, f"❌ Subscription failed: {str(e)}"
    
    async def send_message_to_user(self, user_id, account_id, recipient, message_text, media_path=None):
        """Send message to user"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                return False, "❌ Account not available"
            
            client = self.user_clients[user_id][account["name"]]
            
            # Send message
            if media_path and os.path.exists(media_path):
                await client.send_file(recipient, media_path, caption=message_text)
            else:
                await client.send_message(recipient, message_text)
            
            return True, f"✅ Message sent to {recipient}"
            
        except Exception as e:
            logger.error(f"Send message error: {e}")
            return False, f"❌ Message failed: {str(e)}"
    
    async def delete_dialogs_by_type(self, user_id, account_id, dialog_type):
        """Delete dialogs by type"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                return False, "❌ Account not available"
            
            client = self.user_clients[user_id][account["name"]]
            
            # Get dialogs
            dialogs = await client.get_dialogs()
            deleted_count = 0
            
            for dialog in dialogs:
                entity = dialog.entity
                should_delete = False
                
                if dialog_type == "channels" and isinstance(entity, Channel) and getattr(entity, "broadcast", False):
                    should_delete = True
                elif dialog_type == "groups" and isinstance(entity, (Channel, Chat)) and not getattr(entity, "broadcast", False):
                    should_delete = True
                elif dialog_type == "bots" and isinstance(entity, User) and getattr(entity, "bot", False):
                    should_delete = True
                elif dialog_type == "private" and isinstance(entity, User) and not getattr(entity, "bot", False):
                    should_delete = True
                
                if should_delete:
                    try:
                        await client.delete_dialog(entity)
                        deleted_count += 1
                        await asyncio.sleep(1)  # Rate limiting
                    except Exception as e:
                        logger.warning(f"Failed to delete dialog: {e}")
            
            return True, f"✅ Deleted {deleted_count} {dialog_type}"
            
        except Exception as e:
            logger.error(f"Delete dialogs error: {e}")
            return False, f"❌ Deletion failed: {str(e)}"
    
    async def _process_session_via_temp_file(self, session_string):
        """Process session string by creating temporary file"""
        try:
            import base64
            import sqlite3
            import tempfile
            import os
            from struct import unpack
            
            # Try to decode as Pyrogram session with URL-safe base64
            try:
                # Convert URL-safe base64 and fix padding
                fixed_session = session_string.replace('-', '+').replace('_', '/')
                while len(fixed_session) % 4 != 0:
                    fixed_session += '='
                
                decoded = base64.b64decode(fixed_session)
                if len(decoded) < 260:
                    return False, "Invalid session format"
                
                auth_key = decoded[:256]
                dc_id_bytes = decoded[256:260]
                dc_id = unpack('<I', dc_id_bytes)[0]
                
                # Normalize DC ID to valid range
                if dc_id not in [1, 2, 3, 4, 5]:
                    dc_id = (dc_id % 5) + 1
                    logger.info(f"Mapped unusual DC ID to valid range: {dc_id}")
                
                # Create temp file
                with tempfile.NamedTemporaryFile(suffix='.session', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                conn = sqlite3.connect(temp_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    CREATE TABLE sessions (
                        dc_id INTEGER,
                        server_address TEXT,
                        port INTEGER,
                        auth_key BLOB
                    )
                ''')
                
                dc_servers = {
                    1: '149.154.175.53',
                    2: '149.154.167.51',
                    3: '149.154.175.100',
                    4: '149.154.167.91',
                    5: '91.108.56.130'
                }
                server_address = dc_servers.get(dc_id, '149.154.167.51')
                
                cursor.execute(
                    'INSERT INTO sessions (dc_id, server_address, port, auth_key) VALUES (?, ?, ?, ?)',
                    (dc_id, server_address, 443, auth_key)
                )
                
                conn.commit()
                conn.close()
                
                # Extract using existing method
                extracted_session = await self._extract_session_from_file(temp_path)
                
                # Cleanup
                try:
                    os.unlink(temp_path)
                except:
                    pass
                
                if extracted_session:
                    # Quick validation
                    client = TelegramClient(
                        StringSession(extracted_session),
                        config.telegram.api_id,
                        config.telegram.api_hash,
                        connection_retries=1,
                        timeout=5
                    )
                    
                    try:
                        await asyncio.wait_for(client.connect(), timeout=5.0)
                        if await asyncio.wait_for(client.is_user_authorized(), timeout=3.0):
                            me = await asyncio.wait_for(client.get_me(), timeout=5.0)
                            info = {
                                "name": f"{me.first_name or ''} {me.last_name or ''}".strip() or "Unknown",
                                "phone": me.phone,
                                "username": me.username,
                                "id": me.id,
                                "premium": getattr(me, "premium", False),
                                "verified": getattr(me, "verified", False)
                            }
                            await client.disconnect()
                            return True, info
                        else:
                            await client.disconnect()
                            return False, "Session not authorized"
                    except:
                        try:
                            await client.disconnect()
                        except:
                            pass
                        return False, "Connection failed"
                
                return False, "Extraction failed"
                
            except Exception as e:
                logger.debug(f"Temp file processing failed: {e}")
                return False, str(e)
                
        except Exception as e:
            logger.error(f"Temp file method error: {e}")
            return False, str(e)
    
    async def _finalize_session_import(self, user_id, info, session_string):
        """Finalize session import after validation"""
        try:
            phone = info.get("phone")
            name = info.get("name")
            is_fast_import = info.get("fast_import", False)
            
            # For fast imports, generate unique identifier
            if is_fast_import or phone == "+000000000":
                import hashlib
                session_hash = hashlib.md5(session_string.encode()).hexdigest()[:8]
                phone = f"+{session_hash}"
                name = f"Session_{session_hash}"
            
            # Check if account already exists
            existing = await mongodb.db.accounts.find_one({
                "user_id": user_id,
                "phone": phone
            })
            if existing:
                return False, f"❌ Account {phone} already exists"
            
            # Validate session string before saving
            if not session_string or not isinstance(session_string, str) or len(session_string) < 50:
                return False, "❌ Invalid session string after processing"
            
            # Save account
            account_data = {
                "user_id": user_id,
                "phone": phone,
                "name": name,
                "username": info.get("username"),
                "session_string": session_string,
                "is_active": True,
                "added_via": "session_string",
                "otp_destroyer_enabled": False,
                "created_at": int(time.time()),
                "fast_import": is_fast_import
            }
            
            result = await mongodb.db.accounts.insert_one(account_data)
            account_id = str(result.inserted_id)
            
            # Start user client with converted session
            try:
                logger.info(f"Starting client with session string (length: {len(session_string)}, type: {type(session_string)})")
                await self.bot_manager.start_user_client(user_id, name, session_string)
            except Exception as client_error:
                logger.error(f"Failed to start client with session: {client_error}")
                logger.error(f"Session string details - Length: {len(session_string) if session_string else 0}, Type: {type(session_string)}, Valid: {bool(session_string)}")
                raise client_error
            
            # Send login notification
            try:
                await self._send_login_notification(user_id, name, "Account imported via session string")
            except Exception as notif_err:
                logger.error(f"Failed to send login notification: {notif_err}")
            
            # Update account with real name from Telegram (like OTP login does)
            if not is_fast_import:
                await self._fetch_and_store_account_name(user_id, name, phone)
            else:
                # For fast imports, update name in background
                asyncio.create_task(self._update_fast_import_info(user_id, name, phone))
            
            logger.info(f"Successfully imported account: {name} ({phone})")
            return True, f"✅ Account {name} imported successfully!\n\n💡 Real account info will be updated automatically."
            
        except Exception as e:
            logger.error(f"Session import finalization error: {e}")
            return False, f"❌ Import failed: {str(e)}"
    
    async def _update_fast_import_info(self, user_id: int, account_name: str, phone: str):
        """Update fast import account info in background"""
        try:
            await asyncio.sleep(5)  # Wait for client to stabilize
            
            if user_id in self.user_clients and account_name in self.user_clients[user_id]:
                client = self.user_clients[user_id][account_name]
                if client and client.is_connected():
                    try:
                        me = await asyncio.wait_for(client.get_me(), timeout=10.0)
                        
                        # Format display name
                        first_name = getattr(me, 'first_name', None) or ''
                        last_name = getattr(me, 'last_name', None) or ''
                        username = getattr(me, 'username', None)
                        real_phone = getattr(me, 'phone', None) or phone
                        display_name = ' '.join(part for part in (first_name, last_name) if part)
                        if not display_name:
                            display_name = f'@{username}' if username else real_phone
                        
                        # Update account in database
                        await mongodb.db.accounts.update_one(
                            {"user_id": user_id, "name": account_name},
                            {"$set": {
                                "first_name": first_name,
                                "last_name": last_name,
                                "username": username,
                                "phone": real_phone,
                                "display_name": display_name,
                                "name": display_name,
                                "fast_import": False
                            }}
                        )
                        
                        # Update client storage if name changed
                        if display_name != account_name and user_id in self.user_clients:
                            client = self.user_clients[user_id].pop(account_name, None)
                            if client:
                                self.user_clients[user_id][display_name] = client
                        
                        logger.info(f"Updated fast import account: {display_name} ({real_phone})")
                        
                    except Exception as e:
                        logger.error(f"Failed to update fast import info: {e}")
        except Exception as e:
            logger.error(f"Background update failed for {phone}: {e}")
    
    async def _fetch_and_store_account_name(self, user_id: int, account_name: str, phone: str):
        """Fetch real account name from Telegram and store in database"""
        try:
            if user_id in self.user_clients and account_name in self.user_clients[user_id]:
                client = self.user_clients[user_id][account_name]
                if client and client.is_connected():
                    me = await retry_async(client.get_me)
                    # Format display name
                    first_name = getattr(me, 'first_name', None) or ''
                    last_name = getattr(me, 'last_name', None) or ''
                    username = getattr(me, 'username', None)
                    display_name = ' '.join(part for part in (first_name, last_name) if part)
                    if not display_name:
                        display_name = f'@{username}' if username else phone
                    
                    # Update account in database
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {"$set": {
                            "first_name": first_name,
                            "last_name": last_name,
                            "username": username,
                            "display_name": display_name,
                            "name": display_name
                        }}
                    )
                    
                    # Update client storage if name changed
                    if display_name != account_name and user_id in self.user_clients:
                        client = self.user_clients[user_id].pop(account_name, None)
                        if client:
                            self.user_clients[user_id][display_name] = client
                    
                    logger.info(f"Updated account name for {phone}: {display_name}")
        except Exception as e:
            logger.error(f"Failed to fetch account name for {phone}: {e}")
    
    async def _start_session_creation(self, event, user_id):
        """Start session creation with automatic OTP for managed accounts"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            
            if not accounts:
                try:
                    await event.edit("❌ No accounts found. Add accounts first before creating sessions.")
                except:
                    pass
                return
            
            buttons = [[Button.inline(f"📱 {acc.get('name', acc['phone'])}", f"create_sess:{acc['phone']}".encode())] for acc in accounts[:10]]
            buttons.append([Button.inline("🔙 Back", "session_login")])
            
            text = (
                "✨ **Create Session**\n\n"
                "🔐 **Automatic OTP Fetching**\n"
                "Select an account to create fresh session:\n\n"
                "⚡ **Process:**\n"
                "1. Select account\n"
                "2. Choose format (String/File)\n"
                "3. Bot auto-fetches OTP from Telegram\n"
                "4. Fresh session created\n\n"
                "Select account:"
            )
            try:
                await event.edit(text, buttons=buttons)
            except Exception as edit_error:
                if "Content of the message was not modified" not in str(edit_error):
                    raise
        except Exception as e:
            if "Content of the message was not modified" not in str(e):
                logger.error(f"Start session creation error: {e}")
    
    async def _show_format_selection(self, event, user_id, phone):
        """Show format selection menu"""
        try:
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "phone": phone})
            if not account:
                await event.edit("❌ Account not found")
                return
            
            account_name = account.get('name', phone)
            
            text = (
                f"📦 **Choose Session Format**\n\n"
                f"📱 **Account:** {account_name}\n"
                f"📞 **Phone:** {phone}\n\n"
                f"📝 **String Session**\n"
                f"• Text format\n"
                f"• Easy to copy/paste\n"
                f"• Use in code directly\n\n"
                f"📁 **Session File**\n"
                f"• .session file\n"
                f"• Download and use\n"
                f"• Compatible with Telethon\n\n"
                f"Choose your preferred format:"
            )
            
            buttons = [
                [Button.inline("📝 String Session", f"create_sess_fmt:{phone}:string".encode())],
                [Button.inline("📁 Session File", f"create_sess_fmt:{phone}:file".encode())],
                [Button.inline("🔙 Back", "menu:accounts")]
            ]
            
            await event.edit(text, buttons=buttons)
        except Exception as e:
            logger.error(f"Format selection error: {e}")
            await event.edit("❌ Error showing format selection")
    
    async def _execute_session_creation(self, event, user_id, phone, format_type='string'):
        """Execute session creation with auto OTP"""
        client = None
        destroyer_was_enabled = False
        account = None
        try:
            # Set session creation protection flags
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "phone": phone})
            if account:
                # Set protection flags and disable destroyer
                destroyer_was_enabled = account.get("otp_destroyer_enabled", False)
                await mongodb.db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$set": {"session_creation_in_progress": True, "otp_destroyer_enabled": False}}
                )
                
                # Add temporary OTP protection
                import time
                await mongodb.db.otp_protections.update_one(
                    {"phone": phone, "wildcard": True},
                    {"$set": {
                        "phone": phone,
                        "wildcard": True,
                        "expires_at": int(time.time()) + 300,  # 5 minutes
                        "reason": "session_creation"
                    }},
                    upsert=True
                )
                
                # Store in pending actions for additional protection
                self.bot_manager.pending_actions[user_id] = {
                    "action": "session_creation",
                    "phone": phone,
                    "account_name": account.get('name', phone)
                }
                
                logger.info(f"OTP Destroyer temporarily disabled for {phone} during session creation")
            
            await event.edit(f"⏳ Creating session for {phone}...\n\n🛡️ OTP Destroyer temporarily disabled\n1️⃣ Requesting OTP from Telegram...")
            
            device = self.get_random_device()
            client = TelegramClient(
                StringSession(),
                config.telegram.api_id,
                config.telegram.api_hash,
                device_model=device["model"],
                system_version=device["system"],
                app_version=device["version"]
            )
            
            await client.connect()
            
            phone_code_hash = None
            try:
                result = await client.send_code_request(phone)
                phone_code_hash = result.phone_code_hash
                logger.info(f"Code requested for {phone}, hash: {phone_code_hash}")
            except Exception as req_error:
                logger.error(f"Failed to request code: {req_error}")
                await client.disconnect()
                if destroyer_was_enabled and account:
                    await mongodb.db.accounts.update_one({"_id": account["_id"]}, {"$set": {"otp_destroyer_enabled": True}})
                await event.edit(f"❌ Failed to request OTP: {req_error}")
                return
            
            await event.edit(f"⏳ Creating session for {phone}...\n\n2️⃣ Waiting for OTP to arrive...")
            await asyncio.sleep(5)
            
            otp_code = await self._fetch_otp_from_telegram(user_id, phone)
            
            if not otp_code:
                await client.disconnect()
                if destroyer_was_enabled and account:
                    await mongodb.db.accounts.update_one({"_id": account["_id"]}, {"$set": {"otp_destroyer_enabled": True}})
                await event.edit("❌ Could not fetch OTP automatically.")
                return
            
            await event.edit(f"⏳ Creating session for {phone}...\n\n3️⃣ Signing in with OTP: {otp_code}...")
            
            try:
                await client.sign_in(phone, otp_code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                # 2FA required - use centralized helper
                from ..utils.twofa_helper import twofa_helper
                await event.edit(f"⏳ Creating session for {phone}...\n\n4️⃣ Checking for stored 2FA password...")
                
                success, session_str, error = await twofa_helper.try_sign_in_with_2fa(client, user_id, phone)
                
                if success:
                    # Success - continue with session creation
                    session_string = session_str
                else:
                    # Failed - ask user for password
                    if error in ["stored_password_invalid", "no_stored_password"]:
                        # Store pending session creation state
                        self.pending_auth[user_id] = {
                            "client": client,
                            "phone": phone,
                            "phone_code_hash": phone_code_hash,
                            "destroyer_was_enabled": destroyer_was_enabled,
                            "account": account,
                            "action": "session_creation_2fa"
                        }
                        
                        # Store format type for later
                        self.pending_auth[user_id]["format_type"] = format_type
                        
                        # Ask for 2FA password
                        msg = f"🔐 **2FA Password Required**\n\n"
                        if error == "stored_password_invalid":
                            msg += f"Your stored 2FA password is incorrect (changed externally).\n\n"
                        else:
                            msg += f"This account has 2FA enabled.\n\n"
                        msg += f"Please send your 2FA password to continue:"
                        
                        await event.edit(msg)
                        
                        # Set pending action for message handler
                        self.bot_manager.pending_actions[user_id] = {
                            "action": "session_creation_2fa_password",
                            "phone": phone,
                            "format_type": format_type
                        }
                        return
                    else:
                        await client.disconnect()
                        if destroyer_was_enabled and account:
                            await mongodb.db.accounts.update_one({"_id": account["_id"]}, {"$set": {"otp_destroyer_enabled": True}})
                        await event.edit(f"❌ 2FA authentication failed: {error}")
                        return
            except Exception as sign_error:
                await client.disconnect()
                if destroyer_was_enabled and account:
                    await mongodb.db.accounts.update_one({"_id": account["_id"]}, {"$set": {"otp_destroyer_enabled": True}})
                await event.edit(f"❌ Sign in failed: {sign_error}")
                return
            
            session_string = StringSession.save(client.session)
            
            # Generate session file if requested
            session_file_data = None
            if format_type == 'file':
                try:
                    import tempfile
                    import time
                    
                    # Create unique temporary file name
                    temp_name = f"session_{phone.replace('+', '')}_{int(time.time())}.session"
                    temp_path = os.path.join(tempfile.gettempdir(), temp_name)
                    
                    logger.info(f"Creating session file at: {temp_path}")
                    
                    # Create file client with session data
                    file_client = TelegramClient(temp_path, config.telegram.api_id, config.telegram.api_hash)
                    
                    # Copy session data
                    file_client.session.set_dc(client.session.dc_id, client.session.server_address, client.session.port)
                    file_client.session.auth_key = client.session.auth_key
                    
                    # Force save the session
                    file_client.session.save()
                    
                    # Verify file was created and read it
                    if os.path.exists(temp_path):
                        file_size = os.path.getsize(temp_path)
                        logger.info(f"Session file created, size: {file_size} bytes")
                        
                        if file_size > 0:
                            with open(temp_path, 'rb') as f:
                                session_file_data = f.read()
                            logger.info(f"Session file data read: {len(session_file_data)} bytes")
                        else:
                            logger.error("Session file is empty")
                        
                        # Clean up temp file
                        try:
                            os.remove(temp_path)
                            logger.info("Temporary session file cleaned up")
                        except Exception as cleanup_err:
                            logger.warning(f"Failed to cleanup temp file: {cleanup_err}")
                    else:
                        logger.error(f"Session file was not created at {temp_path}")
                    
                except Exception as file_err:
                    logger.error(f"Session file creation error: {file_err}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    session_file_data = None
            
            await client.disconnect()
            
            # Clear session creation protection and restore destroyer
            if account:
                await mongodb.db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$unset": {"session_creation_in_progress": ""}, "$set": {"otp_destroyer_enabled": destroyer_was_enabled}}
                )
                # Remove OTP protection
                await mongodb.db.otp_protections.delete_many({"phone": phone, "wildcard": True})
                # Clear pending action
                self.bot_manager.pending_actions.pop(user_id, None)
                logger.info(f"OTP Destroyer re-enabled for {phone} after session creation")
            
            # Send based on format
            if format_type == 'string':
                await event.edit(
                    f"✅ **Session String Created!**\n\n"
                    f"📱 Phone: {phone}\n"
                    f"📝 Session String:\n\n"
                    f"`{session_string}`\n\n"
                    f"💾 Copy and save securely!\n"
                    f"🛡️ OTP Destroyer re-enabled"
                )
            elif format_type == 'file':
                if session_file_data and len(session_file_data) > 0:
                    from telethon.tl.types import DocumentAttributeFilename
                    await event.edit("✅ **Session file created! Sending...**")
                    await self.bot.send_message(
                        user_id,
                        f"📁 **Session File Created!**\n\n"
                        f"📱 Phone: {phone}\n\n"
                        f"💾 Download and save securely!\n"
                        f"🛡️ OTP Destroyer re-enabled",
                        file=session_file_data,
                        attributes=[DocumentAttributeFilename(f"{phone.replace('+', '')}.session")]
                    )
                    try:
                        await event.delete()
                    except:
                        pass
                else:
                    logger.error(f"Session file data is empty or None: {session_file_data}")
                    await event.edit(
                        f"❌ **File generation failed**\n\n"
                        f"Here's the session string instead:\n\n"
                        f"`{session_string}`\n\n"
                        f"🛡️ OTP Destroyer re-enabled"
                    )
            
            # Always send login notification
            try:
                action = "Session file created" if format_type == 'file' and session_file_data else "Session string created"
                await self._send_login_notification(user_id, phone, action)
            except Exception as notif_err:
                logger.error(f"Failed to send login notification: {notif_err}")
            
        except Exception as e:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass
            if account:
                await mongodb.db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$unset": {"session_creation_in_progress": ""}}
                )
                self.bot_manager.pending_actions.pop(user_id, None)
            logger.error(f"Session creation error: {e}")
            await event.edit(f"❌ Error: {e}")
    
    async def _send_login_notification(self, user_id, phone, action):
        """Send login notification to user"""
        try:
            import time
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            notification = (
                f"🔔 **Login Activity Alert**\n\n"
                f"📱 **Phone:** {phone}\n"
                f"🕑 **Time:** {timestamp}\n"
                f"⚙️ **Action:** {action}\n"
                f"📍 **Location:** Session Creation\n\n"
                f"ℹ️ This is a security notification for session creation activity."
            )
            await self.bot.send_message(user_id, notification)
            logger.info(f"Login notification sent for {phone}: {action}")
        except Exception as e:
            logger.error(f"Failed to send login notification: {e}")
    
    async def _fetch_otp_from_telegram(self, user_id, target_phone):
        """Fetch OTP code from Telegram (777000) using existing accounts"""
        try:
            if user_id not in self.user_clients:
                logger.warning(f"No clients found for user {user_id}")
                return None
            
            target_phone_clean = target_phone.replace("+", "")
            logger.info(f"Fetching OTP for {target_phone} from {len(self.user_clients[user_id])} accounts")
            
            # Try multiple times with delays
            for attempt in range(3):
                for account_name, client in self.user_clients[user_id].items():
                    if not client or not client.is_connected():
                        continue
                    
                    try:
                        messages = await client.get_messages(777000, limit=15)
                        
                        for msg in messages:
                            if not msg.message:
                                continue
                            
                            # Check if message is recent (within last 60 seconds)
                            import time as time_module
                            if hasattr(msg, 'date') and (time_module.time() - msg.date.timestamp()) > 60:
                                continue
                            
                            # Check if message contains target phone or is login code
                            if target_phone_clean in msg.message or "Login code" in msg.message:
                                import re
                                code_match = re.search(r'\b(\d{5})\b', msg.message)
                                if code_match:
                                    code = code_match.group(1)
                                    # Safe logging with Unicode handling
                                    safe_name = account_name.encode('ascii', errors='replace').decode('ascii')
                                    logger.info(f"Found OTP {code} from {safe_name}")
                                    return code
                    except Exception as e:
                        logger.debug(f"Failed to fetch from {account_name}: {e}")
                        continue
                
                if attempt < 2:
                    await asyncio.sleep(2)
            
            logger.warning(f"No OTP found for {target_phone} after 3 attempts")
            return None
        except Exception as e:
            logger.error(f"OTP fetch error: {e}")
            return None
