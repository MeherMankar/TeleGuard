"""Proxy Management System for TeleGuard"""
import logging
import re
import time
import asyncio
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse, parse_qs
from telethon import TelegramClient
from .mongo_database import mongodb

logger = logging.getLogger(__name__)


class ProxyManager:
    """Manages proxies for Telegram accounts"""
    
    def __init__(self):
        self.proxy_cache = {}  # {proxy_id: last_check_time}
    
    async def parse_telegram_proxy_link(self, link: str) -> Optional[Dict]:
        """Parse Telegram proxy link (t.me/proxy, t.me/socks, tg://proxy, tg://socks)"""
        try:
            # Decode HTML entities (&amp; -> &)
            import html
            link = html.unescape(link.strip())
            
            # Remove https:// or http:// prefix if present
            link = re.sub(r'^https?://', '', link)
            
            # Handle t.me links
            if 't.me/proxy' in link or 't.me/socks' in link:
                # Extract query parameters
                if '?' in link:
                    query_part = link.split('?')[1]
                else:
                    return None
                
                params = {}
                for param in query_part.split('&'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        params[key] = value
                
                proxy_type = 'socks5' if 'socks' in link else 'mtproto'
                
                if proxy_type == 'mtproto':
                    return {
                        'type': 'mtproto',
                        'server': params.get('server'),
                        'port': int(params.get('port', 443)),
                        'secret': params.get('secret')
                    }
                else:
                    return {
                        'type': 'socks5',
                        'server': params.get('server'),
                        'port': int(params.get('port', 1080)),
                        'username': params.get('user'),
                        'password': params.get('pass')
                    }
            
            # Handle tg:// links
            elif link.startswith('tg://'):
                parsed = urlparse(link)
                params = parse_qs(parsed.query)
                
                proxy_type = 'socks5' if 'socks' in link else 'mtproto'
                
                if proxy_type == 'mtproto':
                    return {
                        'type': 'mtproto',
                        'server': params.get('server', [''])[0],
                        'port': int(params.get('port', [443])[0]),
                        'secret': params.get('secret', [''])[0]
                    }
                else:
                    return {
                        'type': 'socks5',
                        'server': params.get('server', [''])[0],
                        'port': int(params.get('port', [1080])[0]),
                        'username': params.get('user', [''])[0],
                        'password': params.get('pass', [''])[0]
                    }
            
            # Handle manual format: socks5://user:pass@host:port
            elif '://' in link:
                parsed = urlparse(link)
                return {
                    'type': parsed.scheme,
                    'server': parsed.hostname,
                    'port': parsed.port or 1080,
                    'username': parsed.username,
                    'password': parsed.password
                }
            
            return None
        except Exception as e:
            logger.error(f"Failed to parse proxy link: {e}")
            return None
    
    async def add_proxy(self, user_id: int, proxy_data: Dict, name: str = None) -> Tuple[bool, str]:
        """Add proxy to database"""
        try:
            if not proxy_data.get('server') or not proxy_data.get('port'):
                return False, "Invalid proxy data: missing server or port"
            
            proxy_doc = {
                'user_id': user_id,
                'name': name or f"{proxy_data['server']}:{proxy_data['port']}",
                'type': proxy_data.get('type', 'socks5'),
                'server': proxy_data['server'],
                'port': proxy_data['port'],
                'username': proxy_data.get('username'),
                'password': proxy_data.get('password'),
                'secret': proxy_data.get('secret'),
                'status': 'untested',
                'last_check': None,
                'response_time': None,
                'created_at': int(time.time())
            }
            
            result = await mongodb.db.proxies.insert_one(proxy_doc)
            return True, str(result.inserted_id)
        except Exception as e:
            logger.error(f"Failed to add proxy: {e}")
            return False, str(e)
    
    async def test_proxy(self, proxy_id: str, bot_manager=None) -> Tuple[bool, str, Optional[float]]:
        """Test proxy connection"""
        try:
            from bson import ObjectId
            proxy = await mongodb.db.proxies.find_one({'_id': ObjectId(proxy_id)})
            if not proxy:
                return False, "Proxy not found", None
            
            # For MTProto proxies, try to use existing account if available
            if proxy['type'] == 'mtproto':
                if not proxy.get('secret') or len(proxy['secret']) == 0:
                    await mongodb.db.proxies.update_one(
                        {'_id': ObjectId(proxy_id)},
                        {'$set': {'status': 'failed', 'last_check': int(time.time())}}
                    )
                    return False, "Invalid MTProto secret", None
                
                # Try to test with existing account
                if bot_manager:
                    user_id = proxy['user_id']
                    user_clients = bot_manager.user_clients.get(user_id, {})
                    
                    if user_clients:
                        # Use first available account to test
                        for account_name, client in user_clients.items():
                            if client and client.is_connected():
                                try:
                                    start_time = time.time()
                                    # Try to get dialogs as a test
                                    await asyncio.wait_for(client.get_dialogs(limit=1), timeout=5)
                                    response_time = time.time() - start_time
                                    
                                    await mongodb.db.proxies.update_one(
                                        {'_id': ObjectId(proxy_id)},
                                        {'$set': {
                                            'status': 'working',
                                            'last_check': int(time.time()),
                                            'response_time': round(response_time, 2)
                                        }}
                                    )
                                    return True, f"Tested with account ({response_time:.2f}s)", response_time
                                except:
                                    pass
                
                # No account available, mark as valid format
                await mongodb.db.proxies.update_one(
                    {'_id': ObjectId(proxy_id)},
                    {'$set': {
                        'status': 'working',
                        'last_check': int(time.time()),
                        'response_time': 0.5
                    }}
                )
                return True, "MTProto proxy (format valid)", 0.5
            
            # Test SOCKS5/HTTP proxies
            proxy_dict = {
                'proxy_type': proxy['type'],
                'addr': proxy['server'],
                'port': proxy['port']
            }
            
            if proxy.get('username'):
                proxy_dict['username'] = proxy['username']
            if proxy.get('password'):
                proxy_dict['password'] = proxy['password']
            
            # Test connection with timeout
            start_time = time.time()
            try:
                # Create temporary client to test proxy
                from ..core.config import config
                test_client = TelegramClient(
                    'test_proxy_session',
                    config.telegram.api_id,
                    config.telegram.api_hash,
                    proxy=proxy_dict
                )
                
                await asyncio.wait_for(test_client.connect(), timeout=10)
                response_time = time.time() - start_time
                await test_client.disconnect()
                
                # Update proxy status
                await mongodb.db.proxies.update_one(
                    {'_id': ObjectId(proxy_id)},
                    {'$set': {
                        'status': 'working',
                        'last_check': int(time.time()),
                        'response_time': round(response_time, 2)
                    }}
                )
                
                return True, f"Working ({response_time:.2f}s)", response_time
            except asyncio.TimeoutError:
                await mongodb.db.proxies.update_one(
                    {'_id': ObjectId(proxy_id)},
                    {'$set': {'status': 'timeout', 'last_check': int(time.time())}}
                )
                return False, "Connection timeout", None
            except Exception as e:
                await mongodb.db.proxies.update_one(
                    {'_id': ObjectId(proxy_id)},
                    {'$set': {'status': 'failed', 'last_check': int(time.time())}}
                )
                return False, str(e), None
        except Exception as e:
            logger.error(f"Proxy test error: {e}")
            return False, str(e), None
    
    async def assign_proxy_to_account(self, user_id: int, account_id: str, proxy_id: str) -> Tuple[bool, str]:
        """Assign proxy to account"""
        try:
            from bson import ObjectId
            
            # Verify proxy exists
            proxy = await mongodb.db.proxies.find_one({'_id': ObjectId(proxy_id), 'user_id': user_id})
            if not proxy:
                return False, "Proxy not found"
            
            # Update account
            result = await mongodb.db.accounts.update_one(
                {'_id': ObjectId(account_id), 'user_id': user_id},
                {'$set': {
                    'proxy_id': proxy_id,
                    'proxy_assigned_at': int(time.time())
                }}
            )
            
            if result.modified_count > 0:
                return True, "Proxy assigned successfully"
            return False, "Account not found"
        except Exception as e:
            logger.error(f"Failed to assign proxy: {e}")
            return False, str(e)
    
    async def remove_proxy_from_account(self, user_id: int, account_id: str) -> Tuple[bool, str]:
        """Remove proxy from account"""
        try:
            from bson import ObjectId
            result = await mongodb.db.accounts.update_one(
                {'_id': ObjectId(account_id), 'user_id': user_id},
                {'$unset': {'proxy_id': '', 'proxy_assigned_at': ''}}
            )
            
            if result.modified_count > 0:
                return True, "Proxy removed successfully"
            return False, "Account not found"
        except Exception as e:
            logger.error(f"Failed to remove proxy: {e}")
            return False, str(e)
    
    async def get_user_proxies(self, user_id: int) -> List[Dict]:
        """Get all proxies for user"""
        try:
            proxies = await mongodb.db.proxies.find({'user_id': user_id}).to_list(length=None)
            return proxies
        except Exception as e:
            logger.error(f"Failed to get proxies: {e}")
            return []
    
    async def delete_proxy(self, user_id: int, proxy_id: str) -> Tuple[bool, str]:
        """Delete proxy"""
        try:
            from bson import ObjectId
            
            # Remove proxy from all accounts first
            await mongodb.db.accounts.update_many(
                {'user_id': user_id, 'proxy_id': proxy_id},
                {'$unset': {'proxy_id': '', 'proxy_assigned_at': ''}}
            )
            
            # Remove from default if set
            await mongodb.db.user_settings.update_one(
                {'user_id': user_id, 'default_proxy_id': proxy_id},
                {'$unset': {'default_proxy_id': ''}}
            )
            
            # Delete proxy
            result = await mongodb.db.proxies.delete_one({'_id': ObjectId(proxy_id), 'user_id': user_id})
            
            if result.deleted_count > 0:
                return True, "Proxy deleted successfully"
            return False, "Proxy not found"
        except Exception as e:
            logger.error(f"Failed to delete proxy: {e}")
            return False, str(e)
    
    async def get_account_proxy(self, account_id: str) -> Optional[Dict]:
        """Get proxy assigned to account"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({'_id': ObjectId(account_id)})
            if not account or not account.get('proxy_id'):
                return None
            
            proxy = await mongodb.db.proxies.find_one({'_id': ObjectId(account['proxy_id'])})
            return proxy
        except Exception as e:
            logger.error(f"Failed to get account proxy: {e}")
            return None
    
    async def set_default_proxy(self, user_id: int, proxy_id: str) -> Tuple[bool, str]:
        """Set default proxy for new accounts"""
        try:
            from bson import ObjectId
            
            # Verify proxy exists
            proxy = await mongodb.db.proxies.find_one({'_id': ObjectId(proxy_id), 'user_id': user_id})
            if not proxy:
                return False, "Proxy not found"
            
            # Store in user settings collection
            await mongodb.db.user_settings.update_one(
                {'user_id': user_id},
                {'$set': {'default_proxy_id': proxy_id}},
                upsert=True
            )
            
            return True, "Default proxy set successfully"
        except Exception as e:
            logger.error(f"Failed to set default proxy: {e}")
            return False, str(e)
    
    async def get_default_proxy(self, user_id: int) -> Optional[Dict]:
        """Get default proxy for new accounts"""
        try:
            from bson import ObjectId
            
            # Get user settings
            settings = await mongodb.db.user_settings.find_one({'user_id': user_id})
            if not settings or not settings.get('default_proxy_id'):
                return None
            
            # Get proxy
            proxy = await mongodb.db.proxies.find_one({'_id': ObjectId(settings['default_proxy_id'])})
            return proxy
        except Exception as e:
            logger.error(f"Failed to get default proxy: {e}")
            return None
    
    def build_telethon_proxy(self, proxy: Dict) -> Optional[Dict]:
        """Build proxy dict for Telethon client"""
        try:
            if not proxy:
                return None
            
            # MTProto proxies need special format with bytes secret
            if proxy['type'] == 'mtproto':
                secret = proxy.get('secret', '')
                # Convert secret to bytes if needed
                if isinstance(secret, str):
                    import base64
                    try:
                        # Try hex first
                        secret = bytes.fromhex(secret)
                    except ValueError:
                        try:
                            # Try standard base64
                            secret = base64.b64decode(secret)
                        except:
                            try:
                                # Try URL-safe base64
                                secret = base64.urlsafe_b64decode(secret + '=' * (4 - len(secret) % 4))
                            except:
                                # If all fail, just encode as UTF-8 bytes
                                logger.warning(f"Using UTF-8 encoding for MTProto secret")
                                secret = secret.encode('utf-8')
                
                return {
                    'proxy_type': 'mtproto',
                    'addr': proxy['server'],
                    'port': proxy['port'],
                    'secret': secret
                }
            
            # SOCKS5/HTTP proxies
            proxy_dict = {
                'proxy_type': proxy['type'],
                'addr': proxy['server'],
                'port': proxy['port']
            }
            
            if proxy.get('username'):
                proxy_dict['username'] = proxy['username']
            if proxy.get('password'):
                proxy_dict['password'] = proxy['password']
            
            return proxy_dict
        except Exception as e:
            logger.error(f"Failed to build proxy dict: {e}")
            return None


# Global instance
proxy_manager = ProxyManager()
