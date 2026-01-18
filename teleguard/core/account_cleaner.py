"""
Account Cleaner for TeleGuard Bot
Integrated from CleanAcc repository: https://github.com/MeherMankar/CleanAcc
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import Any, Dict, Optional

from telethon import TelegramClient
from telethon.errors import (
    ChatAdminRequiredError,
    ChatIdInvalidError,
    FloodWaitError,
    UserNotParticipantError,
)
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.contacts import DeleteContactsRequest, GetContactsRequest
from telethon.tl.functions.messages import DeleteChatUserRequest, DeleteHistoryRequest
from telethon.tl.types import Channel, Chat, User

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
        pass  # Delays are randomized per operation

    async def cleanup_account(self, client: TelegramClient, cleanup_settings: Dict[str, bool], progress_callback: Optional[callable] = None) -> str:
        """Perform account cleanup with progress tracking"""
        progress = CleanupProgress()
        results = []
        try:
            if not await client.is_user_authorized():
                return "❌ Session is invalid, re-authorization required"
            if progress_callback:
                await progress_callback("✅ Connection established\n⏳ Analyzing account...")
            dialogs = await self._collect_dialogs(client, progress_callback)
            progress.total_items = len(dialogs)
            progress.current_operation = f"Found {len(dialogs)} dialogs"
            if progress_callback:
                await progress_callback(progress.get_progress_text())
            results = await self._execute_cleanup_operations(client, dialogs, cleanup_settings, progress, progress_callback)
            remaining_count = await self._final_cleanup_check(client, cleanup_settings, progress, progress_callback)
            if remaining_count > 0:
                results.append(f"🧹 Additionally cleaned: {remaining_count}")
            return self._generate_summary(results, progress)
        except FloodWaitError as e:
            error_msg = f"Rate limited by Telegram: wait {e.seconds} seconds"
            progress.add_error(error_msg)
            return f"⏳ {error_msg}"
        except Exception as e:
            error_msg = f"Cleanup error: {str(e)}"
            progress.add_error(error_msg)
            return f"❌ {error_msg}"

    async def _cleanup_personal_chats(
        self, client, all_dialogs, progress: CleanupProgress, progress_callback=None
    ):
        """Cleanup personal chats with progress tracking"""
        personal_dialogs = [
            dialog for dialog in all_dialogs if dialog.is_user and not dialog.entity.bot
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
            progress.current_operation = (
                f"Personal chats: {i + 1}/{len(personal_dialogs)}"
            )

            if progress_callback and (i + 1) % 5 == 0:
                await progress_callback(progress.get_progress_text())

            await asyncio.sleep(random.uniform(3, 8))

        return count

    async def _cleanup_bot_chats(
        self, client, all_dialogs, progress: CleanupProgress, progress_callback=None
    ):
        """Cleanup bot chats"""
        bot_dialogs = [
            dialog for dialog in all_dialogs if dialog.is_user and dialog.entity.bot
        ]

        progress.current_operation = f"Cleaning {len(bot_dialogs)} bot chats"

        count = 0
        for i, dialog in enumerate(bot_dialogs):
            success = await self._delete_dialog_with_retry(client, dialog, progress)
            if success:
                count += 1

            progress.processed_items += 1
            progress.deleted_items = (
                progress.deleted_items - count + count
            )  # Update count
            progress.current_operation = f"Bot chats: {i + 1}/{len(bot_dialogs)}"

            if progress_callback and (i + 1) % 5 == 0:
                await progress_callback(progress.get_progress_text())

            await asyncio.sleep(random.uniform(3, 8))

        return count

    async def _leave_groups(
        self,
        client: TelegramClient,
        dialogs,
        progress: CleanupProgress,
        progress_callback=None,
    ) -> int:
        """Leave groups with progress tracking"""
        group_dialogs = [d for d in dialogs if isinstance(d.entity, Chat)]
        supergroup_dialogs = [
            d for d in dialogs if isinstance(d.entity, Channel) and d.entity.megagroup
        ]
        all_groups = group_dialogs + supergroup_dialogs

        progress.current_operation = f"Leaving {len(all_groups)} groups"

        count = 0
        for i, dialog in enumerate(all_groups):
            try:
                if isinstance(dialog.entity, Chat):
                    await client(
                        DeleteChatUserRequest(chat_id=dialog.entity.id, user_id="me")
                    )
                else:
                    await client(LeaveChannelRequest(dialog.entity))

                count += 1

            except (
                ChatAdminRequiredError,
                UserNotParticipantError,
                ChatIdInvalidError,
            ):
                pass  # Already left or no permissions
            except FloodWaitError as e:
                progress.add_error(
                    f"Rate limited leaving group {dialog.name}: wait {e.seconds}s"
                )
                await asyncio.sleep(e.seconds)
                continue
            except Exception as e:
                progress.add_error(f"Error leaving group {dialog.name}: {e}")
                continue

            progress.processed_items += 1
            progress.current_operation = f"Groups: {i + 1}/{len(all_groups)}"

            if progress_callback and (i + 1) % 3 == 0:
                await progress_callback(progress.get_progress_text())

            await asyncio.sleep(random.uniform(3, 8))

        return count

    async def _leave_channels(
        self,
        client: TelegramClient,
        dialogs,
        progress: CleanupProgress,
        progress_callback=None,
    ) -> int:
        """Leave channels"""
        channel_dialogs = [
            d
            for d in dialogs
            if isinstance(d.entity, Channel) and not d.entity.megagroup
        ]

        progress.current_operation = (
            f"Unsubscribing from {len(channel_dialogs)} channels"
        )

        count = 0
        for i, dialog in enumerate(channel_dialogs):
            try:
                await client(LeaveChannelRequest(dialog.entity))
                count += 1

            except (UserNotParticipantError, ChatIdInvalidError):
                pass  # Already unsubscribed
            except FloodWaitError as e:
                progress.add_error(
                    f"Rate limited leaving channel {dialog.name}: wait {e.seconds}s"
                )
                await asyncio.sleep(e.seconds)
                continue
            except Exception as e:
                progress.add_error(f"Error leaving channel {dialog.name}: {e}")
                continue

            progress.processed_items += 1
            progress.current_operation = f"Channels: {i + 1}/{len(channel_dialogs)}"

            if progress_callback and (i + 1) % 3 == 0:
                await progress_callback(progress.get_progress_text())

            await asyncio.sleep(random.uniform(3, 8))

        return count

    async def _cleanup_contacts(
        self, client: TelegramClient, progress: CleanupProgress, progress_callback=None
    ) -> int:
        """Cleanup contacts with batching"""
        try:
            progress.current_operation = "Getting contacts list"

            if progress_callback:
                await progress_callback(progress.get_progress_text())

            result = await client(GetContactsRequest(hash=0))

            if not hasattr(result, "contacts") or not result.contacts:
                return 0

            contacts = result.contacts
            progress.current_operation = f"Deleting {len(contacts)} contacts"

            # Delete contacts in batches
            contact_ids = [contact.user_id for contact in contacts]
            batch_size = 50
            deleted_count = 0

            for i in range(0, len(contact_ids), batch_size):
                batch = contact_ids[i: i + batch_size]
                try:
                    await client(DeleteContactsRequest(id=batch))
                    deleted_count += len(batch)

                    progress.processed_items += len(batch)
                    progress.current_operation = f"Contacts: {
                        min(
                            i + batch_size,
                            len(contact_ids))}/{
                        len(contact_ids)}"

                    if progress_callback:
                        await progress_callback(progress.get_progress_text())

                    await asyncio.sleep(
                        random.uniform(5, 12)
                    )  # Longer delay for contacts

                except FloodWaitError as e:
                    progress.add_error(
                        f"Rate limited deleting contacts: wait {e.seconds}s"
                    )
                    await asyncio.sleep(e.seconds)
                    continue
                except Exception as e:
                    progress.add_error(f"Error deleting contact batch: {e}")
                    continue

            return deleted_count

        except Exception as e:
            progress.add_error(f"Error cleaning contacts: {e}")
            return 0

    async def _cleanup_telegram_chat(
        self,
        client: TelegramClient,
        dialogs,
        progress: CleanupProgress,
        progress_callback=None,
    ) -> int:
        """Cleanup Telegram official chat"""
        progress.current_operation = "Looking for Telegram dialogs"

        telegram_usernames = ["telegram", "botfather", "botfather_beta"]
        telegram_names = ["Telegram", "BotFather"]

        count = 0
        for dialog in dialogs:
            if isinstance(dialog.entity, User):
                username = (getattr(dialog.entity, "username", None) or "").lower()
                first_name = (getattr(dialog.entity, "first_name", None) or "").lower()

                is_telegram = (
                    username in telegram_usernames
                    or any(name.lower() in first_name for name in telegram_names)
                    or "telegram" in username
                    or "telegram" in first_name
                )

                if is_telegram:
                    success = await self._delete_dialog_with_retry(
                        client, dialog, progress
                    )
                    if success:
                        count += 1

        return count

    async def _cleanup_spambot_chat(
        self, client, all_dialogs, progress: CleanupProgress, progress_callback=None
    ):
        """Cleanup Spambot dialog"""
        count = 0

        for dialog in all_dialogs:
            try:
                if (
                    dialog.is_user
                    and dialog.entity.username
                    and (dialog.entity.username or "").lower() == "spambot"
                ):

                    success = await self._delete_dialog_with_retry(
                        client, dialog, progress
                    )
                    if success:
                        count += 1
                        break

            except Exception as e:
                progress.add_error(f"Error deleting Spambot dialog: {e}")
                continue

        return count

    async def _delete_owned_groups(
        self,
        client: TelegramClient,
        dialogs,
        progress: CleanupProgress,
        progress_callback=None,
    ) -> int:
        """Delete groups owned by the user"""
        from telethon.tl.functions.channels import DeleteChannelRequest
        from telethon.tl.functions.messages import DeleteChatRequest
        from telethon.tl.types import Channel, Chat

        progress.current_operation = "Finding owned groups"

        owned_groups = []
        for dialog in dialogs:
            try:
                if isinstance(dialog.entity, Chat):
                    # For basic groups, check if we're the creator
                    chat_full = await client.get_entity(dialog.entity.id)
                    if hasattr(chat_full, "creator") and chat_full.creator:
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
                progress.current_operation = f"Owned groups: {
                    i + 1}/{
                    len(owned_groups)}"

                if progress_callback and (i + 1) % 2 == 0:
                    await progress_callback(progress.get_progress_text())

                await asyncio.sleep(random.uniform(6, 15))  # Longer delay for deletions

            except Exception as e:
                progress.add_error(f"Error deleting owned group {dialog.name}: {e}")
                continue

        return count

    async def _delete_owned_channels(
        self,
        client: TelegramClient,
        dialogs,
        progress: CleanupProgress,
        progress_callback=None,
    ) -> int:
        """Delete channels owned by the user"""
        from telethon.tl.functions.channels import DeleteChannelRequest
        from telethon.tl.types import Channel

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
                progress.add_error(
                    f"Error checking channel ownership {dialog.name}: {e}"
                )
                continue

        progress.current_operation = f"Deleting {len(owned_channels)} owned channels"

        count = 0
        for i, dialog in enumerate(owned_channels):
            try:
                await client(DeleteChannelRequest(channel=dialog.entity))
                count += 1
                progress.processed_items += 1
                progress.current_operation = (
                    f"Owned channels: {i + 1}/{len(owned_channels)}"
                )

                if progress_callback and (i + 1) % 2 == 0:
                    await progress_callback(progress.get_progress_text())

                await asyncio.sleep(random.uniform(6, 15))  # Longer delay for deletions

            except Exception as e:
                progress.add_error(f"Error deleting owned channel {dialog.name}: {e}")
                continue

        return count

    async def _final_cleanup_check(
        self,
        client,
        cleanup_settings,
        progress: CleanupProgress,
        progress_callback=None,
    ):
        """Final cleanup check"""
        count = 0

        try:
            progress.current_operation = "Final verification of remaining dialogs"

            remaining_dialogs = []
            async for dialog in client.iter_dialogs():
                remaining_dialogs.append(dialog)

            for dialog in remaining_dialogs:
                should_delete = False

                if (
                    cleanup_settings.get("personal_chats", False)
                    and dialog.is_user
                    and not dialog.entity.bot
                ):
                    should_delete = True
                elif (
                    cleanup_settings.get("bot_chats", False)
                    and dialog.is_user
                    and dialog.entity.bot
                ):
                    should_delete = True

                if should_delete:
                    success = await self._delete_dialog_with_retry(
                        client, dialog, progress
                    )
                    if success:
                        count += 1

        except Exception as e:
            progress.add_error(f"Error in final check: {e}")

        return count

    async def _delete_dialog_with_retry(
        self, client, dialog, progress: CleanupProgress, max_retries: int = 3
    ) -> bool:
        """Delete dialog with retry logic"""
        for attempt in range(max_retries):
            try:
                await client(
                    DeleteHistoryRequest(
                        peer=dialog.entity, max_id=0, just_clear=False, revoke=True
                    )
                )
                return True

            except FloodWaitError as e:
                wait_time = min(e.seconds, 300)  # Cap at 5 minutes
                progress.add_error(
                    f"Rate limited deleting {dialog.name}: waiting {wait_time}s"
                )
                await asyncio.sleep(wait_time)
                continue

            except Exception as e:
                if attempt == max_retries - 1:
                    progress.add_error(
                        f"Failed to delete dialog {
                            dialog.name} after {max_retries} attempts: {e}"
                    )
                await asyncio.sleep(0.5 * (attempt + 1))
                continue

        return False

    async def get_cleanup_preview(
        self, client: TelegramClient, cleanup_settings: Dict[str, bool]
    ) -> Dict[str, Any]:
        """Get preview of what will be cleaned"""
        preview = {
            "personal_chats": [],
            "bot_chats": [],
            "groups": [],
            "channels": [],
            "contacts_count": 0,
            "telegram_chats": [],
            "spambot_chats": [],
            "owned_groups": [],
            "owned_channels": [],
        }

        try:
            if not await client.is_user_authorized():
                return {"error": "Session invalid"}

            # Get dialogs for preview
            dialogs = []
            async for dialog in client.iter_dialogs():
                dialogs.append(dialog)

            # Categorize dialogs
            for dialog in dialogs:
                if (
                    cleanup_settings.get("personal_chats", False)
                    and dialog.is_user
                    and not dialog.entity.bot
                ):
                    preview["personal_chats"].append(
                        {"name": dialog.name, "id": dialog.entity.id}
                    )
                elif (
                    cleanup_settings.get("bot_chats", False)
                    and dialog.is_user
                    and dialog.entity.bot
                ):
                    preview["bot_chats"].append(
                        {"name": dialog.name, "id": dialog.entity.id}
                    )
                elif cleanup_settings.get("groups", False) and isinstance(
                    dialog.entity, (Chat, Channel)
                ):
                    if isinstance(dialog.entity, Channel) and dialog.entity.megagroup:
                        preview["groups"].append(
                            {
                                "name": dialog.name,
                                "id": dialog.entity.id,
                                "type": "supergroup",
                            }
                        )
                    elif isinstance(dialog.entity, Chat):
                        preview["groups"].append(
                            {
                                "name": dialog.name,
                                "id": dialog.entity.id,
                                "type": "group",
                            }
                        )
                elif (
                    cleanup_settings.get("channels", False)
                    and isinstance(dialog.entity, Channel)
                    and not dialog.entity.megagroup
                ):
                    preview["channels"].append(
                        {"name": dialog.name, "id": dialog.entity.id}
                    )

                # Check for owned groups and channels
                if cleanup_settings.get("owned_groups", False):
                    try:
                        if isinstance(dialog.entity, Chat):
                            # Basic group - check if creator
                            chat_full = await client.get_entity(dialog.entity.id)
                            if hasattr(chat_full, "creator") and chat_full.creator:
                                preview["owned_groups"].append(
                                    {
                                        "name": dialog.name,
                                        "id": dialog.entity.id,
                                        "type": "group",
                                    }
                                )
                        elif (
                            isinstance(dialog.entity, Channel)
                            and dialog.entity.megagroup
                        ):
                            # Supergroup - check creator permissions
                            permissions = await client.get_permissions(dialog.entity)
                            if permissions.is_creator:
                                preview["owned_groups"].append(
                                    {
                                        "name": dialog.name,
                                        "id": dialog.entity.id,
                                        "type": "supergroup",
                                    }
                                )
                    except Exception:
                        pass

                if cleanup_settings.get("owned_channels", False):
                    try:
                        if (
                            isinstance(dialog.entity, Channel)
                            and not dialog.entity.megagroup
                        ):
                            # Channel - check creator permissions
                            permissions = await client.get_permissions(dialog.entity)
                            if permissions.is_creator:
                                preview["owned_channels"].append(
                                    {"name": dialog.name, "id": dialog.entity.id}
                                )
                    except Exception:
                        pass

            # Get contacts count if needed
            if cleanup_settings.get("contacts", False):
                try:
                    result = await client(GetContactsRequest(hash=0))
                    if hasattr(result, "contacts"):
                        preview["contacts_count"] = len(result.contacts)
                except BaseException:
                    preview["contacts_count"] = 0

            return preview

        except Exception as e:
            return {"error": str(e)}

    async def _collect_dialogs(self, client, progress_callback):
        """Collect all dialogs with progress updates"""
        dialogs = []
        dialog_count = 0
        async for dialog in client.iter_dialogs():
            dialogs.append(dialog)
            dialog_count += 1
            if dialog_count % 10 == 0 and progress_callback:
                await progress_callback(f"📋 Found {dialog_count} dialogs...")
        return dialogs

    async def _execute_cleanup_operations(self, client, dialogs, cleanup_settings, progress, progress_callback):
        """Execute all cleanup operations based on settings"""
        results = []
        cleanup_map = {
            "personal_chats": (self._cleanup_personal_chats, "💬 Deleted personal chats"),
            "bot_chats": (self._cleanup_bot_chats, "🤖 Deleted bot chats"),
            "groups": (self._leave_groups, "👥 Left groups"),
            "channels": (self._leave_channels, "📺 Unsubscribed from channels"),
            "contacts": (self._cleanup_contacts, "📞 Deleted contacts"),
            "telegram_chat": (self._cleanup_telegram_chat, "📢 Cleaned Telegram dialog"),
            "spambot_chat": (self._cleanup_spambot_chat, "🚫 Spambot cleanup"),
            "owned_groups": (self._delete_owned_groups, "🗑️ Deleted owned groups"),
            "owned_channels": (self._delete_owned_channels, "📺 Deleted owned channels"),
        }
        for setting, (method, label) in cleanup_map.items():
            if cleanup_settings.get(setting, False):
                count = await method(client, dialogs, progress, progress_callback) if setting != "contacts" else await method(client, progress, progress_callback)
                results.append(f"{label}: {count if setting != 'telegram_chat' else ('✅' if count > 0 else '❌')}")
        if progress_callback:
            await progress_callback("🔍 Final verification...")
        return results

    def _generate_summary(self, results, progress):
        """Generate cleanup summary"""
        final_result = "\n".join(results) if results else "✅ Cleanup completed"
        return f"""
📊 Cleanup Summary:
{final_result}

⏱️ Total time: {int((datetime.now() - progress.start_time).total_seconds())}s
📈 Items processed: {progress.processed_items}
✅ Items deleted: {progress.deleted_items}
⚠️ Errors: {len(progress.errors)}
"""
