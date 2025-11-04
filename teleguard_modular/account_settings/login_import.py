"""Split from login_via_session.py - login_import"""
                return
            
            if operation == "update":
                await self._update_session_info(event, user_id, account_id)
            elif operation == "spam_check":
                await self._check_spam_status(event, user_id, account_id)
            elif operation == "subscribe":
                await self._start_channel_subscribe(event, user_id, account_id)
            elif operation == "message":
                await self._start_send_message(event, user_id, account_id)
            elif operation == "delete":
                await self._show_delete_options(event, user_id, account_id)
            elif operation == "export":
                await self._export_contacts(event, user_id, account_id)
            elif operation == "tdata":
                await self._generate_tdata(event, user_id, account_id)
            elif operation == "wallet":
                await self._check_crypto_wallet(event, user_id, account_id)
            else:
                await event.answer("❌ Unknown operation")
                
        except Exception as e:
            logger.error(f"Handle session operation error: {e}")
            await event.answer("❌ Operation failed")
    
    async def _get_live_session_info(self, user_id, account_name):
        """Get live session information"""
        try:
            if user_id not in self.user_clients or account_name not in self.user_clients[user_id]:
                return None
            
            client = self.user_clients[user_id][account_name]
            if not client or not client.is_connected():
                return None
            
            me = await client.get_me()
            dialogs = await client.get_dialogs()
            
            # Count different types of entities
            stats = {"contacts": 0, "channels": 0, "bots": 0, "groups": 0, "private_chats": 0}
            
            for dialog in dialogs:
                entity = dialog.entity
                if isinstance(entity, User):
                    if getattr(entity, "bot", False):
                        stats["bots"] += 1
                    else:
                        stats["private_chats"] += 1
                elif isinstance(entity, Channel):
                    if getattr(entity, "broadcast", False):
                        stats["channels"] += 1
                    else:
                        stats["groups"] += 1
                elif isinstance(entity, Chat):
                    stats["groups"] += 1
            
            return {
                "name": f"{me.first_name or ''} {me.last_name or ''}".strip(),
                "premium": getattr(me, "premium", False),
                "verified": getattr(me, "verified", False),
                "id": me.id,
                "username": me.username,
                "phone": me.phone,
                "dialogs": len(dialogs),
                **stats
            }
            
        except Exception as e:
            logger.error(f"Get live session info error: {e}")
            return None
    
    async def _resend_code(self, event, user_id):
        """Resend verification code"""
        try:
            if user_id not in self.pending_auth:
                await event.answer("❌ No pending authentication")
                return
            
            auth_data = self.pending_auth[user_id]
            phone = auth_data["phone"]
            
            # Cancel current auth and start fresh
            await self._cleanup_auth(user_id)
            
            success, message = await self.process_phone_login(user_id, phone)
            if success:
                await event.edit(f"📨 Code resent to {phone}. Please enter the new verification code:")
            else:
                await event.edit(message)
                
        except Exception as e:
            logger.error(f"Resend code error: {e}")
            await event.answer("❌ Error resending code")
    
    async def _restart_auth(self, event, user_id):
        """Restart authentication process"""
        try:
            await self._cleanup_auth(user_id)
            await self._show_session_login_menu(event, user_id)
        except Exception as e:
            logger.error(f"Restart auth error: {e}")
            await event.answer("❌ Error restarting authentication")
    
    async def _cleanup_auth(self, user_id):
        """Clean up authentication resources"""
        try:
            if user_id in self.pending_auth:
                auth_data = self.pending_auth[user_id]
                client = auth_data.get("client")
                if client:
                    try:
                        await client.disconnect()
                    except:
                        pass
                self.pending_auth.pop(user_id, None)
        except Exception as e:
            logger.error(f"Cleanup auth error: {e}")
    
    async def _update_session_info(self, event, user_id, account_id):
        """Update session information"""
        try:
            await event.answer("🔄 Updating session info...")
            await self._show_session_info(event, user_id, account_id)
        except Exception as e:
            logger.error(f"Update session info error: {e}")
            await event.answer("❌ Error updating session info")
    
    async def _check_spam_status(self, event, user_id, account_id):
        """Check spam status"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                await event.answer("❌ Account not available")
                return
            
            client = self.user_clients[user_id][account["name"]]
            
            # Check spam status with @spambot
            try:
                spambot = await client.get_entity("spambot")
                await client.send_message(spambot, "/start")
                await asyncio.sleep(3)
                
                messages = await client.get_messages(spambot, limit=1)
                if messages and messages[0].message:
                    message_text = messages[0].message.lower()
                    is_blocked = any(word in message_text for word in ["ограничен", "limited", "restricted"])
                    status = "🚫 Spam Blocked" if is_blocked else "✅ Not Blocked"
                else:
                    status = "❓ Unknown Status"
            except Exception:
                status = "❌ Check Failed"
            
            await event.answer(f"Spam Status: {status}")
            
        except Exception as e:
            logger.error(f"Check spam status error: {e}")
            await event.answer("❌ Error checking spam status")
    
    async def _start_channel_subscribe(self, event, user_id, account_id):
        """Start channel subscription process"""
        try:
            self.bot_manager.pending_actions[user_id] = {
                "action": "session_subscribe_channel",
                "account_id": account_id
            }
            
            text = (
                "📢 **Subscribe to Channel**\n\n"
                "Send the channel link or username:\n\n"
                "**Examples:**\n"
                "• @channelname\n"
                "• https://t.me/channelname\n"
                "• t.me/channelname\n\n"
                "Reply with the channel link:"
            )
            
            await event.edit(text)
            await event.answer("📢 Reply with channel link")
            
        except Exception as e:
            logger.error(f"Start channel subscribe error: {e}")
            await event.answer("❌ Error starting channel subscription")
    
    async def _start_send_message(self, event, user_id, account_id):
        """Start send message process"""
        try:
            self.bot_manager.pending_actions[user_id] = {
                "action": "session_send_message_target",
                "account_id": account_id
            }
            
            text = (
                "💬 **Send Message**\n\n"
                "Enter the recipient:\n\n"
                "**Examples:**\n"
                "• @username\n"
                "• +1234567890\n"
                "• 123456789 (user ID)\n\n"
                "Reply with the recipient:"
            )
            
            await event.edit(text)
            await event.answer("💬 Reply with recipient")
            
        except Exception as e:
            logger.error(f"Start send message error: {e}")
            await event.answer("❌ Error starting message send")
    
    async def _show_delete_options(self, event, user_id, account_id):
        """Show dialog deletion options"""
        try:
            text = (
                f"🗑️ **Delete Dialogs**\n\n"
                "Choose what to delete:\n\n"
                "**⚠️ Warning:** This action cannot be undone!\n\n"
                "Select dialog type to delete:"
            )
            
            buttons = [
                [
                    Button.inline("📢 All Channels", f"session_delete:channels:{account_id}"),
                    Button.inline("👥 All Groups", f"session_delete:groups:{account_id}")
                ],
                [
                    Button.inline("🤖 All Bots", f"session_delete:bots:{account_id}"),
                    Button.inline("💭 Private Chats", f"session_delete:private:{account_id}")
                ],
                [Button.inline("🔙 Back", f"session_operations:{account_id}")]
            ]
            
            await event.edit(text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Show delete options error: {e}")
            await event.answer("❌ Error showing delete options")
    
    async def _export_contacts(self, event, user_id, account_id):
        """Export contacts"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                await event.answer("❌ Account not available")
                return
            
            client = self.user_clients[user_id][account["name"]]
            
            # Export contacts
            contacts_result = await client(GetContactsRequest(hash=0))
            users = contacts_result.users
            
            # Create contacts file
            lines = ["Name\tUsername\tPhone\tID"]
            for user in users:
                name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
                username = user.username or ""
                phone = user.phone or ""
                user_id_str = str(user.id)
                lines.append(f"{name}\t{username}\t{phone}\t{user_id_str}")
            
            contacts_text = "\n".join(lines)
            contacts_file = io.BytesIO(contacts_text.encode("utf-8"))
            contacts_file.name = f"contacts_{account['name']}.txt"
            
            await self.bot.send_file(
                user_id,
                contacts_file,
                caption=f"📤 Contacts exported from {account['name']}\n\nTotal contacts: {len(users)}"
            )
            
            await event.answer("📤 Contacts exported successfully!")
            
        except Exception as e:
            logger.error(f"Export contacts error: {e}")
            await event.answer("❌ Error exporting contacts")
    
    async def _generate_tdata(self, event, user_id, account_id):
        """Generate TData archive"""
        try:
            await event.answer("💾 Generating TData... This may take a moment.")
            
            # This is a placeholder - TData generation is complex
            # In a real implementation, you would need to:
            # 1. Create TData directory structure
            # 2. Convert session to TData format
            # 3. Create proper key files
            # 4. Package as archive
            
            text = (
                "💾 **TData Generation**\n\n"
                "TData generation is a complex process that requires:\n\n"
                "• Session conversion to TData format\n"
                "• Key file generation\n"
                "• Directory structure creation\n"
                "• Archive packaging\n\n"
                "This feature is currently under development.\n\n"
                "For now, you can export the session string instead."
            )
            
            buttons = [
                [Button.inline("📝 Export Session String", f"session_export_string:{account_id}")],
                [Button.inline("🔙 Back", f"session_operations:{account_id}")]
            ]
            
            await event.edit(text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Generate TData error: {e}")
            await event.answer("❌ Error generating TData")
    
    async def _check_crypto_wallet(self, event, user_id, account_id):
        """Check cryptocurrency wallet"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                await event.answer("❌ Account not available")
                return
            
            client = self.user_clients[user_id][account["name"]]
            
            # Check wallet with @wallet bot
            try:
                wallet_bot = await client.get_entity("wallet")
                await client.send_message(wallet_bot, "/balance")
                await asyncio.sleep(3)
                
                messages = await client.get_messages(wallet_bot, limit=1)
                if messages and messages[0].message:
                    balance_info = messages[0].message
                else:
                    balance_info = "No wallet information available"
            except Exception:
                balance_info = "Wallet bot not accessible"
            
            text = f"💰 **Crypto Wallet Balance**\n\n{balance_info}"
            buttons = [[Button.inline("🔙 Back", f"session_operations:{account_id}")]]
            
            await event.edit(text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Check crypto wallet error: {e}")
            await event.answer("❌ Error checking wallet")
    
    async def subscribe_to_channel(self, user_id, account_id, channel_link):
        """Subscribe to channel"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                return False, "❌ Account not available"
            
            client = self.user_clients[user_id][account["name"]]
            
            # Subscribe to channel
            await client(JoinChannelRequest(channel_link))
            
            return True, f"✅ Successfully subscribed to {channel_link}"
            
        except Exception as e:
            logger.error(f"Subscribe to channel error: {e}")
            return False, f"❌ Subscription failed: {str(e)}"
    
    async def send_message_to_user(self, user_id, account_id, recipient, message_text, media_path=None):
        """Send message to user"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                return False, "❌ Account not available"
            
            client = self.user_clients[user_id][account["name"]]
            
            # Send message
            if media_path and os.path.exists(media_path):
                await client.send_file(recipient, media_path, caption=message_text)
            else:
                await client.send_message(recipient, message_text)
            
            return True, f"✅ Message sent to {recipient}"
            
        except Exception as e:
            logger.error(f"Send message error: {e}")
            return False, f"❌ Message failed: {str(e)}"
    
    async def delete_dialogs_by_type(self, user_id, account_id, dialog_type):
        """Delete dialogs by type"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                return False, "❌ Account not available"
            
            client = self.user_clients[user_id][account["name"]]
            
            # Get dialogs
            dialogs = await client.get_dialogs()
            deleted_count = 0
            
            for dialog in dialogs:
                entity = dialog.entity
                should_delete = False
                
                if dialog_type == "channels" and isinstance(entity, Channel) and getattr(entity, "broadcast", False):
                    should_delete = True
                elif dialog_type == "groups" and isinstance(entity, (Channel, Chat)) and not getattr(entity, "broadcast", False):
                    should_delete = True
                elif dialog_type == "bots" and isinstance(entity, User) and getattr(entity, "bot", False):
                    should_delete = True
                elif dialog_type == "private" and isinstance(entity, User) and not getattr(entity, "bot", False):
                    should_delete = True
                
                if should_delete:
                    try:
                        await client.delete_dialog(entity)
                        deleted_count += 1
                        await asyncio.sleep(1)  # Rate limiting
                    except Exception as e:
                        logger.warning(f"Failed to delete dialog: {e}")
            
            return True, f"✅ Deleted {deleted_count} {dialog_type}"
            
        except Exception as e:
            logger.error(f"Delete dialogs error: {e}")
            return False, f"❌ Deletion failed: {str(e)}"
    
    async def _process_session_via_temp_file(self, session_string):
        """Process session string by creating temporary file"""
        try:
            import base64
            import sqlite3
            import tempfile
            import os
            from struct import unpack
            
            # Try to decode as Pyrogram session with URL-safe base64
            try:
                # Convert URL-safe base64 and fix padding
                fixed_session = session_string.replace('-', '+').replace('_', '/')
                while len(fixed_session) % 4 != 0:
                    fixed_session += '='
                
                decoded = base64.b64decode(fixed_session)
                if len(decoded) < 260:
                    return False, "Invalid session format"
                
                auth_key = decoded[:256]
                dc_id_bytes = decoded[256:260]
                dc_id = unpack('<I', dc_id_bytes)[0]
                
                # Normalize DC ID to valid range
                if dc_id not in [1, 2, 3, 4, 5]:
                    dc_id = (dc_id % 5) + 1
                    logger.info(f"Mapped unusual DC ID to valid range: {dc_id}")
                
                # Create temp file
                with tempfile.NamedTemporaryFile(suffix='.session', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                conn = sqlite3.connect(temp_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    CREATE TABLE sessions (
                        dc_id INTEGER,
                        server_address TEXT,
                        port INTEGER,
                        auth_key BLOB
                    )
                ''')
                
                dc_servers = {
                    1: '149.154.175.53',
                    2: '149.154.167.51',
