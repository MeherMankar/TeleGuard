"""Session Export Handler - Extract sessions from existing accounts"""
import logging
import os
import asyncio
import time
from datetime import datetime
from telethon import events
from telethon.sessions import StringSession
from telethon import TelegramClient
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)
class SessionExportHandler:
    def __init__(self, bot_manager):
        self.bot = bot_manager.bot
        self.bot_manager = bot_manager
        self.user_clients = bot_manager.user_clients
    def register_handlers(self):
        """Register session export handlers - DEPRECATED"""
        # All session functionality moved to session_login_handler.py
        pass
    async def _show_export_menu(self, event, user_id):
        """Show session type selection first"""
        try:
            from telethon import Button
            buttons = [
                [Button.inline("📝 String Session", "session_type:string")],
                [Button.inline("📁 File Session (.session)", "session_type:file")],
                [Button.inline("🔙 Back", "menu:accounts")]
            ]
            await event.edit(
                "✨ **Fresh Session Creation**\n\n"
                "📋 **Step 1: Choose Session Type**\n\n"
                "Select the format you want to export:",
                buttons=buttons
            )
        except Exception:
            await event.edit("❌ Error loading export menu.")
    
    async def _show_account_selection(self, event, user_id, session_type):
        """Show account selection after type is chosen"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id, "is_active": True}).to_list(length=None)
            if not accounts:
                await event.edit("❌ No active accounts found.")
                return
            
            if not hasattr(self.bot_manager, 'session_selections'):
                self.bot_manager.session_selections = {}
            if user_id not in self.bot_manager.session_selections:
                self.bot_manager.session_selections[user_id] = {'accounts': set(), 'type': session_type}
            else:
                self.bot_manager.session_selections[user_id]['type'] = session_type
            
            from telethon import Button
            buttons = []
            selected_accounts = self.bot_manager.session_selections[user_id]['accounts']
            
            for account in accounts:
                account_name = account.get('name') or account.get('phone', 'Unknown')
                is_selected = account_name in selected_accounts
                prefix = "✅" if is_selected else "📱"
                buttons.append([Button.inline(f"{prefix} {account_name}", f"toggle_session:{account_name}")])
            
            buttons.append([Button.inline("✅ Done (Create Sessions)", "create_selected_sessions")])
            buttons.append([Button.inline("🔄 Clear Selection", "clear_session_selection")])
            buttons.append([Button.inline("🔙 Back", "export_sessions")])
            
            selected_count = len(selected_accounts)
            type_text = "String" if session_type == 'string' else "File"
            selection_text = f"\n\n📋 **Selected:** {selected_count} account(s)" if selected_count > 0 else ""
            
            await event.edit(
                f"✨ **Fresh Session Creation**\n\n"
                f"📋 **Step 2: Select Accounts**\n"
                f"📝 **Type:** {type_text}\n\n"
                "Select accounts to create sessions:\n"
                "• Click to select/deselect\n"
                "• Press Done when ready\n"
                "• Multiple = ZIP file"
                f"{selection_text}",
                buttons=buttons
            )
        except Exception:
            await event.edit("❌ Error loading accounts.")
    async def _toggle_account_selection(self, event, user_id, account_name):
        """Toggle account selection"""
        try:
            if not hasattr(self.bot_manager, 'session_selections') or user_id not in self.bot_manager.session_selections:
                await event.answer("❌ Session expired. Please start again.")
                return
            
            selected_data = self.bot_manager.session_selections[user_id]
            selected_accounts = selected_data['accounts']
            session_type = selected_data['type']
            
            if account_name in selected_accounts:
                selected_accounts.remove(account_name)
            else:
                selected_accounts.add(account_name)
            
            await self._show_account_selection(event, user_id, session_type)
        except Exception:
            await event.edit("❌ Error toggling selection.")
    
    async def _clear_session_selection(self, event, user_id):
        """Clear all selected accounts"""
        try:
            if hasattr(self.bot_manager, 'session_selections') and user_id in self.bot_manager.session_selections:
                session_type = self.bot_manager.session_selections[user_id]['type']
                self.bot_manager.session_selections[user_id]['accounts'].clear()
                await self._show_account_selection(event, user_id, session_type)
        except Exception:
            await event.edit("❌ Error clearing selection.")
    
    async def _create_selected_sessions(self, event, user_id):
        """Create sessions for all selected accounts"""
        try:
            if not hasattr(self.bot_manager, 'session_selections') or user_id not in self.bot_manager.session_selections:
                await event.edit("❌ No accounts selected.")
                return
            
            selected_data = self.bot_manager.session_selections[user_id]
            selected_accounts = list(selected_data['accounts'])
            session_type = selected_data['type']
            
            if not selected_accounts:
                await event.edit("❌ No accounts selected. Please select at least one account.")
                return
            
            self.bot_manager.session_selections[user_id]['accounts'].clear()
            
            if len(selected_accounts) == 1:
                await self._create_fresh_session(event, user_id, selected_accounts[0], format_type=session_type)
            else:
                await self._create_batch_sessions(event, user_id, selected_accounts, session_type)
                
        except Exception as e:
            await event.edit(f"❌ Error creating sessions: {str(e)}")
    
    async def _create_batch_sessions(self, event, user_id, account_names, session_type):
        """Create sessions for multiple accounts and send as ZIP"""
        try:
            type_text = "String" if session_type == 'string' else "File"
            await event.edit(
                f"🔄 **Creating {len(account_names)} Sessions**\n\n"
                f"📝 **Type:** {type_text}\n"
                f"📋 **Accounts:** {', '.join(account_names[:3])}{'...' if len(account_names) > 3 else ''}\n\n"
                f"⏳ Starting batch creation...\n"
                f"You will receive OTP codes for each account."
            )
            
            if not hasattr(self.bot_manager, 'batch_sessions'):
                self.bot_manager.batch_sessions = {}
            
            self.bot_manager.batch_sessions[user_id] = {
                'accounts': account_names.copy(),
                'completed': {},
                'current_index': 0,
                'total': len(account_names),
                'session_type': session_type
            }
            
            await self._process_next_batch_account(user_id)
            
        except Exception as e:
            await event.edit(f"❌ Error starting batch: {str(e)}")
    
    async def _process_next_batch_account(self, user_id):
        """Process next account in batch session creation"""
        try:
            if not hasattr(self.bot_manager, 'batch_sessions') or user_id not in self.bot_manager.batch_sessions:
                return
            
            batch_data = self.bot_manager.batch_sessions[user_id]
            current_index = batch_data['current_index']
            accounts = batch_data['accounts']
            
            if current_index >= len(accounts):
                # All accounts processed - create ZIP
                await self._send_batch_sessions_zip(user_id)
                return
            
            account_name = accounts[current_index]
            
            # Send status update
            await self.bot.send_message(
                user_id,
                f"🔄 **Processing Account {current_index + 1}/{len(accounts)}**\n\n"
                f"📱 **Current:** {account_name}\n\n"
                f"Starting authentication..."
            )
            
            # Create session for current account
            await self._create_fresh_session_batch(user_id, account_name)
            
        except Exception as e:
            logger.error(f"Error processing batch account: {e}")
            await self.bot.send_message(user_id, f"❌ Error processing {account_name}: {str(e)}")
    
    async def _send_batch_sessions_zip(self, user_id):
        """Send all completed sessions as ZIP file"""
        try:
            if not hasattr(self.bot_manager, 'batch_sessions') or user_id not in self.bot_manager.batch_sessions:
                return
            
            batch_data = self.bot_manager.batch_sessions[user_id]
            completed_sessions = batch_data['completed']
            session_type = batch_data.get('session_type', 'file')
            
            if not completed_sessions:
                await self.bot.send_message(user_id, "❌ No sessions created.")
                return
            
            import zipfile
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
                zip_path = temp_zip.name
            
            with zipfile.ZipFile(zip_path, 'w') as zip_file:
                for account_name, session_data in completed_sessions.items():
                    ext = '.txt' if session_type == 'string' else '.session'
                    zip_file.writestr(f"{account_name}{ext}", session_data)
            
            with open(zip_path, 'rb') as zip_file:
                zip_data = zip_file.read()
            
            from telethon.tl.types import DocumentAttributeFilename
            type_text = "String" if session_type == 'string' else "File"
            await self.bot.send_message(
                user_id,
                f"📦 **Batch Export Complete**\n\n"
                f"✅ **Created:** {len(completed_sessions)} sessions\n"
                f"📝 **Type:** {type_text}\n"
                f"📁 **Format:** ZIP\n\n"
                f"**Accounts:**\n" + "\n".join([f"• {name}" for name in list(completed_sessions.keys())[:10]]) + 
                (f"\n... and {len(completed_sessions) - 10} more" if len(completed_sessions) > 10 else "") + "\n\n"
                f"⚠️ **Keep secure!**",
                file=zip_data,
                attributes=[DocumentAttributeFilename(f"sessions_{int(time.time())}.zip")]
            )
            
            os.remove(zip_path)
            del self.bot_manager.batch_sessions[user_id]
            
        except Exception as e:
            logger.error(f"Batch ZIP error: {e}")
            await self.bot.send_message(user_id, f"❌ ZIP error: {str(e)}")
    async def _create_fresh_session_batch(self, user_id, account_name):
        """Create fresh session for batch processing"""
        if not hasattr(self.bot_manager, 'batch_sessions') or user_id not in self.bot_manager.batch_sessions:
            return
        batch_data = self.bot_manager.batch_sessions[user_id]
        session_type = batch_data.get('session_type', 'file')
        await self._create_fresh_session(None, user_id, account_name, format_type=session_type)
    
    async def _export_all_sessions(self, event, user_id):
        """Show bulk fresh session creation info"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                await event.edit("❌ No accounts found.")
                return
            
            from telethon import Button
            message = (
                f"📦 **Bulk Fresh Session Creation**\n\n"
                f"📊 **Available Accounts:** {len(accounts)}\n\n"
                f"🔐 **Security Notice:**\n"
                f"Bulk session creation requires individual OTP authentication for each account.\n\n"
                f"⚠️ **Important:**\n"
                f"Each account will need separate OTP verification.\n"
                f"This ensures maximum security for all sessions.\n\n"
                f"**Recommendation:**\n"
                f"Create sessions individually for better control."
            )
            
            buttons = [
                [Button.inline("📱 Create Individual Sessions", "export_sessions")],
                [Button.inline("🔙 Back to Export Menu", "export_sessions")]
            ]
            await event.edit(message, buttons=buttons)
        except Exception:
            await event.edit("❌ Error loading bulk export info")
    async def _send_string_session(self, event, user_id, account_name):
        """Send string session format"""
        try:
            await self._create_fresh_session(event, user_id, account_name, format_type='string')
            return
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            phone = account.get('phone', 'Unknown') if account else 'Unknown'
            from telethon import Button
            message = (
                f"📝 **String Session - {account_name}**\n\n"
                f"📱 **Account:** {account_name}\n"
                f"📞 **Phone:** {phone}\n"
                f"🕑 **Generated:** {asyncio.get_event_loop().time()}\n\n"
                f"**Session String:**\n"
                f"```\n{session_string}\n```\n\n"
                f"**Python Usage:**\n"
                f"```python\n"
                f"from telethon import TelegramClient\n"
                f"from telethon.sessions import StringSession\n\n"
                f"client = TelegramClient(\n"
                f"    StringSession('{session_string}'),\n"
                f"    api_id, api_hash\n"
                f")\n"
                f"await client.start()\n"
                f"```\n\n"
                f"⚠️ **Keep this session string secure!**"
            )
            buttons = [
                [Button.inline("🔄 Generate New String", f"export_string:{account_name}")],
                [Button.inline("🔙 Back to Options", f"export_session:{account_name}")]
            ]
            await event.edit(message, buttons=buttons)
            # Send login notification
            await self._send_login_notification(user_id, account_name, "String session exported")
        except Exception:
            await event.edit("❌ Error exporting string session")
    async def _send_file_session(self, event, user_id, account_name):
        """Send .session file format"""
        try:
            await self._create_fresh_session(event, user_id, account_name, format_type='file')
            return
            import tempfile
            temp_session_path = f"temp_{account_name}_{user_id}_{int(asyncio.get_event_loop().time())}.session"
            try:
                from telethon import TelegramClient
                from telethon.sessions import StringSession
                from ..core.config import API_ID, API_HASH
                temp_client = TelegramClient(temp_session_path, API_ID, API_HASH)
                temp_client.session = StringSession(session_string)
                await temp_client.connect()
                await temp_client.disconnect()
                # Read the generated .session file
                session_file_data = None
                if os.path.exists(temp_session_path):
                    with open(temp_session_path, 'rb') as f:
                        session_file_data = f.read()
                    os.remove(temp_session_path)  # Clean up
                if session_file_data:
                    account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
                    phone = account.get('phone', 'Unknown') if account else 'Unknown'
                    # Send file
                    await event.respond(
                        f"📁 **Session File - {account_name}**\n\n"
                        f"📱 **Account:** {account_name}\n"
                        f"📞 **Phone:** {phone}\n"
                        f"🕑 **Generated:** Fresh session file\n\n"
                        f"**Usage:** Use this file with Telethon:\n"
                        f"```python\n"
                        f"from telethon import TelegramClient\n\n"
                        f"client = TelegramClient('{account_name}', api_id, api_hash)\n"
                        f"await client.start()\n"
                        f"```\n\n"
                        f"⚠️ **Keep this file secure!**",
                        file=session_file_data,
                        attributes=[DocumentAttributeFilename(f"{account_name}.session")]
                    )
                    from telethon import Button
                    from telethon.tl.types import DocumentAttributeFilename
                    buttons = [
                        [Button.inline("🔄 Generate New File", f"export_file:{account_name}")],
                        [Button.inline("🔙 Back to Options", f"export_session:{account_name}")]
                    ]
                    await event.edit("✅ **Session file sent above!**", buttons=buttons)
                    # Send login notification
                    await self._send_login_notification(user_id, account_name, "Session file exported")
                else:
                    await event.edit("❌ Failed to generate session file.")
            except Exception:
                await event.edit("❌ Error generating session file")
        except Exception:
            await event.edit("❌ Error exporting session file")
    async def _send_login_notification(self, user_id, account_name, action):
        """Send login notification to user"""
        try:
            import time
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            notification = (
                f"🔔 **Login Activity Alert**\n\n"
                f"📱 **Account:** {account_name}\n"
                f"🕑 **Time:** {timestamp}\n"
                f"⚙️ **Action:** {action}\n"
                f"📍 **Location:** Session Export\n\n"
                f"ℹ️ This is a security notification for session export activity."
            )
            await self.bot.send_message(user_id, notification)
        except Exception:
            pass
    async def _copy_string_handler(self, event, account_name):
        """Handle copy string callback"""
        try:
            user_id = event.sender_id
            user_clients = self.user_clients.get(user_id, {})
            client = user_clients.get(account_name)
            if client and client.is_connected():
                session_string = client.session.save()
                await event.answer(f"Session string copied for {account_name}!", alert=True)
            else:
                await event.answer("❌ Account not connected!", alert=True)
        except Exception:
            await event.answer("❌ Error copying session string!", alert=True)
    async def _create_fresh_session(self, event, user_id, account_name, format_type='both'):
        """Create fresh session by re-authenticating existing account"""
        try:
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            if not account:
                await event.edit(f"❌ Account {account_name} not found.")
                return
            phone = account.get('phone')
            if not phone:
                await event.edit(f"❌ No phone number found for {account_name}.")
                return
            
            # Validate and fix phone number format
            if not phone.startswith('+'):
                # Try to add + prefix if it's missing
                if phone.isdigit() and len(phone) >= 10:
                    phone = '+' + phone
                else:
                    await event.edit(f"❌ Invalid phone number format for {account_name}. Expected format: +1234567890")
                    return
            
            # Additional validation
            if len(phone) < 10 or not phone[1:].isdigit():
                await event.edit(f"❌ Invalid phone number format for {account_name}. Expected format: +1234567890")
                return
            await event.edit(
                f"🔄 **Creating Fresh Session - {account_name}**\n\n"
                f"📞 **Phone:** {phone}\n\n"
                f"Starting authentication process...\n"
                f"You will receive an OTP code."
            )
            from telethon import TelegramClient
            from ..core.config import config
            API_ID = config.telegram.api_id
            API_HASH = config.telegram.api_hash
            # Use an in-memory StringSession for fresh-session flows so
            # calling `client.session.save()` returns a valid string.
            temp_client = TelegramClient(StringSession(), API_ID, API_HASH)
            try:
                # Connect to Telegram
                await temp_client.connect()
                if not temp_client.is_connected():
                    await event.edit("❌ Failed to connect to Telegram servers. Please try again later.")
                    return
                
                # Prepare in-memory pending marker BEFORE requesting code to
                # avoid race where the OTP Destroyer might receive the service
                # message before our in-memory marker is set.
                previous_destroyer_state = False
                try:
                    acct = await mongodb.db.accounts.find_one(
                        {"user_id": user_id, "name": account_name}
                    )
                    if acct:
                        previous_destroyer_state = acct.get("otp_destroyer_enabled", False)
                except Exception:
                    pass
                if not hasattr(self.bot_manager, 'pending_fresh_sessions'):
                    self.bot_manager.pending_fresh_sessions = {}
                # Insert an initial pending entry so destroyer checks can see it
                self.bot_manager.pending_fresh_sessions[user_id] = {
                    'client': temp_client,
                    'phone': phone,
                    'account_name': account_name,
                    'sent_code': None,
                    'chat_id': event.chat_id,
                    'previous_destroyer_state': previous_destroyer_state,
                    'format_type': format_type,
                }
                # Disable OTP destroyer and forwarding during session creation
                try:
                    # Store original OTP settings
                    original_destroyer = account.get('otp_destroyer_enabled', False)
                    original_forward = account.get('otp_forward_enabled', False)
                    
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {"$set": {
                            "pending_fresh_session": True,
                            "session_creation_in_progress": True,
                            "otp_destroyer_enabled": False,  # Disable destroyer during session creation
                            "otp_forward_enabled": False,   # Disable forwarding to prevent code sharing
                            "original_destroyer_state": original_destroyer,
                            "original_forward_state": original_forward
                        }}
                    )
                    
                    # Set pending action for additional protection
                    self.bot_manager.pending_actions[user_id] = {
                        "action": "session_creation",
                        "phone": phone,
                        "account_name": account_name
                    }
                    
                    logger.info(f"Session creation started for {phone} - OTP destroyer and forwarding disabled")
                except Exception:
                    pass
                # Request the OTP from Telegram and store phone_code_hash
                try:
                    sent_code = await temp_client.send_code_request(phone)
                    logger.info(f"OTP request sent successfully for {phone}")
                    # Create a cross-process OTP protection entry so other
                    # processes (OTP destroyer) will skip invalidation for any
                    # codes sent to this phone for a short window.
                    try:
                        # Write a phone-level wildcard protection so other processes
                        # skip invalidating any code sent to this phone for 60s.
                        await mongodb.db.otp_protections.update_one(
                            {"phone": phone, "wildcard": True},
                            {"$set": {
                                "phone": phone,
                                "wildcard": True,
                                "expires_at": int(time.time()) + 60,
                                "expires_at_dt": datetime.utcfromtimestamp(int(time.time()) + 60)
                            }},
                            upsert=True,
                        )
                    except Exception:
                        # non-fatal if DB write fails
                        logger.exception("Failed to write otp_protection entry")
                    
                except Exception as send_err:
                    # Clean up and surface a detailed error
                    logger.exception(f"send_code_request failed for {phone}: {send_err}")
                    try:
                        await temp_client.disconnect()
                    except Exception:
                        pass
                    # Clear protection flags and restore OTP settings
                    try:
                        await mongodb.db.accounts.update_one(
                            {"user_id": user_id, "name": account_name},
                            {
                                "$unset": {
                                    "pending_fresh_session": "",
                                    "session_creation_in_progress": "",
                                    "original_destroyer_state": "",
                                    "original_forward_state": ""
                                },
                                "$set": {
                                    "otp_destroyer_enabled": previous_destroyer_state,
                                    "otp_forward_enabled": False  # Reset to safe state
                                }
                            }
                        )
                        self.bot_manager.pending_actions.pop(user_id, None)
                    except Exception:
                        logger.exception("Failed to clear protection flags after send_code_request failure")
                    self.bot_manager.pending_fresh_sessions.pop(user_id, None)
                    
                    # Provide more specific error messages
                    error_type = type(send_err).__name__
                    error_msg = str(send_err)
                    
                    if "FloodWaitError" in error_type or "wait of" in error_msg:
                        await event.edit(f"⏰ Rate limited. Please wait before requesting OTP for this number again.")
                    elif "PhoneNumberBannedError" in error_type:
                        await event.edit(f"❌ This phone number is banned from Telegram.")
                    elif "PhoneNumberInvalidError" in error_type:
                        await event.edit(f"❌ Invalid phone number format.")
                    elif "AuthRestartError" in error_type:
                        await event.edit(f"❌ Telegram server error. Please try again in a few minutes.")
                    elif "ConnectionError" in error_type or "Cannot send requests while disconnected" in error_msg:
                        await event.edit(f"❌ Connection error. Please check your internet connection and try again.")
                    else:
                        await event.edit(f"❌ Error starting authentication: {error_type}: {error_msg}")
                    return
                try:
                    self.bot_manager.pending_fresh_sessions[user_id]['sent_code'] = sent_code
                except Exception:
                    logger.exception("Failed to save sent_code into pending_fresh_sessions")
                await event.edit(
                    f"📱 **OTP Sent - {account_name}**\n\n"
                    f"📞 **Phone:** {phone}\n\n"
                    f"✅ **OTP code sent to your Telegram account**\n\n"
                    f"🔍 **Checking for recent OTP messages...**\n\n"
                    f"Please send the OTP code you received.\n"
                    f"Format: Just the numbers (e.g., 12345)\n\n"
                    f"⏰ **Waiting for your OTP...**"
                )
                
                # Try to fetch recent OTP messages
                try:
                    if hasattr(self.bot_manager, 'message_handlers'):
                        found_otp = await self.bot_manager.message_handlers.fetch_recent_otp(user_id)
                        if found_otp:
                            return  # OTP was found and processed
                except Exception as fetch_err:
                    logger.error(f"Error fetching recent OTP: {fetch_err}")

                # Store pending session creation
                if not hasattr(self.bot_manager, 'pending_fresh_sessions'):
                    self.bot_manager.pending_fresh_sessions = {}
                # Store previous destroyer state so we can restore it later
                self.bot_manager.pending_fresh_sessions[user_id] = {
                    'client': temp_client,
                    'phone': phone,
                    'account_name': account_name,
                    'sent_code': sent_code,
                    'chat_id': event.chat_id,
                    'previous_destroyer_state': previous_destroyer_state,
                    'format_type': format_type,
                }
            except Exception as e:
                # Capture full traceback and return a clearer message
                import traceback
                tb = traceback.format_exc()
                logger.error(f"Fresh session startup exception for {account_name}: {e}\n{tb}")
                try:
                    await temp_client.disconnect()
                except Exception:
                    pass
                # Clear protection flags and restore OTP settings
                try:
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {
                            "$unset": {
                                "pending_fresh_session": "",
                                "session_creation_in_progress": "",
                                "original_destroyer_state": "",
                                "original_forward_state": ""
                            },
                            "$set": {
                                "otp_destroyer_enabled": previous_destroyer_state,
                                "otp_forward_enabled": False  # Reset to safe state
                            }
                        }
                    )
                    self.bot_manager.pending_actions.pop(user_id, None)
                except Exception:
                    logger.exception("Failed to clear protection flags after fresh session startup failure")
                self.bot_manager.pending_fresh_sessions.pop(user_id, None)
                # Provide detailed error information
                error_details = (
                    f"❌ **Authentication Startup Failed**\n\n"
                    f"**Error Details:**\n"
                    f"• Error Type: {type(e).__name__}\n"
                    f"• Error Message: {str(e)}\n"
                    f"• Account: {account_name}\n"
                    f"• Phone: {phone}\n\n"
                    f"**Common Causes:**\n"
                    f"• Network connectivity issues\n"
                    f"• Telegram API rate limiting\n"
                    f"• Invalid API credentials\n"
                    f"• Account restrictions\n\n"
                    f"**Solutions:**\n"
                    f"• Check internet connection\n"
                    f"• Wait a few minutes and try again\n"
                    f"• Verify API_ID and API_HASH are correct\n"
                    f"• Contact support if issue persists"
                )
                await event.edit(error_details)
                return
        except Exception as e:
            await event.edit(f"❌ Error creating fresh session: {str(e)}")
    async def process_fresh_session_otp(self, user_id, otp_code):
        """Process OTP for fresh session creation"""
        try:
            if not hasattr(self.bot_manager, 'pending_fresh_sessions'):
                return False
            session_data = self.bot_manager.pending_fresh_sessions.get(user_id)
            if not session_data:
                return False
            client = session_data['client']
            phone = session_data['phone']
            account_name = session_data['account_name']
            try:
                # Sign in with OTP
                sent_code = session_data.get('sent_code')
                authenticated = False
                
                try:
                    # Ensure client is still connected before sign in
                    if not client.is_connected():
                        await client.connect()
                    
                    # Use explicit keyword args to avoid positional mismatches
                    phone_code_hash = None
                    if sent_code and hasattr(sent_code, 'phone_code_hash'):
                        phone_code_hash = getattr(sent_code, 'phone_code_hash')
                    
                    result = await client.sign_in(phone=phone, code=otp_code, phone_code_hash=phone_code_hash)
                    logger.info(f"Sign-in result for {account_name}: {type(result).__name__}")
                    authenticated = True
                    
                except Exception as e:
                    # Handle 2FA requirement
                    if type(e).__name__ == "SessionPasswordNeededError":
                        from ..core.database_manager import db_manager
                        # Try to get stored password by account ID first
                        account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
                        stored_password = None
                        if account:
                            stored_password = await db_manager.get_2fa_password(user_id, str(account['_id']))
                        # Fallback to phone lookup
                        if not stored_password:
                            stored_password = await db_manager.get_2fa_password_by_phone(user_id, phone)
                        
                        if stored_password:
                            try:
                                # Ensure client is still connected
                                if not client.is_connected():
                                    await client.connect()
                                # Use stored 2FA password
                                await client.sign_in(password=stored_password)
                                authenticated = True
                            except Exception as pwd_err:
                                logger.warning(f"Stored 2FA password failed: {pwd_err}")
                                account = await mongodb.db.accounts.find_one({"user_id": user_id, "phone": phone})
                                if account:
                                    await db_manager.remove_2fa_password(user_id, str(account['_id']))
                                # Ask user for new 2FA password
                                await self.bot.send_message(
                                    user_id,
                                    f"🔐 **2FA Password Required - {account_name}**\n\n"
                                    f"Your stored 2FA password is invalid. Please send your current 2FA password.\n\n"
                                    f"💡 **Tip:** We'll securely store your new password for future use."
                                )
                                # Store pending 2FA request
                                session_data['waiting_for_2fa'] = True
                                self.bot_manager.pending_fresh_sessions[user_id] = session_data
                                return False
                        else:
                            # Ask user for 2FA password
                            await self.bot.send_message(
                                user_id,
                                f"🔐 **2FA Password Required - {account_name}**\n\n"
                                f"Your account has 2FA enabled. Please send your 2FA password.\n\n"
                                f"💡 **Tip:** After successful login, we'll securely store your 2FA password for future use."
                            )
                            # Store pending 2FA request
                            session_data['waiting_for_2fa'] = True
                            self.bot_manager.pending_fresh_sessions[user_id] = session_data
                            return False
                    else:
                        logger.error(f"Sign-in failed for {account_name}: {type(e).__name__}: {e}")
                        raise e
                
                # Only proceed if authentication was successful
                if not authenticated:
                    logger.error(f"Authentication failed for {account_name}")
                    raise Exception("Authentication failed")
                
                logger.info(f"Authentication successful for {account_name}, generating session...")
                
                # Ensure we have a valid session before saving
                if not client.is_connected():
                    await client.connect()
                
                # Wait a moment for the session to be properly established
                await asyncio.sleep(1)
                
                # Verify we're properly authenticated by getting user info
                try:
                    me = await client.get_me()
                    # Safe logging without Unicode characters
                    first_name = (me.first_name or '').encode('ascii', errors='replace').decode('ascii')
                    last_name = (me.last_name or '').encode('ascii', errors='replace').decode('ascii')
                    username = (me.username or 'no_username').encode('ascii', errors='replace').decode('ascii')
                    logger.info(f"Authenticated as: {first_name} {last_name} (@{username})")
                except Exception as e:
                    logger.error(f"Failed to get user info after authentication: {e}")
                    raise Exception("Authentication verification failed")
                
                fresh_session = None
                try:
                    fresh_session = client.session.save()
                except Exception as e:
                    logger.warning(f"client.session.save() raised when generating session string: {e}")

                # If save() did not return a usable string, try to construct a
                # StringSession-backed client and copy auth state (dc_id/auth_key).
                if not fresh_session or str(fresh_session).strip() == '' or str(fresh_session) in ('None', 'null'):
                    try:
                        logger.info("Attempting to create StringSession fallback from authenticated client state")
                        string_client = TelegramClient(StringSession(), API_ID, API_HASH)
                        # copy DC/auth_key from the authenticated client session
                        try:
                            string_client.session.set_dc(
                                client.session.dc_id,
                                client.session.server_address,
                                client.session.port,
                            )
                            string_client.session.auth_key = client.session.auth_key
                        except Exception as copy_err:
                            logger.warning(f"Failed to copy session state to StringSession client: {copy_err}")
                        # Saving the StringSession should produce a valid session string
                        fresh_session = string_client.session.save()
                        logger.info("StringSession fallback generated")
                    except Exception as ss_err:
                        logger.error(f"StringSession fallback failed: {ss_err}")

                # Validate session string - it should be a non-empty string
                if not fresh_session or str(fresh_session).strip() == '' or str(fresh_session) == 'None':
                    logger.error(f"Invalid session string generated for {account_name}: '{fresh_session}'")
                    raise Exception("Failed to generate valid session string")
                
                safe_account_name = account_name.encode('ascii', errors='replace').decode('ascii')
                logger.info(f"Generated session string for {safe_account_name}: {len(fresh_session)} characters")
                from telethon import TelegramClient
                from telethon.sessions import StringSession
                from ..core.config import config
                API_ID = config.telegram.api_id
                API_HASH = config.telegram.api_hash
                
                # Create session file using the fresh session string
                session_file_data = None
                if format_type in ['file', 'both']:
                    import tempfile
                    
                    try:
                        logger.info(f"Creating session file for {account_name}...")
                        
                        # Create temporary session file using Telethon's built-in method
                        with tempfile.NamedTemporaryFile(suffix='.session', delete=False) as temp_file:
                            temp_session_path = temp_file.name
                        
                        # Create a new client with the fresh session string and save as file
                        file_client = TelegramClient(temp_session_path, API_ID, API_HASH)
                        file_client.session = StringSession(fresh_session)
                        file_client.session.save()
                        
                        # Read the session file
                        if os.path.exists(temp_session_path):
                            with open(temp_session_path, 'rb') as f:
                                session_file_data = f.read()
                            logger.info(f"Session file created: {len(session_file_data)} bytes")
                        
                        # Cleanup
                        os.remove(temp_session_path)
                        
                    except Exception as e:
                        logger.error(f"Session file creation error: {e}")
                        session_file_data = None
                format_type = session_data.get('format_type', 'both')
                # Send based on requested format
                if format_type == 'string':
                    # Get DC information for display
                    dc_info = "Unknown"
                    try:
                        if client and client.is_connected():
                            dc_info = f"DC{client.session.dc_id}"
                    except Exception:
                        pass
                    
                    message = (
                        f"📝 **Session Export - {dc_info}**\n\n"
                        f"📱 **Account:** {account_name}\n"
                        f"📞 **Phone:** {phone}\n"
                        f"🌐 **Data Center:** {dc_info}\n\n"
                        f"**Session String:**\n\n"
                        f"{fresh_session}\n\n\n"
                        f"**Usage Example:**\n"
                        f"```python\n"
                        f"from telethon import TelegramClient\n"
                        f"from telethon.sessions import StringSession\n\n"
                        f"# {dc_info} Session\n"
                        f"client = TelegramClient(\n"
                        f"    StringSession('{fresh_session}'),\n"
                        f"    api_id, api_hash\n"
                        f")\n"
                        f"await client.start()\n"
                        f"```\n\n"
                        f"⚠️ **Keep this {dc_info} session secure!**"
                    )
                    await self.bot.send_message(user_id, message)
                elif format_type == 'file':
                    if session_file_data and len(session_file_data) > 0:
                        from telethon.tl.types import DocumentAttributeFilename
                        await self.bot.send_message(
                            user_id,
                            f"📁 **Fresh Session File - {account_name}**\n\n"
                            f"**Usage:** Use this file with Telethon:\n"
                            f"```python\n"
                            f"from telethon import TelegramClient\n\n"
                            f"client = TelegramClient('{account_name}', api_id, api_hash)\n"
                            f"await client.start()\n"
                            f"```",
                            file=session_file_data,
                            attributes=[DocumentAttributeFilename(f"fresh_{account_name}.session")]
                        )
                    else:
                        await self.bot.send_message(
                            user_id,
                            f"📝 **Session String (File Creation Failed)**\n\n"
                            f"**Session String:**\n{fresh_session}\n\n"
                            f"**Manual .session file creation:**\n"
                            f"```python\n"
                            f"from telethon import TelegramClient\n"
                            f"from telethon.sessions import StringSession\n\n"
                            f"client = TelegramClient(\n"
                            f"    StringSession('{fresh_session}'),\n"
                            f"    api_id, api_hash\n"
                            f")\n"
                            f"await client.start()\n\n"
                            f"# Save as .session file\n"
                            f"file_client = TelegramClient('{account_name}', api_id, api_hash)\n"
                            f"file_client.session = client.session\n"
                            f"file_client.session.save()\n"
                            f"```"
                        )
                elif format_type == 'both':
                    # Send string first
                    dc_info = "Unknown"
                    try:
                        if client and client.is_connected():
                            dc_info = f"DC{client.session.dc_id}"
                    except Exception:
                        pass
                    
                    message = (
                        f"📝 **Session Export - {dc_info}**\n\n"
                        f"📱 **Account:** {account_name}\n"
                        f"📞 **Phone:** {phone}\n"
                        f"🌐 **Data Center:** {dc_info}\n\n"
                        f"**Session String:**\n\n"
                        f"{fresh_session}\n\n\n"
                        f"**Usage Example:**\n"
                        f"```python\n"
                        f"from telethon import TelegramClient\n"
                        f"from telethon.sessions import StringSession\n\n"
                        f"# {dc_info} Session\n"
                        f"client = TelegramClient(\n"
                        f"    StringSession('{fresh_session}'),\n"
                        f"    api_id, api_hash\n"
                        f")\n"
                        f"await client.start()\n"
                        f"```\n\n"
                        f"⚠️ **Keep this {dc_info} session secure!**"
                    )
                    await self.bot.send_message(user_id, message)
                    
                    # Send file
                    if session_file_data:
                        from telethon.tl.types import DocumentAttributeFilename
                        await self.bot.send_message(
                            user_id,
                            f"📁 **Fresh Session File - {account_name}**\n\n"
                            f"**Usage:** Use this file with Telethon:\n"
                            f"```python\n"
                            f"from telethon import TelegramClient\n\n"
                            f"client = TelegramClient('{account_name}', api_id, api_hash)\n"
                            f"await client.start()\n"
                            f"```",
                            file=session_file_data,
                            attributes=[DocumentAttributeFilename(f"fresh_{account_name}.session")]
                        )
                # Always send notification
                try:
                    await self._send_login_notification(user_id, account_name, "Fresh session created via OTP")
                except Exception as notif_err:
                    logger.error(f"Failed to send login notification: {notif_err}")
                # Clear session creation protection and restore OTP settings
                try:
                    # Get original states
                    account_data = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
                    original_destroyer = account_data.get('original_destroyer_state', False) if account_data else False
                    original_forward = account_data.get('original_forward_state', False) if account_data else False
                    
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {
                            "$unset": {
                                "pending_fresh_session": "",
                                "session_creation_in_progress": "",
                                "original_destroyer_state": "",
                                "original_forward_state": ""
                            },
                            "$set": {
                                "otp_destroyer_enabled": original_destroyer,
                                "otp_forward_enabled": original_forward
                            }
                        }
                    )
                    # Clear pending action
                    self.bot_manager.pending_actions.pop(user_id, None)
                    logger.info(f"Session creation completed for {phone} - OTP settings restored")
                except Exception:
                    logger.exception("Failed to clear protection flags after successful session creation")
                try:
                    await client.disconnect()
                except Exception:
                    pass
                # Ensure pending entry is removed
                try:
                    if user_id in self.bot_manager.pending_fresh_sessions:
                        del self.bot_manager.pending_fresh_sessions[user_id]
                except Exception:
                    pass
                return True
            except Exception as e:
                # Clear session creation protection on failure and restore OTP settings
                try:
                    # Get original states
                    account_data = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
                    original_destroyer = account_data.get('original_destroyer_state', False) if account_data else False
                    original_forward = account_data.get('original_forward_state', False) if account_data else False
                    
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {
                            "$unset": {
                                "pending_fresh_session": "",
                                "session_creation_in_progress": "",
                                "original_destroyer_state": "",
                                "original_forward_state": ""
                            },
                            "$set": {
                                "otp_destroyer_enabled": original_destroyer,
                                "otp_forward_enabled": original_forward
                            }
                        }
                    )
                    # Clear pending action
                    self.bot_manager.pending_actions.pop(user_id, None)
                    logger.info(f"Session creation failed for {phone} - OTP settings restored")
                except Exception:
                    logger.exception("Failed to clear protection flags after session creation failure")
                try:
                    await client.disconnect()
                except Exception:
                    pass
                import traceback
                tb = traceback.format_exc()
                logger.error(f"Fresh session failed for {account_name}: {type(e).__name__}: {e}\n{tb}")
                if "TLObject was expected" in str(e):
                    error_msg = (
                        f"❌ **TLObject Error - Session Creation Failed**\n\n"
                        f"**Error:** {type(e).__name__}: {str(e)}\n"
                        f"**Account:** {account_name}\n\n"
                        f"**This is a Telethon serialization error.**\n"
                        f"**Possible causes:**\n"
                        f"• Invalid session data format\n"
                        f"• Corrupted authentication state\n"
                        f"• Telethon version compatibility issue\n\n"
                        f"**Solutions:**\n"
                        f"• Try re-authenticating the account\n"
                        f"• Use string session format instead\n"
                        f"• Update Telethon library\n"
                        f"• Contact support with this error message"
                    )
                else:
                    error_msg = (
                        f"❌ **Fresh Session Failed**\n\n"
                        f"**Error:** {type(e).__name__}: {str(e)}\n"
                        f"**Account:** {account_name}\n"
                        f"**Phone:** {phone}\n\n"
                        f"**Common Causes:** Invalid OTP, network issues, rate limiting\n"
                        f"**Solution:** Verify OTP code and try again"
                    )
                await self.bot.send_message(user_id, error_msg)
                try:
                    if user_id in self.bot_manager.pending_fresh_sessions:
                        del self.bot_manager.pending_fresh_sessions[user_id]
                except Exception:
                    pass
                return False
        except Exception as e:
            logger.error(f"Fresh session OTP processing error: {e}")
            return False
    async def process_fresh_session_2fa(self, user_id, password):
        """Process 2FA password for fresh session creation"""
        try:
            if not hasattr(self.bot_manager, 'pending_fresh_sessions'):
                return False
            session_data = self.bot_manager.pending_fresh_sessions.get(user_id)
            if not session_data or not session_data.get('waiting_for_2fa'):
                return False
            client = session_data['client']
            phone = session_data['phone']
            account_name = session_data['account_name']
            try:
                # Ensure client is still connected before sign in
                if not client.is_connected():
                    await client.connect()
                
                # Sign in with 2FA password
                await client.sign_in(password=password)
                # Store 2FA password for future use
                from ..core.database_manager import db_manager
                account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
                if account:
                    await db_manager.store_2fa_password(user_id, str(account['_id']), password)
                
                # Ensure we have a valid session before saving
                if not client.is_connected():
                    await client.connect()
                
                fresh_session = None
                try:
                    fresh_session = client.session.save()
                except Exception as e:
                    logger.warning(f"client.session.save() raised when generating session string (2FA): {e}")

                if not fresh_session or str(fresh_session).strip() == '' or str(fresh_session) in ('None', 'null'):
                    try:
                        logger.info("Attempting StringSession fallback for 2FA flow")
                        string_client = TelegramClient(StringSession(), API_ID, API_HASH)
                        try:
                            string_client.session.set_dc(
                                client.session.dc_id,
                                client.session.server_address,
                                client.session.port,
                            )
                            string_client.session.auth_key = client.session.auth_key
                        except Exception as copy_err:
                            logger.warning(f"Failed to copy session state to StringSession client (2FA): {copy_err}")
                        fresh_session = string_client.session.save()
                        logger.info("StringSession fallback generated for 2FA flow")
                    except Exception as ss_err:
                        logger.error(f"StringSession fallback failed for 2FA flow: {ss_err}")

                if not fresh_session or str(fresh_session).strip() == '' or str(fresh_session) == 'None':
                    logger.error(f"Invalid session string generated for {account_name}")
                    raise Exception("Failed to generate valid session string")
                from telethon import TelegramClient
                from telethon.sessions import StringSession
                from ..core.config import config
                API_ID = config.telegram.api_id
                API_HASH = config.telegram.api_hash
                
                # Create session file using the fresh session string
                session_file_data = None
                temp_session_path = f"sessions/fresh_{account_name}_{user_id}_{int(time.time())}.session"
                
                try:
                    logger.info(f"Creating session file for {account_name} (2FA)...")
                    
                    # Ensure sessions directory exists
                    os.makedirs("sessions", exist_ok=True)
                    
                    # Create a new client with the fresh session string
                    string_client = TelegramClient(StringSession(fresh_session), API_ID, API_HASH)
                    await string_client.connect()
                    
                    # Create file-based client and copy session data
                    file_client = TelegramClient(temp_session_path, API_ID, API_HASH)
                    file_client.session.set_dc(
                        string_client.session.dc_id,
                        string_client.session.server_address,
                        string_client.session.port
                    )
                    file_client.session.auth_key = string_client.session.auth_key
                    file_client.session.save()
                    
                    await string_client.disconnect()
                    logger.info(f"Session file created at {temp_session_path}")
                    
                    # Read the generated .session file
                    if os.path.exists(temp_session_path):
                        with open(temp_session_path, 'rb') as f:
                            session_file_data = f.read()
                        logger.info(f"Session file read successfully: {len(session_file_data)} bytes")
                    else:
                        logger.error(f"Session file not found at {temp_session_path}")
                        
                except Exception as e:
                    logger.error(f"Session file creation error (2FA): {e}")
                    import traceback
                    logger.error(f"Session file creation traceback (2FA): {traceback.format_exc()}")
                finally:
                    try:
                        if os.path.exists(temp_session_path):
                            os.remove(temp_session_path)
                            logger.info(f"Cleaned up temporary session file: {temp_session_path}")
                    except Exception as cleanup_err:
                        logger.error(f"Failed to cleanup session file (2FA): {cleanup_err}")
                format_type = session_data.get('format_type', 'both')
                # Send based on requested format
                if format_type == 'string':
                    # Get DC information for display
                    dc_info = "Unknown"
                    try:
                        if client and client.is_connected():
                            dc_info = f"DC{client.session.dc_id}"
                    except Exception:
                        pass
                    
                    message = (
                        f"📝 **Session Export - {dc_info}**\n\n"
                        f"📱 **Account:** {account_name}\n"
                        f"📞 **Phone:** {phone}\n"
                        f"🌐 **Data Center:** {dc_info}\n\n"
                        f"**Session String:**\n\n"
                        f"{fresh_session}\n\n\n"
                        f"**Usage Example:**\n"
                        f"```python\n"
                        f"from telethon import TelegramClient\n"
                        f"from telethon.sessions import StringSession\n\n"
                        f"# {dc_info} Session\n"
                        f"client = TelegramClient(\n"
                        f"    StringSession('{fresh_session}'),\n"
                        f"    api_id, api_hash\n"
                        f")\n"
                        f"await client.start()\n"
                        f"```\n\n"
                        f"🔐 **2FA password securely stored for future use!**\n"
                        f"⚠️ **Keep this {dc_info} session secure!**"
                    )
                    await self.bot.send_message(user_id, message)
                elif format_type == 'file':
                    if session_file_data:
                        from telethon.tl.types import DocumentAttributeFilename
                        await self.bot.send_message(
                            user_id,
                            f"📁 **Fresh Session File - {account_name}**\n\n"
                            f"**Usage:** Use this file with Telethon:\n"
                            f"```python\n"
                            f"from telethon import TelegramClient\n\n"
                            f"client = TelegramClient('{account_name}', api_id, api_hash)\n"
                            f"await client.start()\n"
                            f"```\n\n"
                            f"🔐 **2FA password securely stored for future use!**",
                            file=session_file_data,
                            attributes=[DocumentAttributeFilename(f"fresh_{account_name}.session")]
                        )
                    else:
                        await self.bot.send_message(user_id, f"❌ Failed to create session file for {account_name}")
                elif format_type == 'both':
                    # Send string first
                    dc_info = "Unknown"
                    try:
                        if client and client.is_connected():
                            dc_info = f"DC{client.session.dc_id}"
                    except Exception:
                        pass
                    
                    message = (
                        f"📝 **Session Export - {dc_info}**\n\n"
                        f"📱 **Account:** {account_name}\n"
                        f"📞 **Phone:** {phone}\n"
                        f"🌐 **Data Center:** {dc_info}\n\n"
                        f"**Session String:**\n\n"
                        f"{fresh_session}\n\n\n"
                        f"**Usage Example:**\n"
                        f"```python\n"
                        f"from telethon import TelegramClient\n"
                        f"from telethon.sessions import StringSession\n\n"
                        f"# {dc_info} Session\n"
                        f"client = TelegramClient(\n"
                        f"    StringSession('{fresh_session}'),\n"
                        f"    api_id, api_hash\n"
                        f")\n"
                        f"await client.start()\n"
                        f"```\n\n"
                        f"🔐 **2FA password securely stored for future use!**\n"
                        f"⚠️ **Keep this {dc_info} session secure!**"
                    )
                    await self.bot.send_message(user_id, message)
                    
                    # Send file
                    if session_file_data:
                        from telethon.tl.types import DocumentAttributeFilename
                        await self.bot.send_message(
                            user_id,
                            f"📁 **Fresh Session File - {account_name}**\n\n"
                            f"**Usage:** Use this file with Telethon:\n"
                            f"```python\n"
                            f"from telethon import TelegramClient\n\n"
                            f"client = TelegramClient('{account_name}', api_id, api_hash)\n"
                            f"await client.start()\n"
                            f"```\n\n"
                            f"🔐 **2FA password securely stored for future use!**",
                            file=session_file_data,
                            attributes=[DocumentAttributeFilename(f"fresh_{account_name}.session")]
                        )
                # Always send notification
                try:
                    await self._send_login_notification(user_id, account_name, "Fresh session created with 2FA")
                except Exception as notif_err:
                    logger.error(f"Failed to send login notification: {notif_err}")
                # Clear protection flags and restore OTP settings
                try:
                    # Get original states
                    account_data = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
                    original_destroyer = account_data.get('original_destroyer_state', False) if account_data else False
                    original_forward = account_data.get('original_forward_state', False) if account_data else False
                    
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {
                            "$unset": {
                                "pending_fresh_session": "",
                                "session_creation_in_progress": "",
                                "original_destroyer_state": "",
                                "original_forward_state": ""
                            },
                            "$set": {
                                "otp_destroyer_enabled": original_destroyer,
                                "otp_forward_enabled": original_forward
                            }
                        }
                    )
                    self.bot_manager.pending_actions.pop(user_id, None)
                except Exception:
                    pass
                await client.disconnect()
                del self.bot_manager.pending_fresh_sessions[user_id]
                return True
            except Exception as e:
                # Clear protection flags on failure and restore OTP settings
                try:
                    # Get original states
                    account_data = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
                    original_destroyer = account_data.get('original_destroyer_state', False) if account_data else False
                    original_forward = account_data.get('original_forward_state', False) if account_data else False
                    
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {
                            "$unset": {
                                "pending_fresh_session": "",
                                "session_creation_in_progress": "",
                                "original_destroyer_state": "",
                                "original_forward_state": ""
                            },
                            "$set": {
                                "otp_destroyer_enabled": original_destroyer,
                                "otp_forward_enabled": original_forward
                            }
                        }
                    )
                    self.bot_manager.pending_actions.pop(user_id, None)
                except Exception:
                    pass
                await client.disconnect()
                import traceback
                tb = traceback.format_exc()
                logger.error(f"2FA failed for {account_name}: {type(e).__name__}: {e}\n{tb}")
                error_msg = (
                    f"❌ **2FA Authentication Failed**\n\n"
                    f"**Error:** {type(e).__name__}: {str(e)}\n"
                    f"**Account:** {account_name}\n\n"
                    f"**Common Causes:** Incorrect password, password changed\n"
                    f"**Solution:** Verify 2FA password and try again"
                )
                await self.bot.send_message(user_id, error_msg)
                if user_id in self.bot_manager.pending_fresh_sessions:
                    del self.bot_manager.pending_fresh_sessions[user_id]
                return False
        except Exception as e:
            logger.error(f"Fresh session 2FA processing error: {e}")
            return False
