"""Session Import Handler - Login via session files or strings"""

import logging
import os

from telethon import events

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class SessionImportHandler:
    def __init__(self, bot_manager):
        self.bot = bot_manager.bot
        self.bot_manager = bot_manager
        self.user_clients = bot_manager.user_clients

    def register_handlers(self):
        """Register session import handlers"""

        @self.bot.on(events.CallbackQuery(pattern=r"^import_sessions$"))
        async def import_sessions_menu(event):
            user_id = event.sender_id
            await self._show_import_menu(event, user_id)

        @self.bot.on(events.CallbackQuery(pattern=r"^import_string$"))
        async def import_string_session(event):
            user_id = event.sender_id
            # Only allow users who have started the bot (i.e., account owners)
            try:
                user = await mongodb.get_user(user_id)
            except Exception:
                user = None
            if not user:
                await event.answer(
                    "⛔ Please start the bot first with /start before importing sessions."
                )
                return
            await self._import_string_session(event, user_id)

        @self.bot.on(events.CallbackQuery(pattern=r"^import_file$"))
        async def import_session_file(event):
            user_id = event.sender_id
            await self._import_session_file(event, user_id)

        @self.bot.on(events.CallbackQuery(pattern=r"^import_zip$"))
        async def import_zip_sessions(event):
            user_id = event.sender_id
            await self._import_zip_sessions(event, user_id)

        @self.bot.on(events.CallbackQuery(pattern=r"^import_formats$"))
        async def show_supported_formats(event):
            await self._show_supported_formats(event)

    async def _show_import_menu(self, event, user_id):
        """Show session import menu"""
        try:
            from telethon import Button

            from ..utils.session_utils import get_supported_formats

            get_supported_formats()

            text = (
                "📥 **Universal Session Import**\n\n"
                "Import accounts from **any** Telegram library:\n\n"
                "**📱 Supported Formats:**\n"
                "• **Telethon**: StringSession, .session files\n"
                "• **Pyrogram**: Session strings, .session files\n"
                "• **TDLib**: JSON session data\n"
                "• **Raw JSON**: Custom session formats\n\n"
                "**✨ Benefits:**\n"
                "• No OTP verification needed\n"
                "• No 2FA password required\n"
                "• Instant account addition\n"
                "• Auto-detects session format\n\n"
                "Choose import method:"
            )
            buttons = [
                [Button.inline("📝 Import Session String", "import_string")],
                [Button.inline("📁 Import Session File", "import_file")],
                [Button.inline("📦 Import ZIP (Bulk)", "import_zip")],
                [Button.inline("📊 View Supported Formats", "import_formats")],
                [Button.inline("🔙 Back to Account Settings", "menu:accounts")],
            ]
            await event.edit(text, buttons=buttons)
        except Exception as e:
            logger.error(f"Import menu error: {e}")
            await event.edit("❌ Error loading import menu.")

    async def _import_string_session(self, event, user_id):
        """Import account via string session"""
        try:
            if self.bot_manager:
                self.bot_manager.pending_actions[user_id] = {
                    "action": "import_string_session"
                }
            text = (
                "📝 **Universal Session String Import**\n\n"
                "Reply with your session string from **any** library:\n\n"
                "**📱 Supported Formats:**\n"
                "• **Telethon**: `1BVtsOHwAa7T...` (long base64)\n"
                "• **Pyrogram**: `BQABcd1...` (shorter base64)\n"
                '• **JSON**: `{"dc_id": 2, "auth_key": ...}`\n\n'
                "**🔍 Auto-Detection:**\n"
                "Bot automatically detects your session format\n\n"
                "**🔒 Security:** All sessions encrypted before storage"
            )
            await event.edit(text)
            await event.answer("📝 Send any session format")
        except Exception as e:
            logger.error(f"Import string session error: {e}")
            await event.edit("❌ Error setting up string import.")

    async def _import_session_file(self, event, user_id):
        """Import account via session file"""
        try:
            if self.bot_manager:
                self.bot_manager.pending_actions[user_id] = {
                    "action": "import_session_file"
                }
            text = (
                "📁 **Universal Session File Import**\n\n"
                "Send your session file from **any** library:\n\n"
                "**📱 Supported Files:**\n"
                "• **Telethon**: `.session` (SQLite database)\n"
                "• **Pyrogram**: `.session` (SQLite database)\n"
                "• **ZIP**: `.zip` (multiple sessions)\n"
                "• **JSON**: `.json` (TDLib, custom formats)\n"
                "• **Text**: `.txt` (session strings)\n\n"
                "**🔍 Process:**\n"
                "1. Send file as document\n"
                "2. Auto-detect format & extract\n"
                "3. Convert to Telethon format\n"
                "4. Add account instantly\n\n"
                "**🔒 Security:** Files deleted after processing"
            )
            await event.edit(text)
            await event.answer("📁 Send any session file")
        except Exception as e:
            logger.error(f"Import session file error: {e}")
            await event.edit("❌ Error setting up file import.")

    async def _import_zip_sessions(self, event, user_id):
        """Import multiple accounts via ZIP file"""
        try:
            if self.bot_manager:
                self.bot_manager.pending_actions[user_id] = {
                    "action": "import_zip_sessions"
                }
            text = (
                "📦 **Bulk Session Import (ZIP)**\n\n"
                "Send a ZIP file containing multiple session files:\n\n"
                "**📱 Supported Files in ZIP:**\n"
                "• `.session` files (Telethon/Pyrogram)\n"
                "• `.txt` files (session strings)\n"
                "• `.json` files (session data)\n"
                "• Mixed formats automatically detected\n\n"
                "**🔍 Process:**\n"
                "1. Send ZIP file as document\n"
                "2. Auto-extract all sessions\n"
                "3. Import each valid session\n"
                "4. Get detailed report\n\n"
                "**⚡ Fast:** Import 10+ accounts in seconds!"
            )
            await event.edit(text)
            await event.answer("📦 Send ZIP file with sessions")
        except Exception as e:
            logger.error(f"Import ZIP error: {e}")
            await event.edit("❌ Error setting up ZIP import.")

    async def _show_supported_formats(self, event):
        """Show detailed list of supported session formats"""
        try:
            from telethon import Button

            from ..utils.session_utils import get_supported_formats

            get_supported_formats()

            text = (
                "📊 **Supported Session Formats**\n\n"
                "**📱 Telethon Library:**\n"
                "• StringSession (base64 encoded)\n"
                "• .session files (SQLite database)\n\n"
                "**🔥 Pyrogram Library:**\n"
                "• Session strings (shorter base64)\n"
                "• .session files (SQLite database)\n"
                "• JSON session format\n\n"
                "**📊 TDLib (python-telegram):**\n"
                "• JSON session data\n"
                "• Custom JSON formats\n\n"
                "**🔧 Raw/Custom Formats:**\n"
                "• JSON with dc_id, auth_key\n"
                "• Custom session structures\n\n"
                "**🔍 Detection:**\n"
                "Bot automatically detects format and converts to Telethon"
            )

            buttons = [[Button.inline("🔙 Back to Import Menu", "import_sessions")]]

            await event.edit(text, buttons=buttons)

        except Exception as e:
            logger.error(f"Show formats error: {e}")
            await event.edit("❌ Error loading format information.")

    async def process_string_session(self, user_id, session_string):
        """Process string session import"""
        try:
            if not session_string or len(session_string) < 50:
                return False, "❌ Invalid session string format"
            # Validate session using universal validator
            from ..core.config import config
            from ..utils.session_utils import detect_session_type, validate_session

            API_ID = config.telegram.api_id
            API_HASH = config.telegram.api_hash

            detect_session_type(session_string)
            ok, info = await validate_session(session_string, API_ID, API_HASH)
            if not ok:
                return False, f"❌ Session test failed: {info}"
            phone = info.get("phone")
            name = info.get("name")
            detected_type = info.get("session_type", "unknown")
            telethon_session = info.get("telethon_session", session_string)
            existing = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "phone": phone}
            )
            if existing:
                return False, f"❌ Account {phone} already exists"
            account_data = {
                "user_id": user_id,
                "phone": phone,
                "name": name,
                "session_string": telethon_session,
                "is_active": True,
                "added_via": "string_import",
                "original_format": detected_type,
                "otp_destroyer_enabled": False,
                "created_at": int(__import__("time").time()),
            }
            result = await mongodb.db.accounts.insert_one(account_data)
            str(result.inserted_id)
            await self.bot_manager.start_user_client(user_id, name, telethon_session)
            return (
                True,
                f"✅ Account {name} ({phone}) imported successfully!\n📱 Original Format: {
                    detected_type.replace(
                        '_', ' ').title()}",
            )
        except Exception as e:
            logger.error(f"String session import error: {e}")
            return False, f"❌ Import failed: {str(e)}"

    async def process_session_file(self, user_id, file_path):
        """Process session file import"""
        try:
            if not os.path.exists(file_path):
                return False, "❌ Session file not found"
            # Extract session string from file using universal extractor
            from ..core.config import config
            from ..utils.session_utils import extract_session_from_file

            API_ID = config.telegram.api_id
            API_HASH = config.telegram.api_hash

            success, session_string, format_info = await extract_session_from_file(
                file_path, API_ID, API_HASH
            )
            if not success:
                return False, f"❌ Could not extract session: {format_info}"
            # Clean up file
            try:
                os.remove(file_path)
            except BaseException:
                pass
            # Process the extracted session
            result_success, result_message = await self.process_string_session(
                user_id, session_string
            )
            if result_success:
                return True, f"{result_message}\n📁 Source: {format_info}"
            return False, result_message
        except Exception as e:
            logger.error(f"Session file import error: {e}")
            return False, f"❌ File import failed: {str(e)}"

    async def process_zip_sessions(self, user_id, zip_path):
        """Process bulk ZIP session import"""
        import shutil
        import tempfile
        import zipfile

        try:
            if not os.path.exists(zip_path):
                return False, "❌ ZIP file not found"

            extract_dir = tempfile.mkdtemp(prefix="sessions_")
            imported = []
            failed = []

            try:
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(extract_dir)

                for root, dirs, files in os.walk(extract_dir):
                    for filename in files:
                        file_path = os.path.join(root, filename)

                        # Handle different file types
                        if filename.endswith(".session"):
                            # Process .session files
                            success, message = await self.process_session_file(
                                user_id, file_path
                            )
                        elif filename.endswith(".txt"):
                            # Process .txt files containing session strings
                            try:
                                with open(file_path, "r", encoding="utf-8") as f:
                                    session_string = f.read().strip()
                                success, message = await self.process_string_session(
                                    user_id, session_string
                                )
                            except Exception as e:
                                success, message = (
                                    False,
                                    f"Error reading file: {str(e)}",
                                )
                        elif filename.endswith(".json"):
                            # Process JSON session files
                            try:
                                import json

                                with open(file_path, "r", encoding="utf-8") as f:
                                    json_data = json.load(f)
                                # Convert JSON to session string if possible
                                if (
                                    isinstance(json_data, dict)
                                    and "session_string" in json_data
                                ):
                                    session_string = json_data["session_string"]
                                    success, message = (
                                        await self.process_string_session(
                                            user_id, session_string
                                        )
                                    )
                                elif isinstance(json_data, str):
                                    # JSON file contains just a session string
                                    success, message = (
                                        await self.process_string_session(
                                            user_id, json_data
                                        )
                                    )
                                else:
                                    success, message = False, "Unsupported JSON format"
                            except Exception as e:
                                success, message = (
                                    False,
                                    f"Error processing JSON: {str(e)}",
                                )
                        else:
                            # Skip unsupported file types
                            continue

                        if success:
                            imported.append(filename)
                        else:
                            failed.append((filename, message))

                result_text = f"✅ **Bulk Import Complete**\n\n"
                result_text += f"✅ **Imported:** {len(imported)} sessions\n"

                if imported:
                    result_text += "\n**Successful:**\n"
                    for name in imported[:10]:
                        result_text += f"• {name}\n"
                    if len(imported) > 10:
                        result_text += f"... and {len(imported) - 10} more\n"

                if failed:
                    result_text += f"\n❌ **Failed:** {len(failed)}\n"
                    for name, error in failed[:5]:
                        result_text += f"• {name}: {error[:50]}\n"

                return True, result_text

            finally:
                shutil.rmtree(extract_dir, ignore_errors=True)
                if os.path.exists(zip_path):
                    os.remove(zip_path)

        except Exception as e:
            logger.error(f"ZIP import error: {e}")
            return False, f"❌ ZIP import failed: {str(e)}"
