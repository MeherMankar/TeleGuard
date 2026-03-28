"""Session Validator - Validate and manage session health
Integrated from SessTg project
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from telethon import TelegramClient
from telethon.errors import (
    ApiIdInvalidError,
    FloodWaitError,
    PhoneNumberInvalidError,
    RPCError,
)
from telethon.sessions import StringSession
from telethon.network import ConnectionTcpFull

logger = logging.getLogger(__name__)


class SessionValidator:
    """Validate and manage Telegram sessions"""
    
    def __init__(self, api_id: int, api_hash: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.validation_log = []
    
    async def validate_session_file(self, session_path: str) -> Tuple[bool, str, Optional[Dict]]:
        """Validate a session file
        
        Returns:
            Tuple of (is_valid, status, user_info)
            status: 'valid', 'need_auth', 'invalid'
        """
        client = None
        try:
            client = TelegramClient(session_path, self.api_id, self.api_hash)
            await client.connect()
            
            if await client.is_user_authorized():
                me = await client.get_me()
                user_info = {
                    'phone': me.phone,
                    'name': f"{me.first_name or ''} {me.last_name or ''}".strip(),
                    'username': me.username,
                    'id': me.id,
                    'premium': getattr(me, 'premium', False),
                    'verified': getattr(me, 'verified', False),
                }
                
                logger.info(f"Session {session_path} is valid: {user_info['phone']}")
                return True, 'valid', user_info
            else:
                logger.warning(f"Session {session_path} needs authorization")
                return False, 'need_auth', None
        
        except (PhoneNumberInvalidError, ApiIdInvalidError) as e:
            logger.error(f"Invalid API data for {session_path}: {e}")
            return False, 'invalid', None
        
        except (FloodWaitError, RPCError) as e:
            logger.error(f"RPC error for {session_path}: {e}")
            return False, 'invalid', None
        
        except ConnectionError as e:
            logger.error(f"Connection error for {session_path}: {e}")
            return False, 'invalid', None
        
        except Exception as e:
            logger.error(f"Validation error for {session_path}: {e}")
            return False, 'invalid', None
        
        finally:
            if client:
                await client.disconnect()
    
    async def validate_session_string(self, session_string: str) -> Tuple[bool, str, Optional[Dict]]:
        """Validate a session string
        
        Returns:
            Tuple of (is_valid, status, user_info)
        """
        client = None
        try:
            client = TelegramClient(
                StringSession(session_string),
                self.api_id,
                self.api_hash
            )
            await client.connect()
            
            if await client.is_user_authorized():
                me = await client.get_me()
                user_info = {
                    'phone': me.phone,
                    'name': f"{me.first_name or ''} {me.last_name or ''}".strip(),
                    'username': me.username,
                    'id': me.id,
                    'premium': getattr(me, 'premium', False),
                    'verified': getattr(me, 'verified', False),
                }
                
                return True, 'valid', user_info
            else:
                return False, 'need_auth', None
        
        except Exception as e:
            logger.error(f"Session string validation error: {e}")
            return False, 'invalid', None
        
        finally:
            if client:
                await client.disconnect()
    
    async def validate_all_sessions(self, sessions_dir: str) -> Dict[str, Dict]:
        """Validate all sessions in a directory
        
        Returns:
            Dict mapping session names to validation results
        """
        sessions_path = Path(sessions_dir)
        if not sessions_path.exists():
            logger.warning(f"Sessions directory {sessions_dir} does not exist")
            return {}
        
        results = {}
        session_files = list(sessions_path.glob("*.session"))
        
        logger.info(f"Validating {len(session_files)} sessions...")
        
        for session_file in session_files:
            session_name = session_file.stem
            is_valid, status, user_info = await self.validate_session_file(str(session_file))
            
            results[session_name] = {
                'path': str(session_file),
                'is_valid': is_valid,
                'status': status,
                'user_info': user_info,
                'size': session_file.stat().st_size / 1024,  # KB
                'last_check': datetime.now(),
            }
            
            # Check for journal file
            journal_file = session_file.with_suffix('.session-journal')
            if journal_file.exists():
                results[session_name]['has_journal'] = True
                results[session_name]['journal_size'] = journal_file.stat().st_size / 1024
            
            await asyncio.sleep(0.5)  # Rate limiting
        
        # Log summary
        valid_count = sum(1 for r in results.values() if r['status'] == 'valid')
        need_auth_count = sum(1 for r in results.values() if r['status'] == 'need_auth')
        invalid_count = sum(1 for r in results.values() if r['status'] == 'invalid')
        
        logger.info(
            f"Validation complete: {valid_count} valid, "
            f"{need_auth_count} need auth, {invalid_count} invalid"
        )
        
        self.validation_log.append({
            'timestamp': datetime.now(),
            'total': len(results),
            'valid': valid_count,
            'need_auth': need_auth_count,
            'invalid': invalid_count,
        })
        
        return results
    
    async def cleanup_invalid_sessions(
        self,
        sessions_dir: str,
        delete_invalid: bool = True,
        delete_need_auth: bool = False
    ) -> Dict[str, int]:
        """Clean up invalid sessions
        
        Args:
            sessions_dir: Directory containing sessions
            delete_invalid: Delete invalid sessions
            delete_need_auth: Delete sessions needing authorization
        
        Returns:
            Dict with counts of deleted sessions
        """
        results = await self.validate_all_sessions(sessions_dir)
        
        deleted = {'invalid': 0, 'need_auth': 0}
        
        for session_name, info in results.items():
            should_delete = False
            reason = ""
            
            if delete_invalid and info['status'] == 'invalid':
                should_delete = True
                reason = "invalid"
            elif delete_need_auth and info['status'] == 'need_auth':
                should_delete = True
                reason = "needs authorization"
            
            if should_delete:
                try:
                    session_path = Path(info['path'])
                    
                    # Delete session file
                    if session_path.exists():
                        os.remove(session_path)
                        logger.info(f"Deleted {session_name}.session ({reason})")
                    
                    # Delete journal file
                    journal_path = session_path.with_suffix('.session-journal')
                    if journal_path.exists():
                        os.remove(journal_path)
                        logger.info(f"Deleted {session_name}.session-journal")
                    
                    deleted[info['status']] += 1
                
                except Exception as e:
                    logger.error(f"Failed to delete {session_name}: {e}")
        
        logger.info(
            f"Cleanup complete: deleted {deleted['invalid']} invalid, "
            f"{deleted['need_auth']} need auth"
        )
        
        return deleted
    
    def get_validation_stats(self) -> Dict:
        """Get validation statistics"""
        if not self.validation_log:
            return {}
        
        latest = self.validation_log[-1]
        return {
            'last_check': latest['timestamp'],
            'total_sessions': latest['total'],
            'valid': latest['valid'],
            'need_auth': latest['need_auth'],
            'invalid': latest['invalid'],
            'total_checks': len(self.validation_log),
        }
    
    async def get_session_info(self, session_path: str) -> Optional[Dict]:
        """Get detailed session information"""
        client = None
        try:
            client = TelegramClient(session_path, self.api_id, self.api_hash)
            await client.connect()
            
            if await client.is_user_authorized():
                me = await client.get_me()
                return {
                    'phone': me.phone,
                    'name': f"{me.first_name or ''} {me.last_name or ''}".strip(),
                    'username': me.username,
                    'id': me.id,
                    'premium': getattr(me, 'premium', False),
                    'verified': getattr(me, 'verified', False),
                    'bot': getattr(me, 'bot', False),
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get session info: {e}")
            return None
        finally:
            if client:
                await client.disconnect()
    
    def save_deletion_log(self, session_name: str, reason: str):
        """Log deleted sessions"""
        log_file = Path('logs/deleted_sessions.log')
        log_file.parent.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] Deleted: {session_name} - Reason: {reason}\n")
    
    def save_validation_log_file(self, valid: int, need_auth: int, invalid: int):
        """Save validation results to log file"""
        log_file = Path('logs/validation.log')
        log_file.parent.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(
                f"[{timestamp}] Valid: {valid}, Need Auth: {need_auth}, "
                f"Invalid: {invalid}\n"
            )
