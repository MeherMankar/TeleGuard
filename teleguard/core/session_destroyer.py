"""Session Destroyer - Background watcher to terminate unauthorized sessions"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Set, List

from telethon import functions, errors

from ..core.mongo_database import mongodb as _mdb
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
        """Main loop that polls for new sessions every 5 seconds."""
        # Short grace delay on startup so connections stabilise
        await asyncio.sleep(3)

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
                    await asyncio.sleep(15)
                    continue

                # 2. Find a connected client
                user_clients = self.bot_manager.user_clients.get(user_id, {})
                if not user_clients:
                    await asyncio.sleep(15)
                    continue

                target_client = None
                for client in user_clients.values():
                    if client and client.is_connected():
                        target_client = client
                        break

                if not target_client:
                    await asyncio.sleep(15)
                    continue

                # 3. Fetch current sessions
                try:
                    result = await target_client(functions.account.GetAuthorizationsRequest())
                    current_auths = result.authorizations
                except errors.FloodWaitError as e:
                    logger.warning(f"FloodWait in Session Destroyer for {user_id}: {e.seconds}s")
                    await asyncio.sleep(min(e.seconds, 60))
                    continue
                except Exception as e:
                    logger.error(f"Error fetching authorizations for {user_id}: {e}")
                    await asyncio.sleep(15)
                    continue

                # 4. On first run: trust ALL existing sessions so we don't destroy them.
                # Also trust any session that pre-dates when SD was enabled — catches
                # sessions that were missed during the initial sync (e.g. bot restart
                # with SD already enabled in DB, or slow client connections).
                if first_run:
                    first_run = False
                    existing_trusted = set(settings.get("trusted_hashes", []))

                    # enabled_at tells us the earliest point from which we should
                    # watch for NEW sessions.  Any session created before this is
                    # pre-existing and must be trusted unconditionally.
                    enabled_at = settings.get("enabled_at")
                    if enabled_at and enabled_at.tzinfo is None:
                        enabled_at = enabled_at.replace(tzinfo=timezone.utc)

                    # Load pending hashes — these are post-enabled sessions awaiting
                    # the 24-h cool-down.  Do NOT trust them; let the retry handle them.
                    pending_on_first_run = {
                        doc["hash"]
                        for doc in await _mdb.db.session_destroyer_pending.find(
                            {"user_id": user_id}
                        ).to_list(None)
                    }

                    new_hashes = set()
                    for auth in current_auths:
                        # Never auto-trust a pending (deferred-kill) session
                        if auth.hash in pending_on_first_run:
                            continue
                        new_hashes.add(auth.hash)
                        # Also trust by timestamp: if the session logged in before
                        # SD was enabled, it is a pre-existing session.
                        if enabled_at:
                            session_date = getattr(auth, "date_active", None) or getattr(auth, "date", None)
                            if session_date:
                                if session_date.tzinfo is None:
                                    session_date = session_date.replace(tzinfo=timezone.utc)
                                if session_date <= enabled_at:
                                    existing_trusted.add(auth.hash)

                    combined = existing_trusted | new_hashes
                    await ProtectionStorage.update_settings(
                        user_id, {"trusted_hashes": list(combined)}
                    )
                    logger.info(
                        f"Session Destroyer first run for user {user_id}: "
                        f"trusted {len(combined)} existing sessions"
                        + (f", skipped {len(pending_on_first_run)} pending" if pending_on_first_run else "")
                    )
                    await asyncio.sleep(5)
                    continue

                # 5. Reload settings after possible first-run update
                settings = await ProtectionStorage.get_settings(user_id)
                trusted_hashes = set(settings.get("trusted_hashes", []))
                destroyed_hashes = set(settings.get("destroyed_hashes", []))
                allow_next = settings.get("allow_next", False)

                # Auto-expire allow_next if the timestamp has passed
                if allow_next:
                    allow_next_until = settings.get("allow_next_until")
                    if allow_next_until:
                        if isinstance(allow_next_until, str):
                            try:
                                allow_next_until = datetime.fromisoformat(allow_next_until)
                            except Exception:
                                allow_next_until = None
                        if allow_next_until and allow_next_until.tzinfo is None:
                            allow_next_until = allow_next_until.replace(tzinfo=timezone.utc)
                        if allow_next_until and datetime.now(timezone.utc) > allow_next_until:
                            await ProtectionStorage.update_settings(
                                user_id, {"allow_next": False, "allow_next_until": None}
                            )
                            allow_next = False

                # Load pending (fresh-restriction) hashes BEFORE the detection
                # loop so they are excluded from newly_detected on every cycle.
                now = datetime.now(timezone.utc)
                pending_docs = await _mdb.db.session_destroyer_pending.find(
                    {"user_id": user_id}
                ).to_list(None)
                pending_hashes = {doc["hash"] for doc in pending_docs}

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
                    # Skip sessions waiting out the 24-h fresh restriction
                    if auth.hash in pending_hashes:
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

                    # Unauthorized session — queue for immediate kill
                    newly_detected.append(auth)

                # 6. Terminate all unauthorized sessions in parallel — no delay between kills
                if newly_detected:
                    async def _kill(auth):
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
                        except Exception as e:
                            error_msg = str(e)
                            if (
                                "FRESH_RESET_AUTHORISATION_FORBIDDEN" in error_msg
                                or "too new" in error_msg.lower()
                            ):
                                # Telegram's 24-h restriction — queue and silence
                                retry_after = now + timedelta(hours=25)
                                await _mdb.db.session_destroyer_pending.update_one(
                                    {"user_id": user_id, "hash": auth.hash},
                                    {"$set": {
                                        "user_id": user_id,
                                        "hash": auth.hash,
                                        "retry_after": retry_after,
                                        "device": getattr(auth, "device_model", "Unknown"),
                                    }},
                                    upsert=True,
                                )
                                logger.warning(
                                    f"⚠️ Session Destroyer: Session {auth.hash} "
                                    f"({getattr(auth, 'device_model', '?')}) for user {user_id} "
                                    f"is too new — queued for retry after "
                                    f"{retry_after.strftime('%Y-%m-%d %H:%M UTC')}"
                                )
                            else:
                                logger.error(
                                    f"Failed to terminate session {auth.hash} "
                                    f"for user {user_id}: {e}"
                                )

                    await asyncio.gather(*[_kill(auth) for auth in newly_detected])

                # 7. Retry any pending sessions whose cool-down has elapsed
                due_pending = [d for d in pending_docs if d.get("retry_after") and (
                    d["retry_after"].replace(tzinfo=timezone.utc)
                    if d["retry_after"].tzinfo is None
                    else d["retry_after"]
                ) <= now]

                for doc in due_pending:
                    live = next((a for a in current_auths if a.hash == doc["hash"]), None)
                    if live:
                        try:
                            await target_client(
                                functions.account.ResetAuthorizationRequest(hash=live.hash)
                            )
                            await ProtectionStorage.add_destroyed_hash(user_id, live.hash)
                            await self.notifier.notify_session_destroyed(user_id, live)
                            logger.warning(
                                f"🛡️ Session Destroyer: Terminated deferred session "
                                f"{live.hash} for user {user_id} "
                                f"(device: {live.device_model})"
                            )
                        except Exception as e:
                            logger.error(
                                f"Deferred kill failed for {doc['hash']}, user {user_id}: {e}"
                            )
                    else:
                        logger.info(
                            f"Pending session {doc['hash']} for user {user_id} "
                            "no longer present — removing from queue"
                        )
                    # Remove pending record whether session was killed or disappeared
                    await _mdb.db.session_destroyer_pending.delete_one(
                        {"user_id": user_id, "hash": doc["hash"]}
                    )

                await ProtectionStorage.update_settings(
                    user_id, {"last_check": datetime.now(timezone.utc)}
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in Session Destroyer loop for {user_id}: {e}")

            # Poll every 5 seconds for near-instant detection
            await asyncio.sleep(5)

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

    async def sync_trusted_for_new_client(self, user_id: int, client) -> int:
        """
        Merge all sessions visible through *client* into the trusted-hashes list.

        Called whenever a new Telegram account is added to TeleGuard while
        Session Destroyer is already active.  Unlike sync_trusted_sessions()
        this does NOT replace the existing trusted list — it merges so that
        sessions belonging to other accounts already in trusted_hashes are not
        disturbed.

        Returns the number of newly-trusted hashes added.
        """
        try:
            settings = await ProtectionStorage.get_settings(user_id)
            if not settings.get("session_destroyer_enabled"):
                return 0  # SD not active — nothing to do

            result = await client(functions.account.GetAuthorizationsRequest())
            new_hashes = {auth.hash for auth in result.authorizations}

            existing_trusted = set(settings.get("trusted_hashes", []))
            to_add = new_hashes - existing_trusted

            if to_add:
                merged = list(existing_trusted | to_add)
                await ProtectionStorage.update_settings(user_id, {"trusted_hashes": merged})
                logger.info(
                    f"Session Destroyer: trusted {len(to_add)} pre-existing session(s) "
                    f"for newly-added account of user {user_id}"
                )
            else:
                logger.debug(
                    f"Session Destroyer: no new hashes to trust for user {user_id} "
                    f"(all sessions already known)"
                )

            return len(to_add)
        except Exception as e:
            logger.error(
                f"Session Destroyer: failed to sync trusted sessions for new client "
                f"(user {user_id}): {e}"
            )
            return 0
