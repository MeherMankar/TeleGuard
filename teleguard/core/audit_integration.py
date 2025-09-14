"""Audit System Integration

Integrates comprehensive audit logging with existing bot components.
Ensures all activity simulator actions are properly logged and auditable.
"""

import asyncio
import logging

from .comprehensive_audit import AuditEventType, ComprehensiveAudit

logger = logging.getLogger(__name__)


class AuditIntegration:
    """Integrates audit system with bot components"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.audit = ComprehensiveAudit()

    async def setup_audit_integration(self):
        """Setup audit integration with existing components"""
        try:
            # Schedule periodic cleanup
            asyncio.create_task(self._periodic_cleanup())
            logger.info("Comprehensive audit system integrated successfully")

        except Exception as e:
            logger.error(f"Failed to setup audit integration: {e}")

    async def log_account_action(
        self, user_id: int, account_id: int, action: str, details: dict
    ):
        """Log general account action"""
        try:
            # Map action to audit event type
            event_type_map = {
                "account_added": AuditEventType.ACCOUNT_ADDED,
                "account_removed": AuditEventType.ACCOUNT_REMOVED,
                "account_login": AuditEventType.ACCOUNT_LOGIN,
                "account_logout": AuditEventType.ACCOUNT_LOGOUT,
                "otp_destroyed": AuditEventType.OTP_DESTROYED,
                "login_blocked": AuditEventType.LOGIN_ATTEMPT_BLOCKED,
                "session_terminated": AuditEventType.SESSION_TERMINATED,
                "automation_triggered": AuditEventType.AUTOMATION_TRIGGERED,
                "online_updated": AuditEventType.ONLINE_STATUS_UPDATED,
                "profile_updated": AuditEventType.PROFILE_UPDATED,
            }

            event_type = event_type_map.get(action, AuditEventType.AUTOMATION_TRIGGERED)
            await self.audit.log_event(account_id, user_id, event_type, details)

        except Exception as e:
            logger.error(f"Failed to log account action: {e}")

    async def get_account_activity_summary(
        self, user_id: int, account_id: int, hours: int = 24
    ) -> dict:
        """Get activity summary for account"""
        return await self.audit.get_activity_summary(user_id, account_id, hours)

    async def get_account_audit_events(
        self, user_id: int, account_id: int, hours: int = 24, limit: int = 100
    ) -> list:
        """Get audit events for account"""
        return await self.audit.get_account_audit_log(user_id, account_id, hours, limit)

    async def _periodic_cleanup(self):
        """Periodic cleanup of old audit events"""
        while True:
            try:
                await asyncio.sleep(24 * 3600)  # Run daily
                await self.audit.cleanup_old_events()
                logger.info("🧹 Audit cleanup completed")
            except Exception as e:
                logger.error(f"Audit cleanup error: {e}")
                await asyncio.sleep(3600)  # Retry in 1 hour on error


# Global audit integration instance
_audit_integration = None


def get_audit_integration(bot_manager=None):
    """Get or create audit integration instance"""
    global _audit_integration
    if _audit_integration is None and bot_manager:
        _audit_integration = AuditIntegration(bot_manager)
    return _audit_integration


async def setup_comprehensive_audit(bot_manager):
    """Setup comprehensive audit system"""
    audit_integration = get_audit_integration(bot_manager)
    if audit_integration:
        await audit_integration.setup_audit_integration()
    return audit_integration
