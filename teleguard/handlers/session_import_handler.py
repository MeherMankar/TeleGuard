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

        @self.bot.on(events.CallbackQuery(pattern=r"^import_tdata$"))
        async def import_tdata_session(event):
            user_id = event.sender_id
            await self._import_tdata_session(event, user_id)

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
                "🔐 **Session Import Manager**\n━━━━━━━━━━━━━━━━━━━━\n\n"
                "Import existing accounts using these professional methods:\n\n"
                "📁 **Session File**\n"
                "• Upload `.session` file\n"
                "• Supports Telethon & Pyrogram\n"
                "• Instant account addition\n\n"
                "📝 **Session String**\n"
                "• Paste any session string format\n"
                "• Quick & reliable import method\n\n"
                "📦 **Bulk Import (ZIP)**\n"
                "• Upload ZIP with multiple sessions\n"
                "• Import 50+ accounts at once\n"
                "• Progress tracking & reporting\n\n"
                "📂 **TData Import (Desktop)**\n"
                "• Telegram Desktop format\n"
                "• Upload TData folder as ZIP\n"
                "• Automatic Telethon conversion\n\n"
                "**Choose your import method below:**"
            )
            buttons = [
                [
                    Button.inline("📁 Session File", "import_file"),
                    Button.inline("📝 Session String", "import_string"),
                ],
                [
                    Button.inline("📦 Bulk Import (ZIP)", "import_zip"),
                    Button.inline("📂 TData Import", "import_tdata"),
                ],
                [Button.inline("📊 Supported Formats Info", "import_formats")],
                [Button.inline("🔙 Back to Main Menu", "menu:main")],
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

    async def _import_tdata_session(self, event, user_id):
        """Set up TData ZIP import"""
        try:
            if self.bot_manager:
                self.bot_manager.pending_actions[user_id] = {
                    "action": "import_tdata_session"
                }
            text = (
                "📂 **TData Import Manager**\n━━━━━━━━━━━━━━━━━━━━\n\n"
                "**Telegram Desktop (TData) Import:**\n\n"
                "1️⃣ Create a ZIP file containing your `tdata` folder\n"
                "2️⃣ Make sure the `key_datas` file is included\n"
                "3️⃣ Send the ZIP file as a **Document**\n\n"
                "**⚠️ Note:** Conversion requires a few seconds. "
                "The bot will automatically detect account info.\n\n"
                "📥 **Ready! Please send your TData ZIP file:**"
            )
            await event.edit(text, buttons=[[Button.inline("🔙 Cancel", "import_sessions")]])
        except Exception as e:
            logger.error(f"TData import setup error: {e}")
            await event.edit("❌ Error setting up TData import.")

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

    async def process_zip_sessions(self, user_id, zip_path, status_callback=None):
        """Process bulk ZIP session import with optional progress updates"""
        import shutil
        import tempfile
        import zipfile
        import time

        try:
            if not os.path.exists(zip_path):
                return False, "❌ ZIP file not found"

            extract_dir = tempfile.mkdtemp(prefix="bulk_import_")
            imported = []
            failed = []
            
            if status_callback:
                await status_callback("📦 **ZIP Analysis...**")

            try:
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    all_files = zip_ref.namelist()
                    zip_ref.extractall(extract_dir)

                session_files = [f for f in all_files if f.endswith(('.session', '.txt', '.json')) and not f.startswith('__')]
                total = len(session_files)
                
                if total == 0:
                    return False, "❌ No valid session files found in ZIP archive."

                for i, filename in enumerate(session_files, 1):
                    file_path = os.path.join(extract_dir, filename)
                    
                    if status_callback and i % 5 == 0:
                        await status_callback(f"⏳ **Importing Accounts...**\n━━━━━━━━━━━━\n🔄 Progress: {i}/{total}\n📱 Current: `{filename}`")

                    # Handle different file types
                    if filename.endswith(".session"):
                        success, message = await self.process_session_file(user_id, file_path)
                    elif filename.endswith(".txt"):
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                session_string = f.read().strip()
                            success, message = await self.process_string_session(user_id, session_string)
                        except Exception as e:
                            success, message = False, str(e)
                    elif filename.endswith(".json"):
                        try:
                            import json
                            with open(file_path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            session_str = data.get("session_string") if isinstance(data, dict) else data if isinstance(data, str) else None
                            if session_str:
                                success, message = await self.process_string_session(user_id, session_str)
                            else:
                                success, message = False, "No session_string in JSON"
                        except Exception as e:
                            success, message = False, str(e)
                    else:
                        continue

                    if success:
                        imported.append(filename)
                    else:
                        failed.append((filename, message))
                    
                    # Prevent flood
                    if total > 20:
                        await asyncio.sleep(0.1)

                result_text = (
                    "📊 **Bulk Import Final Report**\n━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"✅ **Total Imported:** {len(imported)}\n"
                    f"❌ **Failed Attempts:** {len(failed)}\n\n"
                )

                if imported:
                    result_text += "**Successful Imports (Last 5):**\n"
                    for name in imported[-5:]:
                        result_text += f"• `{name}`\n"
                
                if failed:
                    result_text += "\n**Errors (Last 3):**\n"
                    for name, error in failed[-3:]:
                        result_text += f"• `{name}`: {error[:60]}...\n"

                return True, result_text

            finally:
                shutil.rmtree(extract_dir, ignore_errors=True)
                if os.path.exists(zip_path):
                    os.remove(zip_path)

        except Exception as e:
            logger.error(f"ZIP import error: {e}")
            return False, f"❌ ZIP import failed: {str(e)}"

    async def process_tdata_import(self, user_id, zip_path, status_callback=None):
        """Process TData ZIP import with automatic conversion"""
        import shutil
        import tempfile
        import zipfile
        from ..utils.session_converter import SessionConverter

        try:
            if status_callback:
                await status_callback("📂 **Analyzing TData ZIP...**")
            
            extract_dir = tempfile.mkdtemp(prefix="tdata_import_")
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                # Find TData folder
                tdata_path = None
                for root, dirs, files in os.walk(extract_dir):
                    if 'key_datas' in files:
                        tdata_path = root
                        break
                
                if not tdata_path:
                    # Try another check - sometimes tdata is the folder name
                    for root, dirs, files in os.walk(extract_dir):
                        if root.endswith('tdata'):
                            tdata_path = root
                            break
                
                if not tdata_path:
                    return False, "❌ TData folder not found in ZIP. Ensure it contains a `tdata` folder with `key_datas`."

                if status_callback:
                    await status_callback("⚙️ **Converting TData to Telethon...**\nThis may take a few seconds.")

                # Convert TData to Telethon
                sessions_output = os.path.join(extract_dir, "converted_sessions")
                os.makedirs(sessions_output, exist_ok=True)
                
                success, result = await SessionConverter.tdata_to_telethon(tdata_path, proxy=None, output_dir=sessions_output)
                
                if not success:
                    return False, f"❌ Conversion failed: {result}"

                # The result should be the path to the .session file
                if os.path.exists(result):
                    if status_callback:
                        await status_callback("✅ **Conversion Successful!**\nFinalizing account addition...")
                    
                    return await self.process_session_file(user_id, result)
                else:
                    return False, "❌ Converted session file not found."

            finally:
                shutil.rmtree(extract_dir, ignore_errors=True)
                if os.path.exists(zip_path):
                    os.remove(zip_path)

        except Exception as e:
            logger.error(f"TData processing error: {e}")
            return False, f"❌ TData process failed: {str(e)}"
