"""Split from cleanup_tasks.py - cleanup_operations"""
    async def _cleanup_contacts(self, client: TelegramClient, progress: CleanupProgress, progress_callback=None) -> int:
        """Cleanup contacts with batching"""
        try:
            progress.current_operation = "Getting contacts list"
            
            if progress_callback:
                await progress_callback(progress.get_progress_text())

            result = await client(GetContactsRequest(hash=0))

            if not hasattr(result, 'contacts') or not result.contacts:
                return 0

            contacts = result.contacts
            progress.current_operation = f"Deleting {len(contacts)} contacts"

            # Delete contacts in batches
            contact_ids = [contact.user_id for contact in contacts]
            batch_size = 50
            deleted_count = 0

            for i in range(0, len(contact_ids), batch_size):
                batch = contact_ids[i:i + batch_size]
                try:
                    await client(DeleteContactsRequest(id=batch))
                    deleted_count += len(batch)
                    
                    progress.processed_items += len(batch)
                    progress.current_operation = f"Contacts: {min(i + batch_size, len(contact_ids))}/{len(contact_ids)}"
                    
                    if progress_callback:
                        await progress_callback(progress.get_progress_text())
                    
                    await asyncio.sleep(self.cleanup_delay * 2)  # Longer delay for contacts
                    
                except FloodWaitError as e:
                    progress.add_error(f"Rate limited deleting contacts: wait {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                    continue
                except Exception as e:
                    progress.add_error(f"Error deleting contact batch: {e}")
                    continue

            return deleted_count

        except Exception as e:
            progress.add_error(f"Error cleaning contacts: {e}")
            return 0

    async def _cleanup_telegram_chat(self, client: TelegramClient, dialogs, progress: CleanupProgress, progress_callback=None) -> int:
        """Cleanup Telegram official chat"""
        progress.current_operation = "Looking for Telegram dialogs"

        telegram_usernames = ['telegram', 'botfather', 'botfather_beta']
        telegram_names = ['Telegram', 'BotFather']

        count = 0
        for dialog in dialogs:
            if isinstance(dialog.entity, User):
                username = (getattr(dialog.entity, 'username', None) or '').lower()
                first_name = (getattr(dialog.entity, 'first_name', None) or '').lower()

                is_telegram = (
                    username in telegram_usernames or
                    any(name.lower() in first_name for name in telegram_names) or
                    'telegram' in username or
                    'telegram' in first_name
                )

                if is_telegram:
                    success = await self._delete_dialog_with_retry(client, dialog, progress)
                    if success:
                        count += 1

        return count

    async def _cleanup_spambot_chat(self, client, all_dialogs, progress: CleanupProgress, progress_callback=None):
        """Cleanup Spambot dialog"""
        count = 0

        for dialog in all_dialogs:
            try:
                if (dialog.is_user and
                    dialog.entity.username and
                    (dialog.entity.username or '').lower() == 'spambot'):

                    success = await self._delete_dialog_with_retry(client, dialog, progress)
                    if success:
                        count += 1
                        break

            except Exception as e:
                progress.add_error(f"Error deleting Spambot dialog: {e}")
                continue

        return count
    
    async def _delete_owned_groups(self, client: TelegramClient, dialogs, progress: CleanupProgress, progress_callback=None) -> int:
        """Delete groups owned by the user"""
        from telethon.tl.types import Chat, Channel
        from telethon.tl.functions.channels import DeleteChannelRequest
        from telethon.tl.functions.messages import DeleteChatRequest
        
        progress.current_operation = "Finding owned groups"
        
        owned_groups = []
        for dialog in dialogs:
            try:
                if isinstance(dialog.entity, Chat):
                    # For basic groups, check if we're the creator
                    chat_full = await client.get_entity(dialog.entity.id)
                    if hasattr(chat_full, 'creator') and chat_full.creator:
                        owned_groups.append(dialog)
                elif isinstance(dialog.entity, Channel) and dialog.entity.megagroup:
                    # For supergroups, check admin rights
                    try:
                        permissions = await client.get_permissions(dialog.entity)
                        if permissions.is_creator:
                            owned_groups.append(dialog)
                    except Exception:
                        continue
            except Exception as e:
                progress.add_error(f"Error checking group ownership {dialog.name}: {e}")
                continue
        
        progress.current_operation = f"Deleting {len(owned_groups)} owned groups"
        
        count = 0
        for i, dialog in enumerate(owned_groups):
            try:
                if isinstance(dialog.entity, Chat):
                    # Delete basic group
                    await client(DeleteChatRequest(chat_id=dialog.entity.id))
                elif isinstance(dialog.entity, Channel):
                    # Delete supergroup
                    await client(DeleteChannelRequest(channel=dialog.entity))
                
                count += 1
                progress.processed_items += 1
                progress.current_operation = f"Owned groups: {i+1}/{len(owned_groups)}"
                
                if progress_callback and (i + 1) % 2 == 0:
                    await progress_callback(progress.get_progress_text())
                
                await asyncio.sleep(self.cleanup_delay * 2)  # Longer delay for deletions
                
            except Exception as e:
                progress.add_error(f"Error deleting owned group {dialog.name}: {e}")
                continue
        
        return count
    
    async def _delete_owned_channels(self, client: TelegramClient, dialogs, progress: CleanupProgress, progress_callback=None) -> int:
        """Delete channels owned by the user"""
        from telethon.tl.types import Channel
        from telethon.tl.functions.channels import DeleteChannelRequest
        
        progress.current_operation = "Finding owned channels"
        
        owned_channels = []
        for dialog in dialogs:
            try:
                if isinstance(dialog.entity, Channel) and not dialog.entity.megagroup:
                    # Check if we're the creator of this channel
                    try:
                        permissions = await client.get_permissions(dialog.entity)
                        if permissions.is_creator:
                            owned_channels.append(dialog)
                    except Exception:
                        continue
            except Exception as e:
                progress.add_error(f"Error checking channel ownership {dialog.name}: {e}")
                continue
        
        progress.current_operation = f"Deleting {len(owned_channels)} owned channels"
        
        count = 0
        for i, dialog in enumerate(owned_channels):
            try:
                await client(DeleteChannelRequest(channel=dialog.entity))
                count += 1
                progress.processed_items += 1
                progress.current_operation = f"Owned channels: {i+1}/{len(owned_channels)}"
                
                if progress_callback and (i + 1) % 2 == 0:
                    await progress_callback(progress.get_progress_text())
                
                await asyncio.sleep(self.cleanup_delay * 2)  # Longer delay for deletions
                
            except Exception as e:
                progress.add_error(f"Error deleting owned channel {dialog.name}: {e}")
                continue
        
        return count

    async def _final_cleanup_check(self, client, cleanup_settings, progress: CleanupProgress, progress_callback=None):
        """Final cleanup check"""
        count = 0

        try:
            progress.current_operation = "Final verification of remaining dialogs"
            
            remaining_dialogs = []
            async for dialog in client.iter_dialogs():
                remaining_dialogs.append(dialog)

            for dialog in remaining_dialogs:
                should_delete = False

                if cleanup_settings.get('personal_chats', False) and dialog.is_user and not dialog.entity.bot:
                    should_delete = True
                elif cleanup_settings.get('bot_chats', False) and dialog.is_user and dialog.entity.bot:
                    should_delete = True

                if should_delete:
                    success = await self._delete_dialog_with_retry(client, dialog, progress)
                    if success:
                        count += 1

        except Exception as e:
            progress.add_error(f"Error in final check: {e}")

        return count

    async def _delete_dialog_with_retry(self, client, dialog, progress: CleanupProgress, max_retries: int = 3) -> bool:
        """Delete dialog with retry logic"""
        for attempt in range(max_retries):
            try:
                await client(DeleteHistoryRequest(
                    peer=dialog.entity,
                    max_id=0,
                    just_clear=False,
                    revoke=True
                ))
                return True
                
            except FloodWaitError as e:
                wait_time = min(e.seconds, 300)  # Cap at 5 minutes
                progress.add_error(f"Rate limited deleting {dialog.name}: waiting {wait_time}s")
                await asyncio.sleep(wait_time)
                continue
                
            except Exception as e:
                if attempt == max_retries - 1:
                    progress.add_error(f"Failed to delete dialog {dialog.name} after {max_retries} attempts: {e}")
                await asyncio.sleep(0.5 * (attempt + 1))
                continue

        return False

    async def get_cleanup_preview(self, client: TelegramClient, cleanup_settings: Dict[str, bool]) -> Dict[str, Any]:
        """Get preview of what will be cleaned"""
        preview = {
            'personal_chats': [],
            'bot_chats': [],
            'groups': [],
            'channels': [],
            'contacts_count': 0,
            'telegram_chats': [],
            'spambot_chats': [],
            'owned_groups': [],
            'owned_channels': []
        }

        try:
            if not await client.is_user_authorized():
                return {'error': 'Session invalid'}

            # Get dialogs for preview
            dialogs = []
            async for dialog in client.iter_dialogs():
                dialogs.append(dialog)

            # Categorize dialogs
            for dialog in dialogs:
                if cleanup_settings.get('personal_chats', False) and dialog.is_user and not dialog.entity.bot:
                    preview['personal_chats'].append({
                        'name': dialog.name,
                        'id': dialog.entity.id
                    })
                elif cleanup_settings.get('bot_chats', False) and dialog.is_user and dialog.entity.bot:
                    preview['bot_chats'].append({
