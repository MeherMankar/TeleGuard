"""Split from login_via_session.py - login_helpers"""
                    3: '149.154.175.100',
                    4: '149.154.167.91',
                    5: '91.108.56.130'
                }
                server_address = dc_servers.get(dc_id, '149.154.167.51')
                
                cursor.execute(
                    'INSERT INTO sessions (dc_id, server_address, port, auth_key) VALUES (?, ?, ?, ?)',
                    (dc_id, server_address, 443, auth_key)
                )
                
                conn.commit()
                conn.close()
                
                # Extract using existing method
                extracted_session = await self._extract_session_from_file(temp_path)
                
                # Cleanup
                try:
                    os.unlink(temp_path)
                except:
                    pass
                
                if extracted_session:
                    # Quick validation
                    client = TelegramClient(
                        StringSession(extracted_session),
                        config.telegram.api_id,
                        config.telegram.api_hash,
                        connection_retries=1,
                        timeout=5
                    )
                    
                    try:
                        await asyncio.wait_for(client.connect(), timeout=5.0)
                        if await asyncio.wait_for(client.is_user_authorized(), timeout=3.0):
                            me = await asyncio.wait_for(client.get_me(), timeout=5.0)
                            info = {
                                "name": f"{me.first_name or ''} {me.last_name or ''}".strip() or "Unknown",
                                "phone": me.phone,
                                "username": me.username,
                                "id": me.id,
                                "premium": getattr(me, "premium", False),
                                "verified": getattr(me, "verified", False)
                            }
                            await client.disconnect()
                            return True, info
                        else:
                            await client.disconnect()
                            return False, "Session not authorized"
                    except:
                        try:
                            await client.disconnect()
                        except:
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
            existing = await mongodb.db.accounts.find_one({
                "user_id": user_id,
                "phone": phone
            })
            if existing:
                return False, f"❌ Account {phone} already exists"
            
            # Validate session string before saving
            if not session_string or not isinstance(session_string, str) or len(session_string) < 50:
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
                "fast_import": is_fast_import
            }
            
            result = await mongodb.db.accounts.insert_one(account_data)
            account_id = str(result.inserted_id)
            
            # Start user client with converted session
            try:
                logger.info(f"Starting client with session string (length: {len(session_string)}, type: {type(session_string)})")
                await self.bot_manager.start_user_client(user_id, name, session_string)
            except Exception as client_error:
                logger.error(f"Failed to start client with session: {client_error}")
                logger.error(f"Session string details - Length: {len(session_string) if session_string else 0}, Type: {type(session_string)}, Valid: {bool(session_string)}")
                raise client_error
            
            # Update account with real name from Telegram (like OTP login does)
            if not is_fast_import:
                await self._fetch_and_store_account_name(user_id, name, phone)
            else:
                # For fast imports, update name in background
                asyncio.create_task(self._update_fast_import_info(user_id, name, phone))
            
            logger.info(f"Successfully imported account: {name} ({phone})")
            return True, f"✅ Account {name} imported successfully!\n\n💡 Real account info will be updated automatically."
            
        except Exception as e:
            logger.error(f"Session import finalization error: {e}")
            return False, f"❌ Import failed: {str(e)}"
    
    async def _update_fast_import_info(self, user_id: int, account_name: str, phone: str):
        """Update fast import account info in background"""
        try:
            await asyncio.sleep(5)  # Wait for client to stabilize
            
            if user_id in self.user_clients and account_name in self.user_clients[user_id]:
                client = self.user_clients[user_id][account_name]
                if client and client.is_connected():
                    try:
                        me = await asyncio.wait_for(client.get_me(), timeout=10.0)
                        
                        # Format display name
                        first_name = getattr(me, 'first_name', None) or ''
                        last_name = getattr(me, 'last_name', None) or ''
                        username = getattr(me, 'username', None)
                        real_phone = getattr(me, 'phone', None) or phone
                        display_name = ' '.join(part for part in (first_name, last_name) if part)
                        if not display_name:
                            display_name = f'@{username}' if username else real_phone
                        
                        # Update account in database
                        await mongodb.db.accounts.update_one(
                            {"user_id": user_id, "name": account_name},
                            {"$set": {
                                "first_name": first_name,
                                "last_name": last_name,
                                "username": username,
                                "phone": real_phone,
                                "display_name": display_name,
                                "name": display_name,
                                "fast_import": False
                            }}
                        )
                        
                        # Update client storage if name changed
                        if display_name != account_name and user_id in self.user_clients:
                            client = self.user_clients[user_id].pop(account_name, None)
                            if client:
                                self.user_clients[user_id][display_name] = client
                        
                        logger.info(f"Updated fast import account: {display_name} ({real_phone})")
                        
                    except Exception as e:
                        logger.error(f"Failed to update fast import info: {e}")
        except Exception as e:
            logger.error(f"Background update failed for {phone}: {e}")
    
    async def _fetch_and_store_account_name(self, user_id: int, account_name: str, phone: str):
        """Fetch real account name from Telegram and store in database"""
        try:
            if user_id in self.user_clients and account_name in self.user_clients[user_id]:
                client = self.user_clients[user_id][account_name]
                if client and client.is_connected():
                    me = await retry_async(client.get_me)
                    # Format display name
                    first_name = getattr(me, 'first_name', None) or ''
                    last_name = getattr(me, 'last_name', None) or ''
                    username = getattr(me, 'username', None)
                    display_name = ' '.join(part for part in (first_name, last_name) if part)
                    if not display_name:
                        display_name = f'@{username}' if username else phone
                    
                    # Update account in database
                    await mongodb.db.accounts.update_one(
                        {"user_id": user_id, "name": account_name},
                        {"$set": {
                            "first_name": first_name,
                            "last_name": last_name,
                            "username": username,
                            "display_name": display_name,
                            "name": display_name
                        }}
                    )
                    
                    # Update client storage if name changed
                    if display_name != account_name and user_id in self.user_clients:
                        client = self.user_clients[user_id].pop(account_name, None)
                        if client:
                            self.user_clients[user_id][display_name] = client
                    
                    logger.info(f"Updated account name for {phone}: {display_name}")
        except Exception as e:
            logger.error(f"Failed to fetch account name for {phone}: {e}")
    
    async def _start_session_creation(self, event, user_id):
        """Start session creation with automatic OTP for managed accounts"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            
            if not accounts:
                try:
                    await event.edit("❌ No accounts found. Add accounts first before creating sessions.")
                except:
                    pass
                return
            
            buttons = [[Button.inline(f"📱 {acc.get('name', acc['phone'])}", f"create_sess:{acc['phone']}".encode())] for acc in accounts[:10]]
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
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "phone": phone})
            if not account:
                await event.edit("❌ Account not found")
                return
            
            account_name = account.get('name', phone)
            
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
                [Button.inline("📝 String Session", f"create_sess_fmt:{phone}:string".encode())],
                [Button.inline("📁 Session File", f"create_sess_fmt:{phone}:file".encode())],
                [Button.inline("🔙 Back", "menu:accounts")]
            ]
            
            await event.edit(text, buttons=buttons)
        except Exception as e:
            logger.error(f"Format selection error: {e}")
            await event.edit("❌ Error showing format selection")
    
    async def _execute_session_creation(self, event, user_id, phone, format_type='string'):
        """Execute session creation with auto OTP"""
        client = None
        destroyer_was_enabled = False
        account = None
        try:
            # Temporarily disable OTP destroyer
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "phone": phone})
            if account and account.get("otp_destroyer_enabled"):
                destroyer_was_enabled = True
                await mongodb.db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$set": {"otp_destroyer_enabled": False}}
                )
                logger.info(f"Temporarily disabled OTP destroyer for {phone}")
            
            await event.edit(f"⏳ Creating session for {phone}...\n\n🛡️ OTP Destroyer temporarily disabled\n1️⃣ Requesting OTP from Telegram...")
            
            device = self.get_random_device()
            client = TelegramClient(
                StringSession(),
                config.telegram.api_id,
                config.telegram.api_hash,
                device_model=device["model"],
                system_version=device["system"],
                app_version=device["version"]
            )
            
            await client.connect()
            
            phone_code_hash = None
            try:
                result = await client.send_code_request(phone)
                phone_code_hash = result.phone_code_hash
                logger.info(f"Code requested for {phone}, hash: {phone_code_hash}")
            except Exception as req_error:
                logger.error(f"Failed to request code: {req_error}")
                await client.disconnect()
                if destroyer_was_enabled and account:
                    await mongodb.db.accounts.update_one({"_id": account["_id"]}, {"$set": {"otp_destroyer_enabled": True}})
                await event.edit(f"❌ Failed to request OTP: {req_error}")
                return
            
            await event.edit(f"⏳ Creating session for {phone}...\n\n2️⃣ Waiting for OTP to arrive...")
            await asyncio.sleep(5)
            
            otp_code = await self._fetch_otp_from_telegram(user_id, phone)
            
            if not otp_code:
                await client.disconnect()
                if destroyer_was_enabled and account:
                    await mongodb.db.accounts.update_one({"_id": account["_id"]}, {"$set": {"otp_destroyer_enabled": True}})
                await event.edit("❌ Could not fetch OTP automatically.")
                return
            
            await event.edit(f"⏳ Creating session for {phone}...\n\n3️⃣ Signing in with OTP: {otp_code}...")
            
            try:
                await client.sign_in(phone, otp_code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                # 2FA required - use centralized helper
                from ..utils.twofa_helper import twofa_helper
                await event.edit(f"⏳ Creating session for {phone}...\n\n4️⃣ Checking for stored 2FA password...")
                
                success, session_str, error = await twofa_helper.try_sign_in_with_2fa(client, user_id, phone)
                
                if success:
                    # Success - continue with session creation
                    session_string = session_str
                else:
                    # Failed - ask user for password
                    if error in ["stored_password_invalid", "no_stored_password"]:
                        # Store pending session creation state
                        self.pending_auth[user_id] = {
                            "client": client,
                            "phone": phone,
                            "phone_code_hash": phone_code_hash,
                            "destroyer_was_enabled": destroyer_was_enabled,
                            "account": account,
                            "action": "session_creation_2fa"
                        }
                        
                        # Store format type for later
                        self.pending_auth[user_id]["format_type"] = format_type
                        
                        # Ask for 2FA password
                        msg = f"🔐 **2FA Password Required**\n\n"
                        if error == "stored_password_invalid":
                            msg += f"Your stored 2FA password is incorrect (changed externally).\n\n"
                        else:
                            msg += f"This account has 2FA enabled.\n\n"
                        msg += f"Please send your 2FA password to continue:"
                        
                        await event.edit(msg)
                        
                        # Set pending action for message handler
                        self.bot_manager.pending_actions[user_id] = {
                            "action": "session_creation_2fa_password",
                            "phone": phone,
                            "format_type": format_type
                        }
                        return
                    else:
                        await client.disconnect()
                        if destroyer_was_enabled and account:
                            await mongodb.db.accounts.update_one({"_id": account["_id"]}, {"$set": {"otp_destroyer_enabled": True}})
                        await event.edit(f"❌ 2FA authentication failed: {error}")
                        return
            except Exception as sign_error:
                await client.disconnect()
                if destroyer_was_enabled and account:
                    await mongodb.db.accounts.update_one({"_id": account["_id"]}, {"$set": {"otp_destroyer_enabled": True}})
                await event.edit(f"❌ Sign in failed: {sign_error}")
                return
            
            session_string = StringSession.save(client.session)
            
            # Generate session file if requested
            session_file_data = None
            if format_type == 'file':
                file_client = None
                temp_path = None
                try:
                    temp_path = f"temp_{phone}_{user_id}.session"
                    file_client = TelegramClient(temp_path, config.telegram.api_id, config.telegram.api_hash)
                    file_client.session.set_dc(client.session.dc_id, client.session.server_address, client.session.port)
                    file_client.session.auth_key = client.session.auth_key
                    file_client.session.save()
                    
                    # Disconnect and cleanup file_client
                    if file_client:
                        try:
                            await file_client.disconnect()
                        except:
                            pass
                        del file_client
                    
                    await asyncio.sleep(0.5)
                    
                    if os.path.exists(temp_path):
                        with open(temp_path, 'rb') as f:
                            session_file_data = f.read()
                        try:
                            os.remove(temp_path)
                        except Exception as del_err:
                            logger.warning(f"Could not delete temp file immediately: {del_err}")
                            try:
                                await asyncio.sleep(1)
                                os.remove(temp_path)
                            except:
                                pass
                except Exception as file_err:
                    logger.error(f"Session file creation error: {file_err}")
                    if file_client:
                        try:
                            await file_client.disconnect()
                        except:
                            pass
            
            await client.disconnect()
            
            # Re-enable OTP destroyer
            if destroyer_was_enabled and account:
                await mongodb.db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$set": {"otp_destroyer_enabled": True}}
                )
                logger.info(f"Re-enabled OTP destroyer for {phone}")
            
            # Send based on format
            if format_type == 'string':
                await event.edit(
                    f"✅ **Session String Created!**\n\n"
                    f"📱 Phone: {phone}\n"
                    f"📝 Session String:\n\n"
                    f"`{session_string}`\n\n"
                    f"💾 Copy and save securely!\n"
                    f"🛡️ OTP Destroyer re-enabled"
                )
            elif format_type == 'file':
                if session_file_data:
                    from telethon.tl.types import DocumentAttributeFilename
                    await self.bot.send_message(
                        user_id,
                        f"📁 **Session File Created!**\n\n"
                        f"📱 Phone: {phone}\n\n"
                        f"💾 Download and save securely!\n"
                        f"🛡️ OTP Destroyer re-enabled",
                        file=session_file_data,
                        attributes=[DocumentAttributeFilename(f"{phone}.session")]
                    )
                    await event.delete()
                else:
                    await event.edit(
                        f"✅ **Session Created!**\n\n"
                        f"❌ File generation failed, here's the string:\n\n"
                        f"`{session_string}`\n\n"
                        f"🛡️ OTP Destroyer re-enabled"
                    )
            
        except Exception as e:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass
            if destroyer_was_enabled and account:
                await mongodb.db.accounts.update_one({"_id": account["_id"]}, {"$set": {"otp_destroyer_enabled": True}})
            logger.error(f"Session creation error: {e}")
            await event.edit(f"❌ Error: {e}")
    
    async def _fetch_otp_from_telegram(self, user_id, target_phone):
        """Fetch OTP code from Telegram (777000) using existing accounts"""
        try:
            if user_id not in self.user_clients:
                logger.warning(f"No clients found for user {user_id}")
                return None
            
            target_phone_clean = target_phone.replace("+", "")
            logger.info(f"Fetching OTP for {target_phone} from {len(self.user_clients[user_id])} accounts")
            
            # Try multiple times with delays
            for attempt in range(3):
                for account_name, client in self.user_clients[user_id].items():
                    if not client or not client.is_connected():
                        continue
                    
                    try:
                        messages = await client.get_messages(777000, limit=15)
                        
                        for msg in messages:
                            if not msg.message:
                                continue
                            
                            # Check if message is recent (within last 60 seconds)
                            import time as time_module
                            if hasattr(msg, 'date') and (time_module.time() - msg.date.timestamp()) > 60:
                                continue
                            
                            # Check if message contains target phone or is login code
                            if target_phone_clean in msg.message or "Login code" in msg.message:
                                import re
                                code_match = re.search(r'\b(\d{5})\b', msg.message)
                                if code_match:
                                    code = code_match.group(1)
                                    # Safe logging with Unicode handling
                                    safe_name = account_name.encode('ascii', errors='replace').decode('ascii')
                                    logger.info(f"Found OTP {code} from {safe_name}")
                                    return code
                    except Exception as e:
                        logger.debug(f"Failed to fetch from {account_name}: {e}")
                        continue
                
                if attempt < 2:
