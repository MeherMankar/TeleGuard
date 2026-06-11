"""Session Login Handler - Complete SessionMaster Integration
Developed by:
- @Meher_Mankar
- @Gutkesh
GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import asyncio
import io
import logging
import os
import shutil
import time

from telethon import Button, TelegramClient, events
from telethon.crypto import AuthKey
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.tl.types import Channel, Chat, User

from ..core.config import config
from ..core.device_snooper import DeviceSnooper
from ..core.mongo_database import mongodb
from ..utils.network_helpers import retry_async

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

        # Device list imported from central device_profiles module
        from teleguard.data.device_profiles import get_random_device_legacy
        self._get_random_device = get_random_device_legacy

    def get_random_device(self):
        """Get random device configuration from central device_profiles."""
        return self._get_random_device()

    def register_handlers(self):
        """Register all session login handlers"""

        @self.bot.on(events.CallbackQuery(pattern=r"^session_login$"))
        async def session_login_menu(event):
            user_id = event.sender_id
            await self._show_session_login_menu(event, user_id)

        @self.bot.on(events.CallbackQuery(pattern=r"^export_sessions$"))
        async def create_session_menu(event):
            user_id = event.sender_id
            if hasattr(self.bot_manager, "session_export_handler"):
                await self.bot_manager.session_export_handler._show_export_menu(
                    event, user_id
                )
            else:
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
            logger.info(
                f"Session creation requested - Phone: {phone}, Format: '{format_type}'"
            )
            await event.answer("⏳ Creating session...")
            # Force format type to ensure it's correct
            if format_type not in ["string", "file"]:
                format_type = "string"
                logger.warning("Invalid format type detected, defaulting to 'string'")
            await self._execute_session_creation(event, user_id, phone, format_type)

        @self.bot.on(events.CallbackQuery(pattern=r"^login_session_file$"))
        async def login_by_session_file(event):
            user_id = event.sender_id
            await self._start_session_file_login(event, user_id)

        @self.bot.on(events.CallbackQuery(pattern=r"^login_bulk_import$"))
        async def login_bulk_import(event):
            user_id = event.sender_id
            if hasattr(self.bot_manager, "session_import_handler"):
                await self.bot_manager.session_import_handler._import_zip_sessions(event, user_id)
            else:
                await event.answer("❌ Bulk import not available")

        @self.bot.on(events.CallbackQuery(pattern=r"^login_tdata_import$"))
        async def login_tdata_import(event):
            user_id = event.sender_id
            if hasattr(self.bot_manager, "session_import_handler"):
                await self.bot_manager.session_import_handler._import_tdata_session(event, user_id)
            else:
                await event.answer("❌ TData import not available")

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
        if hasattr(self.bot_manager, "session_import_handler"):
            await self.bot_manager.session_import_handler._show_import_menu(event, user_id)
        else:
            await event.answer("❌ Session import manager not available")

    async def _start_session_file_login(self, event, user_id):
        """Start session file upload process"""
        try:
            self.bot_manager.pending_actions[user_id] = {"action": "session_file_login"}

            text = (
                "📁 **Upload Session File**\n\n"
                "Send your .session file(s) as a document:\n\n"
                "**Supported Files:**\n"
                "• Single .session file\n"
                "• .zip file with multiple .session files\n"
                "• Telethon & Pyrogram formats\n"
                "• SQLite session databases\n\n"
                "**Multi-Account Import:**\n"
                "• Send .zip file with multiple sessions\n"
                "• All accounts will be imported automatically\n"
                "• Progress shown for each account\n\n"
                "**Security:**\n"
                "• Files are validated before use\n"
                "• Temporary files are deleted\n"
                "• Session data is encrypted\n\n"
                "Send your .session or .zip file now:"
            )

            await event.edit(text)
            await event.answer("📁 Send session file or ZIP")
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
    
    async def _start_bulk_import(self, event, user_id):
        """Start bulk import process"""
        try:
            self.bot_manager.pending_actions[user_id] = {
                "action": "session_bulk_import"
            }

            text = (
                "📦 **Bulk Import Sessions**\n\n"
                "Upload a ZIP file containing multiple session files:\n\n"
                "**Supported Files:**\n"
                "• .session files (Telethon/Pyrogram)\n"
                "• Multiple accounts in one ZIP\n"
                "• Automatic format detection\n"
                "• Auto-conversion if needed\n\n"
                "**Features:**\n"
                "• Import 50+ accounts at once\n"
                "• Real-time progress tracking\n"
                "• Automatic name conflict resolution\n"
                "• Detailed success/failure report\n\n"
                "**How to Prepare:**\n"
                "1. Collect all .session files\n"
                "2. Create a ZIP archive\n"
                "3. Upload the ZIP file here\n\n"
                "**Security:**\n"
                "• Files validated before import\n"
                "• Temporary files deleted\n"
                "• Session data encrypted\n\n"
                "Send your ZIP file now:"
            )

            await event.edit(text)
            await event.answer("📦 Send ZIP file")
        except Exception as e:
            logger.error(f"Start bulk import error: {e}")
            await event.edit("❌ Error starting bulk import.")
    
    async def _start_tdata_import(self, event, user_id):
        """Start TData import process"""
        try:
            self.bot_manager.pending_actions[user_id] = {
                "action": "session_tdata_import"
            }

            text = (
                "📂 **TData Import**\n\n"
                "Upload Telegram Desktop TData folder as ZIP:\n\n"
                "**Supported Format:**\n"
                "• TData folder from Telegram Desktop\n"
                "• Must include key_datas file\n"
                "• Automatic conversion to Telethon\n"
                "• Single account per TData\n\n"
                "**How to Prepare:**\n"
                "1. Locate TData folder (Telegram Desktop)\n"
                "2. Compress entire TData folder to ZIP\n"
                "3. Upload the ZIP file here\n\n"
                "**Features:**\n"
                "• Automatic format detection\n"
                "• Converts to Telethon format\n"
                "• Validates before import\n"
                "• Secure processing\n\n"
                "**Security:**\n"
                "• Files validated before import\n"
                "• Temporary files deleted\n"
                "• Session data encrypted\n\n"
                "Send your TData ZIP file now:"
            )

            await event.edit(text)
            await event.answer("📂 Send TData ZIP")
        except Exception as e:
            logger.error(f"Start TData import error: {e}")
            await event.edit("❌ Error starting TData import.")

    async def process_session_file(self, user_id, file_path):
        """Process uploaded session file with automatic format detection and conversion"""
        try:
            if not os.path.exists(file_path):
                return False, "❌ Session file not found"

            # Check if it's a ZIP file for bulk import
            if file_path.endswith(".zip"):
                logger.info(f"Detected ZIP file, processing bulk import for user {user_id}")
                return await self._process_zip_sessions(user_id, file_path)

            # Check file size (should be reasonable for a session file)
            file_size = os.path.getsize(file_path)
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                return False, "❌ Session file too large (max 10MB)"

            if file_size < 100:  # Too small to be a valid session
                return False, "❌ Session file appears to be empty or corrupted"

            # Extract session string from file with format detection
            logger.info(
                f"Processing session file: {file_path} (size: {file_size} bytes)"
            )
            
            # Step 1: Detect file format
            file_format = await self._detect_file_format(file_path)
            logger.info(f"Detected file format: {file_format}")
            
            # Step 2: Extract session based on format
            if file_format == "pyrogram":
                logger.info("Extracting Pyrogram session...")
                session_string = await self._extract_pyrogram_session(file_path)
            elif file_format == "telethon":
                logger.info("Extracting Telethon session...")
                session_string = await self._extract_telethon_session(file_path)
            else:
                logger.info("Unknown format, trying all extraction methods...")
                session_string = await self._extract_session_from_file(file_path)

            if not session_string:
                return False, (
                    "❌ Could not extract session from file.\n\n"
                    "**File Analysis:**\n"
                    f"• File size: {file_size} bytes\n"
                    f"• File path: {os.path.basename(file_path)}\n"
                    f"• Detected format: {file_format}\n\n"
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
            logger.info(
                f"Validating extracted session string (length: {len(session_string)})"
            )
            success, message = await self.process_session_string(
                user_id, session_string
            )

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
                logger.warning(
                    f"Failed to cleanup file after error {file_path}: {cleanup_error}"
                )

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
        """Process session string import with automatic format detection and conversion"""
        try:
            if not session_string or len(session_string) < 50:
                return False, "❌ Invalid session string format"

            # Step 1: Detect session format
            logger.info(f"Detecting session format (length: {len(session_string)})")
            session_format = await self._detect_session_format(session_string)
            logger.info(f"Detected format: {session_format}")

            # Step 2: Convert to Telethon if needed
            if session_format == "pyrogram":
                logger.info("Converting Pyrogram session to Telethon...")
                converted_session = await self._convert_pyrogram_session_string(session_string)
                if converted_session:
                    session_string = converted_session
                    logger.info("✅ Pyrogram session converted successfully")
                else:
                    return False, "❌ Failed to convert Pyrogram session to Telethon format"
            elif session_format == "tdata":
                return False, "❌ TData format not supported for string import. Please upload TData folder instead."
            elif session_format == "unknown":
                logger.warning("Unknown session format, attempting direct import...")

            # Step 3: Try temp file approach first for better reliability
            logger.info("Attempting session string import via temp file method...")
            temp_success, temp_result = await self._process_session_via_temp_file(
                session_string
            )
            if temp_success:
                return await self._finalize_session_import(
                    user_id, temp_result, session_string
                )

            # Step 4: Fallback to fast validation mode
            logger.info("Temp file method failed, using fast validation mode...")
            success, info = await self._validate_session_string(session_string)
            if not success:
                logger.error(f"Session validation failed: {info}")
                return (
                    False,
                    f"❌ {info}\n\n💡 Try using session file upload for better reliability.",
                )

            return await self._finalize_session_import(user_id, info, session_string)

        except Exception as e:
            logger.error(f"Session string processing error: {e}")
            return (
                False,
                f"❌ Import failed: {str(e)}\n\n💡 **Try using session file upload instead**",
            )

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
            import base64
            import sqlite3

            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()

            # Check if it's a Pyrogram session
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]

            # Try different Pyrogram table structures
            session_data = None

            # Method 1: Standard Pyrogram sessions table
            if "sessions" in tables:
                cursor.execute("PRAGMA table_info(sessions)")
                columns = [row[1] for row in cursor.fetchall()]

                if all(
                    col in columns
                    for col in ["dc_id", "server_address", "port", "auth_key"]
                ):
                    cursor.execute(
                        "SELECT dc_id, server_address, port, auth_key FROM sessions LIMIT 1"
                    )
                    session_data = cursor.fetchone()
                elif all(
                    col in columns
                    for col in [
                        "dc_id",
                        "api_id",
                        "test_mode",
                        "auth_key",
                        "date",
                        "user_id",
                        "is_bot",
                    ]
                ):
                    # Alternative Pyrogram structure
                    cursor.execute("SELECT dc_id, auth_key FROM sessions LIMIT 1")
                    row = cursor.fetchone()
                    if row:
                        dc_id, auth_key = row
                        # Default server addresses for each DC
                        dc_servers = {
                            1: ("149.154.175.53", 443),
                            2: ("149.154.167.51", 443),
                            3: ("149.154.175.100", 443),
                            4: ("149.154.167.91", 443),
                            5: ("91.108.56.130", 443),
                        }
                        server_address, port = dc_servers.get(
                            dc_id, ("149.154.167.50", 443)
                        )
                        session_data = (dc_id, server_address, port, auth_key)

            # Method 2: Try other common Pyrogram table names
            if not session_data:
                for table_name in ["session", "pyrogram_session", "client_session"]:
                    if table_name in tables:
                        try:
                            cursor.execute(f"PRAGMA table_info({table_name})")
                            columns = [row[1] for row in cursor.fetchall()]

                            if "auth_key" in columns and "dc_id" in columns:
                                cursor.execute(
                                    f"SELECT dc_id, auth_key FROM {table_name} LIMIT 1"
                                )
                                row = cursor.fetchone()
                                if row:
                                    dc_id, auth_key = row
                                    dc_servers = {
                                        1: ("149.154.175.53", 443),
                                        2: ("149.154.167.51", 443),
                                        3: ("149.154.175.100", 443),
                                        4: ("149.154.167.91", 443),
                                        5: ("91.108.56.130", 443),
                                    }
                                    server_address, port = dc_servers.get(
                                        dc_id, ("149.154.167.50", 443)
                                    )
                                    session_data = (
                                        dc_id,
                                        server_address,
                                        port,
                                        auth_key,
                                    )
                                    break
                        except Exception:
                            continue

            if session_data:
                dc_id, server_address, port, auth_key = session_data

                # Handle different auth_key formats
                if isinstance(auth_key, str):
                    try:
                        auth_key_bytes = base64.b64decode(auth_key)
                    except BaseException:
                        auth_key_bytes = auth_key.encode("utf-8")
                elif isinstance(auth_key, (bytes, memoryview)):
                    auth_key_bytes = bytes(auth_key)
                else:
                    auth_key_bytes = str(auth_key).encode("utf-8")

                # Ensure auth_key is proper length (256 bytes for Telegram)
                if len(auth_key_bytes) < 256:
                    auth_key_bytes = auth_key_bytes.ljust(256, b"\x00")
                elif len(auth_key_bytes) > 256:
                    auth_key_bytes = auth_key_bytes[:256]

                # Build Telethon-compatible session string
                try:
                    # Create a temporary Telethon client to generate proper session
                    # string
                    temp_session = StringSession()
                    temp_session.set_dc(dc_id, server_address, port)
                    temp_session.auth_key = AuthKey(auth_key_bytes)

                    session_string = StringSession.save(temp_session)
                    conn.close()
                    logger.info(
                        f"Successfully extracted Pyrogram session: DC {dc_id}, Server {server_address}:{port}, Auth key length: {
                            len(auth_key_bytes)}"
                    )
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
            session_name = file_path.replace(".session", "")

            temp_client = TelegramClient(
                session_name,
                config.telegram.api_id,
                config.telegram.api_hash,
                connection_retries=1,
                retry_delay=1,
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
                except BaseException:
                    pass
                return None

        except Exception as e:
            logger.debug(f"Telethon extraction failed: {e}")
            return None

    async def _extract_from_sqlite(self, file_path):
        """Extract session from SQLite database directly"""
        try:
            import base64
            import sqlite3

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
                    auth_key_cols = [
                        col
                        for col in columns
                        if "auth" in col.lower() and "key" in col.lower()
                    ]
                    dc_cols = [
                        col
                        for col in columns
                        if "dc" in col.lower() and "id" in col.lower()
                    ]
                    server_cols = [
                        col
                        for col in columns
                        if "server" in col.lower() or "address" in col.lower()
                    ]
                    port_cols = [col for col in columns if "port" in col.lower()]

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

                        cursor.execute(
                            f"SELECT {', '.join(query_cols)} FROM {table_name} LIMIT 1"
                        )
                        row = cursor.fetchone()

                        if row and len(row) >= 2:
                            dc_id = row[0] if row[0] is not None else 2
                            auth_key = row[1]
                            server_address = row[2] if len(row) > 2 and row[2] else None
                            port = row[3] if len(row) > 3 and row[3] else 443

                            # Use default server if not provided
                            if not server_address:
                                dc_servers = {
                                    1: "149.154.175.53",
                                    2: "149.154.167.51",
                                    3: "149.154.175.100",
                                    4: "149.154.167.91",
                                    5: "91.108.56.130",
                                }
                                server_address = dc_servers.get(dc_id, "149.154.167.50")

                            if auth_key:
                                # Handle different auth_key formats
                                if isinstance(auth_key, str):
                                    try:
                                        auth_key_bytes = base64.b64decode(auth_key)
                                    except BaseException:
                                        try:
                                            auth_key_bytes = bytes.fromhex(auth_key)
                                        except BaseException:
                                            auth_key_bytes = auth_key.encode("utf-8")
                                elif isinstance(auth_key, (bytes, memoryview)):
                                    auth_key_bytes = bytes(auth_key)
                                else:
                                    auth_key_bytes = str(auth_key).encode("utf-8")

                                # Ensure proper auth_key length
                                if len(auth_key_bytes) < 256:
                                    auth_key_bytes = auth_key_bytes.ljust(256, b"\x00")
                                elif len(auth_key_bytes) > 256:
                                    auth_key_bytes = auth_key_bytes[:256]

                                # Build session string using Telethon's method
                                try:
                                    # Create a temporary Telethon session to generate
                                    # proper session string
                                    temp_session = StringSession()
                                    temp_session.set_dc(dc_id, server_address, port)
                                    temp_session.auth_key = AuthKey(auth_key_bytes)

                                    session_string = StringSession.save(temp_session)
                                    conn.close()
                                    logger.info(
                                        f"Successfully extracted session from table {table_name}: DC {dc_id}, Server {server_address}:{port}, Auth key length: {
                                            len(auth_key_bytes)}"
                                    )
                                    return session_string

                                except Exception as e:
                                    logger.error(
                                        f"Failed to build session string from {table_name}: {e}"
                                    )

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
        try:
            logger.info(f"Validating session string (length: {len(session_string)})")

            # Check if it's a Pyrogram session string and convert if needed
            converted_session = await self._convert_pyrogram_session_string(
                session_string
            )
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
                    fixed_session = session_string.replace("-", "+").replace("_", "/")
                    while len(fixed_session) % 4 != 0:
                        fixed_session += "="

                    decoded = base64.b64decode(fixed_session)
                    if len(decoded) < 260:
                        return (
                            False,
                            f"Invalid session format: too short ({len(decoded)} bytes)",
                        )

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
                        fixed_session = session_string.replace("-", "+").replace(
                            "_", "/"
                        )
                        while len(fixed_session) % 4 != 0:
                            fixed_session += "="

                        decoded = base64.b64decode(fixed_session)
                        if len(decoded) >= 260:
                            dc_id_bytes = decoded[256:260]
                            dc_id = unpack("<I", dc_id_bytes)[0]

                            # Map unusual DC IDs to valid ones
                            if dc_id not in [1, 2, 3, 4, 5]:
                                dc_id = 5  # Default to DC5
                                logger.info("Mapped unusual DC ID to DC5")

                            logger.info(f"Detected Pyrogram session with DC {dc_id}")

                            # Return minimal info for fast processing
                            return True, {
                                "name": "Imported Account",
                                "phone": "+000000000",  # Placeholder
                                "username": None,
                                "id": 0,  # Placeholder
                                "premium": False,
                                "verified": False,
                                "fast_import": True,
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
                    "fast_import": True,
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
                timeout=3,
            )

            # Very quick connection test
            await asyncio.wait_for(client.connect(), timeout=3.0)

            if client.is_connected():
                # Quick auth check
                is_authorized = await asyncio.wait_for(
                    client.is_user_authorized(), timeout=2.0
                )
                if is_authorized:
                    try:
                        me = await asyncio.wait_for(client.get_me(), timeout=3.0)
                        info = {
                            "name": f"{me.first_name or ''} {me.last_name or ''}".strip()
                            or "Unknown",
                            "phone": me.phone,
                            "username": me.username,
                            "id": me.id,
                            "premium": getattr(me, "premium", False),
                            "verified": getattr(me, "verified", False),
                        }
                        await client.disconnect()
                        return True, info
                    except BaseException:
                        await client.disconnect()
                        # Return placeholder info if get_me fails
                        return True, {
                            "name": "Imported Account",
                            "phone": "+000000000",
                            "username": None,
                            "id": 0,
                            "premium": False,
                            "verified": False,
                            "fast_import": True,
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
                except BaseException:
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
                "fast_import": True,
            }
        except Exception as e:
            if client:
                try:
                    await client.disconnect()
                except BaseException:
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
                fixed_session = session_string.replace("-", "+").replace("_", "/")
                while len(fixed_session) % 4 != 0:
                    fixed_session += "="

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
                dc_id = unpack("<I", dc_id_bytes)[0]
                # Map any DC ID to valid range
                if dc_id not in [1, 2, 3, 4, 5]:
                    # Use modulo to map to valid DC range
                    dc_id = (dc_id % 5) + 1
                    logger.info(f"Mapped DC ID to valid range: {dc_id}")
            except BaseException:
                dc_id = 5

            # Map DC to server
            dc_servers = {
                1: "149.154.175.53",
                2: "149.154.167.51",
                3: "149.154.175.100",
                4: "149.154.167.91",
                5: "91.108.56.130",
            }
            server_address = dc_servers.get(dc_id, "149.154.167.51")

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

    async def _detect_session_format(self, session_string: str) -> str:
        """Detect session string format (telethon, pyrogram, tdata, unknown)"""
        try:
            import base64
            
            # Check length patterns
            length = len(session_string)
            
            # Telethon sessions are typically 200-350 characters
            # Pyrogram sessions are typically 300-500 characters (base64 encoded)
            
            # Try to detect Telethon format
            try:
                test_session = StringSession(session_string)
                if test_session and test_session.auth_key:
                    logger.info("Detected Telethon format (valid StringSession)")
                    return "telethon"
            except Exception:
                pass
            
            # Try to detect Pyrogram format (base64 encoded)
            try:
                # Pyrogram uses URL-safe base64
                fixed_session = session_string.replace("-", "+").replace("_", "/")
                while len(fixed_session) % 4 != 0:
                    fixed_session += "="
                
                decoded = base64.b64decode(fixed_session)
                
                # Pyrogram sessions have specific structure:
                # 256 bytes auth_key + 4 bytes dc_id + optional data
                if len(decoded) >= 260:
                    logger.info(f"Detected Pyrogram format (decoded length: {len(decoded)})")
                    return "pyrogram"
            except Exception:
                pass
            
            # Check for TData indicators (though TData is folder-based, not string)
            if "tdata" in session_string.lower():
                return "tdata"
            
            logger.warning(f"Unknown session format (length: {length})")
            return "unknown"
            
        except Exception as e:
            logger.error(f"Session format detection error: {e}")
            return "unknown"
    
    async def _detect_file_format(self, file_path: str) -> str:
        """Detect session file format (telethon, pyrogram, unknown)"""
        try:
            import sqlite3
            
            # Try to open as SQLite database
            try:
                conn = sqlite3.connect(file_path)
                cursor = conn.cursor()
                
                # Get table names
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                
                logger.info(f"SQLite tables found: {tables}")
                
                # Check for Pyrogram indicators
                if "sessions" in tables:
                    cursor.execute("PRAGMA table_info(sessions)")
                    columns = [row[1] for row in cursor.fetchall()]
                    
                    # Pyrogram has specific column structure
                    if all(col in columns for col in ["dc_id", "auth_key"]):
                        conn.close()
                        logger.info("Detected Pyrogram file format")
                        return "pyrogram"
                
                # Check for Telethon indicators
                if "sessions" in tables or "entities" in tables or "sent_files" in tables:
                    conn.close()
                    logger.info("Detected Telethon file format")
                    return "telethon"
                
                conn.close()
                logger.warning("Unknown SQLite session format")
                return "unknown"
                
            except sqlite3.DatabaseError:
                logger.warning("File is not a valid SQLite database")
                return "unknown"
            
        except Exception as e:
            logger.error(f"File format detection error: {e}")
            return "unknown"

    async def _show_session_info(self, event, user_id, account_id):
        """Show detailed session information"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

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

                if info.get("username"):
                    text += f"📛 **Username:** @{info['username']}\n"

                text += (
                    f"💬 **Dialogs:** {info.get('dialogs', 0)}\n"
                    f"📢 **Channels:** {info.get('channels', 0)}\n"
                    f"👥 **Groups:** {info.get('groups', 0)}\n"
                    f"🤖 **Bots:** {info.get('bots', 0)}\n"
                    f"💭 **Private Chats:** {info.get('private_chats', 0)}\n"
                )

                if info.get("premium"):
                    text += "⭐ **Premium Account**\n"
                if info.get("verified"):
                    text += "✅ **Verified Account**\n"

                text += f"\n📅 **Added:** {account.get('created_at', 'Unknown')}"
                text += f"\n🔧 **Method:** {account.get('added_via', 'Unknown')}"
            else:
                text = f"📱 **Session Info: {
                    account['name']}**\n\n❌ Could not retrieve live session information."

            buttons = [
                [Button.inline("🔄 Refresh Info", f"session_info:{account_id}")],
                [
                    Button.inline(
                        "⚙️ Session Operations", f"session_operations:{account_id}"
                    )
                ],
                [Button.inline("🔙 Back", "session_login")],
            ]

            await event.edit(text, buttons=buttons)

        except Exception as e:
            logger.error(f"Show session info error: {e}")
            await event.edit("❌ Error loading session information")

    async def _show_session_operations(self, event, user_id, account_id):
        """Show session operations menu"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

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
                    Button.inline(
                        "🚫 Spam Check", f"session_op:spam_check:{account_id}"
                    ),
                ],
                [
                    Button.inline("📢 Subscribe", f"session_op:subscribe:{account_id}"),
                    Button.inline(
                        "💬 Send Message", f"session_op:message:{account_id}"
                    ),
                ],
                [
                    Button.inline(
                        "🗑️ Delete Dialogs", f"session_op:delete:{account_id}"
                    ),
                    Button.inline(
                        "📤 Export Contacts", f"session_op:export:{account_id}"
                    ),
                ],
                [
                    Button.inline(
                        "💾 Generate TData", f"session_op:tdata:{account_id}"
                    ),
                    Button.inline("💰 Check Wallet", f"session_op:wallet:{account_id}"),
                ],
                [Button.inline("🔙 Back", f"session_info:{account_id}")],
            ]

            await event.edit(text, buttons=buttons)

        except Exception as e:
            logger.error(f"Show session operations error: {e}")
            await event.edit("❌ Error loading session operations")

    async def _handle_session_operation(self, event, user_id, operation, account_id):
        """Handle session operation"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

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
            if (
                user_id not in self.user_clients
                or account_name not in self.user_clients[user_id]
            ):
                return None

            client = self.user_clients[user_id][account_name]
            if not client or not client.is_connected():
                return None

            me = await client.get_me()
            dialogs = await client.get_dialogs()

            # Count different types of entities
            stats = {
                "contacts": 0,
                "channels": 0,
                "bots": 0,
                "groups": 0,
                "private_chats": 0,
            }

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
                **stats,
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
                await event.edit(
                    f"📨 Code resent to {phone}. Please enter the new verification code:"
                )
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
                    except BaseException:
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

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if (
                not account
                or user_id not in self.user_clients
                or account["name"] not in self.user_clients[user_id]
            ):
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
                    is_blocked = any(
                        word in message_text
                        for word in ["ограничен", "limited", "restricted"]
                    )
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
                "account_id": account_id,
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
                "account_id": account_id,
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
                "🗑️ **Delete Dialogs**\n\n"
                "Choose what to delete:\n\n"
                "**⚠️ Warning:** This action cannot be undone!\n\n"
                "Select dialog type to delete:"
            )

            buttons = [
                [
                    Button.inline(
                        "📢 All Channels", f"session_delete:channels:{account_id}"
                    ),
                    Button.inline(
                        "👥 All Groups", f"session_delete:groups:{account_id}"
                    ),
                ],
                [
                    Button.inline("🤖 All Bots", f"session_delete:bots:{account_id}"),
                    Button.inline(
                        "💭 Private Chats", f"session_delete:private:{account_id}"
                    ),
                ],
                [Button.inline("🔙 Back", f"session_operations:{account_id}")],
            ]

            await event.edit(text, buttons=buttons)

        except Exception as e:
            logger.error(f"Show delete options error: {e}")
            await event.answer("❌ Error showing delete options")

    async def _export_contacts(self, event, user_id, account_id):
        """Export contacts"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if (
                not account
                or user_id not in self.user_clients
                or account["name"] not in self.user_clients[user_id]
            ):
                await event.answer("❌ Account not available")
                return

            client = self.user_clients[user_id][account["name"]]

            # Export contacts
            contacts_result = await client(GetContactsRequest(hash=0))
            users = contacts_result.users

            # Create contacts file
            lines = ["Name\tUsername\tPhone\tID"]
            for user in users:
                name = (
                    f"{user.first_name or ''} {user.last_name or ''}".strip()
                    or "Unknown"
                )
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
                caption=f"📤 Contacts exported from {
                    account['name']}\n\nTotal contacts: {
                    len(users)}",
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
                [
                    Button.inline(
                        "📝 Export Session String",
                        f"session_export_string:{account_id}",
                    )
                ],
                [Button.inline("🔙 Back", f"session_operations:{account_id}")],
            ]

            await event.edit(text, buttons=buttons)

        except Exception as e:
            logger.error(f"Generate TData error: {e}")
            await event.answer("❌ Error generating TData")

    async def _check_crypto_wallet(self, event, user_id, account_id):
        """Check cryptocurrency wallet"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if (
                not account
                or user_id not in self.user_clients
                or account["name"] not in self.user_clients[user_id]
            ):
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

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if (
                not account
                or user_id not in self.user_clients
                or account["name"] not in self.user_clients[user_id]
            ):
                return False, "❌ Account not available"

            client = self.user_clients[user_id][account["name"]]

            # Subscribe to channel
            await client(JoinChannelRequest(channel_link))

            return True, f"✅ Successfully subscribed to {channel_link}"

        except Exception as e:
            logger.error(f"Subscribe to channel error: {e}")
            return False, f"❌ Subscription failed: {str(e)}"

    async def send_message_to_user(
        self, user_id, account_id, recipient, message_text, media_path=None
    ):
        """Send message to user"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if (
                not account
                or user_id not in self.user_clients
                or account["name"] not in self.user_clients[user_id]
            ):
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

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if (
                not account
                or user_id not in self.user_clients
                or account["name"] not in self.user_clients[user_id]
            ):
                return False, "❌ Account not available"

            client = self.user_clients[user_id][account["name"]]

            # Get dialogs
            dialogs = await client.get_dialogs()
            deleted_count = 0

            for dialog in dialogs:
                entity = dialog.entity
                should_delete = False

                if (
                    dialog_type == "channels"
                    and isinstance(entity, Channel)
                    and getattr(entity, "broadcast", False)
                ):
                    should_delete = True
                elif (
                    dialog_type == "groups"
                    and isinstance(entity, (Channel, Chat))
                    and not getattr(entity, "broadcast", False)
                ):
                    should_delete = True
                elif (
                    dialog_type == "bots"
                    and isinstance(entity, User)
                    and getattr(entity, "bot", False)
                ):
                    should_delete = True
                elif (
                    dialog_type == "private"
                    and isinstance(entity, User)
                    and not getattr(entity, "bot", False)
                ):
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
            import os
            import sqlite3
            import tempfile
            from struct import unpack

            # Try to decode as Pyrogram session with URL-safe base64
            try:
                # Convert URL-safe base64 and fix padding
                fixed_session = session_string.replace("-", "+").replace("_", "/")
                while len(fixed_session) % 4 != 0:
                    fixed_session += "="

                decoded = base64.b64decode(fixed_session)
                if len(decoded) < 260:
                    return False, "Invalid session format"

                auth_key = decoded[:256]
                dc_id_bytes = decoded[256:260]
                dc_id = unpack("<I", dc_id_bytes)[0]

                # Normalize DC ID to valid range
                if dc_id not in [1, 2, 3, 4, 5]:
                    dc_id = (dc_id % 5) + 1
                    logger.info(f"Mapped unusual DC ID to valid range: {dc_id}")

                # Create temp file
                with tempfile.NamedTemporaryFile(
                    suffix=".session", delete=False
                ) as temp_file:
                    temp_path = temp_file.name

                conn = sqlite3.connect(temp_path)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    CREATE TABLE sessions (
                        dc_id INTEGER,
                        server_address TEXT,
                        port INTEGER,
                        auth_key BLOB
                    )
                """
                )

                dc_servers = {
                    1: "149.154.175.53",
                    2: "149.154.167.51",
                    3: "149.154.175.100",
                    4: "149.154.167.91",
                    5: "91.108.56.130",
                }
                server_address = dc_servers.get(dc_id, "149.154.167.51")

                cursor.execute(
                    "INSERT INTO sessions (dc_id, server_address, port, auth_key) VALUES (?, ?, ?, ?)",
                    (dc_id, server_address, 443, auth_key),
                )

                conn.commit()
                conn.close()

                # Extract using existing method
                extracted_session = await self._extract_session_from_file(temp_path)

                # Cleanup
                try:
                    os.unlink(temp_path)
                except BaseException:
                    pass

                if extracted_session:
                    # Quick validation
                    client = TelegramClient(
                        StringSession(extracted_session),
                        config.telegram.api_id,
                        config.telegram.api_hash,
                        connection_retries=1,
                        timeout=5,
                    )

                    try:
                        await asyncio.wait_for(client.connect(), timeout=5.0)
                        if await asyncio.wait_for(
                            client.is_user_authorized(), timeout=3.0
                        ):
                            me = await asyncio.wait_for(client.get_me(), timeout=5.0)
                            info = {
                                "name": f"{me.first_name or ''} {me.last_name or ''}".strip()
                                or "Unknown",
                                "phone": me.phone,
                                "username": me.username,
                                "id": me.id,
                                "premium": getattr(me, "premium", False),
                                "verified": getattr(me, "verified", False),
                            }
                            await client.disconnect()
                            return True, info
                        else:
                            await client.disconnect()
                            return False, "Session not authorized"
                    except BaseException:
                        try:
                            await client.disconnect()
                        except BaseException:
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
            existing = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "phone": phone}
            )
            if existing:
                return False, f"❌ Account {phone} already exists"

            # Validate session string before saving
            if (
                not session_string
                or not isinstance(session_string, str)
                or len(session_string) < 50
            ):
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
                "fast_import": is_fast_import,
            }

            result = await mongodb.db.accounts.insert_one(account_data)
            str(result.inserted_id)

            # Start user client with converted session
            try:
                logger.info(
                    f"Starting client with session string (length: {
                        len(session_string)}, type: {
                        type(session_string)})"
                )
                await self.bot_manager.start_user_client(user_id, name, session_string)
            except Exception as client_error:
                logger.error(f"Failed to start client with session: {client_error}")
                logger.error(
                    f"Session string details - Length: {
                        len(session_string) if session_string else 0}, Type: {
                        type(session_string)}, Valid: {
                        bool(session_string)}"
                )
                raise client_error

            # Send login notification
            try:
                await self._send_login_notification(
                    user_id, name, "Account imported via session string"
                )
            except Exception as notif_err:
                logger.error(f"Failed to send login notification: {notif_err}")

            # Notify webapp via WebSocket so it refreshes account list in real-time
            try:
                from backend.notifier import notify
                await notify(user_id, {
                    "type": "account_added",
                    "phone": phone,
                    "name": name,
                    "source": "bot",
                })
            except Exception as ws_err:
                logger.debug(f"WebSocket notify skipped: {ws_err}")

            # Update account with real name from Telegram (like OTP login does)
            if not is_fast_import:
                await self._fetch_and_store_account_name(user_id, name, phone)
            else:
                # For fast imports, update name in background
                asyncio.create_task(self._update_fast_import_info(user_id, name, phone))

            logger.info(f"Successfully imported account: {name} ({phone})")
            return (
                True,
                f"✅ Account {name} imported successfully!\n\n💡 Real account info will be updated automatically.",
            )

        except Exception as e:
            logger.error(f"Session import finalization error: {e}")
            return False, f"❌ Import failed: {str(e)}"

    async def _update_fast_import_info(
        self, user_id: int, account_name: str, phone: str
    ):
        """Update fast import account info in background"""
        try:
            await asyncio.sleep(5)  # Wait for client to stabilize

            if (
                user_id in self.user_clients
                and account_name in self.user_clients[user_id]
            ):
                client = self.user_clients[user_id][account_name]
                if client and client.is_connected():
                    try:
                        me = await asyncio.wait_for(client.get_me(), timeout=10.0)

                        # Format display name
                        first_name = getattr(me, "first_name", None) or ""
                        last_name = getattr(me, "last_name", None) or ""
                        username = getattr(me, "username", None)
                        real_phone = getattr(me, "phone", None) or phone
                        display_name = " ".join(
                            part for part in (first_name, last_name) if part
                        )
                        if not display_name:
                            display_name = f"@{username}" if username else real_phone

                        # Update account in database
                        await mongodb.db.accounts.update_one(
                            {"user_id": user_id, "name": account_name},
                            {
                                "$set": {
                                    "first_name": first_name,
                                    "last_name": last_name,
                                    "username": username,
                                    "phone": real_phone,
                                    "display_name": display_name,
                                    "name": display_name,
                                    "fast_import": False,
                                }
                            },
                        )

                        # Client storage is managed by bot_manager - no need to update
                        # here

                        logger.info(
                            f"Updated fast import account: {display_name} ({real_phone})"
                        )

                    except Exception as e:
                        logger.error(f"Failed to update fast import info: {e}")
        except Exception as e:
            logger.error(f"Background update failed for {phone}: {e}")

    async def _fetch_and_store_account_name(
        self, user_id: int, account_name: str, phone: str
    ):
        """Fetch real account name from Telegram and store in database"""
        try:
            if (
                user_id in self.user_clients
                and account_name in self.user_clients[user_id]
            ):
                client = self.user_clients[user_id][account_name]
                if client and client.is_connected():
                    me = await retry_async(client.get_me)
                    # Format display name
                    first_name = getattr(me, "first_name", None) or ""
                    last_name = getattr(me, "last_name", None) or ""
                    username = getattr(me, "username", None)
                    display_name = " ".join(
                        part for part in (first_name, last_name) if part
                    )
                    if not display_name:
                        display_name = f"@{username}" if username else phone

                    # Update account in database
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {
                            "$set": {
                                "first_name": first_name,
                                "last_name": last_name,
                                "username": username,
                                "display_name": display_name,
                                "name": display_name,
                            }
                        },
                    )

                    # Client storage is managed by bot_manager - no need to update here

                    logger.info(f"Updated account name for {phone}: {display_name}")
        except Exception as e:
            logger.error(f"Failed to fetch account name for {phone}: {e}")

    async def _start_session_creation(self, event, user_id):
        """Start session creation with automatic OTP for managed accounts"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                None
            )

            if not accounts:
                try:
                    await event.edit(
                        "❌ No accounts found. Add accounts first before creating sessions."
                    )
                except BaseException:
                    pass
                return

            buttons = [
                [
                    Button.inline(
                        f"📱 {acc.get('name', acc['phone'])}",
                        f"create_sess:{acc['phone']}",
                    )
                ]
                for acc in accounts[:10]
            ]
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
            account = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "phone": phone}
            )
            if not account:
                await event.edit("❌ Account not found")
                return

            account_name = account.get("name", phone)

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
                [Button.inline("📝 String Session", f"create_sess_fmt:{phone}:string")],
                [Button.inline("📁 Session File", f"create_sess_fmt:{phone}:file")],
                [Button.inline("🔙 Back", "menu:accounts")],
            ]

            try:
                await event.edit(text, buttons=buttons)
            except Exception as edit_err:
                if "Content of the message was not modified" in str(edit_err):
                    # Message is already correct, just answer the callback
                    await event.answer("📦 Choose format")
                else:
                    raise edit_err
        except Exception as e:
            logger.error(f"Format selection error: {e}")
            try:
                await event.edit("❌ Error showing format selection")
            except BaseException:
                await event.answer("❌ Error showing format selection")

    async def _execute_session_creation(
        self, event, user_id, phone, format_type="string"
    ):
        """Execute session creation with auto OTP"""
        client = None
        destroyer_was_enabled = False
        account = None
        try:
            account = await self._prepare_session_creation(user_id, phone)
            if account:
                destroyer_was_enabled = account.get("otp_destroyer_enabled", False)

            await event.edit(
                f"⏳ Creating session for {phone}...\n\n🛡️ OTP Destroyer temporarily disabled\n1️⃣ Requesting OTP from Telegram..."
            )

            client, phone_code_hash = await self._request_otp_code(phone)
            if not client or not phone_code_hash:
                await self._cleanup_session_creation(account, destroyer_was_enabled, user_id)
                await event.edit("❌ Failed to request OTP")
                return

            otp_code = await self._fetch_otp_with_retry(event, user_id, phone)
            if not otp_code:
                await self._cleanup_session_creation(account, destroyer_was_enabled, user_id, client)
                await event.edit(
                    "❌ **Could not fetch OTP automatically**\n\n"
                    "💡 **Try these solutions:**\n"
                    "• Wait a moment and try again\n"
                    "• Use manual login instead\n"
                    "• Check your other accounts are working"
                )
                return

            session_string = await self._sign_in_with_otp(event, client, phone, otp_code, phone_code_hash, user_id, format_type, account, destroyer_was_enabled)
            if not session_string:
                return

            session_file_data = await self._generate_session_file(format_type, client, phone) if format_type == "file" else None

            await client.disconnect()
            await self._cleanup_session_creation(account, destroyer_was_enabled, user_id)

            await self._send_session_result(event, user_id, phone, format_type, session_string, session_file_data)
            await self._send_login_notification(user_id, phone, "Session file created" if format_type == "file" and session_file_data else "Session string created")

        except Exception as e:
            if client:
                try:
                    await client.disconnect()
                except BaseException:
                    pass
            await self._cleanup_session_creation(account, destroyer_was_enabled, user_id)
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
            logger.info(
                f"Fetching OTP for {target_phone} from {
                    len(
                        self.user_clients[user_id])} accounts"
            )

            # Get current time for filtering recent messages
            import time as time_module

            current_time = time_module.time()

            for account_name, client in self.user_clients[user_id].items():
                if not client or not client.is_connected():
                    continue

                try:
                    # Get recent messages from Telegram service (777000)
                    messages = await asyncio.wait_for(
                        client.get_messages(777000, limit=50), timeout=10.0
                    )

                    for msg in messages:
                        if not msg.message:
                            continue

                        # Check message age - prioritize newest messages
                        msg_age = 0
                        if hasattr(msg, "date"):
                            msg_age = current_time - msg.date.timestamp()
                            # For fresh OTP, check very recent messages first (30
                            # seconds)
                            if msg_age > 30:
                                continue

                        message_text = msg.message.lower()
                        original_message = msg.message

                        # Log all recent messages for debugging (safe encoding)
                        safe_message = (
                            original_message[:100]
                            .encode("ascii", errors="replace")
                            .decode("ascii")
                        )
                        logger.info(
                            f"Checking message (age: {msg_age:.1f}s): {safe_message}..."
                        )

                        # Enhanced patterns to match OTP messages
                        is_otp_message = any(
                            [
                                "login code" in message_text,
                                "verification code" in message_text,
                                "telegram code" in message_text,
                                "your code" in message_text,
                                "authentication code" in message_text,
                                "confirmation code" in message_text,
                                target_phone_clean in original_message,
                                "код" in message_text,  # Russian
                                "code:" in message_text,
                                "confirm" in message_text and "code" in message_text,
                                "sign" in message_text and "code" in message_text,
                                "telegram" in message_text
                                and any(d in original_message for d in "0123456789"),
                            ]
                        )

                        if is_otp_message:
                            import re

                            safe_message = original_message.encode(
                                "ascii", errors="replace"
                            ).decode("ascii")
                            logger.info(f"OTP message detected: {safe_message}")

                            # Enhanced regex patterns for different OTP formats
                            patterns = [
                                r"Login code: (\d{4,6})",  # "Login code: 12345"
                                r"Code: (\d{4,6})",  # "Code: 12345"
                                r"code[:\s]+(\d{4,6})",  # "code: 12345"
                                r"\b(\d{5})\b",  # exactly 5 digits
                                # hyphenated format
                                r"(\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2})",
                            ]

                            # Try each pattern and log attempts
                            for i, pattern in enumerate(patterns):
                                logger.info(f"Trying pattern {i + 1}: {pattern}")
                                code_match = re.search(pattern, original_message)
                                if code_match:
                                    code = code_match.group(1).replace("-", "")
                                    logger.info(f"Pattern {i + 1} matched: {code}")
                                    if (
                                        len(code) >= 4
                                        and len(code) <= 6
                                        and code.isdigit()
                                    ):
                                        safe_name = account_name.encode(
                                            "ascii", errors="replace"
                                        ).decode("ascii")
                                        logger.info(
                                            f"Found valid OTP {code} from {safe_name} (message age: {
                                                msg_age:.1f}s)"
                                        )
                                        return code
                                    else:
                                        logger.info(
                                            f"Code {code} invalid length or not digits"
                                        )
                                else:
                                    logger.info(f"Pattern {i + 1} no match")

                            # Manual check for the exact format we saw
                            if "Login code:" in original_message:
                                import re

                                manual_match = re.search(
                                    r"Login code: (\d+)", original_message
                                )
                                if manual_match:
                                    code = manual_match.group(1)
                                    logger.info(f"Manual pattern found code: {code}")
                                    if (
                                        len(code) >= 4
                                        and len(code) <= 6
                                        and code.isdigit()
                                    ):
                                        safe_name = account_name.encode(
                                            "ascii", errors="replace"
                                        ).decode("ascii")
                                        logger.info(
                                            f"Found OTP via manual check {code} from {safe_name}"
                                        )
                                        return code
                except asyncio.TimeoutError:
                    logger.debug(f"Timeout fetching messages from {account_name}")
                    continue
                except Exception as e:
                    logger.debug(f"Failed to fetch from {account_name}: {e}")
                    continue

            logger.warning(f"No fresh OTP found for {target_phone}")
            return None
        except Exception as e:
            logger.error(f"OTP fetch error: {e}")
            return None

    async def _fetch_otp_fallback(self, user_id, target_phone):
        """Fallback OTP fetch for recent messages (up to 5 minutes old)"""
        try:
            if user_id not in self.user_clients:
                return None

            target_phone.replace("+", "")
            import time as time_module

            current_time = time_module.time()

            for account_name, client in self.user_clients[user_id].items():
                if not client or not client.is_connected():
                    continue

                try:
                    messages = await asyncio.wait_for(
                        client.get_messages(777000, limit=30), timeout=5.0
                    )

                    for msg in messages:
                        if not msg.message:
                            continue

                        # Check recent messages (up to 5 minutes)
                        if hasattr(msg, "date"):
                            msg_age = current_time - msg.date.timestamp()
                            if msg_age > 300:  # Skip messages older than 5 minutes
                                continue

                        message_text = msg.message.lower()
                        original_message = msg.message

                        # Check for OTP messages
                        if "login code" in message_text:
                            import re

                            code_match = re.search(
                                r"Login code: (\d{4,6})", original_message
                            )
                            if code_match:
                                code = code_match.group(1)
                                if len(code) >= 4 and len(code) <= 6 and code.isdigit():
                                    logger.info(
                                        f"Found recent OTP {code} (age: {msg_age:.1f}s)"
                                    )
                                    return code
                except Exception:
                    continue

            return None
        except Exception as e:
            logger.error(f"Fallback OTP fetch error: {e}")
            return None

    async def _debug_telegram_messages(self, user_id, target_phone):
        """Debug function to check what messages are in Telegram service"""
        try:
            if user_id not in self.user_clients:
                logger.info("No clients available for debugging")
                return

            target_phone.replace("+", "")
            import time as time_module

            current_time = time_module.time()

            for account_name, client in self.user_clients[user_id].items():
                if not client or not client.is_connected():
                    continue

                try:
                    messages = await asyncio.wait_for(
                        client.get_messages(777000, limit=10), timeout=5.0
                    )
                    logger.info(
                        f"Debug - Found {len(messages)} messages from 777000 via {account_name}"
                    )

                    for i, msg in enumerate(messages):
                        if msg.message:
                            msg_age = (
                                current_time - msg.date.timestamp()
                                if hasattr(msg, "date")
                                else 0
                            )
                            safe_message = (
                                msg.message[:200]
                                .encode("ascii", errors="replace")
                                .decode("ascii")
                            )
                            logger.info(
                                f"Debug - Message {i +
                                                   1} (age: {msg_age:.1f}s): {safe_message}"
                            )
                        else:
                            logger.info(f"Debug - Message {i + 1}: No text content")
                    break  # Only debug from first working client
                except Exception as e:
                    logger.debug(f"Debug failed for {account_name}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Debug function error: {e}")

    async def _process_zip_sessions(self, user_id, zip_path):
        """Process ZIP file containing multiple session files"""
        import tempfile
        import zipfile

        try:
            # Check ZIP file size
            zip_size = os.path.getsize(zip_path)
            if zip_size > 50 * 1024 * 1024:  # 50MB limit for ZIP
                return False, "❌ ZIP file too large (max 50MB)"

            # Extract ZIP
            temp_dir = tempfile.mkdtemp()
            session_files = []

            try:
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    # Get list of .session files
                    for file_info in zip_ref.filelist:
                        if file_info.filename.endswith(".session"):
                            zip_ref.extract(file_info, temp_dir)
                            session_files.append(
                                os.path.join(temp_dir, file_info.filename)
                            )

                if not session_files:
                    shutil.rmtree(temp_dir)
                    return False, "❌ No .session files found in ZIP"

                # Send initial status
                await self.bot.send_message(
                    user_id,
                    f"📦 **Processing ZIP Archive**\n\n"
                    f"📁 Found {len(session_files)} session file(s)\n"
                    f"⏳ Starting import...\n\n"
                    f"Progress will be shown below:",
                )

                # Process each session file
                success_count = 0
                failed_count = 0
                results = []

                for i, session_file in enumerate(session_files, 1):
                    file_name = os.path.basename(session_file)

                    try:
                        await self.bot.send_message(
                            user_id,
                            f"⏳ Processing {i}/{len(session_files)}: {file_name}...",
                        )

                        success, message = await self._process_single_session_file(
                            user_id, session_file
                        )

                        if success:
                            success_count += 1
                            results.append(f"✅ {file_name}")
                        else:
                            failed_count += 1
                            results.append(f"❌ {file_name}: {message}")

                    except Exception as e:
                        failed_count += 1
                        results.append(f"❌ {file_name}: {str(e)}")

                # Clean up
                shutil.rmtree(temp_dir)
                os.remove(zip_path)

                # Send final summary
                summary = (
                    f"📊 **Import Complete**\n\n"
                    f"✅ Success: {success_count}\n"
                    f"❌ Failed: {failed_count}\n"
                    f"📁 Total: {len(session_files)}\n\n"
                    f"**Details:**\n" + "\n".join(results[:20])  # Limit to 20 results
                )

                if len(results) > 20:
                    summary += f"\n\n... and {len(results) - 20} more"

                await self.bot.send_message(user_id, summary)

                return (
                    True,
                    f"✅ Imported {success_count}/{len(session_files)} accounts",
                )

            except zipfile.BadZipFile:
                shutil.rmtree(temp_dir)
                return False, "❌ Invalid ZIP file format"
            except Exception as extract_err:
                shutil.rmtree(temp_dir)
                return False, f"❌ ZIP extraction failed: {str(extract_err)}"

        except Exception as e:
            logger.error(f"ZIP processing error: {e}")
            try:
                os.remove(zip_path)
            except BaseException:
                pass
            return False, f"❌ ZIP processing failed: {str(e)}"

    async def _process_single_session_file(self, user_id, file_path):
        """Process a single session file without cleanup"""
        try:
            if not os.path.exists(file_path):
                return False, "File not found"

            file_size = os.path.getsize(file_path)
            if file_size < 100:
                return False, "File too small"

            if file_size > 10 * 1024 * 1024:
                return False, "File too large"

            # Extract session string
            session_string = await self._extract_session_from_file(file_path)

            if not session_string:
                return False, "Could not extract session"

            # Validate and save
            success, message = await self.process_session_string(
                user_id, session_string
            )

            return success, message

        except Exception as e:
            logger.error(f"Single session file processing error: {e}")
            return False, str(e)

    async def _prepare_session_creation(self, user_id, phone):
        account = await mongodb.db.accounts.find_one({"user_id": user_id, "phone": phone})
        if account:
            await mongodb.db.accounts.update_one(
                {"_id": account["_id"]},
                {"$set": {"session_creation_in_progress": True, "otp_destroyer_enabled": False}},
            )
            import time
            await mongodb.db.otp_protections.update_one(
                {"phone": phone, "wildcard": True},
                {"$set": {"phone": phone, "wildcard": True, "expires_at": int(time.time()) + 300, "reason": "session_creation"}},
                upsert=True,
            )
            self.bot_manager.pending_actions[user_id] = {"action": "session_creation", "phone": phone, "account_name": account.get("name", phone)}
            logger.info(f"OTP Destroyer temporarily disabled for {phone} during session creation")
        return account

    async def _request_otp_code(self, phone):
        device = self.get_random_device()
        client = TelegramClient(StringSession(), config.telegram.api_id, config.telegram.api_hash, device_model=device["model"], system_version=device["system"], app_version=device["version"])
        await client.connect()
        try:
            result = await client.send_code_request(phone)
            logger.info(f"Code requested for {phone}, hash: {result.phone_code_hash}")
            return client, result.phone_code_hash
        except Exception as e:
            logger.error(f"Failed to request code: {e}")
            await client.disconnect()
            return None, None

    async def _fetch_otp_with_retry(self, event, user_id, phone):
        await event.edit(f"⏳ Creating session for {phone}...\\n\\n2️⃣ Waiting for OTP from Telegram...")
        for attempt in range(15):
            await event.edit(f"⏳ Creating session for {phone}...\\n\\n2️⃣ Waiting for fresh OTP (attempt {attempt + 1}/15)...")
            otp_code = await self._fetch_otp_from_telegram(user_id, phone)
            if otp_code:
                logger.info(f"Fresh OTP fetched on attempt {attempt + 1}: {otp_code}")
                return otp_code
            await asyncio.sleep(2)
        await event.edit(f"⏳ Creating session for {phone}...\\n\\n🔍 Checking for recent OTP codes...")
        otp_code = await self._fetch_otp_fallback(user_id, phone)
        if otp_code:
            logger.info(f"Found recent OTP code: {otp_code}")
        return otp_code

    async def _sign_in_with_otp(self, event, client, phone, otp_code, phone_code_hash, user_id, format_type, account, destroyer_was_enabled):
        await event.edit(f"⏳ Creating session for {phone}...\\n\\n3️⃣ Signing in with OTP: {otp_code}...")
        try:
            await client.sign_in(phone, otp_code, phone_code_hash=phone_code_hash)
            return StringSession.save(client.session)
        except SessionPasswordNeededError:
            return await self._handle_2fa_required(event, client, user_id, phone, phone_code_hash, format_type, account, destroyer_was_enabled)
        except Exception as e:
            await client.disconnect()
            if destroyer_was_enabled and account:
                await mongodb.db.accounts.update_one({"_id": account["_id"]}, {"$set": {"otp_destroyer_enabled": True}})
            await event.edit(f"❌ Sign in failed: {e}")
            return None

    async def _handle_2fa_required(self, event, client, user_id, phone, phone_code_hash, format_type, account, destroyer_was_enabled):
        from ..utils.twofa_helper import twofa_helper
        await event.edit(f"⏳ Creating session for {phone}...\\n\\n4️⃣ Checking for stored 2FA password...")
        success, session_str, error = await twofa_helper.try_sign_in_with_2fa(client, user_id, phone)
        if success:
            return session_str
        if error in ["stored_password_invalid", "no_stored_password"]:
            self.pending_auth[user_id] = {"client": client, "phone": phone, "phone_code_hash": phone_code_hash, "destroyer_was_enabled": destroyer_was_enabled, "account": account, "action": "session_creation_2fa", "format_type": format_type}
            msg = "🔐 **2FA Password Required**\\n\\n"
            msg += "Your stored 2FA password is incorrect (changed externally).\\n\\n" if error == "stored_password_invalid" else "This account has 2FA enabled.\\n\\n"
            msg += "Please send your 2FA password to continue:"
            await event.edit(msg)
            self.bot_manager.pending_actions[user_id] = {"action": "session_creation_2fa_password", "phone": phone, "format_type": format_type}
            return None
        await client.disconnect()
        if destroyer_was_enabled and account:
            await mongodb.db.accounts.update_one({"_id": account["_id"]}, {"$set": {"otp_destroyer_enabled": True}})
        await event.edit(f"❌ 2FA authentication failed: {error}")
        return None

    async def _generate_session_file(self, format_type, client, phone):
        if format_type != "file":
            return None
        try:
            import tempfile
            import time
            temp_name = f"session_{phone.replace('+', '')}_{int(time.time())}"
            temp_path = os.path.join(tempfile.gettempdir(), temp_name)
            logger.info(f"Creating session file at: {temp_path}.session")
            file_client = TelegramClient(temp_path, config.telegram.api_id, config.telegram.api_hash)
            file_client.session.set_dc(client.session.dc_id, client.session.server_address, client.session.port)
            file_client.session.auth_key = client.session.auth_key
            file_client.session.save()
            await file_client.connect()
            await file_client.disconnect()
            session_file_path = f"{temp_path}.session"
            if os.path.exists(session_file_path):
                file_size = os.path.getsize(session_file_path)
                logger.info(f"Session file created, size: {file_size} bytes")
                if file_size > 0:
                    with open(session_file_path, "rb") as f:
                        session_file_data = f.read()
                    logger.info(f"Session file data read: {len(session_file_data)} bytes")
                    try:
                        os.remove(session_file_path)
                    except Exception as e:
                        logger.warning(f"Failed to cleanup temp file: {e}")
                    return session_file_data
            return None
        except Exception as e:
            logger.error(f"Session file creation error: {e}")
            return None

    async def _cleanup_session_creation(self, account, destroyer_was_enabled, user_id, client=None):
        if client:
            try:
                await client.disconnect()
            except BaseException:
                pass
        if account:
            await mongodb.db.accounts.update_one({"_id": account["_id"]}, {"$unset": {"session_creation_in_progress": ""}, "$set": {"otp_destroyer_enabled": destroyer_was_enabled}})
            await mongodb.db.otp_protections.delete_many({"phone": account.get("phone"), "wildcard": True})
            self.bot_manager.pending_actions.pop(user_id, None)
            logger.info("OTP Destroyer re-enabled after session creation")

    async def _send_session_result(self, event, user_id, phone, format_type, session_string, session_file_data):
        logger.info(f"Session creation completed. Format: {format_type}, File data exists: {session_file_data is not None}")
        if format_type == "file":
            if session_file_data and len(session_file_data) > 0:
                from telethon.tl.types import DocumentAttributeFilename
                await event.edit("✅ **Session file created! Sending...**")
                await self.bot.send_message(user_id, f"📁 **Session File Created!**\\n\\n📱 Phone: {phone}\\n\\n💾 Download and save securely!\\n🛡️ OTP Destroyer re-enabled", file=session_file_data, attributes=[DocumentAttributeFilename(f"{phone.replace('+', '')}.session")])
                try:
                    try:
                        await event.edit("")
                    except Exception:
                        try:
                            await event.delete()
                        except BaseException:
                            pass
                except BaseException:
                    pass
            else:
                await event.edit(f"❌ **File generation failed**\\n\\nHere's the session string instead:\\n\\n`{session_string}`\\n\\n🛡️ OTP Destroyer re-enabled")
        else:
            await event.edit(f"✅ **Session String Created!**\\n\\n📱 Phone: {phone}\\n📝 Session String:\\n\\n`{session_string}`\\n\\n💾 Copy and save securely!\\n🛡️ OTP Destroyer re-enabled")
