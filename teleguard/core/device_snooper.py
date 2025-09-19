"""
Device Snooping Module for TeleGuard
Monitors and tracks device information from sessions and login attempts
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from telethon import TelegramClient
from telethon.tl.functions.account import GetAuthorizationsRequest
from telethon.tl.types import Authorization
# from ..utils.database import Database


logger = logging.getLogger(__name__)

class DeviceSnooper:
    def __init__(self, db):
        self.db = db
        
    async def snoop_device_info(self, client: TelegramClient, user_id: int) -> Dict[str, Any]:
        """Extract device information from active sessions"""
        try:
            authorizations = await client(GetAuthorizationsRequest())
            devices = []
            
            for auth in authorizations.authorizations:
                # Extract OS information from platform and system_version
                os_info = self._extract_os_info(auth.platform, auth.system_version, auth.device_model)
                
                device_info = {
                    'hash': auth.hash,
                    'device_model': auth.device_model,
                    'platform': auth.platform,
                    'system_version': auth.system_version,
                    'os_name': os_info['os_name'],
                    'os_version': os_info['os_version'],
                    'os_architecture': os_info['architecture'],
                    'device_type': os_info['device_type'],
                    'api_id': auth.api_id,
                    'app_name': auth.app_name,
                    'app_version': auth.app_version,
                    'date_created': auth.date_created,
                    'date_active': auth.date_active,
                    'ip': auth.ip,
                    'country': auth.country,
                    'region': auth.region,
                    'current': auth.current,
                    'official_app': auth.official_app,
                    'password_pending': auth.password_pending
                }
                devices.append(device_info)
                
            # Store in database
            await self._store_device_data(user_id, devices)
            return {'devices': devices, 'count': len(devices)}
            
        except Exception as e:
            logger.error(f"Device snooping failed for user {user_id}: {e}")
            return {'devices': [], 'count': 0, 'error': str(e)}
    
    def _extract_os_info(self, platform: str, system_version: str, device_model: str) -> Dict[str, str]:
        """Extract detailed OS information from platform and system version"""
        os_info = {
            'os_name': 'Unknown',
            'os_version': 'Unknown',
            'architecture': 'Unknown',
            'device_type': self._detect_device_type(device_model, platform)
        }
        
        if not platform or not system_version:
            return os_info
            
        platform_lower = platform.lower()
        
        # Windows detection
        if 'windows' in platform_lower:
            os_info['os_name'] = 'Windows'
            if 'NT 10.0' in system_version:
                os_info['os_version'] = 'Windows 10/11'
            elif 'NT 6.3' in system_version:
                os_info['os_version'] = 'Windows 8.1'
            elif 'NT 6.1' in system_version:
                os_info['os_version'] = 'Windows 7'
            else:
                os_info['os_version'] = system_version
                
        # macOS detection
        elif 'darwin' in platform_lower or 'macos' in platform_lower:
            os_info['os_name'] = 'macOS'
            os_info['os_version'] = system_version
            
        # Linux detection
        elif 'linux' in platform_lower:
            os_info['os_name'] = 'Linux'
            os_info['os_version'] = system_version
            
        # Android detection
        elif 'android' in platform_lower:
            os_info['os_name'] = 'Android'
            os_info['os_version'] = system_version
            
        # iOS detection
        elif 'ios' in platform_lower or device_model and ('iphone' in device_model.lower() or 'ipad' in device_model.lower()):
            os_info['os_name'] = 'iOS'
            os_info['os_version'] = system_version
            
        # Architecture detection
        if 'x64' in system_version or 'x86_64' in system_version or 'amd64' in system_version:
            os_info['architecture'] = 'x64'
        elif 'x86' in system_version or 'i386' in system_version:
            os_info['architecture'] = 'x86'
        elif 'arm64' in system_version or 'aarch64' in system_version:
            os_info['architecture'] = 'ARM64'
        elif 'arm' in system_version:
            os_info['architecture'] = 'ARM'
            
        return os_info
    
    def _detect_device_type(self, device_model: str, platform: str) -> str:
        """Detect device type from model and platform"""
        if not device_model:
            return 'Unknown'
            
        model_lower = device_model.lower()
        platform_lower = platform.lower() if platform else ''
        
        # Mobile devices
        if any(x in model_lower for x in ['iphone', 'android', 'samsung', 'pixel', 'oneplus', 'xiaomi', 'huawei']):
            return 'Mobile'
        
        # Tablets
        if any(x in model_lower for x in ['ipad', 'tablet', 'surface']):
            return 'Tablet'
            
        # Laptops
        if any(x in model_lower for x in ['macbook', 'laptop', 'thinkpad', 'dell', 'hp', 'asus', 'lenovo']):
            return 'Laptop'
            
        # Desktops
        if any(x in model_lower for x in ['desktop', 'pc', 'workstation', 'imac']):
            return 'Desktop'
            
        # Web/Browser
        if 'web' in platform_lower or 'browser' in platform_lower:
            return 'Web'
            
        return 'Computer'
    
    async def _store_device_data(self, user_id: int, devices: List[Dict]):
        """Store device information in database"""
        try:
            device_data = {
                'user_id': user_id,
                'devices': devices,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'total_devices': len(devices),
                'last_updated': datetime.now(timezone.utc),
                'device_count': len(devices)
            }
            
            await self.db.device_logs.update_one(
                {'user_id': user_id},
                {'$set': device_data},
                upsert=True
            )
            
        except Exception as e:
            logger.error(f"Failed to store device data: {e}")
    
    async def get_device_history(self, user_id: int) -> Dict[str, Any]:
        """Retrieve device history for user"""
        try:
            doc = await self.db.device_logs.find_one({'user_id': user_id})
            if not doc:
                return {'devices': [], 'count': 0}
                
            return {
                'devices': doc.get('devices', []),
                'count': doc.get('total_devices', 0),
                'last_updated': doc.get('last_updated')
            }
            
        except Exception as e:
            logger.error(f"Failed to retrieve device history: {e}")
            return {'devices': [], 'count': 0, 'error': str(e)}
    
    async def detect_suspicious_devices(self, user_id: int) -> List[Dict]:
        """Detect potentially suspicious devices"""
        try:
            history = await self.get_device_history(user_id)
            suspicious = []
            
            for device in history.get('devices', []):
                # Check for suspicious indicators
                if (not device.get('official_app') or 
                    device.get('password_pending') or
                    'unknown' in device.get('device_model', '').lower() or
                    device.get('country') != device.get('region')):
                    
                    suspicious.append({
                        'device': device,
                        'reasons': self._get_suspicious_reasons(device)
                    })
                    
            return suspicious
            
        except Exception as e:
            logger.error(f"Suspicious device detection failed: {e}")
            return []
    
    def _get_suspicious_reasons(self, device: Dict) -> List[str]:
        """Get reasons why device is suspicious"""
        reasons = []
        
        if not device.get('official_app'):
            reasons.append('Unofficial Telegram app')
        if device.get('password_pending'):
            reasons.append('Password authentication pending')
        if 'unknown' in device.get('device_model', '').lower():
            reasons.append('Unknown device model')
        if device.get('country') != device.get('region'):
            reasons.append('Country/region mismatch')
            
        return reasons
    
    async def terminate_suspicious_sessions(self, client: TelegramClient, user_id: int) -> Dict[str, Any]:
        """Terminate sessions from suspicious devices"""
        try:
            from telethon.tl.functions.account import ResetAuthorizationRequest
            
            suspicious = await self.detect_suspicious_devices(user_id)
            terminated = []
            
            for item in suspicious:
                device = item['device']
                try:
                    await client(ResetAuthorizationRequest(hash=device['hash']))
                    terminated.append(device['hash'])
                except Exception as e:
                    logger.error(f"Failed to terminate session {device['hash']}: {e}")
            
            return {
                'terminated_count': len(terminated),
                'terminated_hashes': terminated,
                'total_suspicious': len(suspicious)
            }
            
        except Exception as e:
            logger.error(f"Session termination failed: {e}")
            return {'terminated_count': 0, 'error': str(e)}