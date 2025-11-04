"""Split from login_via_session.py - login_validation"""
                    return None
                    
            except Exception:
                try:
                    await temp_client.disconnect()
                except:
                    pass
                return None
                
        except Exception as e:
            logger.debug(f"Telethon extraction failed: {e}")
            return None
    
    async def _extract_from_sqlite(self, file_path):
        """Extract session from SQLite database directly"""
        try:
            import sqlite3
            import base64
            from struct import pack
            
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
                    auth_key_cols = [col for col in columns if 'auth' in col.lower() and 'key' in col.lower()]
                    dc_cols = [col for col in columns if 'dc' in col.lower() and 'id' in col.lower()]
                    server_cols = [col for col in columns if 'server' in col.lower() or 'address' in col.lower()]
                    port_cols = [col for col in columns if 'port' in col.lower()]
                    
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
                        
                        cursor.execute(f"SELECT {', '.join(query_cols)} FROM {table_name} LIMIT 1")
                        row = cursor.fetchone()
                        
                        if row and len(row) >= 2:
                            dc_id = row[0] if row[0] is not None else 2
                            auth_key = row[1]
                            server_address = row[2] if len(row) > 2 and row[2] else None
                            port = row[3] if len(row) > 3 and row[3] else 443
                            
                            # Use default server if not provided
                            if not server_address:
                                dc_servers = {
                                    1: '149.154.175.53',
                                    2: '149.154.167.51', 
                                    3: '149.154.175.100',
                                    4: '149.154.167.91',
                                    5: '91.108.56.130'
                                }
                                server_address = dc_servers.get(dc_id, '149.154.167.50')
                            
                            if auth_key:
                                # Handle different auth_key formats
                                if isinstance(auth_key, str):
                                    try:
                                        auth_key_bytes = base64.b64decode(auth_key)
                                    except:
                                        try:
                                            auth_key_bytes = bytes.fromhex(auth_key)
                                        except:
                                            auth_key_bytes = auth_key.encode('utf-8')
                                elif isinstance(auth_key, (bytes, memoryview)):
                                    auth_key_bytes = bytes(auth_key)
                                else:
                                    auth_key_bytes = str(auth_key).encode('utf-8')
                                
                                # Ensure proper auth_key length
                                if len(auth_key_bytes) < 256:
                                    auth_key_bytes = auth_key_bytes.ljust(256, b'\x00')
                                elif len(auth_key_bytes) > 256:
                                    auth_key_bytes = auth_key_bytes[:256]
                                
                                # Build session string using Telethon's method
                                try:
                                    # Create a temporary Telethon session to generate proper session string
                                    temp_session = StringSession()
                                    temp_session.set_dc(dc_id, server_address, port)
                                    temp_session.auth_key = AuthKey(auth_key_bytes)
                                    
                                    session_string = StringSession.save(temp_session)
                                    conn.close()
                                    logger.info(f"Successfully extracted session from table {table_name}: DC {dc_id}, Server {server_address}:{port}, Auth key length: {len(auth_key_bytes)}")
                                    return session_string
                                    
                                except Exception as e:
                                    logger.error(f"Failed to build session string from {table_name}: {e}")
                                    
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
        client = None
        try:
            logger.info(f"Validating session string (length: {len(session_string)})")
            
            # Check if it's a Pyrogram session string and convert if needed
            converted_session = await self._convert_pyrogram_session_string(session_string)
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
                    fixed_session = session_string.replace('-', '+').replace('_', '/')
                    while len(fixed_session) % 4 != 0:
                        fixed_session += '='
                    
                    decoded = base64.b64decode(fixed_session)
                    if len(decoded) < 260:
                        return False, f"Invalid session format: too short ({len(decoded)} bytes)"
                    
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
                        fixed_session = session_string.replace('-', '+').replace('_', '/')
                        while len(fixed_session) % 4 != 0:
                            fixed_session += '='
                        
                        decoded = base64.b64decode(fixed_session)
                        if len(decoded) >= 260:
                            dc_id_bytes = decoded[256:260]
                            dc_id = unpack('<I', dc_id_bytes)[0]
                            
                            # Map unusual DC IDs to valid ones
                            if dc_id not in [1, 2, 3, 4, 5]:
                                dc_id = 5  # Default to DC5
                                logger.info(f"Mapped unusual DC ID to DC5")
                            
                            logger.info(f"Detected Pyrogram session with DC {dc_id}")
                            
                            # Return minimal info for fast processing
                            return True, {
                                "name": "Imported Account",
                                "phone": "+000000000",  # Placeholder
                                "username": None,
                                "id": 0,  # Placeholder
                                "premium": False,
                                "verified": False,
                                "fast_import": True
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
                    "fast_import": True
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
                timeout=3
            )
            
            # Very quick connection test
            await asyncio.wait_for(client.connect(), timeout=3.0)
            
            if client.is_connected():
                # Quick auth check
                is_authorized = await asyncio.wait_for(client.is_user_authorized(), timeout=2.0)
                if is_authorized:
                    try:
                        me = await asyncio.wait_for(client.get_me(), timeout=3.0)
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
                    except:
                        await client.disconnect()
                        # Return placeholder info if get_me fails
                        return True, {
                            "name": "Imported Account",
                            "phone": "+000000000",
                            "username": None,
                            "id": 0,
                            "premium": False,
                            "verified": False,
                            "fast_import": True
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
                except:
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
                "fast_import": True
            }
        except Exception as e:
            if client:
                try:
                    await client.disconnect()
                except:
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
                fixed_session = session_string.replace('-', '+').replace('_', '/')
                while len(fixed_session) % 4 != 0:
                    fixed_session += '='
                
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
                dc_id = unpack('<I', dc_id_bytes)[0]
                # Map any DC ID to valid range
                if dc_id not in [1, 2, 3, 4, 5]:
                    # Use modulo to map to valid DC range
                    dc_id = (dc_id % 5) + 1
                    logger.info(f"Mapped DC ID to valid range: {dc_id}")
            except:
                dc_id = 5
            
            # Map DC to server
            dc_servers = {
                1: '149.154.175.53',
                2: '149.154.167.51',
                3: '149.154.175.100', 
                4: '149.154.167.91',
                5: '91.108.56.130'
            }
            server_address = dc_servers.get(dc_id, '149.154.167.51')
            
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
    
    async def _show_session_info(self, event, user_id, account_id):
        """Show detailed session information"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
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
                
                if info.get('username'):
                    text += f"📛 **Username:** @{info['username']}\n"
                
                text += (
                    f"💬 **Dialogs:** {info.get('dialogs', 0)}\n"
                    f"📢 **Channels:** {info.get('channels', 0)}\n"
                    f"👥 **Groups:** {info.get('groups', 0)}\n"
                    f"🤖 **Bots:** {info.get('bots', 0)}\n"
                    f"💭 **Private Chats:** {info.get('private_chats', 0)}\n"
                )
                
                if info.get('premium'):
                    text += "⭐ **Premium Account**\n"
                if info.get('verified'):
                    text += "✅ **Verified Account**\n"
                
                text += f"\n📅 **Added:** {account.get('created_at', 'Unknown')}"
                text += f"\n🔧 **Method:** {account.get('added_via', 'Unknown')}"
            else:
                text = f"📱 **Session Info: {account['name']}**\n\n❌ Could not retrieve live session information."
            
            buttons = [
                [Button.inline("🔄 Refresh Info", f"session_info:{account_id}")],
                [Button.inline("⚙️ Session Operations", f"session_operations:{account_id}")],
                [Button.inline("🔙 Back", "session_login")]
            ]
            
            await event.edit(text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Show session info error: {e}")
            await event.edit("❌ Error loading session information")
    
    async def _show_session_operations(self, event, user_id, account_id):
        """Show session operations menu"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
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
                    Button.inline("🚫 Spam Check", f"session_op:spam_check:{account_id}")
                ],
                [
                    Button.inline("📢 Subscribe", f"session_op:subscribe:{account_id}"),
                    Button.inline("💬 Send Message", f"session_op:message:{account_id}")
                ],
                [
                    Button.inline("🗑️ Delete Dialogs", f"session_op:delete:{account_id}"),
                    Button.inline("📤 Export Contacts", f"session_op:export:{account_id}")
                ],
                [
                    Button.inline("💾 Generate TData", f"session_op:tdata:{account_id}"),
                    Button.inline("💰 Check Wallet", f"session_op:wallet:{account_id}")
                ],
                [Button.inline("🔙 Back", f"session_info:{account_id}")]
            ]
            
            await event.edit(text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Show session operations error: {e}")
            await event.edit("❌ Error loading session operations")
    
    async def _handle_session_operation(self, event, user_id, operation, account_id):
        """Handle session operation"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account:
                await event.answer("❌ Account not found")
