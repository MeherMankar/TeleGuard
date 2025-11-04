"""Split from login_via_session.py - login_core"""
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
