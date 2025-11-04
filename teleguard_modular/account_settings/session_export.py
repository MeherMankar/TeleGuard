"""Split from create_session.py - session_export"""
                    logger.info(f"Sign-in result for {account_name}: {type(result).__name__}")
                    authenticated = True
                    
                except Exception as e:
                    # Handle 2FA requirement
                    if type(e).__name__ == "SessionPasswordNeededError":
                        from ..core.database_manager import db_manager
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
                    logger.info(f"Authenticated as: {me.first_name} {me.last_name or ''} (@{me.username or 'no_username'})")
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
                
                logger.info(f"Generated session string for {account_name}: {len(fresh_session)} characters")
                from telethon import TelegramClient
                from telethon.sessions import StringSession
                from ..core.config import config
                API_ID = config.telegram.api_id
                API_HASH = config.telegram.api_hash
                temp_session_path = f"fresh_{account_name}_{user_id}.session"
                session_file_data = None
                try:
                    string_client = TelegramClient(StringSession(fresh_session), API_ID, API_HASH)
                    await string_client.connect()
                    file_client = TelegramClient(temp_session_path, API_ID, API_HASH)
                    file_client.session.set_dc(
                        string_client.session.dc_id,
                        string_client.session.server_address,
                        string_client.session.port
                    )
                    file_client.session.auth_key = string_client.session.auth_key
                    file_client.session.save()
                    await string_client.disconnect()
                    if os.path.exists(temp_session_path):
                        with open(temp_session_path, 'rb') as f:
                            session_file_data = f.read()
                except Exception as e:
                    logger.error(f"Session file creation error: {e}")
                finally:
                    try:
                        if os.path.exists(temp_session_path):
                            os.remove(temp_session_path)
                    except Exception:
                        pass
                format_type = session_data.get('format_type', 'both')
                # Send based on requested format
                if format_type == 'string' or format_type == 'both':
                    # Validate session string before sending
                    if not fresh_session or fresh_session in ['None', '', 'null']:
                        await self.bot.send_message(user_id, f"❌ Failed to generate valid session string for {account_name}")
                    else:
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
                if format_type == 'file' or format_type == 'both':
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
                # Send notification
                await self._send_login_notification(user_id, account_name, "Fresh session created via OTP")
                # Restore DB flags and pending session
                try:
                    # unset pending flag and restore otp_destroyer_enabled
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {
                            "$unset": {"pending_fresh_session": ""},
                            "$set": {"otp_destroyer_enabled": self.bot_manager.pending_fresh_sessions[user_id].get('previous_destroyer_state', False)}
                        },
                    )
                except Exception:
                    pass
                # Remove wildcard otp_protection for this phone (cleanup)
                try:
                    await mongodb.db.otp_protections.delete_many({"phone": phone, "wildcard": True})
                except Exception:
                    logger.exception("Failed to remove otp_protections wildcard on success")
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
                # Clear DB flag and pending session on failure and restore destroyer state
                try:
                    prev_state = None
                    if self.bot_manager.pending_fresh_sessions.get(user_id):
                        prev_state = self.bot_manager.pending_fresh_sessions[user_id].get('previous_destroyer_state', False)
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {
                            "$unset": {"pending_fresh_session": ""},
                            "$set": {"otp_destroyer_enabled": prev_state if prev_state is not None else False}
                        }
                    )
                except Exception:
                    logger.exception("Failed to clear pending_fresh_session flag in DB on failure")
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
                temp_session_path = f"fresh_{account_name}_{user_id}.session"
                session_file_data = None
                try:
                    string_client = TelegramClient(StringSession(fresh_session), API_ID, API_HASH)
                    await string_client.connect()
                    file_client = TelegramClient(temp_session_path, API_ID, API_HASH)
                    file_client.session.set_dc(
                        string_client.session.dc_id,
                        string_client.session.server_address,
                        string_client.session.port
                    )
                    file_client.session.auth_key = string_client.session.auth_key
                    file_client.session.save()
                    await string_client.disconnect()
                    if os.path.exists(temp_session_path):
                        with open(temp_session_path, 'rb') as f:
                            session_file_data = f.read()
                except Exception as e:
                    logger.error(f"Session file creation error: {e}")
                finally:
                    try:
                        if os.path.exists(temp_session_path):
                            os.remove(temp_session_path)
                    except Exception:
                        pass
                format_type = session_data.get('format_type', 'both')
                # Send based on requested format
                if format_type == 'string' or format_type == 'both':
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
                if format_type == 'file' or format_type == 'both':
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
                # Send notification
                await self._send_login_notification(user_id, account_name, "Fresh session created with 2FA")
                # Restore DB flags
                try:
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {
                            "$unset": {"pending_fresh_session": ""},
                            "$set": {"otp_destroyer_enabled": session_data.get('previous_destroyer_state', False)}
                        }
                    )
                except Exception:
                    pass
                await client.disconnect()
                del self.bot_manager.pending_fresh_sessions[user_id]
                return True
            except Exception as e:
                # Clear DB flag on failure
                try:
                    prev_state = session_data.get('previous_destroyer_state', False)
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {
                            "$unset": {"pending_fresh_session": ""},
                            "$set": {"otp_destroyer_enabled": prev_state}
                        }
                    )
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
