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
    
    @staticmethod
    def get_spoofed_device_params():
        """Get random device spoofing parameters for TelegramClient"""
        import random
        
        devices = [
            # Google Pixels (Android 10-14)
            {"device_model": "Pixel 8 Pro", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Pixel 8", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Pixel 7 Pro", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Pixel 7", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Pixel 6 Pro", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Pixel 6", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Pixel 5", "system_version": "Android 12", "app_version": "10.14.5"},
            {"device_model": "Pixel 4 XL", "system_version": "Android 11", "app_version": "10.14.5"},
            {"device_model": "Pixel 4", "system_version": "Android 11", "app_version": "10.14.5"},
            {"device_model": "Pixel 3 XL", "system_version": "Android 10", "app_version": "10.14.5"},
            {"device_model": "Pixel 3", "system_version": "Android 10", "app_version": "10.14.5"},
            # Samsung Galaxy S Series (Android 10-14)
            {"device_model": "Galaxy S24 Ultra", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Galaxy S24+", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Galaxy S24", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Galaxy S23 Ultra", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Galaxy S23+", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Galaxy S23", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Galaxy S22 Ultra", "system_version": "Android 12", "app_version": "10.14.5"},
            {"device_model": "Galaxy S22+", "system_version": "Android 12", "app_version": "10.14.5"},
            {"device_model": "Galaxy S22", "system_version": "Android 12", "app_version": "10.14.5"},
            {"device_model": "Galaxy S21 Ultra", "system_version": "Android 11", "app_version": "10.14.5"},
            {"device_model": "Galaxy S21+", "system_version": "Android 11", "app_version": "10.14.5"},
            {"device_model": "Galaxy S21", "system_version": "Android 11", "app_version": "10.14.5"},
            {"device_model": "Galaxy S20 Ultra", "system_version": "Android 10", "app_version": "10.14.5"},
            {"device_model": "Galaxy S20+", "system_version": "Android 10", "app_version": "10.14.5"},
            {"device_model": "Galaxy S20", "system_version": "Android 10", "app_version": "10.14.5"},
            {"device_model": "Galaxy S10+", "system_version": "Android 10", "app_version": "10.14.5"},
            {"device_model": "Galaxy S10", "system_version": "Android 10", "app_version": "10.14.5"},
            # Samsung Galaxy Note Series
            {"device_model": "Galaxy Note 20 Ultra", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Galaxy Note 20", "system_version": "Android 14", "app_version": "10.14.5"},
            # Samsung Galaxy A Series
            {"device_model": "Galaxy A54", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Galaxy A34", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Galaxy A24", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Galaxy A14", "system_version": "Android 14", "app_version": "10.14.5"},
            # OnePlus (Android 10-14)
            {"device_model": "OnePlus 12", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "OnePlus 11", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "OnePlus 10 Pro", "system_version": "Android 12", "app_version": "10.14.5"},
            {"device_model": "OnePlus 10T", "system_version": "Android 12", "app_version": "10.14.5"},
            {"device_model": "OnePlus 9 Pro", "system_version": "Android 11", "app_version": "10.14.5"},
            {"device_model": "OnePlus 9", "system_version": "Android 11", "app_version": "10.14.5"},
            {"device_model": "OnePlus 8 Pro", "system_version": "Android 10", "app_version": "10.14.5"},
            {"device_model": "OnePlus 8", "system_version": "Android 10", "app_version": "10.14.5"},
            {"device_model": "OnePlus 7T Pro", "system_version": "Android 10", "app_version": "10.14.5"},
            {"device_model": "OnePlus 7T", "system_version": "Android 10", "app_version": "10.14.5"},
            {"device_model": "OnePlus Nord 3", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "OnePlus Nord CE 3", "system_version": "Android 13", "app_version": "10.14.5"},
            # Xiaomi/Redmi/POCO (Android 10-14)
            {"device_model": "Xiaomi 14", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Xiaomi 13 Pro", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Xiaomi 13", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Xiaomi 12 Pro", "system_version": "Android 12", "app_version": "10.14.5"},
            {"device_model": "Xiaomi 12", "system_version": "Android 12", "app_version": "10.14.5"},
            {"device_model": "Xiaomi Mi 11", "system_version": "Android 11", "app_version": "10.14.5"},
            {"device_model": "Xiaomi Mi 10", "system_version": "Android 10", "app_version": "10.14.5"},
            {"device_model": "Redmi Note 13 Pro", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Redmi Note 12 Pro", "system_version": "Android 12", "app_version": "10.14.5"},
            {"device_model": "Redmi Note 11 Pro", "system_version": "Android 11", "app_version": "10.14.5"},
            {"device_model": "Redmi Note 10 Pro", "system_version": "Android 10", "app_version": "10.14.5"},
            {"device_model": "Redmi K70", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "POCO F5 Pro", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "POCO F4 GT", "system_version": "Android 12", "app_version": "10.14.5"},
            {"device_model": "POCO F3", "system_version": "Android 11", "app_version": "10.14.5"},
            {"device_model": "POCO F2 Pro", "system_version": "Android 10", "app_version": "10.14.5"},
            {"device_model": "POCO X5 Pro", "system_version": "Android 12", "app_version": "10.14.5"},
            # Oppo
            {"device_model": "Oppo Find X6 Pro", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Oppo Find X5 Pro", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Oppo Reno 10 Pro", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Oppo A98", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Oppo A78", "system_version": "Android 14", "app_version": "10.14.5"},
            # Vivo
            {"device_model": "Vivo X100 Pro", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Vivo X90 Pro", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Vivo V29 Pro", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Vivo Y100", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Vivo T2 Pro", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "vivo V2135", "system_version": "Android 13", "app_version": "10.14.5"},
            # Realme
            {"device_model": "Realme GT 5", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Realme GT Neo 5", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Realme 11 Pro+", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Realme C55", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Realme Narzo 60 Pro", "system_version": "Android 14", "app_version": "10.14.5"},
            # Nothing
            {"device_model": "Nothing Phone 2", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Nothing Phone 1", "system_version": "Android 14", "app_version": "10.14.5"},
            # Huawei
            {"device_model": "Huawei P60 Pro", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Huawei Mate 50 Pro", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Huawei Nova 11", "system_version": "Android 14", "app_version": "10.14.5"},
            # Honor
            {"device_model": "Honor Magic 5 Pro", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Honor 90", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Honor X50", "system_version": "Android 14", "app_version": "10.14.5"},
            # Motorola
            {"device_model": "Motorola Edge 40 Pro", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Motorola G84", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Motorola Edge 30", "system_version": "Android 14", "app_version": "10.14.5"},
            # Sony
            {"device_model": "Sony Xperia 1 V", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Sony Xperia 5 V", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Sony Xperia 10 V", "system_version": "Android 14", "app_version": "10.14.5"},
            # Asus
            {"device_model": "Asus ROG Phone 7", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Asus Zenfone 10", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Asus ROG Phone 6", "system_version": "Android 14", "app_version": "10.14.5"},
            # Fairphone
            {"device_model": "Fairphone 5", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Fairphone 4", "system_version": "Android 13", "app_version": "10.14.5"},
            # TCL
            {"device_model": "TCL 40 SE", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "TCL 30 5G", "system_version": "Android 12", "app_version": "10.14.5"},
            # Nokia
            {"device_model": "Nokia G60", "system_version": "Android 12", "app_version": "10.14.5"},
            {"device_model": "Nokia X30", "system_version": "Android 12", "app_version": "10.14.5"},
            # Additional Popular Models
            {"device_model": "Galaxy Z Fold 5", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Galaxy Z Flip 5", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Galaxy Z Fold 4", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Galaxy Z Flip 4", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Xiaomi Mix Fold 3", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "OnePlus Open", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Pixel Fold", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Honor Magic Vs", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Oppo Find N3", "system_version": "Android 14", "app_version": "10.14.5"},
            {"device_model": "Vivo X Fold 2", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Realme GT Master", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Redmi K60 Pro", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "POCO F4 GT", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Black Shark 5 Pro", "system_version": "Android 12", "app_version": "10.14.5"},
            {"device_model": "Red Magic 8 Pro", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Legion Phone Duel 2", "system_version": "Android 12", "app_version": "10.14.5"},
            {"device_model": "iQOO 11", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "iQOO Neo 7", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Infinix Note 30", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Tecno Phantom V Fold", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "Nubia Z50", "system_version": "Android 13", "app_version": "10.14.5"},
            {"device_model": "ZTE Axon 40 Ultra", "system_version": "Android 12", "app_version": "10.14.5"},
            {"device_model": "Meizu 20 Pro", "system_version": "Android 13", "app_version": "10.14.5"}
        ]
        
        device = random.choice(devices)
        return {
            "device_model": device["device_model"],
            "system_version": device["system_version"],
            "app_version": device["app_version"],
            "lang_code": "en",
            "system_lang_code": "en"
        }
    async def snoop_device_info(self, client: TelegramClient, user_id: int) -> Dict[str, Any]:
        """Extract device information from active sessions"""
        try:
            authorizations = await client(GetAuthorizationsRequest())
            devices = []
            suspicious_count = 0
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
                    'password_pending': auth.password_pending,
                    'scan_timestamp': datetime.now(timezone.utc)
                }
                if self._is_device_suspicious(device_info):
                    suspicious_count += 1
                    device_info['is_suspicious'] = True
                else:
                    device_info['is_suspicious'] = False
                devices.append(device_info)
            # Store in database
            await self._store_device_data(user_id, devices)
            return {
                'devices': devices, 
                'count': len(devices),
                'suspicious_count': suspicious_count,
                'scan_timestamp': datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Device snooping failed: {e}")
            return {'devices': [], 'count': 0, 'error': str(e)}
    def _extract_os_info(self, platform: str, system_version: str, device_model: str) -> Dict[str, str]:
        """Extract Android OS information from platform and system version"""
        os_info = {
            'os_name': 'Unknown',
            'os_version': 'Unknown',
            'architecture': 'Unknown',
            'device_type': self._detect_device_type(device_model, platform)
        }
        if not platform or not system_version:
            return os_info
        platform_lower = platform.lower()
        # Android detection only
        if 'android' in platform_lower:
            os_info['os_name'] = 'Android'
            os_info['os_version'] = system_version
            # Android architecture detection
            if 'arm64' in system_version or 'aarch64' in system_version:
                os_info['architecture'] = 'ARM64'
            elif 'arm' in system_version:
                os_info['architecture'] = 'ARM'
        return os_info
    def _detect_device_type(self, device_model: str, platform: str) -> str:
        """Detect Android device type from model and platform"""
        if not device_model:
            return 'Unknown'
        model_lower = device_model.lower()
        platform_lower = platform.lower() if platform else ''
        # Android mobile devices
        if any(x in model_lower for x in ['android', 'samsung', 'pixel', 'oneplus', 'xiaomi', 'huawei', 'oppo', 'vivo', 'realme']):
            return 'Mobile'
        # Android tablets
        if 'tablet' in model_lower:
            return 'Tablet'
        # Default to mobile for Android
        if 'android' in platform_lower:
            return 'Mobile'
        return 'Unknown'
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
            # Access the database properly through mongodb.db
            from ..core.mongo_database import mongodb
            await mongodb.db.device_logs.update_one(
                {'user_id': user_id},
                {'$set': device_data},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to store device data: {e}")
    async def get_device_history(self, user_id: int) -> Dict[str, Any]:
        """Retrieve device history for user"""
        try:
            from ..core.mongo_database import mongodb
            doc = await mongodb.db.device_logs.find_one({'user_id': user_id})
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
    def _is_device_suspicious(self, device: Dict) -> bool:
        """Check if a device is suspicious based on various indicators"""
        suspicious_indicators = [
            not device.get('official_app'),
            device.get('password_pending'),
            'unknown' in device.get('device_model', '').lower(),
            device.get('country') != device.get('region'),
            not device.get('app_name'),  # Missing app name
            device.get('api_id') and device.get('api_id') not in [349, 2040, 17349],  # Common official API IDs
        ]
        return any(suspicious_indicators)
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
        if not device.get('app_name'):
            reasons.append('Missing application name')
        if device.get('api_id') and device.get('api_id') not in [349, 2040, 17349]:
            reasons.append('Unusual API ID')
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
                    logger.error(f"Failed to terminate session: {e}")
            return {
                'terminated_count': len(terminated),
                'terminated_hashes': terminated,
                'total_suspicious': len(suspicious)
            }
        except Exception as e:
            logger.error(f"Session termination failed: {e}")
            return {'terminated_count': 0, 'error': str(e)}
