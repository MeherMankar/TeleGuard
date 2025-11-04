"""Split from cleanup_tasks.py - cleanup_core"""
"""
Account Cleaner for TeleGuard Bot
Integrated from CleanAcc repository: https://github.com/MeherMankar/CleanAcc
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from telethon import TelegramClient
from telethon.tl.types import User, Chat, Channel
from telethon.tl.functions.messages import DeleteHistoryRequest
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.messages import DeleteChatUserRequest
from telethon.tl.functions.contacts import DeleteContactsRequest, GetContactsRequest
from telethon.errors import ChatAdminRequiredError, UserNotParticipantError, ChatIdInvalidError, FloodWaitError
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class CleanupProgress:
    """Track cleanup progress"""
    
    def __init__(self):
        self.total_items = 0
        self.processed_items = 0
        self.deleted_items = 0
        self.errors = []
        self.start_time = datetime.now()
        self.current_operation = ""
    
    def add_error(self, error: str):
        self.errors.append(f"{datetime.now().isoformat()}: {error}")
        logger.warning(f"Cleanup error: {error}")
    
    def get_progress_text(self) -> str:
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.processed_items / elapsed if elapsed > 0 else 0
        
        return f"""
🔄 {self.current_operation}
📊 Progress: {self.processed_items}/{self.total_items}
✅ Deleted: {self.deleted_items}
⚡ Rate: {rate:.1f} items/sec
⏱️ Elapsed: {int(elapsed)}s
"""

class AccountCleaner:
    """Enhanced account cleanup service"""

    def __init__(self):
        self.cleanup_delay = 0.5  # Delay between operations

    async def cleanup_account(self, client: TelegramClient, 
                            cleanup_settings: Dict[str, bool],
                            progress_callback: Optional[callable] = None) -> str:
        """Perform account cleanup with progress tracking"""
        
        progress = CleanupProgress()
        results = []

        try:
            if not await client.is_user_authorized():
                return "❌ Session is invalid, re-authorization required"

            if progress_callback:
                await progress_callback("✅ Connection established\n⏳ Analyzing account...")

            # Get all dialogs
            dialogs = []
            dialog_count = 0
            async for dialog in client.iter_dialogs():
                dialogs.append(dialog)
                dialog_count += 1
                if dialog_count % 10 == 0 and progress_callback:
                    await progress_callback(f"📋 Found {dialog_count} dialogs...")

            progress.total_items = len(dialogs)
            progress.current_operation = f"Found {len(dialogs)} dialogs"

            if progress_callback:
                await progress_callback(progress.get_progress_text())

            # Execute cleanup operations
            if cleanup_settings.get('personal_chats', False):
                count = await self._cleanup_personal_chats(
                    client, dialogs, progress, progress_callback
                )
                results.append(f"💬 Deleted personal chats: {count}")

            if cleanup_settings.get('bot_chats', False):
                count = await self._cleanup_bot_chats(
                    client, dialogs, progress, progress_callback
                )
                results.append(f"🤖 Deleted bot chats: {count}")

            if cleanup_settings.get('groups', False):
                count = await self._leave_groups(
                    client, dialogs, progress, progress_callback
                )
                results.append(f"👥 Left groups: {count}")

            if cleanup_settings.get('channels', False):
                count = await self._leave_channels(
                    client, dialogs, progress, progress_callback
                )
                results.append(f"📺 Unsubscribed from channels: {count}")

            if cleanup_settings.get('contacts', False):
                count = await self._cleanup_contacts(
                    client, progress, progress_callback
                )
                results.append(f"📞 Deleted contacts: {count}")

            if cleanup_settings.get('telegram_chat', False):
                count = await self._cleanup_telegram_chat(
                    client, dialogs, progress, progress_callback
                )
                results.append(f"📢 Cleaned Telegram dialog: {'✅' if count > 0 else '❌'}")

            if cleanup_settings.get('spambot_chat', False):
                count = await self._cleanup_spambot_chat(
                    client, dialogs, progress, progress_callback
                )
                results.append(f"🚫 Spambot cleanup: {count}")
            
            if cleanup_settings.get('owned_groups', False):
                count = await self._delete_owned_groups(
                    client, dialogs, progress, progress_callback
                )
                results.append(f"🗑️ Deleted owned groups: {count}")
            
            if cleanup_settings.get('owned_channels', False):
                count = await self._delete_owned_channels(
                    client, dialogs, progress, progress_callback
                )
                results.append(f"📺 Deleted owned channels: {count}")

            # Final verification
            if progress_callback:
                await progress_callback("🔍 Final verification...")
            
            remaining_count = await self._final_cleanup_check(
                client, cleanup_settings, progress, progress_callback
            )
            if remaining_count > 0:
                results.append(f"🧹 Additionally cleaned: {remaining_count}")

            final_result = "\n".join(results) if results else "✅ Cleanup completed"
            
            # Add summary statistics
            summary = f"""
📊 Cleanup Summary:
{final_result}

⏱️ Total time: {int((datetime.now() - progress.start_time).total_seconds())}s
📈 Items processed: {progress.processed_items}
✅ Items deleted: {progress.deleted_items}
⚠️ Errors: {len(progress.errors)}
"""
            return summary

        except FloodWaitError as e:
            error_msg = f"Rate limited by Telegram: wait {e.seconds} seconds"
            progress.add_error(error_msg)
            return f"⏳ {error_msg}"
            
        except Exception as e:
            error_msg = f"Cleanup error: {str(e)}"
            progress.add_error(error_msg)
            return f"❌ {error_msg}"

    async def _cleanup_personal_chats(self, client, all_dialogs, progress: CleanupProgress, progress_callback=None):
        """Cleanup personal chats with progress tracking"""
        personal_dialogs = [
            dialog for dialog in all_dialogs
            if dialog.is_user and not dialog.entity.bot
        ]

        progress.current_operation = f"Cleaning {len(personal_dialogs)} personal chats"
        
        if progress_callback:
            await progress_callback(progress.get_progress_text())

        count = 0
        for i, dialog in enumerate(personal_dialogs):
            success = await self._delete_dialog_with_retry(client, dialog, progress)
            if success:
                count += 1
            
            progress.processed_items = i + 1
            progress.deleted_items = count
            progress.current_operation = f"Personal chats: {i+1}/{len(personal_dialogs)}"
            
            if progress_callback and (i + 1) % 5 == 0:
                await progress_callback(progress.get_progress_text())
            
            await asyncio.sleep(self.cleanup_delay)

        return count

    async def _cleanup_bot_chats(self, client, all_dialogs, progress: CleanupProgress, progress_callback=None):
        """Cleanup bot chats"""
        bot_dialogs = [
            dialog for dialog in all_dialogs
            if dialog.is_user and dialog.entity.bot
        ]

        progress.current_operation = f"Cleaning {len(bot_dialogs)} bot chats"
        
        count = 0
        for i, dialog in enumerate(bot_dialogs):
            success = await self._delete_dialog_with_retry(client, dialog, progress)
            if success:
                count += 1
            
            progress.processed_items += 1
            progress.deleted_items = progress.deleted_items - count + count  # Update count
            progress.current_operation = f"Bot chats: {i+1}/{len(bot_dialogs)}"
            
            if progress_callback and (i + 1) % 5 == 0:
                await progress_callback(progress.get_progress_text())
            
            await asyncio.sleep(self.cleanup_delay)

        return count

    async def _leave_groups(self, client: TelegramClient, dialogs, progress: CleanupProgress, progress_callback=None) -> int:
        """Leave groups with progress tracking"""
        group_dialogs = [d for d in dialogs if isinstance(d.entity, Chat)]
        supergroup_dialogs = [d for d in dialogs if isinstance(d.entity, Channel) and d.entity.megagroup]
        all_groups = group_dialogs + supergroup_dialogs

        progress.current_operation = f"Leaving {len(all_groups)} groups"

        count = 0
        for i, dialog in enumerate(all_groups):
            try:
                if isinstance(dialog.entity, Chat):
                    await client(DeleteChatUserRequest(
                        chat_id=dialog.entity.id,
                        user_id='me'
                    ))
                else:
                    await client(LeaveChannelRequest(dialog.entity))
                
                count += 1
                
            except (ChatAdminRequiredError, UserNotParticipantError, ChatIdInvalidError):
                pass  # Already left or no permissions
            except FloodWaitError as e:
                progress.add_error(f"Rate limited leaving group {dialog.name}: wait {e.seconds}s")
                await asyncio.sleep(e.seconds)
                continue
            except Exception as e:
                progress.add_error(f"Error leaving group {dialog.name}: {e}")
                continue
            
            progress.processed_items += 1
            progress.current_operation = f"Groups: {i+1}/{len(all_groups)}"
            
            if progress_callback and (i + 1) % 3 == 0:
                await progress_callback(progress.get_progress_text())
            
            await asyncio.sleep(self.cleanup_delay)

        return count

    async def _leave_channels(self, client: TelegramClient, dialogs, progress: CleanupProgress, progress_callback=None) -> int:
        """Leave channels"""
        channel_dialogs = [d for d in dialogs if isinstance(d.entity, Channel) and not d.entity.megagroup]

        progress.current_operation = f"Unsubscribing from {len(channel_dialogs)} channels"

        count = 0
        for i, dialog in enumerate(channel_dialogs):
            try:
                await client(LeaveChannelRequest(dialog.entity))
                count += 1
                
            except (UserNotParticipantError, ChatIdInvalidError):
                pass  # Already unsubscribed
            except FloodWaitError as e:
                progress.add_error(f"Rate limited leaving channel {dialog.name}: wait {e.seconds}s")
                await asyncio.sleep(e.seconds)
                continue
            except Exception as e:
                progress.add_error(f"Error leaving channel {dialog.name}: {e}")
                continue
            
            progress.processed_items += 1
            progress.current_operation = f"Channels: {i+1}/{len(channel_dialogs)}"
            
            if progress_callback and (i + 1) % 3 == 0:
                await progress_callback(progress.get_progress_text())
            
            await asyncio.sleep(self.cleanup_delay)

        return count

