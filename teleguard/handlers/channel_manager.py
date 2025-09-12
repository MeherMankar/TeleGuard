"""
Channel Management System for TeleGuard

Handles all channel/group operations via button interface
"""

import logging

from telethon import Button, errors, functions, types

from ..core.exceptions import AccountError, SessionError, ValidationError
from ..core.mongo_database import mongodb
from ..utils.validators import Validators

logger = logging.getLogger(__name__)


class ChannelManager:
    """Manages channel operations for accounts"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        self.pending_actions = bot_manager.pending_actions

    async def join_channel(
        self, user_id: int, account_phone: str, channel_link: str
    ) -> tuple[bool, str]:
        """Join a channel/group via any Telegram link format"""
        try:
            # Validate inputs
            Validators.validate_channel_link(channel_link)

            client = await self._get_client(user_id, account_phone)
            if not client:
                raise AccountError("Account not connected")

            channel_link = channel_link.strip()

            # Extract invite hash from various link formats
            invite_hash = self._extract_invite_hash(channel_link)
            if invite_hash:
                result = await client(
                    functions.messages.ImportChatInviteRequest(invite_hash)
                )
                chat_title = (
                    getattr(result.chats[0], "title", "Unknown")
                    if result.chats
                    else "Unknown"
                )
                return True, f"Successfully joined {chat_title}"

            # Handle regular channels/usernames
            channel_entity = await self._resolve_channel(client, channel_link)
            if not channel_entity:
                raise ValidationError("Channel not found or invalid link")

            await client(functions.channels.JoinChannelRequest(channel_entity))

            channel_name = getattr(channel_entity, "title", channel_link)
            return True, f"Successfully joined {channel_name}"

        except errors.ChannelPrivateError:
            return False, "Channel is private or doesn't exist"
        except errors.UserAlreadyParticipantError:
            return False, "Already a member of this channel"
        except errors.InviteHashExpiredError:
            return False, "Invite link has expired"
        except errors.InviteHashInvalidError:
            return False, "Invalid invite link"
        except (ValidationError, AccountError) as e:
            return False, str(e)
        except Exception as e:
            logger.error(f"Join channel error: {e}")
            return False, "Failed to join channel. Please try again."

    async def leave_channel(
        self, user_id: int, account_phone: str, channel_link: str
    ) -> tuple[bool, str]:
        """Leave a channel/group"""
        try:
            client = await self._get_client(user_id, account_phone)
            if not client:
                return False, "Account not connected"

            channel_link = channel_link.strip()

            # For invite links, check invite details and find matching channel
            if self._extract_invite_hash(channel_link):
                channel_entity = await self._leave_via_invite_link(client, channel_link)
                if not channel_entity:
                    return (
                        False,
                        "Channel not found or you're not a member. The invite link may be for a channel you haven't joined.",
                    )

            # Try to resolve channel entity for regular links
            channel_entity = await self._resolve_channel(client, channel_link)
            # If can't resolve, try to find in user's dialogs
            if not channel_entity:
                channel_entity = await self._find_channel_in_dialogs(
                    client, channel_link
                )

            if not channel_entity:
                return (
                    False,
                    "Channel not found. Use channel name, @username, or select from channel list.",
                )

            # Leave the channel/group
            if hasattr(channel_entity, "broadcast") or hasattr(
                channel_entity, "megagroup"
            ):
                await client(functions.channels.LeaveChannelRequest(channel_entity))
            else:
                # For regular groups
                await client(
                    functions.messages.DeleteChatUserRequest(channel_entity.id, "me")
                )

            channel_name = getattr(channel_entity, "title", channel_link)
            return True, f"Successfully left {channel_name}"

        except errors.UserNotParticipantError:
            return False, "Not a member of this channel"
        except Exception as e:
            logger.error(f"Leave channel error: {e}")
            return False, f"Error: {str(e)}"

    async def _leave_via_invite_link(self, client, invite_link: str):
        """Leave channel using invite link by checking invite details"""
        try:
            invite_hash = self._extract_invite_hash(invite_link)
            if not invite_hash:
                return None

            # Check invite details
            invite_info = await client(
                functions.messages.CheckChatInviteRequest(invite_hash)
            )

            if hasattr(invite_info, "chat"):
                # We're already in this chat, get the entity
                chat_id = invite_info.chat.id

                # Find this chat in our dialogs
                dialogs = await client.get_dialogs()
                for dialog in dialogs:
                    if dialog.entity.id == chat_id:
                        return dialog.entity

            return None

        except Exception as e:
            logger.error(f"Leave via invite link error: {e}")
            return None

    async def create_channel(
        self,
        user_id: int,
        account_phone: str,
        channel_type: str,
        title: str,
        about: str = "",
    ) -> tuple[bool, str]:
        """Create a new channel/group"""
        try:
            client = await self._get_client(user_id, account_phone)
            if not client:
                return False, "Account not connected"

            if channel_type.lower() == "channel":
                result = await client(
                    functions.channels.CreateChannelRequest(
                        title=title, about=about, broadcast=True
                    )
                )
            else:  # group
                result = await client(
                    functions.channels.CreateChannelRequest(
                        title=title, about=about, megagroup=True
                    )
                )

            return True, f"Successfully created {channel_type}: {title}"

        except Exception as e:
            logger.error(f"Create channel error: {e}")
            return False, f"Error: {str(e)}"

    async def delete_channel(
        self, user_id: int, account_phone: str, channel_link: str
    ) -> tuple[bool, str]:
        """Delete a channel/group (owner only)"""
        try:
            client = await self._get_client(user_id, account_phone)
            if not client:
                return False, "Account not connected"

            channel_entity = await self._resolve_channel(client, channel_link)
            if not channel_entity:
                # Try finding in dialogs as fallback
                channel_entity = await self._find_channel_in_dialogs(client, channel_link)
                
            if not channel_entity:
                return False, "Channel not found or you're not a member"

            await client(functions.channels.DeleteChannelRequest(channel_entity))

            channel_name = getattr(channel_entity, "title", channel_link)
            return True, f"Successfully deleted {channel_name}"

        except errors.ChatAdminRequiredError:
            return False, "Only channel owners can delete channels"
        except Exception as e:
            logger.error(f"Delete channel error: {e}")
            return False, f"Error: {str(e)}"

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
            # Get user clients first
            user_clients = self.user_clients.get(user_id, {})
            if not user_clients:
                logger.error(f"No clients found for user {user_id}")
                return None

            # Find account by phone
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

            client = user_clients.get(account["name"])
            if not client:
                logger.error(f"Client not found for account {account['name']}")
                return None

            return client

        except Exception as e:
            logger.error(f"Get client error: {e}")
            return None

    async def _resolve_channel(self, client, channel_link: str):
        """Resolve channel entity from link or username"""
        try:
            # Clean the input
            channel_link = channel_link.strip()

            # For invite links, find in dialogs instead of resolving
            invite_hash = self._extract_invite_hash(channel_link)
            if invite_hash:
                return await self._find_channel_by_invite(client, invite_hash)

            # Handle regular formats
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
                # Plain username
                return await client.get_entity(channel_link)

        except Exception as e:
            logger.error(f"Resolve channel error: {e}")
            return None

    async def _find_channel_by_invite(self, client, invite_hash: str):
        """Find channel by checking invite details"""
        try:
            # Check invite details first
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

                # Check by title
                if hasattr(entity, "title") and search_term in entity.title.lower():
                    return entity

                # Check by username
                if (
                    hasattr(entity, "username")
                    and entity.username
                    and search_term in entity.username.lower()
                ):
                    return entity

                # Check by ID (if numeric)
                if search_term.isdigit() and str(entity.id) == search_term:
                    return entity

            return None

        except Exception as e:
            logger.error(f"Find channel in dialogs error: {e}")
            return None

    def _extract_invite_hash(self, link: str) -> str:
        """Extract invite hash from various Telegram link formats"""
        import re

        # Remove whitespace
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

        return None
