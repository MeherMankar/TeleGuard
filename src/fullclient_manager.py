"""Full Telegram Client Manager - Profile, Sessions, Automation

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Any
from telethon import functions, types, errors
from telethon.tl.types import InputPeerEmpty
from database import get_session
from models import Account, User, AutomationJob, MessageTemplate, AuditEvent

logger = logging.getLogger(__name__)

class FullClientManager:
    """Manages full Telegram client features for accounts"""
    
    def __init__(self, bot_instance, user_clients: Dict):
        self.bot = bot_instance
        self.user_clients = user_clients
        
    # TODO: REVIEW - Profile management methods interact with user sessions
    async def update_profile_photo(self, user_id: int, account_id: int, photo_path: str) -> tuple[bool, str]:
        """Update account profile photo"""
        try:
            client = await self._get_account_client(user_id, account_id)
            if not client:
                return False, "Account client not found"
            
            # Upload and set profile photo
            uploaded_file = await client.upload_file(photo_path)
            result = await client(functions.photos.UploadProfilePhotoRequest(
                file=uploaded_file
            ))
            
            # Update database
            async with get_session() as session:
                from sqlalchemy import select
                result_db = await session.execute(
                    select(Account).where(Account.id == account_id)
                )
                account = result_db.scalar_one_or_none()
                if account:
                    account.profile_photo_id = str(result.photo.id) if hasattr(result, 'photo') else None
                    await session.commit()
            
            await self._log_audit_event(user_id, account_id, "profile_photo_updated", {"photo_id": str(result.photo.id) if hasattr(result, 'photo') else None})
            return True, "Profile photo updated successfully"
            
        except Exception as e:
            logger.error(f"Failed to update profile photo: {e}")
            return False, f"Error: {str(e)}"
    
    async def update_profile_name(self, user_id: int, account_id: int, first_name: str, last_name: str = "") -> tuple[bool, str]:
        """Update account name"""
        try:
            client = await self._get_account_client(user_id, account_id)
            if not client:
                return False, "Account client not found"
            
            await client(functions.account.UpdateProfileRequest(
                first_name=first_name,
                last_name=last_name
            ))
            
            # Update database
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account).where(Account.id == account_id)
                )
                account = result.scalar_one_or_none()
                if account:
                    account.profile_first_name = first_name
                    account.profile_last_name = last_name
                    await session.commit()
            
            await self._log_audit_event(user_id, account_id, "profile_name_updated", {"first_name": first_name, "last_name": last_name})
            return True, "Profile name updated successfully"
            
        except Exception as e:
            logger.error(f"Failed to update profile name: {e}")
            return False, f"Error: {str(e)}"
    
    async def update_username(self, user_id: int, account_id: int, username: str) -> tuple[bool, str]:
        """Update account username"""
        try:
            client = await self._get_account_client(user_id, account_id)
            if not client:
                return False, "Account client not found"
            
            # Check username availability first
            try:
                result = await client(functions.account.CheckUsernameRequest(username=username))
                if not result:
                    return False, "Username not available"
            except Exception:
                return False, "Username not available or invalid"
            
            # Set username
            await client(functions.account.UpdateUsernameRequest(username=username))
            
            # Update database
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account).where(Account.id == account_id)
                )
                account = result.scalar_one_or_none()
                if account:
                    account.username = username
                    await session.commit()
            
            await self._log_audit_event(user_id, account_id, "username_updated", {"username": username})
            return True, f"Username set to @{username}"
            
        except Exception as e:
            logger.error(f"Failed to update username: {e}")
            return False, f"Error: {str(e)}"
    
    async def update_bio(self, user_id: int, account_id: int, bio: str) -> tuple[bool, str]:
        """Update account bio/about"""
        try:
            client = await self._get_account_client(user_id, account_id)
            if not client:
                return False, "Account client not found"
            
            await client(functions.account.UpdateProfileRequest(about=bio))
            
            # Update database
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account).where(Account.id == account_id)
                )
                account = result.scalar_one_or_none()
                if account:
                    account.about = bio
                    await session.commit()
            
            await self._log_audit_event(user_id, account_id, "bio_updated", {"bio": bio[:100]})
            return True, "Bio updated successfully"
            
        except Exception as e:
            logger.error(f"Failed to update bio: {e}")
            return False, f"Error: {str(e)}"
    
    # Session Management
    async def list_active_sessions(self, user_id: int, account_id: int) -> tuple[bool, List[Dict]]:
        """List all active sessions for account"""
        try:
            client = await self._get_account_client(user_id, account_id)
            if not client:
                return False, []
            
            auths = await client(functions.account.GetAuthorizationsRequest())
            
            sessions = []
            for auth in auths.authorizations:
                sessions.append({
                    "hash": auth.hash,
                    "device": auth.device_model,
                    "platform": auth.platform,
                    "system_version": auth.system_version,
                    "app_name": auth.app_name,
                    "app_version": auth.app_version,
                    "date_created": auth.date_created.isoformat() if auth.date_created else None,
                    "date_active": auth.date_active.isoformat() if auth.date_active else None,
                    "ip": auth.ip,
                    "country": auth.country,
                    "region": auth.region,
                    "current": auth.current
                })
            
            # Update session count in database
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account).where(Account.id == account_id)
                )
                account = result.scalar_one_or_none()
                if account:
                    account.active_sessions_count = len(sessions)
                    account.last_session_check = time.strftime('%Y-%m-%d %H:%M:%S')
                    await session.commit()
            
            return True, sessions
            
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return False, []
    
    async def terminate_session(self, user_id: int, account_id: int, session_hash: int) -> tuple[bool, str]:
        """Terminate a specific session"""
        try:
            client = await self._get_account_client(user_id, account_id)
            if not client:
                return False, "Account client not found"
            
            await client(functions.account.ResetAuthorizationRequest(hash=session_hash))
            
            await self._log_audit_event(user_id, account_id, "session_terminated", {"session_hash": session_hash})
            return True, "Session terminated successfully"
            
        except Exception as e:
            logger.error(f"Failed to terminate session: {e}")
            return False, f"Error: {str(e)}"
    
    async def terminate_all_sessions(self, user_id: int, account_id: int) -> tuple[bool, str]:
        """Terminate all sessions except current"""
        try:
            client = await self._get_account_client(user_id, account_id)
            if not client:
                return False, "Account client not found"
            
            await client(functions.auth.ResetAuthorizationsRequest())
            
            await self._log_audit_event(user_id, account_id, "all_sessions_terminated", {})
            return True, "All sessions terminated successfully"
            
        except Exception as e:
            logger.error(f"Failed to terminate all sessions: {e}")
            return False, f"Error: {str(e)}"
    
    # Online Maker
    async def toggle_online_maker(self, user_id: int, account_id: int, enabled: bool, interval: int = 3600) -> tuple[bool, str]:
        """Toggle online maker for account"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account).where(Account.id == account_id)
                )
                account = result.scalar_one_or_none()
                if not account:
                    return False, "Account not found"
                
                account.online_maker_enabled = enabled
                account.online_maker_interval = interval
                await session.commit()
            
            await self._log_audit_event(user_id, account_id, "online_maker_toggled", {"enabled": enabled, "interval": interval})
            return True, f"Online maker {'enabled' if enabled else 'disabled'}"
            
        except Exception as e:
            logger.error(f"Failed to toggle online maker: {e}")
            return False, f"Error: {str(e)}"
    
    async def update_online_status(self, user_id: int, account_id: int) -> tuple[bool, str]:
        """Update online status for account"""
        try:
            client = await self._get_account_client(user_id, account_id)
            if not client:
                return False, "Account client not found"
            
            # Send updateStatus to mark as online
            await client(functions.account.UpdateStatusRequest(offline=False))
            
            # Update last online time in database
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account).where(Account.id == account_id)
                )
                account = result.scalar_one_or_none()
                if account:
                    account.last_online_update = time.strftime('%Y-%m-%d %H:%M:%S')
                    await session.commit()
            
            return True, "Online status updated"
            
        except Exception as e:
            logger.error(f"Failed to update online status: {e}")
            return False, f"Error: {str(e)}"
    
    # Helper methods
    async def _get_account_client(self, user_id: int, account_id: int):
        """Get Telethon client for account"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()
                if not account:
                    return None
                
                # Get client from user_clients dict
                user_clients = self.user_clients.get(user_id, {})
                return user_clients.get(account.name)
                
        except Exception as e:
            logger.error(f"Failed to get account client: {e}")
            return None
    
    async def _log_audit_event(self, user_id: int, account_id: int, event_type: str, event_data: Dict[str, Any]):
        """Log audit event"""
        try:
            async with get_session() as session:
                audit_event = AuditEvent(
                    account_id=account_id,
                    user_id=user_id,
                    event_type=event_type,
                    event_data=json.dumps(event_data),
                    timestamp=time.strftime('%Y-%m-%d %H:%M:%S')
                )
                session.add(audit_event)
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")