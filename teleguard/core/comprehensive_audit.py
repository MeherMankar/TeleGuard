"""Comprehensive Audit System for TeleGuard

Tracks all bot actions including:
- Active sim activities (reactions, joins, messages, comments, leaves)
- Account management actions
- Security events
- User interactions

Provides complete transparency for users.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .mongo_database import mongodb


class AuditEventType(Enum):
    # Active Sim Events
    SIM_REACTION = "sim_reaction"
    SIM_JOIN_CHANNEL = "sim_join_channel"
    SIM_LEAVE_CHANNEL = "sim_leave_channel"
    SIM_MESSAGE_SENT = "sim_message_sent"
    SIM_COMMENT_POSTED = "sim_comment_posted"
    SIM_POLL_VOTED = "sim_poll_voted"
    SIM_PROFILE_VIEWED = "sim_profile_viewed"
    SIM_ENTITY_VIEWED = "sim_entity_viewed"
    SIM_SESSION_START = "sim_session_start"
    SIM_SESSION_END = "sim_session_end"

    # Account Management
    ACCOUNT_ADDED = "account_added"
    ACCOUNT_REMOVED = "account_removed"
    ACCOUNT_LOGIN = "account_login"
    ACCOUNT_LOGOUT = "account_logout"

    # Security Events
    OTP_DESTROYED = "otp_destroyed"
    LOGIN_ATTEMPT_BLOCKED = "login_attempt_blocked"
    SESSION_TERMINATED = "session_terminated"

    # Bot Actions
    AUTOMATION_TRIGGERED = "automation_triggered"
    ONLINE_STATUS_UPDATED = "online_status_updated"
    PROFILE_UPDATED = "profile_updated"


class ComprehensiveAudit:
    """Enhanced audit system for complete action tracking"""

    def __init__(self):
        self.retention_days = 30  # Keep audit logs for 30 days
        self.max_events_per_account = 1000  # Limit events per account

    async def log_event(
        self,
        account_id: str,
        user_id: int,
        event_type: AuditEventType,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
    ):
        """Log a comprehensive audit event"""
        try:
            from bson import ObjectId

            audit_event = {
                "account_id": ObjectId(account_id),
                "user_id": user_id,
                "event_type": event_type.value,
                "event_data": json.dumps(details),
                "ip_address": ip_address,
                "timestamp": datetime.now(timezone.utc),
            }
            await mongodb.db.audit_events.insert_one(audit_event)

            # Also update account's activity log for quick access
            await self._update_account_activity_log(account_id, event_type, details)

        except Exception as e:
            import logging

            logging.getLogger(__name__).error(f"Failed to log audit event: {e}")

    async def log_sim_reaction(
        self,
        account_id: str,
        user_id: int,
        channel_name: str,
        emoji: str,
        message_id: int,
    ):
        """Log active sim reaction event"""
        details = {
            "action": "reaction",
            "channel": channel_name,
            "emoji": emoji,
            "message_id": message_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.log_event(account_id, user_id, AuditEventType.SIM_REACTION, details)

    async def log_sim_join_channel(
        self, account_id: str, user_id: int, channel_name: str, channel_id: int
    ):
        """Log active sim channel join"""
        details = {
            "action": "join_channel",
            "channel": channel_name,
            "channel_id": channel_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.log_event(
            account_id, user_id, AuditEventType.SIM_JOIN_CHANNEL, details
        )

    async def log_sim_leave_channel(
        self, account_id: str, user_id: int, channel_name: str, channel_id: int
    ):
        """Log active sim channel leave"""
        details = {
            "action": "leave_channel",
            "channel": channel_name,
            "channel_id": channel_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.log_event(
            account_id, user_id, AuditEventType.SIM_LEAVE_CHANNEL, details
        )

    async def log_sim_message_sent(
        self, account_id: str, user_id: int, chat_name: str, message_preview: str
    ):
        """Log active sim message sent"""
        details = {
            "action": "message_sent",
            "chat": chat_name,
            "message_preview": message_preview[:100],  # First 100 chars
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.log_event(
            account_id, user_id, AuditEventType.SIM_MESSAGE_SENT, details
        )

    async def log_sim_comment_posted(
        self, account_id: str, user_id: int, channel_name: str, comment_preview: str
    ):
        """Log active sim comment posted"""
        details = {
            "action": "comment_posted",
            "channel": channel_name,
            "comment_preview": comment_preview[:100],
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.log_event(
            account_id, user_id, AuditEventType.SIM_COMMENT_POSTED, details
        )

    async def log_sim_poll_voted(
        self,
        account_id: str,
        user_id: int,
        channel_name: str,
        poll_question: str,
        selected_option: str,
    ):
        """Log active sim poll vote"""
        details = {
            "action": "poll_voted",
            "channel": channel_name,
            "poll_question": poll_question[:100],
            "selected_option": selected_option,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.log_event(
            account_id, user_id, AuditEventType.SIM_POLL_VOTED, details
        )

    async def log_sim_profile_viewed(
        self, account_id: str, user_id: int, profile_name: str, view_duration: float
    ):
        """Log active sim profile view"""
        details = {
            "action": "profile_viewed",
            "profile": profile_name,
            "duration_seconds": round(view_duration, 1),
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.log_event(
            account_id, user_id, AuditEventType.SIM_PROFILE_VIEWED, details
        )

    async def log_sim_entity_viewed(
        self,
        account_id: str,
        user_id: int,
        entity_name: str,
        messages_read: int,
        duration: float,
    ):
        """Log active sim entity view"""
        details = {
            "action": "entity_viewed",
            "entity": entity_name,
            "messages_read": messages_read,
            "duration_seconds": round(duration, 1),
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.log_event(
            account_id, user_id, AuditEventType.SIM_ENTITY_VIEWED, details
        )

    async def log_sim_session(
        self, account_id: str, user_id: int, session_type: str, actions_count: int
    ):
        """Log active sim session start/end"""
        event_type = (
            AuditEventType.SIM_SESSION_START
            if session_type == "start"
            else AuditEventType.SIM_SESSION_END
        )
        details = {
            "action": f"session_{session_type}",
            (
                "actions_planned" if session_type == "start" else "actions_completed"
            ): actions_count,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.log_event(account_id, user_id, event_type, details)

    async def get_account_audit_log(
        self, user_id: int, account_id: str, hours: int = 24, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit log for specific account"""
        try:
            from bson import ObjectId

            cutoff_time = datetime.utcnow() - timedelta(hours=hours)

            cursor = (
                mongodb.db.audit_events.find(
                    {
                        "user_id": user_id,
                        "account_id": ObjectId(account_id),
                        "timestamp": {"$gte": cutoff_time},
                    }
                )
                .sort("timestamp", -1)
                .limit(limit)
            )

            events = []
            async for event in cursor:
                try:
                    event_data = json.loads(event["event_data"])
                    events.append(
                        {
                            "id": str(event["_id"]),
                            "event_type": event["event_type"],
                            "timestamp": event["timestamp"].isoformat(),
                            "details": event_data,
                        }
                    )
                except json.JSONDecodeError:
                    continue
            return events

        except Exception as e:
            import logging

            logging.getLogger(__name__).error(f"Failed to get audit log: {e}")
            return []

    async def get_activity_summary(
        self, user_id: int, account_id: str, hours: int = 24
    ) -> Dict[str, Any]:
        """Get activity summary for account"""
        try:
            events = await self.get_account_audit_log(user_id, account_id, hours)

            summary = {
                "total_events": len(events),
                "reactions": 0,
                "channels_joined": 0,
                "channels_left": 0,
                "messages_sent": 0,
                "comments_posted": 0,
                "polls_voted": 0,
                "profiles_viewed": 0,
                "entities_viewed": 0,
                "sessions": 0,
                "last_activity": None,
            }

            for event in events:
                event_type = event["event_type"]

                if event_type == "sim_reaction":
                    summary["reactions"] += 1
                elif event_type == "sim_join_channel":
                    summary["channels_joined"] += 1
                elif event_type == "sim_leave_channel":
                    summary["channels_left"] += 1
                elif event_type == "sim_message_sent":
                    summary["messages_sent"] += 1
                elif event_type == "sim_comment_posted":
                    summary["comments_posted"] += 1
                elif event_type == "sim_poll_voted":
                    summary["polls_voted"] += 1
                elif event_type == "sim_profile_viewed":
                    summary["profiles_viewed"] += 1
                elif event_type == "sim_entity_viewed":
                    summary["entities_viewed"] += 1
                elif event_type == "sim_session_start":
                    summary["sessions"] += 1

                if not summary["last_activity"]:
                    summary["last_activity"] = event["timestamp"]

            return summary

        except Exception as e:
            import logging

            logging.getLogger(__name__).error(f"Failed to get activity summary: {e}")
            return {}

    async def _update_account_activity_log(
        self, account_id: str, event_type: AuditEventType, details: Dict[str, Any]
    ):
        """Update account's quick access activity log"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id)})

            if account:
                try:
                    activity_log = json.loads(account.get("activity_audit_log") or "[]")
                except (json.JSONDecodeError, AttributeError):
                    activity_log = []

                entry = {
                    "timestamp": int(time.time()),
                    "event_type": event_type.value,
                    "details": details,
                    "time_str": datetime.now().strftime("%H:%M:%S"),
                }
                activity_log.append(entry)

                if len(activity_log) > 50:
                    activity_log = activity_log[-50:]

                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {"activity_audit_log": json.dumps(activity_log)}},
                )

        except Exception as e:
            import logging

            logging.getLogger(__name__).error(
                f"Failed to update account activity log: {e}"
            )

    async def cleanup_old_events(self):
        """Clean up old audit events based on retention policy"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=self.retention_days)
            await mongodb.db.audit_events.delete_many(
                {"timestamp": {"$lt": cutoff_time}}
            )

        except Exception as e:
            import logging

            logging.getLogger(__name__).error(f"Failed to cleanup old events: {e}")
