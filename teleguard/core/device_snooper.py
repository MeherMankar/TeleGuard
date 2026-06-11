"""
Device Snooping Module for TeleGuard
Monitors and tracks device information from sessions and login attempts
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from telethon import TelegramClient
from telethon.tl.functions.account import GetAuthorizationsRequest

# from ..utils.database import Database
logger = logging.getLogger(__name__)


class DeviceSnooper:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def get_spoofed_device_params():
        """Get random device spoofing parameters for TelegramClient.
        Delegates to the central device_profiles module — single source of truth.
        """
        from teleguard.data.device_profiles import get_spoofed_device_params as _get
        return _get()
    

    async def snoop_device_info(
        self, client: TelegramClient, user_id: int
    ) -> Dict[str, Any]:
        """Extract device information from active sessions"""
        try:
            authorizations = await client(GetAuthorizationsRequest())
            devices = []
            suspicious_count = 0
            for auth in authorizations.authorizations:
                # Extract OS information from platform and system_version
                os_info = self._extract_os_info(
                    auth.platform, auth.system_version, auth.device_model
                )
                device_info = {
                    "hash": auth.hash,
                    "device_model": auth.device_model,
                    "platform": auth.platform,
                    "system_version": auth.system_version,
                    "os_name": os_info["os_name"],
                    "os_version": os_info["os_version"],
                    "os_architecture": os_info["architecture"],
                    "device_type": os_info["device_type"],
                    "api_id": auth.api_id,
                    "app_name": auth.app_name,
                    "app_version": auth.app_version,
                    "date_created": auth.date_created,
                    "date_active": auth.date_active,
                    "ip": auth.ip,
                    "country": auth.country,
                    "region": auth.region,
                    "current": auth.current,
                    "official_app": auth.official_app,
                    "password_pending": auth.password_pending,
                    "scan_timestamp": datetime.now(timezone.utc),
                }
                if self._is_device_suspicious(device_info):
                    suspicious_count += 1
                    device_info["is_suspicious"] = True
                else:
                    device_info["is_suspicious"] = False
                devices.append(device_info)
            # Run advanced security checks
            from ..utils.security_monitor import security_monitor
            await security_monitor.check_impossible_travel(user_id, devices)
            await security_monitor.check_device_fingerprint(user_id, devices)

            # Store in database
            await self._store_device_data(user_id, devices)
            return {
                "devices": devices,
                "count": len(devices),
                "suspicious_count": suspicious_count,
                "scan_timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"Device snooping failed: {e}")
            return {"devices": [], "count": 0, "error": str(e)}

    def _extract_os_info(
        self, platform: str, system_version: str, device_model: str
    ) -> Dict[str, str]:
        """Extract Android OS information from platform and system version"""
        os_info = {
            "os_name": "Unknown",
            "os_version": "Unknown",
            "architecture": "Unknown",
            "device_type": self._detect_device_type(device_model, platform),
        }
        if not platform or not system_version:
            return os_info
        platform_lower = platform.lower()
        # Android detection only
        if "android" in platform_lower:
            os_info["os_name"] = "Android"
            os_info["os_version"] = system_version
            # Android architecture detection
            if "arm64" in system_version or "aarch64" in system_version:
                os_info["architecture"] = "ARM64"
            elif "arm" in system_version:
                os_info["architecture"] = "ARM"
        return os_info

    def _detect_device_type(self, device_model: str, platform: str) -> str:
        """Detect Android device type from model and platform"""
        if not device_model:
            return "Unknown"
        model_lower = device_model.lower()
        platform_lower = platform.lower() if platform else ""
        # Android mobile devices
        if any(
            x in model_lower
            for x in [
                "android",
                "samsung",
                "pixel",
                "oneplus",
                "xiaomi",
                "huawei",
                "oppo",
                "vivo",
                "realme",
            ]
        ):
            return "Mobile"
        # Android tablets
        if "tablet" in model_lower:
            return "Tablet"
        # Default to mobile for Android
        if "android" in platform_lower:
            return "Mobile"
        return "Unknown"

    async def _store_device_data(self, user_id: int, devices: List[Dict]):
        """Store device information in database"""
        try:
            device_data = {
                "user_id": user_id,
                "devices": devices,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_devices": len(devices),
                "last_updated": datetime.now(timezone.utc),
                "device_count": len(devices),
            }
            # Access the database properly through mongodb.db
            from ..core.mongo_database import mongodb

            await mongodb.db.device_logs.update_one(
                {"user_id": user_id}, {"$set": device_data}, upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to store device data: {e}")

    async def get_device_history(self, user_id: int) -> Dict[str, Any]:
        """Retrieve device history for user"""
        try:
            from ..core.mongo_database import mongodb

            doc = await mongodb.db.device_logs.find_one({"user_id": user_id})
            if not doc:
                return {"devices": [], "count": 0}
            return {
                "devices": doc.get("devices", []),
                "count": doc.get("total_devices", 0),
                "last_updated": doc.get("last_updated"),
            }
        except Exception as e:
            logger.error(f"Failed to retrieve device history: {e}")
            return {"devices": [], "count": 0, "error": str(e)}

    async def detect_suspicious_devices(self, user_id: int) -> List[Dict]:
        """Detect potentially suspicious devices"""
        try:
            history = await self.get_device_history(user_id)
            suspicious = []
            for device in history.get("devices", []):
                if (
                    not device.get("official_app")
                    or device.get("password_pending")
                    or "unknown" in device.get("device_model", "").lower()
                    or device.get("country") != device.get("region")
                ):
                    suspicious.append(
                        {
                            "device": device,
                            "reasons": self._get_suspicious_reasons(device),
                        }
                    )
            return suspicious
        except Exception as e:
            logger.error(f"Suspicious device detection failed: {e}")
            return []

    def _is_device_suspicious(self, device: Dict) -> bool:
        """Check if a device is suspicious based on various indicators"""
        suspicious_indicators = [
            not device.get("official_app"),
            device.get("password_pending"),
            "unknown" in device.get("device_model", "").lower(),
            device.get("country") != device.get("region"),
            not device.get("app_name"),  # Missing app name
            device.get("api_id")
            and device.get("api_id")
            not in [349, 2040, 17349],  # Common official API IDs
        ]
        return any(suspicious_indicators)

    def _get_suspicious_reasons(self, device: Dict) -> List[str]:
        """Get reasons why device is suspicious"""
        reasons = []
        if not device.get("official_app"):
            reasons.append("Unofficial Telegram app")
        if device.get("password_pending"):
            reasons.append("Password authentication pending")
        if "unknown" in device.get("device_model", "").lower():
            reasons.append("Unknown device model")
        if device.get("country") != device.get("region"):
            reasons.append("Country/region mismatch")
        if not device.get("app_name"):
            reasons.append("Missing application name")
        if device.get("api_id") and device.get("api_id") not in [349, 2040, 17349]:
            reasons.append("Unusual API ID")
        return reasons

    async def terminate_suspicious_sessions(
        self, client: TelegramClient, user_id: int
    ) -> Dict[str, Any]:
        """Terminate sessions from suspicious devices"""
        try:
            from telethon.tl.functions.account import ResetAuthorizationRequest

            suspicious = await self.detect_suspicious_devices(user_id)
            terminated = []
            for item in suspicious:
                device = item["device"]
                try:
                    await client(ResetAuthorizationRequest(hash=device["hash"]))
                    terminated.append(device["hash"])
                except Exception as e:
                    logger.error(f"Failed to terminate session: {e}")
            return {
                "terminated_count": len(terminated),
                "terminated_hashes": terminated,
                "total_suspicious": len(suspicious),
            }
        except Exception as e:
            logger.error(f"Session termination failed: {e}")
            return {"terminated_count": 0, "error": str(e)}

