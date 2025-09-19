"""Full Telegram Client Manager - Profile, Sessions, Automation

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import asyncio
import json
import logging
import os
import time
from functools import wraps
from typing import Any, Dict, List, Optional

from bson import ObjectId
from telethon import errors, functions, types
from telethon.tl.types import InputPeerEmpty

from .mongo_database import mongodb

logger = logging.getLogger(__name__)


def with_account_client(func):
    @wraps(func)
    async def wrapper(self, user_id: int, account_id: str, *args, **kwargs):
        client = await self._get_account_client(user_id, account_id)
        if not client:
            if func.__name__ == "list_active_sessions":
                return False, []
            else:
                return False, "Account client not found"

        kwargs["client"] = client
        return await func(self, user_id, account_id, *args, **kwargs)

    return wrapper


class FullClientManager:
    """Manages full Telegram client features for accounts"""

    def __init__(self, bot_instance, user_clients: Dict):
        self.bot = bot_instance
        self.user_clients = user_clients

    @with_account_client
    async def update_profile_photo(
        self, user_id: int, account_id: str, photo_path: str, client=None
    ) -> tuple[bool, str]:
        """Update account profile photo"""
        try:
            if not os.path.isfile(photo_path) or ".." in photo_path:
                return False, "Invalid file path"
            uploaded_file = await client.upload_file(photo_path)
            result = await client(
                functions.photos.UploadProfilePhotoRequest(file=uploaded_file)
            )

            photo_id = str(result.photo.id) if hasattr(result, "photo") else None
            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id), "user_id": user_id},
                {"$set": {"profile_photo_id": photo_id}},
            )

            await self._log_audit_event(
                user_id, account_id, "profile_photo_updated", {"photo_id": photo_id}
            )
            return True, "Profile photo updated successfully"

        except Exception as e:
            logger.error(f"Failed to update profile photo: {e}")
            return False, f"Error: {str(e)}"

    @with_account_client
    async def update_profile_name(
        self,
        user_id: int,
        account_id: str,
        first_name: str,
        last_name: str = "",
        client=None,
    ) -> tuple[bool, str]:
        """Update account name"""
        try:
            logger.info(
                f"Updating profile name for user {user_id}, account {account_id}"
            )

            logger.info(
                f"Calling Telegram API to update name: {first_name} {last_name}"
            )
            await client(
                functions.account.UpdateProfileRequest(
                    first_name=first_name, last_name=last_name
                )
            )

            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id), "user_id": user_id},
                {
                    "$set": {
                        "profile_first_name": first_name,
                        "profile_last_name": last_name,
                    }
                },
            )

            await self._log_audit_event(
                user_id,
                account_id,
                "profile_name_updated",
                {"first_name": first_name, "last_name": last_name},
            )
            logger.info(
                f"Profile name updated successfully for {first_name} {last_name}"
            )
            return True, "Profile name updated successfully"

        except Exception as e:
            logger.error(f"Failed to update profile name: {e}")
            return False, f"Error: {str(e)}"

    @with_account_client
    async def update_username(
        self, user_id: int, account_id: str, username: str, client=None
    ) -> tuple[bool, str]:
        """Update account username"""
        try:
            logger.info(
                f"Updating username for user {user_id}, account {account_id} to {username}"
            )

            try:
                result = await client(
                    functions.account.CheckUsernameRequest(username=username)
                )
                if not result:
                    return False, "Username not available"
            except Exception:
                return False, "Username not available or invalid"

            logger.info(f"Setting username to {username}")
            await client(functions.account.UpdateUsernameRequest(username=username))

            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id), "user_id": user_id},
                {"$set": {"username": username}},
            )

            await self._log_audit_event(
                user_id, account_id, "username_updated", {"username": username}
            )
            logger.info(f"Username updated successfully to @{username}")
            return True, f"Username set to @{username}"

        except Exception as e:
            logger.error(f"Failed to update username: {e}")
            return False, f"Error: {str(e)}"

    @with_account_client
    async def update_bio(
        self, user_id: int, account_id: str, bio: str, client=None
    ) -> tuple[bool, str]:
        """Update account bio/about"""
        try:
            logger.info(f"Updating bio for user {user_id}, account {account_id}")

            logger.info(f"Setting bio to: {bio}")
            await client(functions.account.UpdateProfileRequest(about=bio))

            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id), "user_id": user_id},
                {"$set": {"about": bio}},
            )

            await self._log_audit_event(
                user_id, account_id, "bio_updated", {"bio": bio[:100]}
            )
            logger.info(f"Bio updated successfully")
            return True, "Bio updated successfully"

        except Exception as e:
            logger.error(f"Failed to update bio: {e}")
            return False, f"Error: {str(e)}"

    # Session Management
    @with_account_client
    async def list_active_sessions(
        self, user_id: int, account_id: str, client=None
    ) -> tuple[bool, List[Dict]]:
        """List all active sessions for account"""
        try:
            auths = await client(functions.account.GetAuthorizationsRequest())

            sessions = []
            for auth in auths.authorizations:
                sessions.append(
                    {
                        "hash": auth.hash,
                        "device": auth.device_model,
                        "platform": auth.platform,
                        "system_version": auth.system_version,
                        "app_name": auth.app_name,
                        "app_version": auth.app_version,
                        "date_created": (
                            auth.date_created.isoformat() if auth.date_created else None
                        ),
                        "date_active": (
                            auth.date_active.isoformat() if auth.date_active else None
                        ),
                        "ip": auth.ip,
                        "country": auth.country,
                        "region": auth.region,
                        "current": auth.current,
                    }
                )

            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id), "user_id": user_id},
                {
                    "$set": {
                        "active_sessions_count": len(sessions),
                        "last_session_check": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                },
            )

            return True, sessions

        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return False, []

    @with_account_client
    async def terminate_session(
        self, user_id: int, account_id: str, session_hash: int, client=None
    ) -> tuple[bool, str]:
        """Terminate a specific session"""
        try:
            await client(functions.account.ResetAuthorizationRequest(hash=session_hash))

            await self._log_audit_event(
                user_id,
                account_id,
                "session_terminated",
                {"session_hash": session_hash},
            )
            return True, "Session terminated successfully"

        except Exception as e:
            logger.error(f"Failed to terminate session: {e}")
            return False, f"Error: {str(e)}"

    @with_account_client
    async def terminate_all_sessions(
        self, user_id: int, account_id: str, client=None
    ) -> tuple[bool, str]:
        """Terminate all sessions except current"""
        try:
            await client(functions.auth.ResetAuthorizationsRequest())

            await self._log_audit_event(
                user_id, account_id, "all_sessions_terminated", {}
            )
            return True, "All sessions terminated successfully"

        except Exception as e:
            logger.error(f"Failed to terminate all sessions: {e}")
            return False, f"Error: {str(e)}"

    # Online Maker
    async def toggle_online_maker(
        self, user_id: int, account_id: str, enabled: bool, interval: int = 3600
    ) -> tuple[bool, str]:
        """Toggle online maker for account"""
        try:
            result = await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id), "user_id": user_id},
                {
                    "$set": {
                        "online_maker_enabled": enabled,
                        "online_maker_interval": interval,
                    }
                },
            )

            if result.matched_count == 0:
                return False, "Account not found"

            await self._log_audit_event(
                user_id,
                account_id,
                "online_maker_toggled",
                {"enabled": enabled, "interval": interval},
            )
            return True, f"Online maker {'enabled' if enabled else 'disabled'}"

        except Exception as e:
            logger.error(f"Failed to toggle online maker: {e}")
            return False, f"Error: {str(e)}"

    @with_account_client
    async def update_online_status(
        self, user_id: int, account_id: str, client=None
    ) -> tuple[bool, str]:
        """Update online status for account"""
        try:
            await client(functions.account.UpdateStatusRequest(offline=False))

            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id), "user_id": user_id},
                {"$set": {"last_online_update": time.strftime("%Y-%m-%d %H:%M:%S")}},
            )

            return True, "Online status updated"

        except Exception as e:
            logger.error(f"Failed to update online status: {e}")
            return False, f"Error: {str(e)}"

    # Helper methods
    async def _get_account_client(self, user_id: int, account_id: str):
        """Get Telethon client for account"""
        try:
            logger.info(f"Looking for account {account_id} for user {user_id}")
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                logger.error(f"Account {account_id} not found in database")
                return None

            account_name = account.get('name') or account.get('phone') or account.get('display_name', 'Unknown')
            logger.info(f"Found account: {account_name}")
            # Get client from user_clients dict
            user_clients = self.user_clients.get(user_id, {})
            logger.info(
                f"Available clients for user {user_id}: {list(user_clients.keys())}"
            )
            client = user_clients.get(account_name)
            if client:
                logger.info(f"Found client for {account_name}")
                if not client.is_connected():
                    logger.info(
                        f"Client for {account_name} is not connected, connecting..."
                    )
                    await client.connect()
                    logger.info(f"Client for {account_name} connected.")
            else:
                logger.error(f"No client found for {account_name}")
            return client

        except Exception as e:
            logger.error(f"Failed to get account client: {e}")
            return None

    async def _log_audit_event(
        self, user_id: int, account_id: str, event_type: str, event_data: Dict[str, Any]
    ):
        """Log audit event"""
        try:
            audit_event = {
                "account_id": ObjectId(account_id),
                "user_id": user_id,
                "event_type": event_type,
                "event_data": event_data,
                "timestamp": time.time(),
            }

            # Add to account's audit log
            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)}, {"$push": {"audit_log": audit_event}}
            )

        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
