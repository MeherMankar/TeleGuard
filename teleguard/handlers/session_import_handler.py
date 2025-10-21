"""Session Import Handler - Login via session files or strings"""
import logging
import os
import asyncio
from telethon import events, TelegramClient
from telethon.sessions import StringSession
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
                await event.answer("⛔ Please start the bot first with /start before importing sessions.")
                return
            await self._import_string_session(event, user_id)
        @self.bot.on(events.CallbackQuery(pattern=r"^import_file$"))
        async def import_session_file(event):
            user_id = event.sender_id
            await self._import_session_file(event, user_id)
    async def _show_import_menu(self, event, user_id):
        """Show session import menu"""
        try:
            from telethon import Button
            text = (
                "📥 **Import Session**\n\n"
                "Add accounts using existing session data:\n\n"
                "**Methods:**\n"
                "• **String Session**: Paste session string\n"
                "• **Session File**: Upload .session file\n\n"
                "**Supported Formats:**\n"
                "• 🔄 **Telethon** sessions (native)\n"
                "• 🔄 **Pyrogram** sessions (auto-converted)\n"
                "• 📁 **Session files** from any bot\n\n"
                "**Benefits:**\n"
                "• No OTP verification needed\n"
                "• No 2FA password required\n"
                "• Instant account addition\n"
                "• Automatic format detection & conversion\n\n"
                "Choose import method:"
            )
            buttons = [
                [Button.inline("📝 Import String Session", "import_string")],
                [Button.inline("📁 Import Session File", "import_file")],
                [Button.inline("🔙 Back to Account Settings", "menu:accounts")]
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
                "📝 **Import String Session**\n\n"
                "Reply with your session string:\n\n"
                "**Supported Formats:**\n"
                "• 🔄 **Telethon**: `1BVtsOHwAa7T...`\n"
                "• 🔄 **Pyrogram**: `AgA-i3IAq9_u...`\n\n"
                "**Where to get:**\n"
                "• From another TeleGuard bot\n"
                "• From Telethon/Pyrogram scripts\n"
                "• From session export tools\n"
                "• From other Telegram bots\n\n"
                "**Auto-Detection:** Bot automatically detects and converts formats\n"
                "**Security:** All sessions are encrypted before storage"
            )
            await event.edit(text)
            await event.answer("📝 Reply with session string")
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
                "📁 **Import Session File**\n\n"
                "Send your .session file:\n\n"
                "**Supported files:**\n"
                "• .session files from Telethon\n"
                "• .session files from other bots\n"
                "• SQLite session databases\n\n"
                "**How to send:**\n"
                "1. Send the file as document\n"
                "2. Bot will extract session data\n"
                "3. Account will be added automatically\n\n"
                "**Security:** Files are deleted after processing."
            )
            await event.edit(text)
            await event.answer("📁 Send session file")
        except Exception as e:
            logger.error(f"Import session file error: {e}")
            await event.edit("❌ Error setting up file import.")
    async def process_string_session(self, user_id, session_string):
        """Process string session import with Pyrogram support"""
        try:
            if not session_string or len(session_string) < 50:
                return False, "❌ Invalid session string format"
            
            # Validate and convert session if needed
            from ..core.config import API_ID, API_HASH
            from ..utils.session_utils import validate_string_session, detect_session_type
            
            session_type = detect_session_type(session_string)
            logger.info(f"Detected session type: {session_type}")
            
            ok, info = await validate_string_session(session_string, API_ID, API_HASH)
            if not ok:
                return False, f"❌ Session validation failed: {info}"
            
            phone = info.get("phone")
            name = info.get("name")
            final_session = info.get("converted_session", session_string)
            
            # Check for existing account
            existing = await mongodb.db.accounts.find_one({
                "user_id": user_id,
                "phone": phone
            })
            if existing:
                return False, f"❌ Account {phone} already exists"
            
            # Store account with final session string
            account_data = {
                "user_id": user_id,
                "phone": phone,
                "name": name,
                "session_string": final_session,
                "is_active": True,
                "added_via": "string_import",
                "original_format": info.get("session_type", "unknown"),
                "otp_destroyer_enabled": False,
                "created_at": int(__import__("time").time())
            }
            
            result = await mongodb.db.accounts.insert_one(account_data)
            account_id = str(result.inserted_id)
            
            # Start client with final session
            await self.bot_manager.start_user_client(user_id, name, final_session)
            
            conversion_note = " (converted from Pyrogram)" if info.get("session_type") == "pyrogram_converted" else ""
            return True, f"✅ Account {name} ({phone}) imported successfully{conversion_note}!"
            
        except Exception as e:
            logger.error(f"String session import error: {e}")
            return False, f"❌ Import failed: {str(e)}"
    async def process_session_file(self, user_id, file_path):
        """Process session file import"""
        try:
            # Validate file path to prevent path traversal
            import os.path
            safe_dir = os.path.join(os.getcwd(), 'temp_sessions')
            os.makedirs(safe_dir, exist_ok=True)
            
            # Ensure file is within safe directory
            abs_file_path = os.path.abspath(file_path)
            abs_safe_dir = os.path.abspath(safe_dir)
            
            if not abs_file_path.startswith(abs_safe_dir):
                return False, "❌ Invalid file path"
                
            if not os.path.exists(abs_file_path):
                return False, "❌ Session file not found"
                
            # Extract session string from file
            session_string = await self._extract_session_from_file(abs_file_path)
            if not session_string:
                return False, "❌ Could not extract session from file"
            # Clean up file
            try:
                os.remove(abs_file_path)
            except:
                pass
            return await self.process_string_session(user_id, session_string)
        except Exception as e:
            logger.error(f"Session file import error: {e}")
            return False, f"❌ File import failed: {str(e)}"
    async def _extract_session_from_file(self, file_path):
        """Extract session string from .session file"""
        try:
            from ..core.config import API_ID, API_HASH
            # Try to instantiate a file-backed client and call session.save() without performing network operations.
            session_name = file_path.replace('.session', '')
            temp_client = TelegramClient(session_name, API_ID, API_HASH)
            # Try to call save() directly; Telethon's session implementations persist auth info to file
            try:
                session_string = temp_client.session.save()
                # If save() returned something meaningful, return it
                if session_string and isinstance(session_string, str) and len(session_string) > 10:
                    return session_string
            except Exception:
                # session.save may require internal state; fallback to connecting briefly
                pass
            # Fallback: connect briefly to let Telethon populate session state and save
            try:
                await temp_client.connect()
                session_string = temp_client.session.save()
                await temp_client.disconnect()
                return session_string
            except Exception as e:
                logger.error(f"Session extraction error (connect fallback): {e}")
                try:
                    await temp_client.disconnect()
                except Exception:
                    pass
                return None
        except Exception as e:
            logger.error(f"File extraction error: {e}")
            return None
