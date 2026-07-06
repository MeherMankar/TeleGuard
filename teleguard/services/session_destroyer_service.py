"""
Session Destroyer Service
Logic for monitoring and terminating unauthorized sessions.
"""

import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from telethon import functions, errors, types

from ..sync.session_destroyer_db import SessionDestroyerDB
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class SessionDestroyerService:
    """Handles core logic for session monitoring and destruction"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot

    async def get_active_sessions(self, client) -> List[types.Authorization]:
        """Fetch all active authorizations for a client"""
        try:
            result = await client(functions.account.GetAuthorizationsRequest())
            return result.authorizations
        except errors.FloodWaitError as e:
            logger.warning(f"FloodWait in Session Destroyer: {e.seconds}s")
            await asyncio.sleep(e.seconds)
            return []
        except Exception as e:
            logger.error(f"Error fetching authorizations: {e}")
            return []

    async def sync_trusted_sessions(self, user_id: int, account_id: str, client):
        """Store all current sessions as trusted"""
        sessions = await self.get_active_sessions(client)
        if sessions:
            hashes = [s.hash for s in sessions]
            await SessionDestroyerDB.save_trusted_sessions(user_id, account_id, hashes)
            logger.info(f"Synced {len(hashes)} trusted sessions for user {user_id}, account {account_id}")
            return len(hashes)
        return 0

    async def process_account_protection(self, user_id: int, account_id: str, client, account_name: str):
        """Check for and destroy new unauthorized sessions for an account"""
        try:
            # 1. Check for Temp Bypass (Global and per-account)
            from ..services.protection_storage import ProtectionStorage
            from datetime import datetime, timezone
            
            settings = await ProtectionStorage.get_settings(user_id)
            pause_until = settings.get("pause_until")
            is_paused = pause_until and pause_until > datetime.now(timezone.utc)
            
            if is_paused:
                logger.debug(f"⏭️ Skipping protection for {account_name} due to Temp Bypass")
                return

            # 2. Get current sessions from Telegram
            current_sessions = await self.get_active_sessions(client)
            if not current_sessions:
                return

            # 3. Get trusted sessions and fresh-pending hashes from DB
            trusted_hashes = await SessionDestroyerDB.get_trusted_sessions(user_id, account_id)

            now = datetime.now(timezone.utc)

            # Load pending hashes — hashes that hit FRESH_RESET_AUTHORISATION_FORBIDDEN
            pending_docs = await mongodb.db.session_destroyer_pending.find(
                {"user_id": user_id, "account_id": account_id}
            ).to_list(None)
            pending_map = {doc["hash"]: doc for doc in pending_docs}

            # 4. Retry any pending hashes whose cool-down has expired
            for hash_val, doc in list(pending_map.items()):
                retry_after = doc.get("retry_after")
                if retry_after and retry_after.tzinfo is None:
                    retry_after = retry_after.replace(tzinfo=timezone.utc)
                if retry_after and now >= retry_after:
                    # Find the live session object if it still exists
                    live_session = next(
                        (s for s in current_sessions if s.hash == hash_val), None
                    )
                    if live_session:
                        logger.info(
                            f"🔄 Retrying deferred kill for session {hash_val} "
                            f"({doc.get('device', '?')}) on {account_name}"
                        )
                        await self.destroy_session(
                            user_id, account_id, client, live_session, account_name
                        )
                    else:
                        # Session is gone — clean up the pending record
                        logger.info(
                            f"✅ Pending session {hash_val} for {account_name} "
                            "no longer present — removing from queue"
                        )
                    # Remove the pending record regardless (killed or gone)
                    await mongodb.db.session_destroyer_pending.delete_one(
                        {"user_id": user_id, "account_id": account_id, "hash": hash_val}
                    )
                    del pending_map[hash_val]

            # 5. Identify new suspicious sessions
            suspicious_sessions = []
            for session in current_sessions:
                # Never destroy the current session (the bot itself)
                if session.current:
                    if session.hash not in trusted_hashes:
                        await SessionDestroyerDB.add_trusted_hash(user_id, account_id, session.hash)
                    continue

                # Already trusted
                if session.hash in trusted_hashes:
                    continue

                # Still inside the fresh cool-down window — skip silently
                if session.hash in pending_map:
                    continue

                suspicious_sessions.append(session)

            # 6. Destroy suspicious sessions
            for session in suspicious_sessions:
                await self.destroy_session(user_id, account_id, client, session, account_name)

        except Exception as e:
            logger.error(f"Error processing protection for {account_name}: {e}")

    async def destroy_session(self, user_id: int, account_id: str, client, session: types.Authorization, account_name: str):
        """Terminate a specific session and log the event"""
        try:
            # Terminate via Telegram API
            await client(functions.account.ResetAuthorizationRequest(hash=session.hash))
            
            # Formulate timezones natively
            from datetime import timezone, timedelta
            ist_tz = timezone(timedelta(hours=5, minutes=30))
            
            # Parse Login Time (date_created)
            login_time_str = "Unknown"
            if getattr(session, 'date_created', None):
                try:
                    dt_utc = session.date_created.astimezone(timezone.utc)
                    dt_ist = dt_utc.astimezone(ist_tz)
                    login_time_str = f"{dt_utc.strftime('%I:%M %p')} UTC ({dt_ist.strftime('%I:%M %p')} IST)"
                except Exception as ex:
                    logger.error(f"Error formatting login time: {ex}")
            
            # Clean and sanitize attributes, handling missing/empty ones
            device = session.device_model.strip() if getattr(session, 'device_model', None) else "Unknown Device"
            platform = session.platform.strip() if getattr(session, 'platform', None) else "Unknown Platform"
            system_version = session.system_version.strip() if getattr(session, 'system_version', None) else "Unknown"
            
            ip_val = session.ip.strip() if getattr(session, 'ip', None) else "Unknown"
            if not ip_val:
                ip_val = "Unknown"
                
            country = session.country.strip() if getattr(session, 'country', None) else "Unknown"
            if not country:
                country = "Unknown"
                
            region = session.region.strip() if getattr(session, 'region', None) else "Unknown"
            if not region:
                region = "Unknown"
                
            app_name = session.app_name.strip() if getattr(session, 'app_name', None) else "Unknown App"
            app_version = session.app_version.strip() if getattr(session, 'app_version', None) else ""
            
            # Prepare session info for logging and notification
            session_info = {
                "device": device,
                "platform": platform,
                "system_version": system_version,
                "ip": ip_val,
                "country": country,
                "region": region,
                "app_name": app_name,
                "app_version": app_version,
                "hash": session.hash,
                "login_time": login_time_str,
                "success": True
            }

            # Log to DB
            await SessionDestroyerDB.log_destruction(user_id, account_id, session_info)
            
            # Notify User
            await self.notify_user_of_destruction(user_id, account_name, session_info)
            
            logger.warning(f"🔥 Session Destroyer: Terminated session {session.hash} ({device}) for {account_name}")
            
        except Exception as e:
            error_msg = str(e)
            if "FRESH_RESET_AUTHORISATION_FORBIDDEN" in error_msg or "too new" in error_msg.lower():
                # Telegram enforces a ~24h cool-down before a brand-new session
                # is allowed to terminate other authorizations.  We store the hash
                # in a "fresh_pending" document so the poller can retry after the
                # window passes instead of hammering the same error every 5 seconds.
                from datetime import timezone, timedelta
                retry_after = datetime.now(timezone.utc) + timedelta(hours=25)
                await mongodb.db.session_destroyer_pending.update_one(
                    {"user_id": user_id, "account_id": account_id, "hash": session.hash},
                    {"$set": {
                        "user_id": user_id,
                        "account_id": account_id,
                        "hash": session.hash,
                        "retry_after": retry_after,
                        "device": getattr(session, "device_model", "Unknown"),
                    }},
                    upsert=True,
                )
                logger.warning(
                    f"⚠️ Session Destroyer: Session {session.hash} for {account_name} is too new to terminate — "
                    f"queued for retry after {retry_after.strftime('%Y-%m-%d %H:%M UTC')}"
                )
            else:
                logger.error(f"Failed to destroy session {session.hash} for {account_name}: {e}")
            
            # Log failure
            session_info = {"hash": session.hash, "success": False, "device": session.device_model}
            await SessionDestroyerDB.log_destruction(user_id, account_id, session_info)

    async def notify_user_of_destruction(self, user_id: int, account_name: str, session: Dict[str, Any]):
        """Send the required notification format to the user"""
        try:
            # Format:
            # 🚨 New Unauthorized Session Destroyed
            # 🖥 Device: iPhone 15 Pro
            # 📱 Platform: iOS
            # 🌍 Country: India
            # 📍 IP Address: 49.xxx.xxx.xxx
            # 🕒 Login Time: 12:31 PM UTC (06:01 PM IST)
            # 🕒 Detection Time: 12:32 PM UTC (06:02 PM IST)
            # 📦 App: Telegram iOS 11.2
            # 🔐 Status: Session Terminated Successfully
            
            from datetime import timezone, timedelta
            ist_tz = timezone(timedelta(hours=5, minutes=30))
            now_utc = datetime.now(timezone.utc)
            now_ist = now_utc.astimezone(ist_tz)
            
            detection_time = f"{now_utc.strftime('%I:%M %p')} UTC ({now_ist.strftime('%I:%M %p')} IST)"
            
            # Use 'login_time' if present, otherwise default to "Unknown"
            login_time = session.get("login_time", "Unknown")
            
            # Check if app version is present, format beautifully
            app_str = session['app_name']
            if session.get('app_version'):
                app_str += f" {session['app_version']}"
            
            message = (
                "🚨 **New Unauthorized Session Destroyed**\n\n"
                f"🖥 **Device:** {session['device']}\n"
                f"📱 **Platform:** {session['platform']}\n"
                f"🌍 **Country:** {session['country']}\n"
                f"📍 **IP Address:** `{session['ip']}`\n"
                f"🕒 **Login Time:** {login_time}\n"
                f"🕒 **Detection Time:** {detection_time}\n"
                f"📦 **App:** {app_str}\n"
                "🔐 **Status:** Session Terminated Successfully\n\n"
                f"💡 **Account:** {account_name}\n"
                "⚡ **Session Destroyer protected your account.**"
            )
            
            await self.bot.send_message(user_id, message)
        except Exception as e:
            logger.error(f"Error sending notification to {user_id}: {e}")
