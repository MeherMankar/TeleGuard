"""
TeleGuard Device Snooper
========================
Queries the Telegram API for all active authorizations on an account,
enriches each with OS/device metadata, flags suspicious sessions, and
stores the snapshot in MongoDB for the security dashboard.

This is READ-ONLY with respect to Telegram — it never terminates sessions
itself.  Session termination is handled by SessionDestroyer.

Two distinct roles (not to be confused with device_profiles.py):
  - device_profiles.py  →  what device WE pretend to be when connecting
  - device_snooper.py   →  what devices OTHERS are using to access the account
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from telethon import TelegramClient
from telethon.tl.functions.account import GetAuthorizationsRequest
from telethon.tl.types import Authorization

logger = logging.getLogger(__name__)

# ── Telegram official API IDs (used to flag unofficial clients) ───────────────
# Source: https://core.telegram.org/api/obtaining_api_id#official-apps
_OFFICIAL_API_IDS = {
    2040,   # Telegram Desktop
    6,      # Telegram for Android (legacy)
    17349,  # Telegram for Android
    4,      # Telegram for iOS (legacy)
    10840,  # Telegram for iOS
    1025907, # Telegram macOS
    349,    # TelegramX / old official
    21724,  # Telegram Web
    2496,   # Telegram Web K
}

# ── Strings that indicate a bot or unofficial client ──────────────────────────
_SUSPICIOUS_APP_NAMES = {"tdata", "gram", "plus", "nicegram", "bgram", "api"}
_BOT_PLATFORMS = {"bot", "server", "linux"}


class DeviceSnooper:
    """
    Reads active Telegram sessions for an account and produces a structured
    report used by the security dashboard and session destroyer.
    """

    def __init__(self, db):
        self.db = db  # Motor MongoDB client — kept for compatibility

    # ── Spoofing helper (delegates to device_profiles) ────────────────────────

    @staticmethod
    def get_spoofed_device_params() -> Dict[str, str]:
        """
        Return random Android device params for TelegramClient.
        Delegates to the central device_profiles module.
        """
        from teleguard.data.device_profiles import get_spoofed_device_params
        return get_spoofed_device_params()

    # ── Main public API ───────────────────────────────────────────────────────

    async def snoop_device_info(
        self, client: TelegramClient, user_id: int
    ) -> Dict[str, Any]:
        """
        Fetch all active authorizations for the account connected via *client*,
        enrich each with OS/security metadata, and persist to MongoDB.

        Returns:
            {
                "devices": List[DeviceInfo],
                "count": int,
                "suspicious_count": int,
                "current_session": DeviceInfo | None,
                "scan_timestamp": ISO-8601 str,
            }
        """
        try:
            result = await client(GetAuthorizationsRequest())
            devices: List[Dict[str, Any]] = []
            suspicious_count = 0
            current_session: Optional[Dict] = None

            for auth in result.authorizations:
                device_info = self._build_device_info(auth)

                if device_info["is_suspicious"]:
                    suspicious_count += 1

                if auth.current:
                    current_session = device_info

                devices.append(device_info)

            # Sort: current session first, then by last-active descending
            devices.sort(key=lambda d: (
                not d.get("current", False),
                -(d.get("date_active") or datetime.min.replace(tzinfo=timezone.utc)).timestamp()
                if d.get("date_active") else 0,
            ))

            # Run advanced security checks
            try:
                from teleguard.utils.security_monitor import security_monitor
                await security_monitor.check_impossible_travel(user_id, devices)
                await security_monitor.check_device_fingerprint(user_id, devices)
            except Exception as e:
                logger.debug(f"Security monitor checks skipped: {e}")

            # Persist snapshot
            await self._store_snapshot(user_id, devices)

            scan_time = datetime.now(timezone.utc).isoformat()
            return {
                "devices": devices,
                "count": len(devices),
                "suspicious_count": suspicious_count,
                "current_session": current_session,
                "scan_timestamp": scan_time,
            }

        except Exception as e:
            logger.error(f"Device snooping failed for user {user_id}: {e}")
            return {"devices": [], "count": 0, "suspicious_count": 0,
                    "current_session": None, "error": str(e)}

    async def get_device_history(self, user_id: int) -> Dict[str, Any]:
        """Return the last persisted device snapshot from MongoDB."""
        try:
            from teleguard.core.mongo_database import mongodb
            doc = await mongodb.db.device_logs.find_one({"user_id": user_id})
            if not doc:
                return {"devices": [], "count": 0}
            return {
                "devices": doc.get("devices", []),
                "count": doc.get("total_devices", 0),
                "last_updated": doc.get("last_updated"),
                "suspicious_count": doc.get("suspicious_count", 0),
            }
        except Exception as e:
            logger.error(f"Failed to retrieve device history: {e}")
            return {"devices": [], "count": 0, "error": str(e)}

    async def detect_suspicious_devices(self, user_id: int) -> List[Dict]:
        """
        Return suspicious devices from the last snapshot with their reasons.
        Does NOT re-query Telegram — uses the cached snapshot.
        """
        try:
            history = await self.get_device_history(user_id)
            return [
                {"device": d, "reasons": d.get("suspicious_reasons", [])}
                for d in history.get("devices", [])
                if d.get("is_suspicious")
            ]
        except Exception as e:
            logger.error(f"Suspicious device detection failed: {e}")
            return []

    # ── Device info builder ───────────────────────────────────────────────────

    def _build_device_info(self, auth: Authorization) -> Dict[str, Any]:
        """Convert a Telegram Authorization object into an enriched dict."""
        platform   = auth.platform or ""
        model      = auth.device_model or ""
        sys_ver    = auth.system_version or ""
        app_name   = auth.app_name or ""
        app_ver    = auth.app_version or ""

        os_info     = self._extract_os_info(platform, sys_ver, model)
        suspicious, reasons = self._assess_suspicion(auth, os_info)

        return {
            # Telegram fields
            "hash":             auth.hash,
            "device_model":     model,
            "platform":         platform,
            "system_version":   sys_ver,
            "app_name":         app_name,
            "app_version":      app_ver,
            "api_id":           auth.api_id,
            "date_created":     auth.date_created,
            "date_active":      auth.date_active,
            "ip":               auth.ip,
            "country":          auth.country,
            "region":           auth.region,
            "current":          auth.current,
            "official_app":     auth.official_app,
            "password_pending": auth.password_pending,
            # Enriched fields
            "os_name":          os_info["os_name"],
            "os_version":       os_info["os_version"],
            "architecture":     os_info["architecture"],
            "device_type":      os_info["device_type"],
            "is_suspicious":    suspicious,
            "suspicious_reasons": reasons,
            "scan_timestamp":   datetime.now(timezone.utc),
        }

    # ── OS extraction ─────────────────────────────────────────────────────────

    def _extract_os_info(
        self, platform: str, system_version: str, device_model: str
    ) -> Dict[str, str]:
        """Extract OS name, version, architecture, and device type."""
        pl = platform.lower()
        sv = system_version.lower()
        dm = device_model.lower()

        os_name = "Unknown"
        os_version = system_version or "Unknown"
        architecture = "ARM64"  # Default for modern Android
        device_type = self._classify_device_type(dm, pl)

        if "android" in pl or "android" in sv:
            os_name = "Android"
            if "arm64" in sv or "aarch64" in sv:
                architecture = "ARM64"
            elif "arm" in sv:
                architecture = "ARM32"
            else:
                architecture = "ARM64"  # Safe default for Android

        elif "ios" in pl or "iphone" in dm or "ipad" in dm:
            os_name = "iOS"
            architecture = "ARM64"

        elif "macos" in pl or "mac os" in pl:
            os_name = "macOS"
            architecture = "x86_64" if "intel" in sv else "ARM64"

        elif "windows" in pl:
            os_name = "Windows"
            architecture = "x86_64"

        elif "linux" in pl:
            os_name = "Linux"
            architecture = "x86_64"

        elif "web" in pl or "browser" in pl:
            os_name = "Web"
            architecture = "N/A"

        return {
            "os_name":     os_name,
            "os_version":  os_version,
            "architecture": architecture,
            "device_type": device_type,
        }

    def _classify_device_type(self, model_lower: str, platform_lower: str) -> str:
        """Classify device as Mobile / Tablet / Foldable / Desktop / Bot / Web."""
        fold_keywords = ("fold", "flip", "razr", "find n", "mix fold", "wing")
        tablet_keywords = ("tab ", "tablet", "pad ", "ipad")
        desktop_keywords = ("windows", "macos", "mac os", "linux", "desktop")
        web_keywords = ("web", "browser", "chrome", "firefox", "safari")
        bot_keywords = ("bot", "server", "api", "script")
        mobile_brands = (
            "samsung", "pixel", "oneplus", "xiaomi", "redmi", "poco",
            "oppo", "vivo", "realme", "huawei", "honor", "nothing",
            "motorola", "sony", "asus", "fairphone", "nokia", "tcl",
            "iphone", "android",
        )

        if any(k in model_lower for k in fold_keywords):
            return "Foldable"
        if any(k in model_lower for k in tablet_keywords):
            return "Tablet"
        if any(k in platform_lower for k in desktop_keywords):
            return "Desktop"
        if any(k in platform_lower for k in web_keywords):
            return "Web"
        if any(k in platform_lower for k in bot_keywords):
            return "Bot/Script"
        if any(k in model_lower for k in mobile_brands):
            return "Mobile"
        if "android" in platform_lower:
            return "Mobile"
        if "ios" in platform_lower:
            return "Mobile"
        return "Unknown"

    # ── Suspicion assessment ──────────────────────────────────────────────────

    def _assess_suspicion(
        self, auth: Authorization, os_info: Dict[str, str]
    ) -> tuple[bool, List[str]]:
        """
        Determine whether a session looks suspicious.
        Returns (is_suspicious: bool, reasons: List[str]).
        """
        reasons: List[str] = []

        # 1. Unofficial app (api_id not in known-official set)
        if auth.api_id and auth.api_id not in _OFFICIAL_API_IDS:
            if not auth.official_app:
                reasons.append(f"Unofficial client (API ID: {auth.api_id})")

        # 2. Telegram itself marks it as unofficial
        if not auth.official_app and not reasons:
            reasons.append("Marked unofficial by Telegram")

        # 3. Bot / script-like app name
        app_lower = (auth.app_name or "").lower()
        if any(s in app_lower for s in _SUSPICIOUS_APP_NAMES):
            reasons.append(f"Suspicious app name: {auth.app_name}")

        # 4. 2FA password still pending (logged in but didn't complete 2FA)
        if auth.password_pending:
            reasons.append("2FA verification incomplete")

        # 5. Unknown or empty device model
        model = (auth.device_model or "").strip()
        if not model or model.lower() in ("unknown", "none", ""):
            reasons.append("Unknown device model")

        # 6. Desktop session on an account normally used from mobile
        #    (only flag if the account has no other desktop sessions —
        #     handled at a higher level; here just note device type)
        if os_info["device_type"] == "Bot/Script":
            reasons.append("Automated/bot client detected")

        # 7. Empty country — unusual for real clients
        if not auth.country:
            reasons.append("No country information")

        return bool(reasons), reasons

    # ── Persistence ───────────────────────────────────────────────────────────

    async def _store_snapshot(self, user_id: int, devices: List[Dict]) -> None:
        """Persist device snapshot to MongoDB for dashboard display."""
        try:
            from teleguard.core.mongo_database import mongodb

            # Serialize datetime objects before storing
            serialized = []
            for d in devices:
                row = dict(d)
                for k in ("date_created", "date_active", "scan_timestamp"):
                    v = row.get(k)
                    if hasattr(v, "isoformat"):
                        row[k] = v.isoformat()
                serialized.append(row)

            suspicious_count = sum(1 for d in serialized if d.get("is_suspicious"))

            await mongodb.db.device_logs.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "user_id":         user_id,
                        "devices":         serialized,
                        "total_devices":   len(serialized),
                        "suspicious_count": suspicious_count,
                        "last_updated":    datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"Could not persist device snapshot for {user_id}: {e}")
