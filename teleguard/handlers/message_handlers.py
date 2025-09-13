"""Message handlers for user input processing"""

import logging
import re

from telethon import events

from ..core.mongo_database import mongodb

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
        self.secure_2fa = bot_manager.secure_2fa
        self.session_backup = bot_manager.session_backup

    def register_handlers(self):
        """Register message handlers"""

        @self.bot.on(events.NewMessage(func=lambda e: e.photo))
        async def photo_handler(event):
            await self._handle_photo_upload(event)

        @self.bot.on(events.NewMessage(incoming=True))
        async def reply_handler(event):
            await self._handle_user_reply(event)

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
                    client = self.user_clients.get(user_id, {}).get(account["name"])
                    if client:
                        photo_path = await event.download_media()

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
                except Exception as e:
                    await event.reply(f"❌ Failed to update profile photo: {e}")
            else:
                await event.reply("❌ Account not found")

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

        if user_id not in self.pending_actions:
            logger.info("User sent message but no action was pending")
            return

        action = self.pending_actions[user_id]["action"]
        logger.info(f"Processing user action: {action.replace('_', ' ').title()}")

        user = await mongodb.db.users.find_one({"telegram_id": user_id})
        if not user:
            await event.reply("Please start the bot first with /start")
            self.pending_actions.pop(user_id, None)
            return

        # Route to appropriate handler
        if action in ["add_account", "verify_otp", "verify_2fa"]:
            await self._handle_auth_actions(event, user, action, message)
        elif action.startswith("2fa_") and action != "verify_2fa":
            await self._handle_2fa_actions(event, user, action, message)
        elif action.startswith("profile_"):
            await self._handle_profile_actions(event, user, action, message)
        elif action.startswith(("message_", "set_autoreply", "compose_message")):
            await self._handle_messaging_actions(event, user, action, message)
        elif action.startswith(("otp_", "disable_otp", "set_otp", "enable_temp")):
            await self._handle_otp_actions(event, user, action, message)
        elif action.startswith("channel_"):
            await self._handle_channel_actions(event, user, action, message)
        elif action == "set_dm_group_id":
            await self._handle_dm_group_actions(event, user, action, message)
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
        if not phone.startswith("+"):
            await event.reply(
                "Please provide phone number with country code (e.g., +1234567890)"
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
                f"OTP sent to {phone}\\n\\n📱 **Enter OTP Code**\\n\\nReply with the verification code in format: 1-2-3-4-5\\n(Use hyphens between digits)"
            )

        except Exception as e:
            error_msg = str(e)
            if "wait of" in error_msg and "seconds is required" in error_msg:
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
                        f"⏰ Rate limited! Please wait {time_str} before requesting OTP for this number again.\\n\\nTry using a different phone number or wait for the cooldown to expire."
                    )
                else:
                    await event.reply(f"Rate limited: {error_msg}")
            else:
                await event.reply(f"Error sending OTP: {error_msg}")

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

            # Create account in MongoDB
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

            # Start the client for this account
            await self.bot_manager.start_user_client(user_id, phone, session_string)

            await event.reply(
                f"✅ Account {phone} added successfully!\\nUse /toggle_protection to enable OTP destroyer."
            )
            self.pending_actions.pop(user_id, None)

        except Exception as e:
            logger.error(f"Auth error: {str(e)}")
            if "Two-factor" in str(e) or "password" in str(e).lower():
                self.pending_actions[user_id]["action"] = "verify_2fa"
                await event.reply(
                    "🔐 Two-factor authentication required.\\nReply with your 2FA password."
                )
                return
            else:
                await event.reply(f"❌ Authentication failed: {str(e)}")
                # Cleanup pending actions on all error paths
                self.pending_actions.pop(user_id, None)

    async def _process_verify_2fa(self, event, user_id, password, user):
        """Process 2FA verification"""
        phone = self.pending_actions[user_id].get("phone")

        await event.reply("Verifying 2FA password...")

        try:
            session_string = await self.auth_manager.complete_auth(
                user_id, "", password
            )

            if session_string == "OTP_DESTROYED":
                await event.reply("OTP code destroyed successfully!")
                return

            await mongodb.create_account(
                user_id=user_id,
                phone=phone,
                name=phone,
                session_string=session_string,
                is_active=True,
                otp_destroyer_enabled=False,
            )

            if self.session_backup:
                try:
                    self.session_backup.store_session(phone, session_string)
                    logger.info(f"Session backed up to MongoDB for {phone}")
                except Exception as e:
                    logger.error(f"Failed to backup session for {phone}: {e}")

            await self.bot_manager.start_user_client(user_id, phone, session_string)

            await event.reply(
                f"✅ Account {phone} added successfully with 2FA!\\nUse /toggle_protection to enable OTP destroyer."
            )

        except Exception as e:
            await event.reply(f"❌ 2FA failed: {str(e)}")
            logger.error(f"2FA failed: {str(e)}")

        # Always cleanup pending actions after 2FA processing
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
                client = self.user_clients.get(user_id, {}).get(account["name"])
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
                    except Exception as e:
                        await event.reply(f"Failed to update name: {e}")
                else:
                    await event.reply("Account client not found")
            else:
                await event.reply("Account not found")

        elif action == "change_username":
            username = message.replace("@", "").strip()

            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if account:
                client = self.user_clients.get(user_id, {}).get(account["name"])
                if client:
                    try:
                        from telethon import functions

                        await client(
                            functions.account.UpdateUsernameRequest(username=username)
                        )
                        await event.reply(f"Username updated to: @{username}")
                    except Exception as e:
                        await event.reply(f"Failed to update username: {e}")
                else:
                    await event.reply("Account client not found")
            else:
                await event.reply("Account not found")

        elif action == "change_bio":
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if account:
                client = self.user_clients.get(user_id, {}).get(account["name"])
                if client:
                    try:
                        from telethon import functions

                        await client(
                            functions.account.UpdateProfileRequest(about=message)
                        )
                        await event.reply(f"Bio updated successfully")
                    except Exception as e:
                        await event.reply(f"Failed to update bio: {e}")
                else:
                    await event.reply("Account client not found")
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
            await event.reply("📝 Now send the message content:")

        elif action == "compose_message_content":
            account_id = self.pending_actions[user_id].get("account_id")
            target = self.pending_actions[user_id].get("target")
            
            # Get account name from account_id
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            
            if account:
                success = await self.bot_manager.messaging_manager.send_message(
                    user_id, account["name"], target, message
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

                # Update user's topic routing settings
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
            except Exception as e:
                logger.error(f"Failed to setup topic routing: {e}")
                await event.reply("❌ Failed to setup topic routing.")

            self.pending_actions.pop(user_id, None)

    async def _handle_otp_actions(self, event, user, action, message):
        """Handle OTP Destroyer related actions"""
        user_id = event.sender_id

        # Delete the user's message for security
        try:
            await event.delete()
        except Exception as e:
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

            (
                success,
                msg,
            ) = await self.bot_manager.command_handlers.channel_manager.create_channel(
                user_id, account_phone, channel_type, title, about
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
