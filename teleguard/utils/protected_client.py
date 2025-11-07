"""
Protected Telethon Client Wrapper
Wraps Telethon client with session protection and rate limiting
"""

import asyncio
import logging
from typing import Any, Optional, Union, List
from telethon import TelegramClient
from telethon.errors import AuthKeyUnregisteredError, SessionRevokedError, FloodWaitError
from telethon.tl.types import User, Chat, Channel

from ..core.session_guardian import get_guardian

logger = logging.getLogger(__name__)

class ProtectedTelegramClient:
    """Telethon client wrapper with comprehensive protection"""
    
    def __init__(self, client: TelegramClient):
        self.client = client
        self.guardian = get_guardian()
        self._original_methods = {}
        self._wrap_methods()
    
    def _wrap_methods(self):
        """Wrap dangerous methods with protection"""
        dangerous_methods = [
            'send_message',
            'forward_messages', 
            'join_channel',
            'leave_channel',
            'add_participants',
            'kick_participant',
            'edit_message',
            'delete_messages'
        ]
        
        for method_name in dangerous_methods:
            if hasattr(self.client, method_name):
                original_method = getattr(self.client, method_name)
                self._original_methods[method_name] = original_method
                
                # Create protected wrapper
                protected_method = self._create_protected_method(method_name, original_method)
                setattr(self, method_name, protected_method)
    
    def _create_protected_method(self, method_name: str, original_method):
        """Create a protected version of a client method"""
        
        async def protected_wrapper(*args, **kwargs):
            if not self.guardian:
                # Fallback to original method if guardian not available
                return await original_method(*args, **kwargs)
            
            try:
                # Determine rate limit category
                rate_limit_key = self._get_rate_limit_key(method_name)
                
                # Apply rate limiting
                await self.guardian.rate_limit(rate_limit_key)
                
                # Execute with exponential backoff
                result = await self.guardian.exponential_backoff(
                    self._safe_execute,
                    method_name,
                    original_method,
                    *args,
                    **kwargs
                )
                
                # Log successful action
                target = self._extract_target(*args, **kwargs)
                self.guardian.log_action(method_name, target, True)
                
                return result
                
            except Exception as e:
                # Log failed action
                target = self._extract_target(*args, **kwargs)
                self.guardian.log_action(method_name, target, False, str(e))
                
                # Check for auth key errors
                if self.guardian.is_auth_key_error(e):
                    await self.guardian.handle_auth_key_error(e, {
                        'method': method_name,
                        'target': target,
                        'args': str(args)[:200]
                    })
                
                raise e
        
        return protected_wrapper
    
    async def _safe_execute(self, method_name: str, original_method, *args, **kwargs):
        """Safely execute original method with error handling"""
        try:
            return await original_method(*args, **kwargs)
            
        except (AuthKeyUnregisteredError, SessionRevokedError) as e:
            # These are critical - let guardian handle them
            raise e
            
        except FloodWaitError as e:
            # Handle flood wait with proper delay
            logger.warning(f"Flood wait for {e.seconds} seconds in {method_name}")
            await asyncio.sleep(e.seconds + 1)
            
            # Retry once after flood wait
            return await original_method(*args, **kwargs)
            
        except Exception as e:
            # Log and re-raise other exceptions
            logger.error(f"Error in {method_name}: {e}")
            raise e
    
    def _get_rate_limit_key(self, method_name: str) -> str:
        """Map method names to rate limit categories"""
        mapping = {
            'send_message': 'message',
            'forward_messages': 'forward', 
            'join_channel': 'join',
            'leave_channel': 'join',
            'add_participants': 'bulk',
            'kick_participant': 'bulk',
            'edit_message': 'message',
            'delete_messages': 'bulk'
        }
        return mapping.get(method_name, 'bulk')
    
    def _extract_target(self, *args, **kwargs) -> str:
        """Extract target information from method arguments"""
        try:
            # First argument is usually the target
            if args:
                target = args[0]
                if hasattr(target, 'id'):
                    return f"ID:{target.id}"
                elif hasattr(target, 'username'):
                    return f"@{target.username}"
                else:
                    return str(target)[:50]
            
            # Check kwargs for entity/chat
            for key in ['entity', 'chat', 'channel']:
                if key in kwargs:
                    target = kwargs[key]
                    if hasattr(target, 'id'):
                        return f"ID:{target.id}"
                    elif hasattr(target, 'username'):
                        return f"@{target.username}"
                    else:
                        return str(target)[:50]
            
            return "unknown"
            
        except Exception:
            return "unknown"
    
    # Delegate all other attributes to the original client
    def __getattr__(self, name):
        return getattr(self.client, name)
    
    async def __aenter__(self):
        await self.client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self.client.__aexit__(exc_type, exc_val, exc_tb)

def create_protected_client(session_path: str, api_id: int, api_hash: str) -> ProtectedTelegramClient:
    """Create a protected Telethon client"""
    
    # Check session lock first
    guardian = get_guardian()
    if guardian:
        if not asyncio.run(guardian.acquire_session_lock(session_path)):
            raise RuntimeError(f"Cannot acquire session lock for {session_path}")
    
    # Create original client
    client = TelegramClient(session_path, api_id, api_hash)
    
    # Wrap with protection
    return ProtectedTelegramClient(client)
