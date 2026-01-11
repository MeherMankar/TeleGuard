"""
Session Health Monitor
Detects session issues early to prevent account logout
"""

import logging
import time
from datetime import datetime
from typing import Dict

from telethon.errors import AuthKeyError, UnauthorizedError

logger = logging.getLogger(__name__)


class SessionHealth:
    """Monitor session health and detect issues early"""

    def __init__(self):
        # {account_phone: {'status': str, 'last_check': float, 'errors': int, 'warnings': []}}
        self.health_status: Dict[str, dict] = {}
        self.check_interval = 300  # Check every 5 minutes

    async def check_session(self, client, account_phone: str) -> tuple[bool, str]:
        """Check if session is healthy"""
        try:
            # Try to get current user info
            me = await client.get_me()

            if not me:
                self._record_issue(account_phone, "critical", "Cannot get user info")
                return False, "❌ Session invalid - cannot get user info"

            # Check if client is connected
            if not client.is_connected():
                self._record_issue(account_phone, "warning", "Client disconnected")
                return False, "⚠️ Client disconnected"

            # Session is healthy
            self._record_healthy(account_phone)
            return True, "✅ Session healthy"

        except (AuthKeyError, UnauthorizedError) as e:
            self._record_issue(account_phone, "critical", f"Auth error: {str(e)}")
            return False, f"❌ Session expired: {str(e)}"

        except Exception as e:
            self._record_issue(account_phone, "warning", f"Check failed: {str(e)}")
            return False, f"⚠️ Health check failed: {str(e)}"

    def get_status(self, account_phone: str) -> dict:
        """Get health status for an account"""
        if account_phone not in self.health_status:
            return {
                "status": "unknown",
                "last_check": None,
                "errors": 0,
                "warnings": [],
            }
        return self.health_status[account_phone]

    def is_healthy(self, account_phone: str) -> bool:
        """Check if account is healthy"""
        status = self.get_status(account_phone)
        return status["status"] == "healthy" and status["errors"] < 3

    def get_all_unhealthy(self) -> list:
        """Get all unhealthy accounts"""
        unhealthy = []
        for phone, status in self.health_status.items():
            if status["status"] != "healthy" or status["errors"] >= 3:
                unhealthy.append(
                    {
                        "phone": phone,
                        "status": status["status"],
                        "errors": status["errors"],
                        "warnings": status["warnings"][-3:],  # Last 3 warnings
                    }
                )
        return unhealthy

    def _record_healthy(self, account_phone: str):
        """Record healthy status"""
        self.health_status[account_phone] = {
            "status": "healthy",
            "last_check": time.time(),
            "errors": 0,
            "warnings": [],
        }

    def _record_issue(self, account_phone: str, severity: str, message: str):
        """Record an issue"""
        if account_phone not in self.health_status:
            self.health_status[account_phone] = {
                "status": "unknown",
                "last_check": 0,
                "errors": 0,
                "warnings": [],
            }

        status = self.health_status[account_phone]
        status["last_check"] = time.time()
        status["warnings"].append(f"{datetime.now().strftime('%H:%M:%S')} - {message}")

        if severity == "critical":
            status["status"] = "critical"
            status["errors"] += 1
        elif severity == "warning":
            status["status"] = "warning"
            status["errors"] += 0.5

        # Keep only last 10 warnings
        if len(status["warnings"]) > 10:
            status["warnings"] = status["warnings"][-10:]

        logger.warning(
            f"Session health issue for {account_phone}: {severity} - {message}"
        )

    def reset_account(self, account_phone: str):
        """Reset health status for an account"""
        if account_phone in self.health_status:
            del self.health_status[account_phone]
        logger.info(f"Reset health status for {account_phone}")


# Global session health monitor
session_health = SessionHealth()
