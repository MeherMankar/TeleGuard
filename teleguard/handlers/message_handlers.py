"""Message handlers for user input processing"""
import logging
import re
import time
from telethon import events
from ..core.mongo_database import mongodb
from ..utils.network_helpers import retry_async

logger = logging.getLogger(__name__)
class MessageHandlers:
    """Handles user message input and pending actions"""
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.auth_manager = bot_manager.auth_manager
        self.pending_actions = bot_manager.pending_actions
        self.user_clients = bot_manager.user_clients
        self.messaging_manager = bot_manager.messaging_manager
        self.template_handler = getattr(bot_manager, 'template_handler', None)
        self.secure_2fa = getattr(bot_manager, 'secure_2fa', None)
        self.session_backup = getattr(bot_manager, 'session_backup', None)
    def register_handlers(self):
        """Register message handlers"""
        @self.bot.on(events.NewMessage(func=lambda e: e.photo))
        async def photo_handler(event):
            await self._handle_photo_upload(event)
        @self.bot.on(events.NewMessage(func=lambda e: e.document))
        async def document_handler(event):
            await self._handle_document_upload(event)
        
        # OTP auto-fetch handler for session creation
        @self.bot.on(events.NewMessage(chats=[777000, 42777]))
        async def otp_fetch_handler(event):
            try:
                message = event.raw_text.strip()
                
                # Extract OTP code with multiple patterns
                otp_code = None
                
                # Pattern 1: "Login code: 12345" or "Login code: /12345"
                otp_match = re.search(r'Login code: /?(\d{5,7})', message)
                if otp_match:
                    otp_code = otp_match.group(1)
                
                # Pattern 2: Any 5-7 digit number (with optional / prefix)
                if not otp_code:
                    otp_match = re.search(r'/?\b(\d{5,7})\b', message)
                    if otp_match:
                        otp_code = otp_match.group(1)
                
                if otp_code:
                    logger.info(f"Detected OTP code: {otp_code} from Telegram")
                    
                    # Check all pending fresh sessions
                    if hasattr(self.bot_manager, 'pending_fresh_sessions'):
                        for user_id, session_data in list(self.bot_manager.pending_fresh_sessions.items()):
                            try:
                                success = await self.bot_manager.session_export_handler.process_fresh_session_otp(user_id, otp_code)
                                if success:
                                    self.pending_actions.pop(user_id, None)
                                    await self.bot.send_message(user_id, f"✅ OTP {otp_code} auto-detected and processed!")
                                    break
                            except Exception as e:
                                logger.debug(f"Failed to process OTP for user {user_id}: {e}")
                                continue
            except Exception as e:
                logger.error(f"OTP fetch error: {e}")
    
    async def fetch_recent_otp(self, user_id):
        """Fetch recent OTP messages from Telegram official account"""
        try:
            if user_id not in self.bot_manager.pending_fresh_sessions:
                return False
            
            # Check both recent messages and unread messages from Telegram official accounts
            telegram_accounts = [777000, 42777]  # Telegram official accounts
            
            for account_id in telegram_accounts:
                try:
                    # Check recent messages (last 10 minutes)
                    from datetime import datetime, timedelta
                    async for message in self.bot.iter_messages(
                        account_id,
                        limit=20,
                        offset_date=datetime.now() - timedelta(minutes=10)
                    ):
                        if message.text:
                            # Look for OTP patterns (with optional / prefix)
                            otp_match = re.search(r'Login code: /?(\d{5,7})', message.text)
                            if not otp_match:
                                otp_match = re.search(r'/?\b(\d{5,7})\b', message.text)
                            
                            if otp_match:
                                otp_code = otp_match.group(1)
                                logger.info(f"Found recent OTP {otp_code} from {account_id}")
                                
                                success = await self.bot_manager.session_export_handler.process_fresh_session_otp(user_id, otp_code)
                                if success:
                                    return True
                    
                    # Also check unread messages specifically
                    try:
                        dialogs = await self.bot.get_dialogs(limit=None)
                        for dialog in dialogs:
                            if dialog.entity.id == account_id and dialog.unread_count > 0:
                                # Get unread messages
                                async for message in self.bot.iter_messages(
                                    account_id,
                                    limit=dialog.unread_count
                                ):
                                    if message.text:
                                        otp_match = re.search(r'Login code: /?(\d{5,7})', message.text)
                                        if not otp_match:
                                            otp_match = re.search(r'/?\b(\d{5,7})\b', message.text)
                                        
                                        if otp_match:
                                            otp_code = otp_match.group(1)
                                            logger.info(f"Found unread OTP {otp_code} from {account_id}")
                                            
                                            success = await self.bot_manager.session_export_handler.process_fresh_session_otp(user_id, otp_code)
                                            if success:
                                                return True
                                break
                    except Exception as unread_err:
                        logger.debug(f"Could not check unread messages from {account_id}: {unread_err}")
                        
                except Exception as account_err:
                    logger.debug(f"Could not check messages from {account_id}: {account_err}")
            
            return False
        except Exception as e:
            logger.error(f"Error fetching recent OTP: {e}")
            return False
    
        @self.bot.on(events.NewMessage(incoming=True))
        async def reply_handler(event):
            try:
                await self._handle_user_reply(event)
            except Exception as e:
                logger.error(f"Unhandled exception in reply_handler: {e}")
                try:
                    from ..utils.logger import BotLogger
                    await BotLogger.log_error("Message Handler Error", str(e), user_id=event.sender_id, context="reply_handler")
                except:
                    pass
                try:
                    await event.reply("❌ An error occurred. Please try again or contact support.")
                except Exception:
                    pass
    async def _handle_photo_upload(self, event):
        """Handle photo uploads for profile changes"""
        user_id = event.sender_id
        if user_id not in self.pending_actions:
            return
        action = self.pending_actions[user_id].get("action")
        if action == "change_profile_photo":
            account_id = self.pending_actions[user_id].get("account_id")
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if account:
                try:
                    account_name = account.get('name') or account.get('phone') or account.get('display_name', 'Unknown')
                    client = self.user_clients.get(user_id, {}).get(account_name)
                    if client:
                        import os
                        import tempfile
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                            photo_path = tmp.name
                        photo_path = await event.download_media(file=photo_path)
                        if not photo_path or not os.path.exists(photo_path):
                            await event.reply("❌ Invalid file path")
                            return
                        from telethon import functions
                        uploaded_file = await client.upload_file(photo_path)
                        await client(
                            functions.photos.UploadProfilePhotoRequest(
                                file=uploaded_file
                            )
                        )
                        if os.path.exists(photo_path):
                            os.remove(photo_path)
                        await event.reply("✅ Profile photo updated successfully!")
                    else:
                        await event.reply("❌ Account client not found")
                except (OSError, IOError, ValueError) as e:
                    await event.reply(f"❌ Failed to update profile photo: {e}")
                except (OSError, IOError, ValueError) as e:
                    logger.error(f"Unexpected error updating profile photo: {e}")
                    await event.reply("❌ Failed to update profile photo")
            else:
                await event.reply("❌ Account not found")
            self.pending_actions.pop(user_id, None)
    async def _handle_document_upload(self, event):
        """Handle document uploads for session file imports"""
        user_id = event.sender_id
        if user_id not in self.pending_actions:
            return
        action = self.pending_actions[user_id].get("action")
        if action == "session_file_login":
            try:
                if event.document and event.document.attributes:
                    filename = None
                    for attr in event.document.attributes:
                        if hasattr(attr, 'file_name'):
                            filename = attr.file_name
                            break
                    if filename and filename.endswith('.session'):
                        import tempfile
                        import os
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.session') as tmp:
                            file_path = tmp.name
                        file_path = await event.download_media(file=file_path)
                        if file_path and os.path.exists(file_path):
                            if hasattr(self.bot_manager, 'session_login_handler'):
                                success, msg = await self.bot_manager.session_login_handler.process_session_file(user_id, file_path)
                                await event.reply(msg)
                            else:
                                await event.reply("❌ Session login not available")
                        else:
                            await event.reply("❌ Invalid file path")
                    else:
                        await event.reply("❌ Please send a .session file")
                else:
                    await event.reply("❌ Invalid document format")
            except (OSError, IOError, ValueError) as e:
                logger.error(f"Session file import error: {e}")
                await event.reply(f"❌ Error processing session file: {str(e)}")
            except (OSError, IOError, ValueError) as e:
                logger.error(f"Unexpected session file error: {e}")
                await event.reply("❌ Error processing session file")
            self.pending_actions.pop(user_id, None)
    async def _handle_user_reply(self, event):
        """Handle user text replies for pending actions"""
        user_id = event.sender_id
        message = event.raw_text.strip()
        logger.info(f"=== MESSAGE HANDLER === User {user_id} sent: '{message}'")
        logger.info(f"Pending actions keys: {list(self.pending_actions.keys())}")
        if user_id in self.pending_actions:
            logger.info(f"User {user_id} pending action: {self.pending_actions[user_id]}")
        
        # Skip messages in admin group (forum topics) - they're handled by unified_messaging
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if user and user.get("dm_reply_group_id") == event.chat_id:
                return
        except Exception:
            pass
        
        # Check for transfer ownership or co-owner input FIRST (before OTP check)
        if hasattr(self.bot_manager, 'transfer_ownership_handler'):
            if user_id in self.bot_manager.transfer_ownership_handler.pending_transfers or user_id in self.bot_manager.transfer_ownership_handler.pending_coowner:
                await self.bot_manager.transfer_ownership_handler.process_user_input(event, user_id, message)
                return
        
        # Manual OTP or 2FA input during session creation (only if not in transfer mode)
        if hasattr(self.bot_manager, 'pending_fresh_sessions') and user_id in self.bot_manager.pending_fresh_sessions:
            session_data = self.bot_manager.pending_fresh_sessions.get(user_id, {})
            logger.info(f"Fresh session data for {user_id}: waiting_for_2fa={session_data.get('waiting_for_2fa')}")
            if session_data.get('waiting_for_2fa'):
                # This is a 2FA password
                logger.info(f"Processing 2FA password for user {user_id}")
                try:
                    # Attempt to delete the password message for security
                    await event.delete()
                except Exception:
                    pass

                # Send a short acknowledgement so the user knows input was received
                ack_msg = None
                try:
                    ack_msg = await self.bot.send_message(user_id, "🔐 Processing your 2FA password now...")
                except Exception:
                    pass

                success = False
                try:
                    success = await self.bot_manager.session_export_handler.process_fresh_session_2fa(user_id, message.strip())
                except Exception as e:
                    logger.error(f"Error while processing 2FA for user {user_id}: {e}")
                    try:
                        await self.bot.send_message(user_id, f"❌ Error processing 2FA: {e}")
                    except Exception:
                        pass

                # Remove acknowledgement message if possible
                try:
                    if ack_msg:
                        await ack_msg.delete()
                except Exception:
                    pass

                if success:
                    try:
                        self.pending_actions.pop(user_id, None)
                    except Exception:
                        pass
                return
            else:
                # This is an OTP code - accept both "12345" and "/12345" formats
                import re
                # Strip leading slash if present
                otp_code = message.strip().lstrip('/')
                if re.match(r'^\d{5,7}$', otp_code):
                    logger.info(f"Processing manual OTP {otp_code} for user {user_id}")
                    success = await self.bot_manager.session_export_handler.process_fresh_session_otp(user_id, otp_code)
                    if success:
                        self.pending_actions.pop(user_id, None)
                        logger.info(f"OTP processed successfully for user {user_id}")
                    else:
                        logger.error(f"OTP processing failed for user {user_id}")
                    return
                else:
                    logger.warning(f"Message '{message}' doesn't match OTP pattern and not waiting for 2FA")
        
        if message.startswith("/"):
            # Clear pending actions for certain commands
            if message in ["/start", "/cancel", "/help"]:
                self.pending_actions.pop(user_id, None)
            return
        

        # Check for OTP auto-fetch during session creation (additional fallback)
        if hasattr(self.bot_manager, 'session_login_handler') and hasattr(self.bot_manager.session_login_handler, 'pending_auth'):
            if user_id in self.bot_manager.session_login_handler.pending_auth:
                auth_data = self.bot_manager.session_login_handler.pending_auth[user_id]
                if auth_data.get('step') != '2fa':
                    # This might be an OTP code - accept both "12345" and "/12345" formats
                    import re
                    otp_code = message.strip().lstrip('/')
                    if re.match(r'^\d{5,7}$', otp_code):
                        logger.info(f"Auto-processing OTP code {otp_code} for session login")
                        success, msg = await self.bot_manager.session_login_handler.process_verification_code(user_id, otp_code)
                        await event.reply(msg)
                        if user_id not in self.bot_manager.session_login_handler.pending_auth:
                            self.pending_actions.pop(user_id, None)
                        return
        
        logger.info("User sent a message for pending action")
        if hasattr(self.bot_manager, 'session_export_handler') and hasattr(self.bot_manager, 'pending_fresh_sessions'):
            if user_id in self.bot_manager.pending_fresh_sessions:
                session_data = self.bot_manager.pending_fresh_sessions[user_id]
                if session_data.get('waiting_for_2fa'):
                    # This is a 2FA password for fresh session creation
                        logger.info(f"Pending fresh session 2FA received from {user_id}; session_data keys={list(session_data.keys())}")
                        try:
                            try:
                                await event.delete()
                            except Exception:
                                pass

                            # Acknowledge receipt so user sees activity
                            ack_msg = None
                            try:
                                ack_msg = await self.bot.send_message(user_id, "🔐 Processing your 2FA password now...")
                            except Exception:
                                pass

                            success = await self.bot_manager.session_export_handler.process_fresh_session_2fa(user_id, message.strip())

                            try:
                                if ack_msg:
                                    await ack_msg.delete()
                            except Exception:
                                pass
                        except Exception as e:
                            logger.error(f"Error processing 2FA for user {user_id}: {e}")
                            success = False
                        # Clear pending_fresh_sessions and any pending_actions set by the flow
                        try:
                            if user_id in self.bot_manager.pending_fresh_sessions:
                                del self.bot_manager.pending_fresh_sessions[user_id]
                        except Exception:
                            pass
                        try:
                            self.pending_actions.pop(user_id, None)
                        except Exception:
                            pass
                        logger.info(f"2FA processing result for {user_id}: {success}")
                        return
                else:
                    # This is an OTP for fresh session creation - accept both "12345" and "/12345" formats
                    otp_code = message.strip().lstrip('/')
                    success = await self.bot_manager.session_export_handler.process_fresh_session_otp(user_id, otp_code)
                    if success:
                        self.pending_actions.pop(user_id, None)
                    return
        # If there's no explicit pending action, check whether this looks like
        # a 2FA password (alphanumeric, length >=6). If so, provide clear
        # feedback to the user instead of silently doing nothing.
        if user_id not in self.pending_actions:
            logger.warning(f"!!! User {user_id} sent '{message}' but NO pending action found !!!")
            logger.debug(f"Current pending_actions: {dict(self.pending_actions)}")

            import re as _re
            # common 2FA password pattern: mixed alnum and symbols, length >=6
            if _re.match(r'^[A-Za-z0-9@#\$%\^&\-_]{6,}$', message):
                try:
                    await event.reply(
                        "⚠️ No active authentication flow found. If you were asked for a 2FA password, please restart the login process and try again."
                    )
                except Exception:
                    pass
                return

            return
        action = self.pending_actions[user_id]["action"]
        logger.info(f"Processing user action for {user_id}: {action}")
        user = await mongodb.get_user(user_id)
        if not user:
            await event.reply("Please start the bot first with /start")
            self.pending_actions.pop(user_id, None)
            return
        # Route to appropriate handler
        if action in ["add_account", "verify_otp", "verify_2fa", "2fa_password"]:
            await self._handle_auth_actions(event, user, action, message)
        elif action.startswith("2fa_") and action != "verify_2fa":
            await self._handle_2fa_actions(event, user, action, message)
        elif action in ["change_2fa", "remove_2fa", "set_2fa", "change_2fa_current", "remove_2fa_password", "set_2fa_password", "change_2fa_new"]:
            # Route to twofa_commands handler
            if hasattr(self.bot_manager, 'twofa_commands'):
                handled = await self.bot_manager.twofa_commands.handle_text_message(event, user_id, message)
                if handled:
                    return
            await self._handle_2fa_management_actions(event, user, action, message)
        elif action == "update_2fa_password":
            if hasattr(self.bot_manager, 'twofa_manager'):
                success = await self.bot_manager.twofa_manager.process_2fa_update(event, user_id, message)
                if success:
                    try:
                        await event.delete()
                    except (OSError, IOError):
                        pass
            else:
                await event.reply("❌ 2FA management not available")
            self.pending_actions.pop(user_id, None)
        elif action.startswith("profile_"):
            await self._handle_profile_actions(event, user, action, message)
        elif action.startswith(("message_", "set_autoreply", "compose_message")):
            await self._handle_messaging_actions(event, user, action, message)
        elif action.startswith("template_"):
            # Redirect template actions to new template handler
            if hasattr(self.bot_manager, 'template_handler'):
                await self.bot_manager.template_handler.process_text_input(event, self.pending_actions[user_id], message)
            else:
                await event.reply("Template system not available")
                self.pending_actions.pop(user_id, None)
        elif action.startswith(("otp_", "disable_otp", "set_otp", "enable_temp")):
            await self._handle_otp_actions(event, user, action, message)
        elif action.startswith("channel_"):
            await self._handle_channel_actions(event, user, action, message)
        elif action == "set_dm_group_id":
            await self._handle_dm_group_actions(event, user, action, message)
        elif action == "session_string_login" or action == "import_string_session":
            await self._handle_session_string_import(event, user, action, message)
        elif action == "session_phone_login":
            await self._handle_session_phone_login(event, user, action, message)
        elif action == "validate_session_string":
            await self._handle_session_validation(event, user, action, message)
        elif action == "cleanup_selection":
            logger.info(f"Routing to cleanup_selection handler for user {user_id}")
            await self._handle_cleanup_selection(event, user, action, message)
        elif action == "bulk_cleanup_selection":
            await self._handle_bulk_cleanup_selection(event, user, action, message)
        elif action == "session_creation_2fa_password":
            await self._handle_session_creation_2fa(event, user, action, message)
        else:
            if hasattr(self.bot_manager, 'session_export_handler') and hasattr(self.bot_manager, 'pending_fresh_sessions'):
                if user_id in self.bot_manager.pending_fresh_sessions:
                    session_data = self.bot_manager.pending_fresh_sessions[user_id]
                    if session_data.get('waiting_for_2fa'):
                        # This is a 2FA password for fresh session creation
                        try:
                            try:
                                await event.delete()
                            except Exception:
                                pass

                            ack_msg = None
                            try:
                                ack_msg = await self.bot.send_message(user_id, "🔐 Processing your 2FA password now...")
                            except Exception:
                                pass

                            success = await self.bot_manager.session_export_handler.process_fresh_session_2fa(user_id, message.strip())

                            try:
                                if ack_msg:
                                    await ack_msg.delete()
                            except Exception:
                                pass
                        except Exception as e:
                            logger.error(f"Error processing fresh-session 2FA (fallback branch) for {user_id}: {e}")
                            success = False

                        try:
                            self.pending_actions.pop(user_id, None)
                        except Exception:
                            pass

                        return
                    else:
                        # This is an OTP for fresh session creation
                        success = await self.bot_manager.session_export_handler.process_fresh_session_otp(user_id, message.strip())
                        if success:
                            self.pending_actions.pop(user_id, None)
                        return
            if action.startswith("create_template"):
                await event.reply("Please use /templates command for the new advanced template system")
                self.pending_actions.pop(user_id, None)
            else:
                await self._handle_misc_actions(event, user, action, message)
    async def _handle_auth_actions(self, event, user, action, message):
        """Handle authentication related actions"""
        user_id = event.sender_id
        if action == "add_account":
            await self._process_add_account(event, user_id, message)
        elif action == "verify_otp":
            await self._process_verify_otp(event, user_id, message, user)
        elif action == "verify_2fa" or action == "2fa_password":
            await self._process_verify_2fa(event, user_id, message, user)
    async def _process_add_account(self, event, user_id, phone):
        """Process adding new account"""
        # Validate phone number format
        if not phone.startswith("+"):
            await event.reply(
                "Please provide phone number with country code (e.g., +1234567890)"
            )
            return
        
        # Basic phone number validation
        if not re.match(r'^\+[1-9]\d{1,14}$', phone):
            await event.reply(
                "❌ Invalid phone number format. Please use international format with country code (e.g., +1234567890)"
            )
            return
        
        try:
            await self.auth_manager.start_auth(user_id, phone, use_otp_destroyer=False)
            
            # Add OTP protection for this phone number to prevent destroyer from invalidating legitimate codes
            try:
                await mongodb.db.otp_protections.update_one(
                    {"phone": phone},
                    {"$set": {
                        "phone": phone,
                        "wildcard": True,  # Protect all codes for this phone
                        "expires_at": int(time.time()) + 600,  # 10 minutes protection
                        "reason": "account_addition",
                        "user_id": user_id
                    }},
                    upsert=True
                )
                logger.info(f"Added OTP protection for {phone} during account addition")
            except Exception as e:
                logger.warning(f"Failed to add OTP protection: {e}")
            
            self.pending_actions[user_id] = {
                "action": "verify_otp",
                "phone": phone,
                "otp_destroyer": False,
            }
            await event.reply(
                f"OTP sent to {phone}\n\n📱 **Enter OTP Code**\n\nReply with the verification code:\n• Format 1: 1 2 3 4 5\n• Format 2: 1-2-3-4-5\n• Format 3: /12345 (recommended if code expires)\n\nAll formats work!\n\n💡 **Tip:** If your code expires immediately, use the `/` prefix (e.g., `/12345`) to bypass Telegram's security detection.\n\n🛡️ **Note:** OTP protection enabled for 10 minutes"
            )
        except (ValueError, ConnectionError, TimeoutError) as e:
            error_msg = str(e)
            # Clear pending actions on error
            self.pending_actions.pop(user_id, None)
            
            if "phone number is invalid" in error_msg.lower():
                await event.reply(
                    "❌ Invalid phone number. Please check the number and try again.\n\nMake sure to include the correct country code."
                )
            elif "wait of" in error_msg and "seconds is required" in error_msg:
                wait_match = re.search(r"wait of (\\d+) seconds", error_msg)
                if wait_match:
                    wait_seconds = int(wait_match.group(1))
                    wait_minutes = wait_seconds // 60
                    wait_hours = wait_minutes // 60
                    if wait_hours > 0:
                        time_str = f"{wait_hours}h {wait_minutes % 60}m"
                    else:
                        time_str = f"{wait_minutes}m"
                    await event.reply(
                        f"⏰ Rate limited! Please wait {time_str} before requesting OTP for this number again.\n\nTry using a different phone number or wait for the cooldown to expire."
                    )
                else:
                    await event.reply(f"Rate limited: {error_msg}")
            else:
                await event.reply(f"❌ Error sending OTP: {error_msg}")
    async def _process_verify_otp(self, event, user_id, code, user):
        """Process OTP verification"""
        phone = self.pending_actions[user_id].get("phone")
        
        # Normalize OTP code format - handle "12345", "1-2-3-4-5", and "/12345" formats
        normalized_code = code.replace("-", "").replace(" ", "").strip().lstrip('/')
        
        logger.info(f"User is verifying OTP code: {normalized_code}")
        await event.reply(f"Verifying OTP {normalized_code}...")
        try:
            session_string = await self.auth_manager.complete_auth(user_id, normalized_code)
            logger.info("Account authentication completed successfully")
            if session_string == "OTP_DESTROYED":
                await event.reply("OTP code destroyed successfully!")
                self.pending_actions.pop(user_id, None)
                return
            await mongodb.create_account(
                user_id=user_id,
                phone=phone,
                name=phone,
                session_string=session_string,
                is_active=True,
                otp_destroyer_enabled=False,
            )
            logger.info("New account added to user's account list")
            # Store session in MongoDB backup system (if enabled)
            if self.session_backup:
                try:
                    self.session_backup.store_session(phone, session_string)
                    logger.info(f"Session backed up to MongoDB for {phone}")
                except Exception as e:
                    logger.error(f"Failed to backup session for {phone}: {e}")
            await self.bot_manager.start_user_client(user_id, phone, session_string)
            
            # Remove OTP protection after successful account addition
            try:
                await mongodb.db.otp_protections.delete_one({"phone": phone, "reason": "account_addition"})
                logger.info(f"Removed OTP protection for {phone} after successful addition")
            except Exception as e:
                logger.warning(f"Failed to remove OTP protection: {e}")
            
            # Fetch and store real account name
            await self._fetch_and_store_account_name(user_id, phone)
            
            # Log to logs bot
            try:
                from ..utils.logger import BotLogger
                try:
                    user = await self.bot.get_entity(user_id)
                    username = user.username if hasattr(user, 'username') else None
                except:
                    username = None
                await BotLogger.log_account_added(user_id, phone, username)
            except Exception as log_error:
                logger.error(f"Failed to log account addition: {log_error}")
            
            await event.reply(
                f"✅ Account {phone} added successfully!\nUse /toggle_protection to enable OTP destroyer."
            )
            self.pending_actions.pop(user_id, None)
        except Exception as e:
            logger.error(f"Auth error: {str(e)}")
            error_msg = str(e)
            
            if "Two-factor" in error_msg or "password" in error_msg.lower():
                # Keep the action as 2fa_password (set by auth_handler)
                # Don't send message here - auth_handler already sent the proper 2FA message
                return
            elif "expired" in error_msg.lower():
                await event.reply(
                    "❌ The confirmation code has expired. Please request a new OTP by adding the account again."
                )
                self.pending_actions.pop(user_id, None)
            elif "invalid" in error_msg.lower():
                await event.reply(
                    "❌ Invalid OTP code. Please check the code and try again."
                )
                # Don't clear pending actions for invalid code - allow retry
            else:
                await event.reply(f"❌ Authentication failed: {error_msg}")
                # Cleanup pending actions and OTP protection on other errors
                try:
                    await mongodb.db.otp_protections.delete_one({"phone": phone, "reason": "account_addition"})
                    logger.info(f"Removed OTP protection for {phone} after auth failure")
                except Exception:
                    pass
                self.pending_actions.pop(user_id, None)
    async def _process_verify_2fa(self, event, user_id, password, user):
        """Process 2FA verification"""
        phone = self.pending_actions[user_id].get("phone")
        await event.reply("Verifying 2FA password...")
        try:
            session_string = await self.auth_manager.complete_auth(
                user_id, code=None, password=password
            )
            if session_string == "OTP_DESTROYED":
                await event.reply("OTP code destroyed successfully!")
                return
            account_id = await mongodb.create_account(
                user_id=user_id,
                phone=phone,
                name=phone,
                session_string=session_string,
                is_active=True,
                otp_destroyer_enabled=False,
            )
            # Store 2FA password automatically
            if account_id and self.bot_manager:
                try:
                    from ..core.database_manager import db_manager
                    await db_manager.store_2fa_password(user_id, account_id, password)
                except Exception as e:
                    logger.error(f"Failed to store 2FA password: {e}")
            if self.session_backup:
                try:
                    self.session_backup.store_session(phone, session_string)
                    logger.info(f"Session backed up to MongoDB for {phone}")
                except Exception as e:
                    logger.error(f"Failed to backup session for {phone}: {e}")
            await self.bot_manager.start_user_client(user_id, phone, session_string)
            
            # Fetch and store real account name
            await self._fetch_and_store_account_name(user_id, phone)
            
            # Log to logs bot
            try:
                from ..utils.logger import BotLogger
                try:
                    user = await self.bot.get_entity(user_id)
                    username = user.username if hasattr(user, 'username') else None
                except:
                    username = None
                await BotLogger.log_account_added(user_id, phone, username)
            except Exception as log_error:
                logger.error(f"Failed to log account addition: {log_error}")
            
            await event.reply(
                f"✅ Account {phone} added successfully!\nUse /toggle_protection to enable OTP destroyer."
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"2FA error for user {user_id}: {error_msg}")
            if "attempts left" in error_msg or "Try again in" in error_msg:
                # Password retry case - keep pending action for retry
                await event.reply(f"❌ {error_msg}")
                return  # Don't clear pending actions
            elif "Too many incorrect attempts" in error_msg:
                # Terminal failure - clear everything
                await event.reply(f"❌ {error_msg}")
            else:
                # Other errors - show full error message
                await event.reply(f"❌ 2FA failed: {error_msg if error_msg else 'Unknown error'}")
        # Cleanup pending actions after 2FA processing (except for retries)
        if user_id in self.pending_actions:
            self.pending_actions.pop(user_id, None)
    async def _handle_2fa_actions(self, event, user, action, message):
        """Handle 2FA related actions"""
        user_id = event.sender_id
        if action == "set_2fa_password":
            account_id = self.pending_actions[user_id].get("account_id")
            if account_id:
                success = await self.secure_2fa.set_2fa_password(
                    user_id, account_id, message
                )
                if success:
                    await event.reply("🔐 2FA password set successfully!")
                else:
                    await event.reply("❌ Failed to set 2FA password.")
            else:
                await event.reply("❌ Account ID not found")
            self.pending_actions.pop(user_id, None)
    
    async def _handle_2fa_management_actions(self, event, user, action, message):
        """Handle 2FA management actions from menu system"""
        user_id = event.sender_id
        
        # Try to use twofa_commands handler if available
        twofa_handler = None
        if hasattr(self.bot_manager, 'twofa_commands'):
            twofa_handler = self.bot_manager.twofa_commands
        elif hasattr(self.bot_manager.account_manager, 'twofa_commands'):
            twofa_handler = self.bot_manager.account_manager.twofa_commands
        
        if twofa_handler:
            # Use the twofa_commands handler
            handled = await twofa_handler.handle_text_message(event, user_id, message)
            if handled:
                return
        
        # Fallback to old implementation
        account_id = self.pending_actions[user_id].get("account_id")
        
        # Delete the user's message for security
        try:
            await event.delete()
        except (OSError, IOError):
            pass
        
        if not account_id:
            await self.bot.send_message(user_id, "❌ Account ID not found")
            self.pending_actions.pop(user_id, None)
            return
        
        if action == "change_2fa_current":
            # This is the current password, now ask for new password
            current_password = message.strip()
            
            # Verify current password first
            if hasattr(self.bot_manager, 'twofa_manager'):
                is_valid = await self.bot_manager.twofa_manager.verify_current_password(user_id, account_id, current_password)
                if is_valid:
                    # Current password is correct, now ask for new password
                    self.pending_actions[user_id] = {
                        "action": "change_2fa_new",
                        "account_id": account_id,
                        "current_password": current_password
                    }
                    await self.bot.send_message(
                        user_id, 
                        "✅ Current password verified!\n\n🔑 **Set New 2FA Password**\n\nReply with your new 2FA password:\n\n⚠️ Message will be deleted after processing for security."
                    )
                else:
                    await self.bot.send_message(user_id, "❌ Current password is incorrect")
                    self.pending_actions.pop(user_id, None)
            else:
                await self.bot.send_message(user_id, "❌ 2FA management not available")
                self.pending_actions.pop(user_id, None)
        
        elif action == "change_2fa_new":
            # This is the new password
            new_password = message.strip()
            current_password = self.pending_actions[user_id].get("current_password")
            
            if hasattr(self.bot_manager, 'twofa_manager'):
                success = await self.bot_manager.twofa_manager.change_2fa_password(
                    user_id, account_id, current_password, new_password
                )
                if success:
                    await self.bot.send_message(user_id, "✅ 2FA password changed successfully!")
                else:
                    await self.bot.send_message(user_id, "❌ Failed to change 2FA password")
            else:
                await self.bot.send_message(user_id, "❌ 2FA management not available")
            
            self.pending_actions.pop(user_id, None)
        
        elif action == "remove_2fa_password":
            # This is the current password for removal
            current_password = message.strip()
            
            if hasattr(self.bot_manager, 'twofa_manager'):
                success = await self.bot_manager.twofa_manager.remove_2fa_password(
                    user_id, account_id, current_password
                )
                if success:
                    await self.bot.send_message(user_id, "✅ 2FA password removed successfully!\n\n⚠️ Your account is now less secure.")
                else:
                    await self.bot.send_message(user_id, "❌ Failed to remove 2FA password. Check your password.")
            else:
                await self.bot.send_message(user_id, "❌ 2FA management not available")
            
            self.pending_actions.pop(user_id, None)
        
        elif action == "set_2fa_password":
            # This is setting a new 2FA password
            new_password = message.strip()
            
            if hasattr(self.bot_manager, 'twofa_manager'):
                success = await self.bot_manager.twofa_manager.set_2fa_password(
                    user_id, account_id, new_password
                )
                if success:
                    await self.bot.send_message(user_id, "✅ 2FA password set successfully!")
                else:
                    await self.bot.send_message(user_id, "❌ Failed to set 2FA password")
            else:
                await self.bot.send_message(user_id, "❌ 2FA management not available")
            
            self.pending_actions.pop(user_id, None)
    async def _handle_profile_actions(self, event, user, action, message):
        """Handle profile related actions"""
        user_id = event.sender_id
        account_id = self.pending_actions[user_id].get("account_id")
        if action == "change_profile_name":
            names = message.split(" ", 1)
            first_name = names[0]
            last_name = names[1] if len(names) > 1 else ""
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if account:
                phone = account.get('phone')
                session_string = account.get('session_string')
                client = await self._get_or_reconnect_client(user_id, account)
                
                if client:
                    try:
                        from telethon import functions
                        await client(
                            functions.account.UpdateProfileRequest(
                                first_name=first_name, last_name=last_name
                            )
                        )
                        await event.reply(
                            f"✅ Profile name updated to: {first_name} {last_name}"
                        )
                    except (ValueError, ConnectionError) as e:
                        await event.reply(f"❌ Failed to update name: {e}")
                else:
                    await event.reply(f"❌ Could not connect to account")
            else:
                await event.reply("❌ Account not found")
        elif action == "change_username":
            username = message.replace("@", "").strip()
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if account:
                client = await self._get_or_reconnect_client(user_id, account)
                
                if client:
                    try:
                        from telethon import functions
                        await client(
                            functions.account.UpdateUsernameRequest(username=username)
                        )
                        await event.reply(f"✅ Username updated to: @{username}")
                    except (ValueError, ConnectionError) as e:
                        await event.reply(f"❌ Failed to update username: {e}")
                else:
                    await event.reply(f"❌ Could not connect to account")
            else:
                await event.reply("❌ Account not found")
        elif action == "change_bio":
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if account:
                client = await self._get_or_reconnect_client(user_id, account)
                
                if client:
                    try:
                        from telethon import functions
                        await client(
                            functions.account.UpdateProfileRequest(about=message)
                        )
                        await event.reply(f"✅ Bio updated successfully")
                    except (ValueError, ConnectionError) as e:
                        await event.reply(f"❌ Failed to update bio: {e}")
                else:
                    await event.reply(f"❌ Could not connect to account")
            else:
                await event.reply("❌ Account not found")
        self.pending_actions.pop(user_id, None)
    
    async def _get_or_reconnect_client(self, user_id, account):
        """Get client or automatically reconnect if disconnected"""
        phone = account.get('phone')
        session_string = account.get('session_string')
        
        # Try to find existing client
        user_clients_dict = self.user_clients.get(user_id, {})
        for key in [phone, account.get('name'), account.get('display_name'), account.get('first_name'), account.get('username')]:
            if key and key in user_clients_dict:
                client = user_clients_dict[key]
                if client and client.is_connected():
                    return client
        
        # Try phone variations
        if phone:
            phone_clean = phone.replace('+', '')
            for key in user_clients_dict.keys():
                if phone_clean in str(key).replace('+', ''):
                    client = user_clients_dict[key]
                    if client and client.is_connected():
                        return client
        
        # Client not found or disconnected - reconnect automatically
        if session_string and phone:
            try:
                logger.info(f"Auto-reconnecting client for {phone}")
                account_name = account.get('name') or account.get('display_name') or phone
                await self.bot_manager.start_user_client(user_id, account_name, session_string)
                
                # Return the newly connected client
                user_clients_dict = self.user_clients.get(user_id, {})
                return user_clients_dict.get(account_name)
            except Exception as e:
                logger.error(f"Auto-reconnect failed for {phone}: {e}")
                return None
        
        return None
    async def _handle_messaging_actions(self, event, user, action, message):
        """Handle messaging related actions"""
        user_id = event.sender_id
        if action == "compose_message_target":
            account_id = self.pending_actions[user_id].get("account_id")
            self.pending_actions[user_id] = {
                "action": "compose_message_content",
                "account_id": account_id,
                "target": message.strip(),
            }
            await event.reply("📝 Now send the message content:\n\n💡 Type 'template' to use a message template")
        elif action == "compose_message_content":
            account_id = self.pending_actions[user_id].get("account_id")
            target = self.pending_actions[user_id].get("target")
            if message.lower() == "template":
                from telethon.tl.custom import Button
                text, buttons = await self.bot_manager.template_handler.get_template_selection_menu(user_id)
                await event.reply(text, buttons=buttons)
                return
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                await event.reply("❌ Account not found.")
                self.pending_actions.pop(user_id, None)
                return
            
            account_name = account.get('name') or account.get('phone') or account.get('display_name', 'Unknown')
            
            # Check if client is connected
            client = self.user_clients.get(user_id, {}).get(account_name)
            if not client or not client.is_connected():
                await event.reply(
                    f"❌ Account {account_name} is not connected.\n\n"
                    "Please restart the bot or re-add the account."
                )
                self.pending_actions.pop(user_id, None)
                return
            
            # Send message
            success = await self.messaging_manager.send_message(
                user_id, account_name, target, message
            )
            
            if success:
                await event.reply(f"✅ Message sent to {target}!")
            else:
                await event.reply(
                    f"❌ Failed to send message to {target}.\n\n"
                    "Possible reasons:\n"
                    "• User not found or username incorrect\n"
                    "• You haven't started a chat with this user\n"
                    "• Account is restricted or banned\n\n"
                    "Try sending a message to this user manually first."
                )
            self.pending_actions.pop(user_id, None)
        elif action == "set_autoreply_message":
            account_id = self.pending_actions[user_id].get("account_id")
            if account_id:
                from bson import ObjectId
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id), "user_id": user_id},
                    {"$set": {"auto_reply_message": message.strip()}}
                )
                await event.reply("✅ Auto-reply message set successfully!")
            else:
                await event.reply("❌ Account not found.")
            self.pending_actions.pop(user_id, None)
    async def _handle_misc_actions(self, event, user, action, message):
        """Handle miscellaneous actions"""
        user_id = event.sender_id
        if action == "setup_topic_routing":
            try:
                chat_id = int(message.strip())
                if chat_id > 0:
                    await event.reply(
                        "❌ Please provide a negative chat ID for groups/channels."
                    )
                    return
                await mongodb.db.users.update_one(
                    {"telegram_id": user_id},
                    {
                        "$set": {
                            "topic_routing_enabled": True,
                            "manager_forum_chat_id": chat_id,
                        }
                    },
                )
                await event.reply(f"✅ Topic routing enabled for forum {chat_id}")
            except ValueError:
                await event.reply(
                    "❌ Invalid chat ID. Please provide a numeric chat ID."
                )
            except (ValueError, ConnectionError) as e:
                logger.error(f"Failed to setup routing: {e}")
                await event.reply("❌ Failed to setup topic routing.")
            self.pending_actions.pop(user_id, None)
    async def _handle_otp_actions(self, event, user, action, message):
        """Handle OTP Destroyer related actions"""
        user_id = event.sender_id
        try:
            await event.delete()
        except (OSError, IOError) as e:
            logger.debug(f"Could not delete message: {e}")
            pass  # Message might already be deleted or we don't have permission
        if action == "disable_otp_destroyer":
            account_id = self.pending_actions[user_id].get("account_id")
            if account_id:
                success, msg = await self.bot_manager.otp_manager.toggle_destroyer(
                    user_id, account_id, False, message
                )
                if success:
                    await self.bot.send_message(user_id, f"🔴 {msg}")
                else:
                    await self.bot.send_message(user_id, f"❌ {msg}")
            else:
                await self.bot.send_message(user_id, "❌ Account ID not found")
        elif action == "set_otp_disable_password":
            account_id = self.pending_actions[user_id].get("account_id")
            if account_id:
                success, msg = await self.bot_manager.otp_manager.set_disable_password(
                    user_id, account_id, message
                )
                if success:
                    await self.bot.send_message(user_id, f"🔒 {msg}")
                else:
                    await self.bot.send_message(user_id, f"❌ {msg}")
            else:
                await self.bot.send_message(user_id, "❌ Account ID not found")
        elif action == "enable_temp_otp":
            account_id = self.pending_actions[user_id].get("account_id")
            if account_id:
                (
                    success,
                    msg,
                ) = await self.bot_manager.otp_manager.enable_temp_passthrough(
                    user_id, account_id, message
                )
                if success:
                    await self.bot.send_message(user_id, f"⏰ {msg}")
                else:
                    await self.bot.send_message(user_id, f"❌ {msg}")
            else:
                await self.bot.send_message(user_id, "❌ Account ID not found")
        self.pending_actions.pop(user_id, None)
    async def _handle_dm_group_actions(self, event, user, action, message):
        """Handle DM group configuration actions"""
        user_id = event.sender_id
        if action == "set_dm_group_id":
            await self.bot_manager.dm_reply_commands.handle_dm_group_input(event, user_id, message)
            self.pending_actions.pop(user_id, None)
    async def _handle_channel_actions(self, event, user, action, message):
        """Handle channel management actions"""
        from telethon import Button
        user_id = event.sender_id
        account_phone = self.pending_actions[user_id].get("account_phone")
        if action == "channel_join_target":
            (
                success,
                msg,
            ) = await self.bot_manager.command_handlers.channel_manager.join_channel(
                user_id, account_phone, message.strip()
            )
            result_text = f"✅ {msg}" if success else f"❌ {msg}"
            buttons = [
                [Button.inline("🔙 Back to Actions", f"manage:{account_phone}")],
                [Button.inline("🔙 Back to Accounts", "back:accounts")],
            ]
            await event.reply(result_text, buttons=buttons)
        elif action == "channel_leave_target":
            (
                success,
                msg,
            ) = await self.bot_manager.command_handlers.channel_manager.leave_channel(
                user_id, account_phone, message.strip()
            )
            result_text = f"✅ {msg}" if success else f"❌ {msg}"
            buttons = [
                [Button.inline("🔙 Back to Actions", f"manage:{account_phone}")],
                [Button.inline("🔙 Back to Accounts", "back:accounts")],
            ]
            await event.reply(result_text, buttons=buttons)
        elif action == "channel_create_type":
            channel_type = message.strip().lower()
            if channel_type not in ["channel", "group"]:
                await event.reply("❌ Invalid type. Reply with 'channel' or 'group':")
                return
            self.pending_actions[user_id] = {
                "action": "channel_create_title",
                "account_phone": account_phone,
                "type": channel_type,
            }
            await event.reply(
                f"🆕 **Create {channel_type.title()}**\n\nReply with the {channel_type} title:"
            )
        elif action == "channel_create_title":
            channel_type = self.pending_actions[user_id].get("type")
            title = message.strip()
            self.pending_actions[user_id] = {
                "action": "channel_create_about",
                "account_phone": account_phone,
                "type": channel_type,
                "title": title,
            }
            await event.reply(
                f"🆕 **Create {channel_type.title()}: {title}**\n\nReply with description (or 'skip'):"
            )
        elif action == "channel_create_about":
            channel_type = self.pending_actions[user_id].get("type")
            title = self.pending_actions[user_id].get("title")
            about = "" if message.strip().lower() == "skip" else message.strip()
            
            # Add privacy selection step
            self.pending_actions[user_id] = {
                "action": "channel_create_privacy",
                "account_phone": account_phone,
                "type": channel_type,
                "title": title,
                "about": about,
            }
            await event.reply(
                f"🔒 **Create {channel_type.title()}: {title}**\n\nChoose privacy setting:\n\n📝 Reply with:\n• 'public' - Anyone can find and join\n• 'private' - Invite-only access"
            )
        elif action == "channel_create_privacy":
            channel_type = self.pending_actions[user_id].get("type")
            title = self.pending_actions[user_id].get("title")
            about = self.pending_actions[user_id].get("about", "")
            privacy = message.strip().lower()
            
            if privacy not in ["public", "private"]:
                await event.reply("❌ Invalid privacy setting. Reply with 'public' or 'private':")
                return
            
            (
                success,
                msg,
            ) = await self.bot_manager.command_handlers.channel_manager.create_channel(
                user_id, account_phone, channel_type, title, about, privacy
            )
            result_text = f"✅ {msg}" if success else f"❌ {msg}"
            buttons = [
                [Button.inline("🔙 Back to Actions", f"manage:{account_phone}")],
                [Button.inline("🔙 Back to Accounts", "back:accounts")],
            ]
            await event.reply(result_text, buttons=buttons)
            # Clear pending action after channel creation attempt
            self.pending_actions.pop(user_id, None)
        elif action == "channel_delete_target":
            (
                success,
                msg,
            ) = await self.bot_manager.command_handlers.channel_manager.delete_channel(
                user_id, account_phone, message.strip()
            )
            result_text = f"✅ {msg}" if success else f"❌ {msg}"
            buttons = [
                [Button.inline("🔙 Back to Actions", f"manage:{account_phone}")],
                [Button.inline("🔙 Back to Accounts", "back:accounts")],
            ]
            await event.reply(result_text, buttons=buttons)
            self.pending_actions.pop(user_id, None)
        # Only clear pending actions for final actions
        if action in ["channel_join_target", "channel_leave_target", "channel_create_about", "channel_delete_target"]:
            if action not in ["channel_create_type", "channel_create_title"]:
                pass  # Already handled above
    async def _handle_session_string_import(self, event, user, action, message):
        """Handle string session import"""
        user_id = event.sender_id
        session_string = message.strip()
        
        # Handle both session login and import actions
        if hasattr(self.bot_manager, 'session_login_handler') and action == "session_string_login":
            success, msg = await self.bot_manager.session_login_handler.process_session_string(user_id, session_string)
            await event.reply(msg)
        elif hasattr(self.bot_manager, 'session_import_handler') and action == "import_string_session":
            success, msg = await self.bot_manager.session_import_handler.process_string_session(user_id, session_string)
            await event.reply(msg)
        else:
            await event.reply("❌ Session import not available")
        self.pending_actions.pop(user_id, None)
    async def _handle_session_phone_login(self, event, user, action, message):
        """Handle phone login process"""
        user_id = event.sender_id
        if hasattr(self.bot_manager, 'session_login_handler'):
            # Check if this is a verification code or 2FA password
            if user_id in self.bot_manager.session_login_handler.pending_auth:
                auth_data = self.bot_manager.session_login_handler.pending_auth[user_id]
                if auth_data.get('step') == '2fa':
                    success, msg = await self.bot_manager.session_login_handler.process_2fa_password(user_id, message.strip())
                else:
                    success, msg = await self.bot_manager.session_login_handler.process_verification_code(user_id, message.strip())
            else:
                # This is a phone number
                success, msg = await self.bot_manager.session_login_handler.process_phone_login(user_id, message.strip())
            await event.reply(msg)
        else:
            await event.reply("❌ Session login not available")
        
        # Only clear pending actions if authentication is complete
        if user_id not in getattr(self.bot_manager.session_login_handler, 'pending_auth', {}):
            self.pending_actions.pop(user_id, None)
    
    async def _handle_session_validation(self, event, user, action, message):
        """Handle session string validation"""
        user_id = event.sender_id
        session_string = message.strip()
        
        try:
            from ..core.config import API_ID, API_HASH
            from ..utils.session_utils import validate_string_session
            
            # Validate the session string
            is_valid, result = await validate_string_session(session_string, API_ID, API_HASH)
            
            if is_valid:
                # Extract session info
                user_info = result
                name = user_info.get('name', 'Unknown')
                phone = user_info.get('phone', 'Unknown')
                user_id_info = user_info.get('id', 'Unknown')
                
                # Try to determine DC from session string
                dc_info = "Unknown"
                try:
                    # Basic DC detection from session string format
                    if len(session_string) > 50:
                        # This is a rough estimation - actual DC detection would require parsing
                        dc_info = "DC1-DC5 (Valid session)"
                except:
                    dc_info = "Unknown"
                
                response = (
                    f"✅ **Session Valid**\n\n"
                    f"**Account Info:**\n"
                    f"• Name: {name}\n"
                    f"• Phone: {phone}\n"
                    f"• User ID: {user_id_info}\n"
                    f"• DC: {dc_info}\n\n"
                    f"**Session Status:** Active and authorized\n"
                    f"**Format:** Valid Telethon StringSession"
                )
            else:
                response = f"❌ **Invalid Session**\n\nError: {result}"
                
        except (ValueError, ConnectionError, ImportError) as e:
            logger.error(f"Session validation error: {e}")
            response = f"❌ **Validation Failed**\n\nError: {str(e)}"
        
        await event.reply(response)
        self.pending_actions.pop(user_id, None)
    
    async def _handle_cleanup_selection(self, event, user, action, message):
        """Handle cleanup selection input"""
        user_id = event.sender_id
        logger.info(f"Cleanup selection handler called for user {user_id}, message: {message}")
        logger.info(f"Pending actions: {self.pending_actions.get(user_id)}")
        account_id = self.pending_actions[user_id].get("account_id")
        
        if not account_id:
            await event.reply("❌ Account ID not found")
            self.pending_actions.pop(user_id, None)
            return
        
        # Validate cleanup types
        cleanup_types = message.strip().lower()
        valid_types = ['personal', 'bots', 'telegram', 'spambot', 'channels', 'groups', 'owned_groups', 'owned_channels', 'all']
        
        if cleanup_types == 'all':
            selected_types = 'all'
        else:
            selected_list = [t.strip() for t in cleanup_types.split(',')]
            invalid_types = [t for t in selected_list if t not in valid_types]
            
            if invalid_types:
                await event.reply(
                    f"❌ Invalid cleanup types: {', '.join(invalid_types)}\n\n"
                    f"Valid options: {', '.join(valid_types)}"
                )
                return
            
            selected_types = ','.join(selected_list)
        
        logger.info(f"Validated cleanup types: {selected_types} for account {account_id}")
        
        # Clear pending action before executing cleanup
        self.pending_actions.pop(user_id, None)
        
        # Delegate to cleanup operations module
        try:
            if hasattr(self.bot_manager, 'menu_system') and hasattr(self.bot_manager.menu_system, 'cleanup_operations'):
                logger.info(f"Executing cleanup via menu_system.cleanup_operations")
                # Create a mock event object for execute_cleanup
                class MockEvent:
                    def __init__(self, message_id):
                        self.message_id = message_id
                    async def answer(self, text):
                        logger.info(f"MockEvent answer: {text}")
                
                mock_event = MockEvent(event.id)
                await self.bot_manager.menu_system.cleanup_operations.execute_cleanup(
                    mock_event, user_id, account_id, selected_types
                )
                logger.info(f"Cleanup execution completed")
            else:
                logger.error("Cleanup service not available - menu_system or cleanup_operations not found")
                await event.reply("❌ Cleanup service not available")
        except Exception as e:
            logger.error(f"Error executing cleanup: {e}", exc_info=True)
            await event.reply(f"❌ Error executing cleanup: {str(e)}")
    
    async def _handle_bulk_cleanup_selection(self, event, user, action, message):
        """Handle bulk cleanup selection input"""
        user_id = event.sender_id
        cleanup_types = message.strip().lower()
        valid_types = ['personal', 'bots', 'telegram', 'spambot', 'channels', 'groups', 'owned_groups', 'owned_channels', 'all']
        
        if cleanup_types == 'all':
            selected_types = 'all'
        else:
            selected_list = [t.strip() for t in cleanup_types.split(',')]
            invalid_types = [t for t in selected_list if t not in valid_types]
            
            if invalid_types:
                await event.reply(
                    f"❌ Invalid cleanup types: {', '.join(invalid_types)}\n\n"
                    f"Valid options: {', '.join(valid_types)}"
                )
                return
            
            selected_types = ','.join(selected_list)
        
        self.pending_actions.pop(user_id, None)
        
        try:
            if hasattr(self.bot_manager, 'menu_system') and hasattr(self.bot_manager.menu_system, 'cleanup_operations'):
                await self.bot_manager.menu_system.cleanup_operations.execute_bulk_cleanup(user_id, selected_types)
            else:
                await event.reply("❌ Cleanup service not available")
        except Exception as e:
            logger.error(f"Error executing bulk cleanup: {e}")
            await event.reply(f"❌ Error: {str(e)}")
    
    
    async def _fetch_and_store_account_name(self, user_id: int, phone: str):
        """Fetch real account name from Telegram and store in database"""
        try:
            if user_id in self.user_clients and phone in self.user_clients[user_id]:
                client = self.user_clients[user_id][phone]
                if client and client.is_connected():
                    me = await retry_async(client.get_me)
                    # Format display name
                    first_name = getattr(me, 'first_name', None) or ''
                    last_name = getattr(me, 'last_name', None) or ''
                    username = getattr(me, 'username', None)
                    telegram_id = getattr(me, 'id', None)
                    display_name = ' '.join(part for part in (first_name, last_name) if part)
                    if not display_name:
                        display_name = f'@{username}' if username else phone
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "phone": phone},
                        {"$set": {
                            "first_name": first_name,
                            "last_name": last_name,
                            "username": username,
                            "telegram_id": telegram_id,
                            "display_name": display_name,
                            "name": display_name
                        }}
                    )
                    logger.info(f"Updated account info for {phone}: {display_name} (ID: {telegram_id})")
        except (ValueError, ConnectionError, AttributeError) as e:
            logger.error(f"Failed to fetch account name for {phone}: {e}")



    async def _handle_session_creation_2fa(self, event, user, action, message):
        """Handle 2FA password for session creation"""
        user_id = event.sender_id
        password = message.strip()
        
        try:
            # Delete the password message for security
            try:
                await event.delete()
            except:
                pass
            
            # Get pending auth data
            if not hasattr(self.bot_manager, 'session_login_handler'):
                await self.bot.send_message(user_id, "❌ Session login handler not available")
                self.pending_actions.pop(user_id, None)
                return
            
            session_handler = self.bot_manager.session_login_handler
            if user_id not in session_handler.pending_auth:
                await self.bot.send_message(user_id, "❌ Session creation expired. Please try again.")
                self.pending_actions.pop(user_id, None)
                return
            
            auth_data = session_handler.pending_auth[user_id]
            client = auth_data.get("client")
            phone = auth_data.get("phone")
            destroyer_was_enabled = auth_data.get("destroyer_was_enabled", False)
            account = auth_data.get("account")
            
            if not client or not phone:
                await self.bot.send_message(user_id, "❌ Invalid session state. Please try again.")
                self.pending_actions.pop(user_id, None)
                session_handler.pending_auth.pop(user_id, None)
                return
            
            # Try to sign in with 2FA password
            status_msg = await self.bot.send_message(user_id, f"🔐 Authenticating with 2FA password...")
            
            try:
                from telethon.sessions import StringSession
                await client.sign_in(password=password)
                
                # Store the password for future use
                from ..core.database_manager import db_manager
                if account:
                    await db_manager.store_2fa_password(user_id, str(account['_id']), password)
                
                # Get session string
                session_string = StringSession.save(client.session)
                await client.disconnect()
                
                # Re-enable OTP destroyer
                if destroyer_was_enabled and account:
                    await mongodb.db.accounts.update_one(
                        {"_id": account["_id"]},
                        {"$set": {"otp_destroyer_enabled": True}}
                    )
                
                # Send success message
                await status_msg.edit(
                    f"✅ **Session Created Successfully!**\n\n"
                    f"📱 Phone: {phone}\n"
                    f"📝 Session String:\n\n"
                    f"`{session_string}`\n\n"
                    f"💾 Copy and save this session string securely!\n\n"
                    f"🔐 2FA password stored for future use\n"
                    f"🛡️ OTP Destroyer re-enabled"
                )
                
            except Exception as e:
                await client.disconnect()
                if destroyer_was_enabled and account:
                    await mongodb.db.accounts.update_one(
                        {"_id": account["_id"]},
                        {"$set": {"otp_destroyer_enabled": True}}
                    )
                
                error_msg = str(e)
                if "PASSWORD_HASH_INVALID" in error_msg or "password" in error_msg.lower():
                    await status_msg.edit(
                        f"❌ **Incorrect 2FA Password**\n\n"
                        f"The password you entered is incorrect.\n\n"
                        f"Please try again by sending your correct 2FA password:"
                    )
                    # Keep the pending action so user can try again
                    return
                else:
                    await status_msg.edit(f"❌ 2FA authentication failed: {error_msg}")
            
            # Clean up
            self.pending_actions.pop(user_id, None)
            session_handler.pending_auth.pop(user_id, None)
            
        except Exception as e:
            logger.error(f"Session creation 2FA error: {e}")
            await self.bot.send_message(user_id, f"❌ Error processing 2FA password: {str(e)}")
            self.pending_actions.pop(user_id, None)
            if hasattr(self.bot_manager, 'session_login_handler'):
                self.bot_manager.session_login_handler.pending_auth.pop(user_id, None)
