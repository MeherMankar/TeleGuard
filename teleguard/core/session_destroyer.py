"""Session Destroyer - Background watcher to terminate unauthorized sessions"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Set, List

from telethon import functions, errors

from ..services.protection_storage import ProtectionStorage
from ..services.protection_notifier import ProtectionNotifier

logger = logging.getLogger(__name__)

class SessionDestroyer:
    """Watch for and terminate unauthorized Telegram sessions"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.notifier = ProtectionNotifier(bot_manager.bot)
        self.active_watchers: Dict[int, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self.is_shutdown = False

    async def start_all(self):
        """Start watchers for all users with session protection enabled"""
        users = await ProtectionStorage.get_all_active_session_destroyers()
        for user_settings in users:
            user_id = user_settings["user_id"]
            await self.start_watcher(user_id)

    async def stop_all(self):
        """Stop all active watchers"""
        self.is_shutdown = True
        for user_id, task in self.active_watchers.items():
            task.cancel()
        self.active_watchers.clear()

    async def start_watcher(self, user_id: int):
        """Start a background watcher task for a specific user"""
        async with self._lock:
            if user_id in self.active_watchers:
                if not self.active_watchers[user_id].done():
                    return
            task = asyncio.create_task(self._watcher_loop(user_id))
            self.active_watchers[user_id] = task
            logger.info(f"Started Session Destroyer watcher for user {user_id}")

    async def stop_watcher(self, user_id: int):
        """Stop watcher for a specific user"""
        async with self._lock:
            task = self.active_watchers.pop(user_id, None)
            if task:
                task.cancel()
                logger.info(f"Stopped Session Destroyer watcher for user {user_id}")

    async def _watcher_loop(self, user_id: int):
        """Main loop that polls for new sessions every 60 seconds"""
        # Grace delay on startup so connections stabilize
        await asyncio.sleep(10)

        # On first run, sync ALL current sessions as trusted
        # so we never destroy pre-existing sessions
        first_run = True

        while not self.is_shutdown:
            try:
                # 1. Check if still enabled and not paused
                settings = await ProtectionStorage.get_settings(user_id)
                if not settings.get("session_destroyer_enabled"):
                    break

                pause_until = settings.get("pause_until")
                if pause_until and pause_until > datetime.now(timezone.utc):
                    await asyncio.sleep(60)
                    continue

                # 2. Find a connected client
                user_clients = self.bot_manager.user_clients.get(user_id, {})
                if not user_clients:
                    await asyncio.sleep(60)
                    continue

                target_client = None
                for client in user_clients.values():
                    if client and client.is_connected():
                        target_client = client
                        break

                if not target_client:
                    await asyncio.sleep(60)
                    continue

                # 3. Fetch current sessions
                try:
                    result = await target_client(functions.account.GetAuthorizationsRequest())
                    current_auths = result.authorizations
                except errors.FloodWaitError as e:
                    logger.warning(f"FloodWait in Session Destroyer for {user_id}: {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                    continue
                except Exception as e:
                    logger.error(f"Error fetching authorizations for {user_id}: {e}")
                    await asyncio.sleep(60)
                    continue

                # 4. On first run: trust ALL existing sessions so we don't destroy them
                if first_run:
                    first_run = False
                    existing_trusted = set(settings.get("trusted_hashes", []))
                    new_hashes = {auth.hash for auth in current_auths}
                    combined = existing_trusted | new_hashes
                    await ProtectionStorage.update_settings(
                        user_id, {"trusted_hashes": list(combined)}
                    )
                    logger.info(
                        f"Session Destroyer first run for user {user_id}: "
                        f"trusted {len(combined)} existing sessions"
                    )
                    await asyncio.sleep(60)
                    continue

                # 5. Reload settings after possible first-run update
                settings = await ProtectionStorage.get_settings(user_id)
                trusted_hashes = set(settings.get("trusted_hashes", []))
                destroyed_hashes = set(settings.get("destroyed_hashes", []))
                allow_next = settings.get("allow_next", False)

                newly_detected = []

                for auth in current_auths:
                    # Always skip current session
                    if auth.current:
                        continue
                    # Skip trusted
                    if auth.hash in trusted_hashes:
                        continue
                    # Skip already destroyed (may linger briefly)
                    if auth.hash in destroyed_hashes:
                        continue

                    # If 'allow next login' is active, trust this new session
                    if allow_next:
                        await ProtectionStorage.add_trusted_hash(user_id, auth.hash)
                        await ProtectionStorage.update_settings(user_id, {"allow_next": False})
                        allow_next = False
                        logger.info(
                            f"User {user_id}: New session {auth.hash} trusted via 'Allow Next Login'"
                        )
                        continue

                    # Unauthorized session
                    newly_detected.append(auth)

                # 6. Terminate unauthorized sessions
                for auth in newly_detected:
                    try:
                        await target_client(
                            functions.account.ResetAuthorizationRequest(hash=auth.hash)
                        )
                        await ProtectionStorage.add_destroyed_hash(user_id, auth.hash)
                        await self.notifier.notify_session_destroyed(user_id, auth)
                        logger.warning(
                            f"🛡️ Session Destroyer: Terminated unauthorized session "
                            f"{auth.hash} for user {user_id} "
                            f"(device: {auth.device_model}, ip: {auth.ip})"
                        )
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.error(
                            f"Failed to terminate session {auth.hash} for user {user_id}: {e}"
                        )

                await ProtectionStorage.update_settings(
                    user_id, {"last_check": datetime.now(timezone.utc)}
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in Session Destroyer loop for {user_id}: {e}")

            await asyncio.sleep(60)

    async def sync_trusted_sessions(self, user_id: int, client):
        """
        Fetch all current sessions and save them as trusted.
        Call this when first enabling Session Destroyer so existing
        sessions are never destroyed.
        """
        try:
            result = await client(functions.account.GetAuthorizationsRequest())
            hashes = [auth.hash for auth in result.authorizations]
            await ProtectionStorage.update_settings(user_id, {"trusted_hashes": hashes})
            logger.info(f"Synced {len(hashes)} trusted sessions for user {user_id}")
            return len(hashes)
        except Exception as e:
            logger.error(f"Error syncing trusted sessions for {user_id}: {e}")
            return 0
