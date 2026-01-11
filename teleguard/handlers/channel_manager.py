"""
Channel Management System for TeleGuard
Handles all channel/group operations via button interface
"""

import asyncio
import logging
import random

from telethon import errors, functions, types

from ..core.exceptions import AccountError, ValidationError
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
            Validators.validate_channel_link(channel_link)
            client = await self._get_client(user_id, account_phone)
            if not client:
                # Check if account has invalid session
                account = await mongodb.db.accounts.find_one(
                    {"user_id": user_id, "phone": account_phone}
                )
                if account and account.get("session_invalid"):
                    raise AccountError(
                        "Session expired due to IP conflict. Please remove and re-add this account."
                    )
                raise AccountError(
                    "Account not connected. Please add an account first or check if the account is active."
                )
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
            channel_entity = await self._resolve_channel(client, channel_link)
            if not channel_entity:
                raise ValidationError("Channel not found or invalid link")
            await client(functions.channels.JoinChannelRequest(channel_entity))
            channel_name = getattr(channel_entity, "title", channel_link)
            await asyncio.sleep(random.uniform(2, 5))  # Human-like delay after join
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

            # If channel_link is just a number, treat as channel ID selection
            if channel_link.isdigit():
                channels = await self._get_user_channels_with_ids(client)
                try:
                    selected_index = int(channel_link) - 1
                    if 0 <= selected_index < len(channels):
                        channel_entity = channels[selected_index]["entity"]
                        channel_name = channels[selected_index]["title"]
                        channel_id = channels[selected_index]["id"]
                    else:
                        return False, "Invalid channel selection"
                except (ValueError, IndexError):
                    return False, "Invalid channel selection"
            else:
                # For invite links, check invite details and find matching channel
                if self._extract_invite_hash(channel_link):
                    channel_entity = await self._leave_via_invite_link(
                        client, channel_link
                    )
                    if not channel_entity:
                        return (
                            False,
                            "Channel not found or you're not a member. The invite link may be for a channel you haven't joined.",
                        )
                else:
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

                channel_name = getattr(channel_entity, "title", channel_link)
                channel_id = getattr(channel_entity, "id", "Unknown")

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

            await asyncio.sleep(random.uniform(2, 5))  # Human-like delay after leave
            return True, f"Successfully left {channel_name} (ID: {channel_id})"
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
        privacy: str = "private",
    ) -> tuple[bool, str]:
        """Create a new channel/group"""
        try:
            client = await self._get_client(user_id, account_phone)
            if not client:
                # Check if account has invalid session
                account = await mongodb.db.accounts.find_one(
                    {"user_id": user_id, "phone": account_phone}
                )
                if account and account.get("session_invalid"):
                    return (
                        False,
                        "Session expired due to IP conflict. Please remove and re-add this account.",
                    )
                return False, "Account not connected. Try reconnecting the account."

            # Create the channel/group
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

            # Set privacy if public
            if privacy.lower() == "public" and result.chats:
                try:
                    channel = result.chats[0]
                    # Make channel public by setting a username
                    import random

                    username = f"{
                        title.lower().replace(
                            ' ', '_')}_{
                        random.randint(
                            1000, 9999)}"
                    username = "".join(c for c in username if c.isalnum() or c == "_")[
                        :32
                    ]

                    await client(
                        functions.channels.UpdateUsernameRequest(
                            channel=channel, username=username
                        )
                    )
                    return (
                        True,
                        f"Successfully created {privacy} {channel_type}: {title} (@{username})",
                    )
                except Exception as username_error:
                    logger.warning(f"Failed to set username: {username_error}")
                    return (
                        True,
                        f"Successfully created {channel_type}: {title} (private - username setting failed)",
                    )

            return True, f"Successfully created {privacy} {channel_type}: {title}"
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

            # If channel_link is just a number, treat as channel ID selection
            if channel_link.isdigit():
                channels = await self._get_user_channels_with_ids(client)
                try:
                    selected_index = int(channel_link) - 1
                    if 0 <= selected_index < len(channels):
                        channel_entity = channels[selected_index]["entity"]
                        channel_name = channels[selected_index]["title"]
                        channel_id = channels[selected_index]["id"]
                    else:
                        return False, "Invalid channel selection"
                except (ValueError, IndexError):
                    return False, "Invalid channel selection"
            else:
                channel_entity = await self._resolve_channel(client, channel_link)
                if not channel_entity:
                    channel_entity = await self._find_channel_in_dialogs(
                        client, channel_link
                    )
                if not channel_entity:
                    return False, "Channel not found or you're not a member"
                channel_name = getattr(channel_entity, "title", channel_link)
                channel_id = getattr(channel_entity, "id", "Unknown")

            # Check if user is admin/owner before attempting deletion
            try:
                participant = await client(
                    functions.channels.GetParticipantRequest(
                        channel=channel_entity, participant=client.get_me()
                    )
                )

                # Check if user has delete permissions
                if not (
                    hasattr(participant.participant, "admin_rights")
                    and getattr(
                        participant.participant.admin_rights, "delete_messages", False
                    )
                ) and not isinstance(
                    participant.participant, types.ChannelParticipantCreator
                ):
                    return (
                        False,
                        "You don't have permission to delete this channel. Only owners can delete channels.",
                    )
            except Exception as perm_error:
                logger.warning(f"Could not check permissions: {perm_error}")
                # Continue with deletion attempt

            # Attempt to delete the channel
            result = await client(
                functions.channels.DeleteChannelRequest(channel_entity)
            )

            # Verify deletion by trying to get the channel again
            try:
                await client.get_entity(channel_entity)
                return (
                    False,
                    f"Channel deletion may have failed. Channel {channel_name} still exists.",
                )
            except (errors.ChannelPrivateError, errors.PeerIdInvalidError):
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
                    accounts = await mongodb.db.accounts.find(
                        {"user_id": user_id}
                    ).to_list(length=None)
                    if accounts:
                        invalid_sessions = [
                            acc for acc in accounts if acc.get("session_invalid")
                        ]
                        if invalid_sessions:
                            logger.error(
                                f"User {user_id} has accounts but sessions are invalid due to IP conflicts"
                            )
                        else:
                            logger.error(
                                f"User {user_id} has accounts but no active clients loaded"
                            )
                    else:
                        logger.error(
                            f"No accounts found for user {user_id}. User needs to add accounts first."
                        )
                    return None

            # Try to find client by phone directly first
            client = user_clients.get(account_phone)
            if client:
                return client

            # Find account by phone in database
            try:
                account = await mongodb.db.accounts.find_one(
                    {"user_id": user_id, "phone": account_phone}
                )
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
                if (
                    account.get("display_name")
                    and account["display_name"] != account["name"]
                ):
                    client = user_clients.get(account["display_name"])

            if not client:
                # Try to reload this specific account
                if account.get("session_string"):
                    try:
                        await self.bot_manager.start_user_client(
                            user_id, account["name"], account["session_string"]
                        )
                        client = self.user_clients.get(user_id, {}).get(account["name"])
                        if client:
                            return client
                    except Exception as reload_error:
                        error_msg = str(reload_error)
                        if (
                            "authorization key" in error_msg
                            and "different IP addresses" in error_msg
                        ):
                            logger.error(
                                f"Session invalidated for {
                                    account['name']}: Session used from different IP"
                            )
                            # Mark account as inactive due to invalid session
                            await mongodb.db.accounts.update_one(
                                {"user_id": user_id, "phone": account_phone},
                                {"$set": {"is_active": False, "session_invalid": True}},
                            )
                        else:
                            logger.error(
                                f"Failed to reload client for {
                                    account['name']}: {reload_error}"
                            )

                logger.error(
                    f"Client not found for account {
                        account['name']} (phone: {account_phone}). Available clients: {
                        list(
                            user_clients.keys())}"
                )
                return None

            return client
        except Exception as e:
            logger.error(f"Get client error: {e}")
            return None

    async def _reload_user_clients(self, user_id: int):
        """Reload all clients for a user from database"""
        try:
            accounts = await mongodb.db.accounts.find(
                {"user_id": user_id, "is_active": True}
            ).to_list(length=None)

            for account in accounts:
                if account.get("session_string"):
                    try:
                        await self.bot_manager.start_user_client(
                            user_id, account["name"], account["session_string"]
                        )
                        logger.info(f"Reloaded client for {account['name']}")
                    except Exception as e:
                        logger.warning(
                            f"Failed to reload client for {account['name']}: {e}"
                        )
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
            elif channel_link.lstrip("-").isdigit():
                # Channel ID (with or without -100 prefix)
                channel_id = int(channel_link)
                return await client.get_entity(channel_id)
            else:
                # Check if it contains spaces or special chars - likely a channel name
                if " " in channel_link or any(
                    not c.isalnum() and c != "_" for c in channel_link
                ):
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
                    channels.append(
                        {
                            "entity": dialog.entity,
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
            # https://telegram.me/joinchat/uk_who_im
            r"telegram\.me/joinchat/([A-Za-z0-9_-]+)",
            r"t\.me/addlist/([A-Za-z0-9_-]+)",  # https://t.me/addlist/hash (folder)
            r"\+([A-Za-z0-9_-]+)$",  # Direct +uk_who_im
        ]
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                return match.group(1)
        return None
