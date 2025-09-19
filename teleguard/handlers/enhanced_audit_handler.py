"""Enhanced Audit Log Handler

Provides comprehensive audit log viewing with detailed action tracking.
Shows all bot actions transparently to users.
"""

import logging
from datetime import datetime, timedelta

from telethon import Button

from ..core.comprehensive_audit import ComprehensiveAudit
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class EnhancedAuditHandler:
    """Handles enhanced audit log viewing and management"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.audit = ComprehensiveAudit()

    async def show_comprehensive_audit_log(
        self, bot, user_id: int, account_id: int, message_id: int, hours: int = 24
    ):
        """Show comprehensive audit log for account"""
        try:
            from bson import ObjectId
            
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                await bot.send_message(user_id, "❌ Account not found")
                return

                # Get audit events
                events = await self.audit.get_account_audit_log(
                    user_id, account_id, hours, 50
                )

                if not events:
                    text = (
                        f"📋 **Comprehensive Audit Log: {account['name']}**\\n\\n"
                        f"No activities recorded in the last {hours} hours.\\n\\n"
                        f"Activities are logged when simulation is enabled and running."
                    )
                else:
                    text = f"📋 **Comprehensive Audit Log: {account['name']}** (Last {hours}h)\\n\\n"

                    # Group events by type for summary
                    summary = await self.audit.get_activity_summary(
                        user_id, account_id, hours
                    )

                    if summary:
                        text += "**📊 Activity Summary:**\\n"
                        if summary.get("reactions", 0) > 0:
                            text += f"👍 Reactions: {summary['reactions']}\\n"
                        if summary.get("channels_joined", 0) > 0:
                            text += (
                                f"➕ Channels Joined: {summary['channels_joined']}\\n"
                            )
                        if summary.get("channels_left", 0) > 0:
                            text += f"➖ Channels Left: {summary['channels_left']}\\n"
                        if summary.get("messages_sent", 0) > 0:
                            text += f"💬 Messages Sent: {summary['messages_sent']}\\n"
                        if summary.get("comments_posted", 0) > 0:
                            text += (
                                f"💭 Comments Posted: {summary['comments_posted']}\\n"
                            )
                        if summary.get("polls_voted", 0) > 0:
                            text += f"🗳️ Polls Voted: {summary['polls_voted']}\\n"
                        if summary.get("profiles_viewed", 0) > 0:
                            text += (
                                f"👤 Profiles Viewed: {summary['profiles_viewed']}\\n"
                            )
                        if summary.get("entities_viewed", 0) > 0:
                            text += (
                                f"👀 Entities Viewed: {summary['entities_viewed']}\\n"
                            )
                        if summary.get("sessions", 0) > 0:
                            text += f"🎬 Sessions: {summary['sessions']}\\n"

                        text += f"\\n**📝 Recent Activities:**\\n"

                    # Show recent activities
                    for event in events[:15]:  # Show last 15 events
                        timestamp = event.get("timestamp", "")
                        event_type = event.get("event_type", "unknown")
                        details = event.get("details", {})

                        # Parse timestamp
                        try:
                            dt = datetime.fromisoformat(
                                timestamp.replace("Z", "+00:00")
                            )
                            time_str = dt.strftime("%H:%M:%S")
                        except Exception as e:
                            logger.warning(
                                f"Could not parse timestamp '{timestamp}': {e}"
                            )
                            time_str = "??:??:??"

                        # Format event for display
                        icon, action_text = self._format_event_display(
                            event_type, details
                        )
                        text += f"{icon} {time_str}: {action_text}\\n"

                    if len(events) > 15:
                        text += f"\\n... and {len(events) - 15} more activities"

                buttons = [
                    [
                        Button.inline(
                            "🔄 Refresh", f"audit:refresh:{account_id}:{hours}"
                        ),
                        Button.inline("⏰ 6h", f"audit:refresh:{account_id}:6"),
                    ],
                    [
                        Button.inline("📊 Summary", f"audit:summary:{account_id}"),
                        Button.inline("📈 Stats", f"audit:stats:{account_id}"),
                    ],
                    [Button.inline("🔙 Back", f"simulate:status:{account_id}")],
                ]

                await bot.edit_message(user_id, message_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Show comprehensive audit log error: {e}")
            text = "❌ Error loading comprehensive audit log"
            buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
            await bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def show_activity_summary(
        self, bot, user_id: int, account_id: int, message_id: int
    ):
        """Show detailed activity summary"""
        try:
            from bson import ObjectId
            
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                await bot.send_message(user_id, "❌ Account not found")
                return

                # Get summaries for different time periods
                summary_24h = await self.audit.get_activity_summary(
                    user_id, account_id, 24
                )
                summary_7d = await self.audit.get_activity_summary(
                    user_id, account_id, 168
                )  # 7 days

                text = f"📊 **Activity Summary: {account['name']}**\\n\\n"

                # 24 hour summary
                text += "**📅 Last 24 Hours:**\\n"
                if summary_24h.get("total_events", 0) > 0:
                    text += f"• Total Actions: {summary_24h['total_events']}\\n"
                    text += f"• Reactions: {summary_24h.get('reactions', 0)}\\n"
                    text += (
                        f"• Channels Joined: {summary_24h.get('channels_joined', 0)}\\n"
                    )
                    text += f"• Channels Left: {summary_24h.get('channels_left', 0)}\\n"
                    text += f"• Messages Sent: {summary_24h.get('messages_sent', 0)}\\n"
                    text += (
                        f"• Comments Posted: {summary_24h.get('comments_posted', 0)}\\n"
                    )
                    text += f"• Polls Voted: {summary_24h.get('polls_voted', 0)}\\n"
                    text += (
                        f"• Profiles Viewed: {summary_24h.get('profiles_viewed', 0)}\\n"
                    )
                    text += (
                        f"• Entities Viewed: {summary_24h.get('entities_viewed', 0)}\\n"
                    )
                    text += f"• Sessions: {summary_24h.get('sessions', 0)}\\n"
                else:
                    text += "No activities in the last 24 hours\\n"

                text += "\\n**📊 Last 7 Days:**\\n"
                if summary_7d.get("total_events", 0) > 0:
                    text += f"• Total Actions: {summary_7d['total_events']}\\n"
                    text += f"• Average per day: {summary_7d['total_events'] // 7}\\n"
                    text += f"• Most active: Reactions ({summary_7d.get('reactions', 0)})\\n"

                    if summary_24h.get("last_activity"):
                        try:
                            dt = datetime.fromisoformat(
                                summary_24h["last_activity"].replace("Z", "+00:00")
                            )
                            last_activity = dt.strftime("%Y-%m-%d %H:%M:%S")
                            text += f"• Last Activity: {last_activity}\\n"
                        except Exception as e:
                            logger.warning(
                                f"Could not parse last_activity timestamp '{summary_24h.get('last_activity')}': {e}"
                            )
                else:
                    text += "No activities in the last 7 days\\n"

                buttons = [
                    [
                        Button.inline("📋 Full Log", f"audit:refresh:{account_id}:24"),
                        Button.inline("📈 Stats", f"audit:stats:{account_id}"),
                    ],
                    [Button.inline("🔙 Back", f"simulate:status:{account_id}")],
                ]

                await bot.edit_message(user_id, message_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Show activity summary error: {e}")
            text = "❌ Error loading activity summary"
            buttons = [[Button.inline("🔙 Back", f"simulate:status:{account_id}")]]
            await bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def show_activity_stats(
        self, bot, user_id: int, account_id: int, message_id: int
    ):
        """Show detailed activity statistics"""
        try:
            from bson import ObjectId
            
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                await bot.send_message(user_id, "❌ Account not found")
                return

                # Get events for analysis
                events_24h = await self.audit.get_account_audit_log(
                    user_id, account_id, 24, 1000
                )
                events_7d = await self.audit.get_account_audit_log(
                    user_id, account_id, 168, 1000
                )

                text = f"📈 **Activity Statistics: {account['name']}**\\n\\n"

                if events_24h:
                    # Analyze activity patterns
                    hourly_activity = {}
                    event_types = {}

                    for event in events_24h:
                        try:
                            dt = datetime.fromisoformat(
                                event["timestamp"].replace("Z", "+00:00")
                            )
                            hour = dt.hour
                            hourly_activity[hour] = hourly_activity.get(hour, 0) + 1

                            event_type = event["event_type"]
                            event_types[event_type] = event_types.get(event_type, 0) + 1
                        except Exception as e:
                            logger.warning(f"Could not parse event timestamp: {e}")
                            continue

                    # Most active hours
                    if hourly_activity:
                        most_active_hour = max(hourly_activity, key=hourly_activity.get)
                        text += f"**⏰ Activity Patterns (24h):**\\n"
                        text += f"• Most Active Hour: {most_active_hour:02d}:00 ({hourly_activity[most_active_hour]} actions)\\n"
                        text += f"• Total Active Hours: {len(hourly_activity)}\\n"

                    # Most common activities
                    if event_types:
                        text += f"\\n**🎯 Most Common Activities:**\\n"
                        sorted_types = sorted(
                            event_types.items(), key=lambda x: x[1], reverse=True
                        )
                        for event_type, count in sorted_types[:5]:
                            icon, _ = self._format_event_display(event_type, {})
                            readable_name = (
                                event_type.replace("sim_", "").replace("_", " ").title()
                            )
                            text += f"{icon} {readable_name}: {count}\\n"

                    # Weekly comparison
                    if events_7d:
                        text += f"\\n**📊 Weekly Overview:**\\n"
                        text += f"• Total Events (7d): {len(events_7d)}\\n"
                        text += f"• Daily Average: {len(events_7d) // 7}\\n"
                        text += f"• Today's Activity: {len(events_24h)} events\\n"

                        # Calculate activity trend
                        if len(events_7d) > len(events_24h):
                            trend = "📈 Increasing"
                        elif len(events_7d) < len(events_24h) * 7:
                            trend = "📉 Decreasing"
                        else:
                            trend = "📊 Stable"
                        text += f"• Trend: {trend}\\n"
                else:
                    text += "No activity data available for analysis.\\n"

                buttons = [
                    [
                        Button.inline("📋 Full Log", f"audit:refresh:{account_id}:24"),
                        Button.inline("📊 Summary", f"audit:summary:{account_id}"),
                    ],
                    [Button.inline("🔙 Back", f"simulate:status:{account_id}")],
                ]

                await bot.edit_message(user_id, message_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Show activity stats error: {e}")
            text = "❌ Error loading activity statistics"
            buttons = [[Button.inline("🔙 Back", f"simulate:status:{account_id}")]]
            await bot.edit_message(user_id, message_id, text, buttons=buttons)

    def _format_event_display(self, event_type: str, details: dict) -> tuple[str, str]:
        """Format event for display with icon and readable text"""
        if event_type == "sim_reaction":
            emoji = details.get("emoji", "👍")
            channel = details.get("channel", "Unknown")
            return "👍", f"Reacted {emoji} in {channel}"

        elif event_type == "sim_join_channel":
            channel = details.get("channel", "Unknown")
            return "➕", f"Joined channel {channel}"

        elif event_type == "sim_leave_channel":
            channel = details.get("channel", "Unknown")
            return "➖", f"Left channel {channel}"

        elif event_type == "sim_message_sent":
            chat = details.get("chat", "Unknown")
            preview = details.get("message_preview", "")[:20]
            return "💬", f"Sent message in {chat}: {preview}..."

        elif event_type == "sim_comment_posted":
            channel = details.get("channel", "Unknown")
            preview = details.get("comment_preview", "")[:20]
            return "💭", f"Commented in {channel}: {preview}..."

        elif event_type == "sim_poll_voted":
            channel = details.get("channel", "Unknown")
            option = details.get("selected_option", "Unknown")
            return "🗳️", f"Voted '{option}' in {channel}"

        elif event_type == "sim_profile_viewed":
            profile = details.get("profile", "Unknown")
            duration = details.get("duration_seconds", 0)
            return "👤", f"Viewed profile {profile} ({duration}s)"

        elif event_type == "sim_entity_viewed":
            entity = details.get("entity", "Unknown")
            messages = details.get("messages_read", 0)
            return "👀", f"Viewed {entity} ({messages} messages)"

        elif event_type == "sim_session_start":
            actions = details.get("actions_planned", 0)
            return "🎬", f"Started session ({actions} actions planned)"

        elif event_type == "sim_session_end":
            actions = details.get("actions_completed", 0)
            return "🎬", f"Ended session ({actions} actions completed)"

        elif event_type == "automation_triggered":
            action = details.get("action", "Unknown")
            return "⚙️", f"Automation: {action}"

        else:
            # Generic formatting
            readable_name = event_type.replace("sim_", "").replace("_", " ").title()
            return "ℹ️", readable_name
