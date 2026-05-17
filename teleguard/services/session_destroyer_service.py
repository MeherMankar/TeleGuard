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

            # 2. Get trusted sessions from DB
            trusted_hashes = await SessionDestroyerDB.get_trusted_sessions(user_id, account_id)
            
            # 3. Identify new sessions
            suspicious_sessions = []
            for session in current_sessions:
                # Rule: Never destroy current session (the bot itself)
                if session.current:
                    # Automatically trust the current session if not already trusted
                    if session.hash not in trusted_hashes:
                        await SessionDestroyerDB.add_trusted_hash(user_id, account_id, session.hash)
                    continue

                # Rule: If session hash is in trusted list, skip
                if session.hash in trusted_hashes:
                    continue

                # Rule: Any other NEW session is suspicious
                suspicious_sessions.append(session)

            # 4. Destroy suspicious sessions
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
                logger.warning(
                    f"⚠️ Session Destroyer: Cannot destroy session {session.hash} for {account_name} yet. "
                    "Telegram requires the newly logged-in session to be active (usually for 24 hours) "
                    "before it is allowed to terminate other active authorizations."
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
