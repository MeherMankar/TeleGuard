"""Activity logging and audit trail"""
import logging
from datetime import datetime
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class ActivityLogger:
    @staticmethod
    async def log_action(user_id: int, action: str, details: dict = None):
        """Log user action to audit trail"""
        try:
            await mongodb.db.activity_logs.insert_one({
                "user_id": user_id,
                "action": action,
                "details": details or {},
                "timestamp": datetime.utcnow(),
                "ip": details.get("ip") if details else None
            })
        except Exception as e:
            logger.error(f"Failed to log activity: {e}")
    
    @staticmethod
    async def get_user_activity(user_id: int, limit: int = 100):
        """Get user activity history"""
        try:
            activities = await mongodb.db.activity_logs.find(
                {"user_id": user_id}
            ).sort("timestamp", -1).limit(limit).to_list(length=limit)
            return activities
        except Exception as e:
            logger.error(f"Failed to get activity: {e}")
            return []
    
    @staticmethod
    async def log_account_action(user_id: int, account_name: str, action: str):
        """Log account-specific action"""
        await ActivityLogger.log_action(user_id, action, {
            "account": account_name,
            "action_type": "account_management"
        })
    
    @staticmethod
    async def log_security_action(user_id: int, action: str, severity: str = "info"):
        """Log security-related action"""
        await ActivityLogger.log_action(user_id, action, {
            "action_type": "security",
            "severity": severity
        })


activity_logger = ActivityLogger()
