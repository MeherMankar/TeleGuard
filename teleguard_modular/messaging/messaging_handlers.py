"""Split from smart_messaging.py - messaging_handlers"""
        try:
            sender_name = self._get_topic_title(sender)
            account_name = getattr(managed_account, 'username', None)
            if account_name:
                account_name = f"@{account_name}"
            else:
                account_name = getattr(managed_account, 'first_name', f"ID: {managed_account.id}")
            if event.text:
                content = event.text
            elif event.media:
                content = "[Media/File]"
            else:
                content = "[Message]"
            forward_text = (
                f"📨 **From:** {sender_name}\n"
                f"📱 **To:** {account_name}\n\n"
                f"{content}"
            )
            await self.bot.send_message(
                admin_group_id,
                forward_text,
                reply_to=topic_id,
                parse_mode='md'
            )
        except Exception as e:
            logger.error(f"Failed to forward to topic: {e}")
    async def _get_topic_mapping(self, admin_group_id: int, topic_id: int) -> Optional[dict]:
        """Get user and account mapping from database"""
        try:
            if not isinstance(admin_group_id, int) or not isinstance(topic_id, int):
                logger.error("Invalid input types for topic mapping lookup")
                return None
            mapping = await mongodb.db.topic_mappings.find_one({
                "admin_group_id": admin_group_id,
                "topic_id": topic_id
            })
            if mapping:
                return {
                    'user_id': mapping['sender_id'],
                    'account_id': mapping['account_id']
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get topic mapping: {e}")
            return None
    async def _send_topic_reply(self, mapping: dict, message_text: str):
        """Send reply from topic to original sender"""
        try:
            target_user_id = mapping['user_id']
            managed_account_id = mapping['account_id']
            # Find the managed client
            managed_client = await self._get_client_by_id(managed_account_id)
            if managed_client:
                await managed_client.send_message(target_user_id, message_text)
        except Exception as e:
            logger.error(f"Failed to send topic reply: {e}", exc_info=True)
    async def _get_client_by_id(self, account_id: int):
        """Get managed client by account ID"""
        for user_id, clients in self.user_clients.items():
            for account_name, client in clients.items():
                if client and client.is_connected():
                    try:
                        me = await client.get_me()
                        if me.id == account_id:
                            return client
                    except Exception:
                        continue
        return None
    async def _send_bot_message_directly(self, user_id: int, sender, managed_account, event):
        """Send bot messages directly via bot instead of topics"""
        try:
            sender_name = self._get_topic_title(sender)
            account_name = getattr(managed_account, 'username', None)
            if account_name:
                account_name = f"@{account_name}"
            else:
                account_name = getattr(managed_account, 'first_name', f"ID: {managed_account.id}")
            if event.text:
                content = event.text
            elif event.media:
                content = "[Media/File]"
            else:
                content = "[Message]"
            direct_message = (
                f"🤖 **Bot Message**\n"
                f"📨 **From:** {sender_name} (Bot)\n"
                f"📱 **To:** {account_name}\n\n"
                f"{content}"
            )
            await self.bot.send_message(
                user_id,
                direct_message,
                parse_mode='md'
            )
        except Exception as e:
            logger.error(f"Failed to send bot message directly: {e}")
    async def _get_user_admin_group(self, user_id: int) -> Optional[int]:
        """Get admin group ID for user"""
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if not user:
                return None
            admin_group_id = user.get("dm_reply_group_id")
            if not admin_group_id:
                return None
            try:
                await self.bot.get_entity(admin_group_id)
                return admin_group_id
            except Exception as access_error:
                return None
        except Exception as e:
            logger.error(f"Failed to get admin group: {e}")
            return None
    # Messaging functionality
    async def send_message(self, user_id: int, account_name: str, target: str, message: str) -> bool:
        """Send message from specific account with proper target handling"""
        try:
            client = self.user_clients.get(user_id, {}).get(account_name)
            if not client:
                logger.error(f"Client not found for {account_name}")
                return False
            resolved_target = await self._resolve_target(client, target)
            if resolved_target is None:
                return False
            await client.send_message(resolved_target, message)
            return True
        except Exception as e:
            error_msg = str(e)
            if "authorization key" in error_msg and "simultaneously" in error_msg:
                logger.warning(f"Session conflict detected for {account_name}")
                # Mark account as having session conflict
                await mongodb.db.accounts.update_one(
                    {"user_id": user_id, "name": account_name},
                    {"$set": {"session_conflict": True}}
                )
                return False
            logger.error(f"Failed to send message from {account_name} to {target}: {e}")
            return False
    async def _resolve_target(self, client, target: str):
        """Resolve target to proper entity"""
        try:
            # If it's a numeric string, treat as user ID
            if target.isdigit():
                user_id = int(target)
                # Try multiple approaches for user ID resolution
                try:
                    # First try to get entity normally
                    entity = await client.get_entity(user_id)
                    return entity
                except Exception as e1:
                    # Try using InputPeerUser with access_hash=0
                    try:
                        from telethon.tl.types import InputPeerUser
                        input_peer = InputPeerUser(user_id=user_id, access_hash=0)
                        return input_peer
                    except Exception as e2:
                        return None
            # If it starts with @, it's a username
            if target.startswith('@'):
                username = target[1:]
                return username
            # If it starts with +, it's a phone number
            if target.startswith('+'):
                return target
            # If it starts with -, it's likely a group/channel ID
            if target.startswith('-'):
                chat_id = int(target)
                return chat_id
            # Try to resolve as entity directly
            entity = await client.get_entity(target)
            return entity
        except ValueError as e:
            logger.error(f"Invalid target format: {target} - {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to resolve target {target}: {e}")
            return None
    async def get_messaging_statistics(self, user_id: int) -> dict:
        """Get messaging statistics for user"""
        try:
            stats = {
                'total_messages_sent': 0,
                'auto_replies_sent': 0,
                'active_accounts': 0,
                'dm_topics_created': 0
            }
            
            # Count active accounts
            user_clients = self.user_clients.get(user_id, {})
            stats['active_accounts'] = len([c for c in user_clients.values() if c and c.is_connected()])
            
            # Get auto-reply stats if available
            if hasattr(self.bot_manager, 'auto_reply_handler'):
                auto_reply_stats = self.bot_manager.auto_reply_handler.analytics
                stats['auto_replies_sent'] = auto_reply_stats.get('auto_replies_sent', 0)
                stats['total_messages_sent'] = auto_reply_stats.get('total_messages', 0)
            
            # Count DM topics
            try:
                topic_count = await mongodb.db.topic_mappings.count_documents({
                    "admin_group_id": {"$exists": True}
                })
                stats['dm_topics_created'] = topic_count
            except Exception:
                pass
                
            return stats
        except Exception as e:
            logger.error(f"Error getting messaging statistics: {e}")
            return {'error': str(e)}

    async def setup_auto_reply(self, user_id: int, account_name: str, reply_message: str) -> bool:
        """Setup auto-reply for an account"""
        try:
            # Enable auto-reply for account
            await mongodb.db.accounts.update_one(
                {"user_id": user_id, "name": account_name},
                {"$set": {"auto_reply_enabled": True}}
            )
            # Store default message in settings
            await mongodb.db.auto_reply_settings.update_one(
                {"user_id": user_id},
                {"$set": {
                    "time_based_replies_enabled": True,
                    "available_message": reply_message
                }},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to setup auto-reply: {e}")
            return False
    async def disable_auto_reply(self, user_id: int, account_name: str) -> bool:
        """Disable auto-reply for an account"""
        try:
            await mongodb.db.accounts.update_one(
                {"user_id": user_id, "name": account_name},
                {"$set": {"auto_reply_enabled": False}}
            )
            return True
        except Exception as e:
            logger.error(f"Failed to disable auto-reply: {e}")
            return False
    async def setup_new_client_handler(self, user_id: int, account_name: str, client):
        """Set up handlers for newly added client"""
        if client and client.is_connected():
            self._setup_client_handlers(user_id, account_name, client)
    def cleanup_handlers(self):
        """Clean up all registered handlers"""
        self.handled_clients.clear()
        self.registered_client_objects.clear()
        if hasattr(self.bot_manager, 'registered_handlers'):
