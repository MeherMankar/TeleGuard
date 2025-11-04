"""Split from join_channel.py - channel_operations"""
                # Channel no longer accessible, deletion successful
                return True, f"Successfully deleted {channel_name} (ID: {channel_id})"
            
        except errors.ChatAdminRequiredError:
            return False, "Only channel owners can delete channels"
        except errors.ChannelPrivateError:
            return False, "Channel is private or doesn't exist"
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Delete channel error: {e}")
            if "CHAT_ADMIN_REQUIRED" in error_msg:
                return False, "You don't have admin rights to delete this channel"
            elif "CHANNEL_PRIVATE" in error_msg:
                return False, "Channel is private or no longer exists"
            return False, f"Failed to delete channel: {error_msg}"
    async def get_user_channels(
        self, user_id: int, account_phone: str
    ) -> tuple[bool, list]:
        """Get list of user's channels/groups"""
        try:
            client = await self._get_client(user_id, account_phone)
            if not client:
                return False, []
            dialogs = await client.get_dialogs()
            channels = []
            for dialog in dialogs:
                if hasattr(dialog.entity, "broadcast") or hasattr(
                    dialog.entity, "megagroup"
                ):
                    channels.append(
                        {
                            "id": dialog.entity.id,
                            "title": dialog.entity.title,
                            "username": getattr(dialog.entity, "username", None),
                            "type": (
                                "channel"
                                if getattr(dialog.entity, "broadcast", False)
                                else "group"
                            ),
                        }
                    )
            return True, channels
        except Exception as e:
            logger.error(f"Get channels error: {e}")
            return False, []
    async def _get_client(self, user_id: int, account_phone: str):
        """Get Telethon client for account"""
        try:
            user_clients = self.user_clients.get(user_id, {})
            if not user_clients:
                # Try to reload clients from database
                await self._reload_user_clients(user_id)
                user_clients = self.user_clients.get(user_id, {})
                if not user_clients:
                    # Check if user has accounts but sessions are invalid
                    accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
                    if accounts:
                        invalid_sessions = [acc for acc in accounts if acc.get('session_invalid')]
                        if invalid_sessions:
                            logger.error(f"User {user_id} has accounts but sessions are invalid due to IP conflicts")
                        else:
                            logger.error(f"User {user_id} has accounts but no active clients loaded")
                    else:
                        logger.error(f"No accounts found for user {user_id}. User needs to add accounts first.")
                    return None
            
            # Try to find client by phone directly first
            client = user_clients.get(account_phone)
            if client:
                return client
            
            # Find account by phone in database
            try:
                account = await mongodb.db.accounts.find_one({
                    "user_id": user_id,
                    "phone": account_phone
                })
            except Exception as db_error:
                logger.error(f"MongoDB query error: {db_error}")
                return None
                
            if not account:
                logger.error(f"Account not found: {account_phone} for user {user_id}")
                return None
            
            # Try to find client by account name
            client = user_clients.get(account["name"])
            if not client:
                # Try display name if different
                if account.get('display_name') and account['display_name'] != account['name']:
                    client = user_clients.get(account['display_name'])
                
            if not client:
                # Try to reload this specific account
                if account.get('session_string'):
                    try:
                        await self.bot_manager.start_user_client(
                            user_id, account['name'], account['session_string']
                        )
                        client = self.user_clients.get(user_id, {}).get(account['name'])
                        if client:
                            return client
                    except Exception as reload_error:
                        error_msg = str(reload_error)
                        if "authorization key" in error_msg and "different IP addresses" in error_msg:
                            logger.error(f"Session invalidated for {account['name']}: Session used from different IP")
                            # Mark account as inactive due to invalid session
                            await mongodb.db.accounts.update_one(
                                {"user_id": user_id, "phone": account_phone},
                                {"$set": {"is_active": False, "session_invalid": True}}
                            )
                        else:
                            logger.error(f"Failed to reload client for {account['name']}: {reload_error}")
                
                logger.error(f"Client not found for account {account['name']} (phone: {account_phone}). Available clients: {list(user_clients.keys())}")
                return None
                
            return client
        except Exception as e:
            logger.error(f"Get client error: {e}")
            return None
    
    async def _reload_user_clients(self, user_id: int):
        """Reload all clients for a user from database"""
        try:
            accounts = await mongodb.db.accounts.find({
                "user_id": user_id,
                "is_active": True
            }).to_list(length=None)
            
            for account in accounts:
                if account.get('session_string'):
                    try:
                        await self.bot_manager.start_user_client(
                            user_id, account['name'], account['session_string']
                        )
                        logger.info(f"Reloaded client for {account['name']}")
                    except Exception as e:
                        logger.warning(f"Failed to reload client for {account['name']}: {e}")
        except Exception as e:
            logger.error(f"Failed to reload user clients: {e}")
    async def _resolve_channel(self, client, channel_link: str):
        """Resolve channel entity from link or username"""
        try:
            # Clean the input
            channel_link = channel_link.strip()
            # For invite links, find in dialogs instead of resolving
            invite_hash = self._extract_invite_hash(channel_link)
            if invite_hash:
                return await self._find_channel_by_invite(client, invite_hash)
            if channel_link.startswith("https://t.me/"):
                username = channel_link.split("/")[-1]
                return await client.get_entity(username)
            elif channel_link.startswith("@"):
                username = channel_link[1:]
                return await client.get_entity(username)
            elif channel_link.lstrip('-').isdigit():
                # Channel ID (with or without -100 prefix)
                channel_id = int(channel_link)
                return await client.get_entity(channel_id)
            else:
                # Check if it contains spaces or special chars - likely a channel name
                if ' ' in channel_link or any(not c.isalnum() and c != '_' for c in channel_link):
                    # Search in dialogs instead of trying to resolve as username
                    return await self._find_channel_in_dialogs(client, channel_link)
                else:
                    # Plain username
                    return await client.get_entity(channel_link)
        except Exception as e:
            logger.error(f"Resolve channel error: {e}")
            return None
    async def _find_channel_by_invite(self, client, invite_hash: str):
        """Find channel by checking invite details"""
        try:
            invite_info = await client(
                functions.messages.CheckChatInviteRequest(invite_hash)
            )
            if hasattr(invite_info, "chat"):
                # Already in this chat
                return invite_info.chat
            return None
        except Exception as e:
            logger.error(f"Find channel by invite error: {e}")
            return None
    async def _find_channel_in_dialogs(self, client, search_term: str):
        """Find channel in user's dialogs by name, username, or invite link"""
        try:
            dialogs = await client.get_dialogs()
            search_term = search_term.lower().strip()
            for dialog in dialogs:
                entity = dialog.entity
                if hasattr(entity, "title") and search_term in entity.title.lower():
                    return entity
                if (
                    hasattr(entity, "username")
                    and entity.username
                    and search_term in entity.username.lower()
                ):
                    return entity
                if search_term.isdigit() and str(entity.id) == search_term:
                    return entity
            return None
        except Exception as e:
            logger.error(f"Find channel in dialogs error: {e}")
            return None
    async def _get_user_channels_with_ids(self, client) -> list:
        """Get user's channels with IDs for selection"""
        try:
            dialogs = await client.get_dialogs()
            channels = []
            for dialog in dialogs:
                if hasattr(dialog.entity, "broadcast") or hasattr(
                    dialog.entity, "megagroup"
                ):
                    channels.append({
                        "entity": dialog.entity,
                        "id": dialog.entity.id,
                        "title": dialog.entity.title,
                        "username": getattr(dialog.entity, "username", None),
                        "type": (
                            "channel"
                            if getattr(dialog.entity, "broadcast", False)
                            else "group"
                        ),
                    })
            return channels
        except Exception as e:
            logger.error(f"Get channels with IDs error: {e}")
            return []

    def _extract_invite_hash(self, link: str) -> str:
        """Extract invite hash from various Telegram link formats"""
        import re
        link = link.strip()
        # Pattern for various invite link formats
        patterns = [
            r"t\.me/\+([A-Za-z0-9_-]+)",  # https://t.me/uk_who_im
            r"t\.me/joinchat/([A-Za-z0-9_-]+)",  # https://t.me/joinchat/uk_who_im
            r"telegram\.me/joinchat/([A-Za-z0-9_-]+)",  # https://telegram.me/joinchat/uk_who_im
            r"t\.me/addlist/([A-Za-z0-9_-]+)",  # https://t.me/addlist/hash (folder)
            r"\+([A-Za-z0-9_-]+)$",  # Direct +uk_who_im
        ]
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                return match.group(1)
