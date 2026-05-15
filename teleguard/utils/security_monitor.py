"""Security monitoring and threat detection"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from .geolocation import calculate_speed, get_ip_location, haversine_distance
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class SecurityMonitor:
    def __init__(self):
        self.failed_attempts = defaultdict(list)
        self.suspicious_ips = set()
        self.rate_limits = defaultdict(int)
        self.location_history = defaultdict(dict)  # user_id -> {device_hash: last_location_data}

    async def log_security_event(self, user_id: int, event_type: str, details: dict):
        """Log security event to database"""
        try:
            await mongodb.db.security_events.insert_one(
                {
                    "user_id": user_id,
                    "event_type": event_type,
                    "details": details,
                    "timestamp": datetime.utcnow(),
                    "severity": self._get_severity(event_type),
                }
            )
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")

    async def check_failed_login(self, user_id: int, ip: str = None) -> bool:
        """Track failed login attempts"""
        now = datetime.utcnow()
        self.failed_attempts[user_id].append(now)

        # Remove old attempts (older than 1 hour)
        self.failed_attempts[user_id] = [
            t for t in self.failed_attempts[user_id] if now - t < timedelta(hours=1)
        ]

        # Check if threshold exceeded
        if len(self.failed_attempts[user_id]) >= 5:
            await self.log_security_event(
                user_id,
                "multiple_failed_logins",
                {"attempts": len(self.failed_attempts[user_id]), "ip": ip},
            )
            return True
        return False

    async def detect_suspicious_activity(self, user_id: int, activity: str) -> bool:
        """Detect suspicious patterns"""
        suspicious_patterns = [
            "rapid_account_creation",
            "mass_messaging",
            "unusual_login_location",
            "session_hijack_attempt",
        ]

        if activity in suspicious_patterns:
            await self.log_security_event(
                user_id,
                "suspicious_activity",
                {"activity": activity, "detected_at": datetime.utcnow().isoformat()},
            )
            return True
        return False

    async def get_security_report(self, user_id: int) -> dict:
        """Generate security report for user"""
        events = (
            await mongodb.db.security_events.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(50)
            .to_list(length=50)
        )

        return {
            "total_events": len(events),
            "recent_events": events[:10],
            "failed_logins": len(
                [e for e in events if e["event_type"] == "multiple_failed_logins"]
            ),
            "suspicious_activities": len(
                [e for e in events if e["event_type"] == "suspicious_activity"]
            ),
        }

    def _get_severity(self, event_type: str) -> str:
        """Determine event severity"""
        high_severity = ["session_hijack_attempt", "unauthorized_access"]
        medium_severity = ["multiple_failed_logins", "suspicious_activity"]

        if event_type in high_severity:
            return "high"
        elif event_type in medium_severity:
            return "medium"
        return "low"

    async def check_impossible_travel(self, user_id: int, current_devices: list):
        """
        Detect sessions appearing in different locations too quickly.
        """
        try:
            # Get previous device logs for comparison
            prev_log = await mongodb.db.device_logs.find_one({"user_id": user_id})
            if not prev_log or "devices" not in prev_log:
                return

            prev_devices = {d["hash"]: d for d in prev_log["devices"]}
            
            for dev in current_devices:
                dev_hash = dev.get("hash")
                ip = dev.get("ip")
                
                if not dev_hash or not ip:
                    continue

                # Get current geolocation
                current_loc = await get_ip_location(ip)
                if not current_loc:
                    continue

                # If we have history for this specific session hash
                if dev_hash in prev_devices:
                    prev_dev = prev_devices[dev_hash]
                    prev_ip = prev_dev.get("ip")
                    prev_time = prev_dev.get("date_active") or prev_dev.get("scan_timestamp")
                    
                    if isinstance(prev_time, str):
                        prev_time = datetime.fromisoformat(prev_time.replace('Z', '+00:00'))

                    if prev_ip and prev_ip != ip:
                        prev_loc = await get_ip_location(prev_ip)
                        if prev_loc:
                            # Calculate distance and time
                            dist = haversine_distance(
                                prev_loc["lat"], prev_loc["lon"],
                                current_loc["lat"], current_loc["lon"]
                            )
                            
                            now = datetime.utcnow().replace(tzinfo=None)
                            if prev_time.tzinfo:
                                prev_time = prev_time.replace(tzinfo=None)
                                
                            time_diff = (now - prev_time).total_seconds()
                            
                            # Max speed threshold: 900 km/h (commercial jet speed)
                            if time_diff > 0:
                                speed = calculate_speed(dist, time_diff)
                                if speed > 900 and dist > 100:  # Distance check to avoid IP jitter
                                    await self.log_security_event(
                                        user_id,
                                        "impossible_travel",
                                        {
                                            "device": dev.get("device_model"),
                                            "from_ip": prev_ip,
                                            "to_ip": ip,
                                            "distance_km": round(dist, 2),
                                            "speed_kmh": round(speed, 2),
                                            "time_diff_sec": time_diff
                                        }
                                    )
                                    logger.warning(f"Impossible travel detected for user {user_id}: {speed} km/h")

        except Exception as e:
            logger.error(f"Error checking impossible travel: {e}")

    async def check_device_fingerprint(self, user_id: int, current_devices: list):
        """
        Alert if a new, unknown device model accesses the account.
        """
        try:
            # Get known devices for this user
            user_settings = await mongodb.db.user_security_settings.find_one({"user_id": user_id}) or {}
            known_devices = set(user_settings.get("known_devices", []))
            
            new_known = []
            for dev in current_devices:
                model = dev.get("device_model")
                if not model:
                    continue
                
                if model not in known_devices:
                    # Log as new device
                    await self.log_security_event(
                        user_id,
                        "new_device_detected",
                        {
                            "model": model,
                            "ip": dev.get("ip"),
                            "country": dev.get("country"),
                            "app": dev.get("app_name")
                        }
                    )
                    new_known.append(model)
            
            if new_known:
                await mongodb.db.user_security_settings.update_one(
                    {"user_id": user_id},
                    {"$addToSet": {"known_devices": {"$each": new_known}}},
                    upsert=True
                )
        except Exception as e:
            logger.error(f"Error checking device fingerprint: {e}")


security_monitor = SecurityMonitor()
