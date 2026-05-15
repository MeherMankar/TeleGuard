"""
Audit Handler for TeleGuard
Provides audit logging and activity reporting for the Human-like Activity Simulator.
Developed by:
- @Meher_Mankar
- @Gutkesh
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from telethon import Button

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class AuditHandler:
    """Handles audit log display and activity reporting for simulation"""

    COLLECTION = "simulation_audit"

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot

    # ------------------------------------------------------------------
    # Public API used by SimulationHandlers
    # ------------------------------------------------------------------

    async def show_comprehensive_audit_log(
        self,
        bot,
        user_id: int,
        account_id,
        message_id: int,
        hours: int = 24,
    ):
        """Edit *message_id* with the last *hours* of audit entries for *account_id*."""
        try:
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
            entries = await self._fetch_entries(
                user_id, str(account_id), since=since, limit=20
            )

            if not entries:
                text = (
                    f"📋 **Audit Log** (last {hours}h)\n\n"
                    "No activity recorded in this period."
                )
            else:
                text = f"📋 **Audit Log** (last {hours}h) — {len(entries)} entries\n\n"
                for e in entries:
                    ts = e.get("timestamp", "")
                    if isinstance(ts, datetime):
                        ts = ts.strftime("%H:%M:%S")
                    action = e.get("action", "unknown")
                    detail = e.get("detail", "")
                    status = "✅" if e.get("success", True) else "❌"
                    text += f"{status} `{ts}` **{action}**"
                    if detail:
                        text += f" — {detail}"
                    text += "\n"

            buttons = [
                [
                    Button.inline("🔄 Refresh (24h)", f"audit:refresh:{account_id}:24"),
                    Button.inline("📅 Last 48h", f"audit:refresh:{account_id}:48"),
                ],
                [
                    Button.inline("📊 Summary", f"audit:summary:{account_id}"),
                    Button.inline("📈 Stats", f"audit:stats:{account_id}"),
                ],
            ]

            await bot.edit_message(user_id, message_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"show_comprehensive_audit_log error: {e}")
            try:
                await bot.edit_message(
                    user_id, message_id, f"❌ Error loading audit log: {e}"
                )
            except Exception:
                pass

    async def show_activity_summary(
        self,
        bot,
        user_id: int,
        account_id,
        message_id: int,
    ):
        """Edit *message_id* with a 24-hour activity summary for *account_id*."""
        try:
            since = datetime.now(timezone.utc) - timedelta(hours=24)
            entries = await self._fetch_entries(user_id, str(account_id), since=since)

            total = len(entries)
            success = sum(1 for e in entries if e.get("success", True))
            failed = total - success

            # Count by action type
            action_counts: dict = {}
            for e in entries:
                action = e.get("action", "unknown")
                action_counts[action] = action_counts.get(action, 0) + 1

            text = "📊 **Activity Summary (last 24h)**\n\n"
            text += f"• Total actions: **{total}**\n"
            text += f"• Successful: **{success}**\n"
            text += f"• Failed: **{failed}**\n\n"

            if action_counts:
                text += "**Breakdown:**\n"
                for action, count in sorted(
                    action_counts.items(), key=lambda x: -x[1]
                ):
                    text += f"  • {action}: {count}\n"

            buttons = [
                [Button.inline("📋 Full Log", f"audit:refresh:{account_id}:24")],
                [Button.inline("📈 Statistics", f"audit:stats:{account_id}")],
            ]

            await bot.edit_message(user_id, message_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"show_activity_summary error: {e}")
            try:
                await bot.edit_message(
                    user_id, message_id, f"❌ Error loading summary: {e}"
                )
            except Exception:
                pass

    async def show_activity_stats(
        self,
        bot,
        user_id: int,
        account_id,
        message_id: int,
    ):
        """Edit *message_id* with cumulative statistics for *account_id*."""
        try:
            entries = await self._fetch_entries(user_id, str(account_id), limit=500)

            total = len(entries)
            success = sum(1 for e in entries if e.get("success", True))

            # Earliest entry
            timestamps = [
                e["timestamp"]
                for e in entries
                if isinstance(e.get("timestamp"), datetime)
            ]
            if timestamps:
                first = min(timestamps).strftime("%Y-%m-%d %H:%M UTC")
                last = max(timestamps).strftime("%Y-%m-%d %H:%M UTC")
            else:
                first = last = "N/A"

            text = "📈 **Simulation Statistics**\n\n"
            text += f"• Total logged actions: **{total}**\n"
            text += f"• Success rate: **{(success / total * 100):.1f}%**\n" if total else "• No data yet\n"
            text += f"• First activity: {first}\n"
            text += f"• Last activity: {last}\n"

            buttons = [
                [Button.inline("📋 Full Log", f"audit:refresh:{account_id}:24")],
                [Button.inline("📊 Summary", f"audit:summary:{account_id}")],
            ]

            await bot.edit_message(user_id, message_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"show_activity_stats error: {e}")
            try:
                await bot.edit_message(
                    user_id, message_id, f"❌ Error loading stats: {e}"
                )
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Logging helper (called by ActivitySimulator or other workers)
    # ------------------------------------------------------------------

    async def log_action(
        self,
        user_id: int,
        account_id: str,
        action: str,
        detail: str = "",
        success: bool = True,
    ):
        """Persist a single audit entry to MongoDB."""
        try:
            doc = {
                "user_id": user_id,
                "account_id": str(account_id),
                "action": action,
                "detail": detail,
                "success": success,
                "timestamp": datetime.now(timezone.utc),
            }
            await mongodb.db[self.COLLECTION].insert_one(doc)
        except Exception as e:
            logger.warning(f"audit log_action failed: {e}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_entries(
        self,
        user_id: int,
        account_id: str,
        since: Optional[datetime] = None,
        limit: int = 100,
    ):
        """Fetch audit entries from MongoDB."""
        try:
            query: dict = {"user_id": user_id, "account_id": str(account_id)}
            if since:
                query["timestamp"] = {"$gte": since}
            cursor = (
                mongodb.db[self.COLLECTION]
                .find(query)
                .sort("timestamp", -1)
                .limit(limit)
            )
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.warning(f"_fetch_entries error: {e}")
            return []
