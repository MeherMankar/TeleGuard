"""Message handlers for user input processing"""
import logging
import re
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
        @self.bot.on(events.NewMessage(incoming=True))
        async def reply_handler(event):
            try:
                await self._handle_user_reply(event)
            except Exception as e:
                logger.error(f"Unhandled exception in reply_handler: {e}")
                try:
                    await event.reply("❌ An error occurred. Please try again or contact support.")
                except Exception:
                    pass  # Ignore if we can't send error message
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
                        # Use secure temporary directory
                        temp_dir = tempfile.gettempdir()
                        photo_path = await event.download_media(file=temp_dir)
                        if not photo_path or not os.path.realpath(photo_path).startswith(os.path.realpath(temp_dir)):
                            await event.reply("❌ Invalid file path")
                            return
                        from telethon import functions
                        uploaded_file = await client.upload_file(photo_path)
                        await client(
                            functions.photos.UploadProfilePhotoRequest(
                                file=uploaded_file
                            )
                        )
                        import os
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
                        # Download the file
                        import tempfile
                        import os
                        temp_dir = tempfile.gettempdir()
                        file_path = await event.download_media(file=temp_dir)
                        if file_path and os.path.realpath(file_path).startswith(os.path.realpath(temp_dir)):
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
        if message.startswith("/"):
            # Clear pending actions for certain commands
            if message in ["/start", "/cancel", "/help"]:
                self.pending_actions.pop(user_id, None)
            return
        logger.info("User sent a message for pending action")
        if hasattr(self.bot_manager, 'session_export_handler') and hasattr(self.bot_manager, 'pending_fresh_sessions'):
            if user_id in self.bot_manager.pending_fresh_sessions:
                session_data = self.bot_manager.pending_fresh_sessions[user_id]
                if session_data.get('waiting_for_2fa'):
                    # This is a 2FA password for fresh session creation
                    success = await self.bot_manager.session_export_handler.process_fresh_session_2fa(user_id, message.strip())
                    self.pending_actions.pop(user_id, None)
                    return
                else:
                    # This is an OTP for fresh session creation
                    success = await self.bot_manager.session_export_handler.process_fresh_session_otp(user_id, message.strip())
                    if success:
                        self.pending_actions.pop(user_id, None)
                    return
        if user_id not in self.pending_actions:
            logger.info("User sent message but no action was pending")
            return
        action = self.pending_actions[user_id]["action"]
        logger.info(f"Processing user action: {action.replace('_', ' ').title()}")
        user = await mongodb.get_user(user_id)
        if not user:
            await event.reply("Please start the bot first with /start")
            self.pending_actions.pop(user_id, None)
            return
        # Route to appropriate handler
        if action in ["add_account", "verify_otp", "verify_2fa"]:
            await self._handle_auth_actions(event, user, action, message)
        elif action.startswith("2fa_") and action != "verify_2fa":
            await self._handle_2fa_actions(event, user, action, message)
        elif action in ["change_2fa_current", "remove_2fa_password", "set_2fa_password"]:
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

        else:
            if hasattr(self.bot_manager, 'session_export_handler') and hasattr(self.bot_manager, 'pending_fresh_sessions'):
                if user_id in self.bot_manager.pending_fresh_sessions:
                    session_data = self.bot_manager.pending_fresh_sessions[user_id]
                    if session_data.get('waiting_for_2fa'):
                        # This is a 2FA password for fresh session creation
                        success = await self.bot_manager.session_export_handler.process_fresh_session_2fa(user_id, message.strip())
                        self.pending_actions.pop(user_id, None)
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
        elif action == "verify_2fa":
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
            self.pending_actions[user_id] = {
                "action": "verify_otp",
                "phone": phone,
                "otp_destroyer": False,
            }
            await event.reply(
                f"OTP sent to {phone}\n\n📱 **Enter OTP Code**\n\nReply with the verification code in format: 1-2-3-4-5\n(Use hyphens between digits)"
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
        logger.info("User is verifying OTP code")
        await event.reply(f"Verifying OTP {code}...")
        try:
            session_string = await self.auth_manager.complete_auth(user_id, code)
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
            
            # Fetch and store real account name
            await self._fetch_and_store_account_name(user_id, phone)
            await event.reply(
                f"✅ Account {phone} added successfully!\nUse /toggle_protection to enable OTP destroyer."
            )
            self.pending_actions.pop(user_id, None)
        except Exception as e:
            logger.error(f"Auth error: {str(e)}")
            error_msg = str(e)
            
            if "Two-factor" in error_msg or "password" in error_msg.lower():
                self.pending_actions[user_id]["action"] = "verify_2fa"
                await event.reply(
                    "🔐 Two-factor authentication required.\nReply with your 2FA password."
                )
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
                # Cleanup pending actions on other errors
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
            # Ask permission before storing 2FA password
            if account_id and self.bot_manager:
                self.bot_manager.pending_2fa_storage[user_id] = {
                    "account_id": account_id,
                    "password": password,
                    "phone": phone
                }
            if self.session_backup:
                try:
                    self.session_backup.store_session(phone, session_string)
                    logger.info(f"Session backed up to MongoDB for {phone}")
                except Exception as e:
                    logger.error(f"Failed to backup session for {phone}: {e}")
            await self.bot_manager.start_user_client(user_id, phone, session_string)
            
            # Fetch and store real account name
            await self._fetch_and_store_account_name(user_id, phone)
            await event.reply(
                f"✅ Account {phone} added successfully with 2FA!\n🔐 2FA password securely stored for future use.\nUse /toggle_protection to enable OTP destroyer."
            )
        except (ValueError, ConnectionError, TimeoutError) as e:
            error_msg = str(e)
            if "attempts left" in error_msg or "Try again in" in error_msg:
                # Password retry case - keep pending action for retry
                await event.reply(f"❌ {error_msg}")
                logger.info(f"2FA retry for user {user_id}: {error_msg}")
                return  # Don't clear pending actions
            elif "Too many incorrect attempts" in error_msg:
                # Terminal failure - clear everything
                await event.reply(f"❌ {error_msg}")
                logger.error(f"2FA terminal failure for user {user_id}: {error_msg}")
            else:
                # Other errors
                await event.reply(f"❌ 2FA failed: {error_msg}")
                logger.error(f"2FA failed: {error_msg}")
        # Cleanup pending actions after 2FA processing (except for retries)
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
                        "🔑 **Set New 2FA Password**\n\nReply with your new 2FA password:\n\n⚠️ Message will be deleted after processing for security."
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
                account_name = account.get('name') or account.get('phone') or account.get('display_name', 'Unknown')
                client = self.user_clients.get(user_id, {}).get(account_name)
                if client:
                    try:
                        from telethon import functions
                        await client(
                            functions.account.UpdateProfileRequest(
                                first_name=first_name, last_name=last_name
                            )
                        )
                        await event.reply(
                            f"Profile name updated to: {first_name} {last_name}"
                        )
                    except (ValueError, ConnectionError) as e:
                        await event.reply(f"Failed to update name: {e}")
                else:
                    await event.reply(f"Account client not found. Account: {account.get('name', 'Unknown')}, User: {user_id}")
            else:
                await event.reply("Account not found")
        elif action == "change_username":
            username = message.replace("@", "").strip()
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if account:
                account_name = account.get('name') or account.get('phone') or account.get('display_name', 'Unknown')
                client = self.user_clients.get(user_id, {}).get(account_name)
                if client:
                    try:
                        from telethon import functions
                        await client(
                            functions.account.UpdateUsernameRequest(username=username)
                        )
                        await event.reply(f"Username updated to: @{username}")
                    except (ValueError, ConnectionError) as e:
                        await event.reply(f"Failed to update username: {e}")
                else:
                    await event.reply(f"Account client not found. Account: {account.get('name', 'Unknown')}, User: {user_id}")
            else:
                await event.reply("Account not found")
        elif action == "change_bio":
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if account:
                account_name = account.get('name') or account.get('phone') or account.get('display_name', 'Unknown')
                client = self.user_clients.get(user_id, {}).get(account_name)
                if client:
                    try:
                        from telethon import functions
                        await client(
                            functions.account.UpdateProfileRequest(about=message)
                        )
                        await event.reply(f"Bio updated successfully")
                    except (ValueError, ConnectionError) as e:
                        await event.reply(f"Failed to update bio: {e}")
                else:
                    await event.reply(f"Account client not found. Account: {account.get('name', 'Unknown')}, User: {user_id}")
            else:
                await event.reply("Account not found")
        self.pending_actions.pop(user_id, None)
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
            if account:
                account_name = account.get('name') or account.get('phone') or account.get('display_name', 'Unknown')
                success = await self.messaging_manager.send_message(
                    user_id, account_name, target, message
                )
                await event.reply(
                    "✅ Message sent!" if success else "❌ Failed to send message."
                )
            else:
                await event.reply("❌ Account not found.")
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
                    display_name = ' '.join(part for part in (first_name, last_name) if part)
                    if not display_name:
                        display_name = f'@{username}' if username else phone
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "phone": phone},
                        {"$set": {
                            "first_name": first_name,
                            "last_name": last_name,
                            "username": username,
                            "display_name": display_name,
                            "name": display_name
                        }}
                    )
                    logger.info(f"Updated account name for {phone}: {display_name}")
        except (ValueError, ConnectionError, AttributeError) as e:
            logger.error(f"Failed to fetch account name for {phone}: {e}")
