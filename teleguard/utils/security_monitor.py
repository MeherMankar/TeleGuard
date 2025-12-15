"""Security monitoring and threat detection"""
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class SecurityMonitor:
    def __init__(self):
        self.failed_attempts = defaultdict(list)
        self.suspicious_ips = set()
        self.rate_limits = defaultdict(int)
    
    async def log_security_event(self, user_id: int, event_type: str, details: dict):
        """Log security event to database"""
        try:
            await mongodb.db.security_events.insert_one({
                "user_id": user_id,
                "event_type": event_type,
                "details": details,
                "timestamp": datetime.utcnow(),
                "severity": self._get_severity(event_type)
            })
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")
    
    async def check_failed_login(self, user_id: int, ip: str = None) -> bool:
        """Track failed login attempts"""
        now = datetime.utcnow()
        self.failed_attempts[user_id].append(now)
        
        # Remove old attempts (older than 1 hour)
        self.failed_attempts[user_id] = [
            t for t in self.failed_attempts[user_id] 
            if now - t < timedelta(hours=1)
        ]
        
        # Check if threshold exceeded
        if len(self.failed_attempts[user_id]) >= 5:
            await self.log_security_event(user_id, "multiple_failed_logins", {
                "attempts": len(self.failed_attempts[user_id]),
                "ip": ip
            })
            return True
        return False
    
    async def detect_suspicious_activity(self, user_id: int, activity: str) -> bool:
        """Detect suspicious patterns"""
        suspicious_patterns = [
            "rapid_account_creation",
            "mass_messaging",
            "unusual_login_location",
            "session_hijack_attempt"
        ]
        
        if activity in suspicious_patterns:
            await self.log_security_event(user_id, "suspicious_activity", {
                "activity": activity,
                "detected_at": datetime.utcnow().isoformat()
            })
            return True
        return False
    
    async def get_security_report(self, user_id: int) -> dict:
        """Generate security report for user"""
        events = await mongodb.db.security_events.find(
            {"user_id": user_id}
        ).sort("timestamp", -1).limit(50).to_list(length=50)
        
        return {
            "total_events": len(events),
            "recent_events": events[:10],
            "failed_logins": len([e for e in events if e["event_type"] == "multiple_failed_logins"]),
            "suspicious_activities": len([e for e in events if e["event_type"] == "suspicious_activity"])
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


security_monitor = SecurityMonitor()
