"""Protection Manager UI - Inline Menu Handlers"""

import logging
from datetime import datetime, timezone

from telethon import events, Button

from ..core.mongo_database import mongodb
from ..services.protection_storage import ProtectionStorage

logger = logging.getLogger(__name__)


def _as_utc(value):
    if not value:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class ProtectionMenu:
    """Handle UI for the advanced Protection Manager"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot

    async def send_main_menu(self, event, user_id: int, edit: bool = False):
        """Display the premium protection dashboard"""
        settings = await ProtectionStorage.get_settings(user_id)
        stats = settings.get("stats") or {}
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
            length=None
        )
        otp_enabled = sum(
            1 for account in accounts if account.get("otp_destroyer_enabled", False)
        )
        all_otp_enabled = bool(accounts) and otp_enabled == len(accounts)
        
        # Determine status indicators
        otp_status = f"Enabled for {otp_enabled}/{len(accounts)} accounts"
        session_status = "Enabled ✅" if settings.get("session_destroyer_enabled") else "Disabled ❌"
        
        now = datetime.now(timezone.utc)
        pause_until = _as_utc(settings.get("pause_until"))
        if pause_until and pause_until > now:
            remaining = (pause_until - now).total_seconds()
            status_text = f"Paused ⏳ ({int(remaining // 60)}m left)"
        else:
            status_text = "Active 🛡"

        trusted_count = len(settings.get("trusted_hashes") or [])
        
        last_threat_time = _as_utc(stats.get("last_threat"))
        if last_threat_time:
            diff = max(0, (now - last_threat_time).total_seconds())
            if diff < 60:
                last_threat = "Just now"
            elif diff < 3600:
                last_threat = f"{int(diff // 60)}m ago"
            else:
                last_threat = f"{int(diff // 3600)}h ago"
        else:
            last_threat = "None detected"

        text = (
            "🛡 **TeleGuard Protection Manager**\n\n"
            f"**Status:** {status_text}\n\n"
            f"**OTP Destroyer:**\n{otp_status}\n\n"
            f"**Session Destroyer:**\n{session_status}\n\n"
            f"👤 **Trusted Sessions:** {trusted_count} Devices\n"
            f"⚠️ **Last Threat:** {last_threat}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 _Advanced protection is monitoring your accounts 24/7._"
        )

        buttons = [
            [
                Button.inline(
                    "🔴 Disable OTP Destroyer"
                    if all_otp_enabled
                    else "🟢 Enable OTP Destroyer",
                    data="prot_otp_settings",
                ),
                Button.inline(
                    "🔴 Disable Session Destroyer"
                    if settings.get("session_destroyer_enabled")
                    else "🟢 Enable Session Destroyer",
                    data="prot_session_settings",
                ),
            ],
            [
                Button.inline("⏳ Pause Protection", data="prot_pause_menu"),
                Button.inline("🔓 Allow Next Login", data="prot_allow_next")
            ],
            [
                Button.inline("📊 Statistics", data="prot_stats"),
                Button.inline("📝 Logs", data="prot_logs")
            ],
            [
                Button.inline("🔄 Refresh", data="prot_refresh"),
                Button.inline("🔙 Protection Manager", data="menu:protection"),
                Button.inline("✖️ Close", data="prot_close")
            ]
        ]

        if edit:
            await event.edit(text, buttons=buttons)
        else:
            await event.respond(text, buttons=buttons)

    async def send_pause_menu(self, event, user_id: int):
        """Display pause duration options"""
        text = (
            "⏳ **Pause Protection**\n\n"
            "Temporarily disable all protection systems. "
            "Protection will auto-resume after the timer expires.\n\n"
            "⚠️ **Warning:** Your account will be vulnerable during this period."
        )
        
        buttons = [
            [Button.inline("5 Minutes", data="prot_pause_5"), Button.inline("30 Minutes", data="prot_pause_30")],
            [Button.inline("1 Hour", data="prot_pause_60"), Button.inline("24 Hours", data="prot_pause_1440")],
            [Button.inline("🔙 Back", data="prot_main")]
        ]
        
        await event.edit(text, buttons=buttons)

    async def send_stats(self, event, user_id: int):
        """Display protection statistics"""
        settings = await ProtectionStorage.get_settings(user_id)
        stats = settings.get("stats", {})
        
        enabled_at = _as_utc(settings.get("enabled_at"))
        active_since = enabled_at.strftime("%Y-%m-%d") if enabled_at else "Not enabled"
        text = (
            "📊 **Protection Statistics**\n\n"
            f"🔥 **OTP Destroyed:** {stats.get('otp_destroyed', 0)}\n"
            f"🚫 **Sessions Terminated:** {stats.get('sessions_destroyed', 0)}\n"
            f"📅 **Session Destroyer Enabled Since:** {active_since}\n"
            f"🛡 **Trust Score:** High ✅\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Generated by TeleGuard Sentinel"
        )
        
        await event.edit(text, buttons=[[Button.inline("🔙 Back", data="prot_main")]])

    async def send_logs(self, event, user_id: int):
        """Display recent session-destruction events."""
        from ..sync.session_destroyer_db import SessionDestroyerDB

        logs = await SessionDestroyerDB.get_logs(user_id)
        if not logs:
            text = "📝 **Protection Logs**\n\nNo session-destruction events have been recorded."
        else:
            entries = ["📝 **Recent Session Protection Events**\n"]
            for entry in logs:
                timestamp = _as_utc(entry.get("timestamp"))
                when = timestamp.strftime("%Y-%m-%d %H:%M UTC") if timestamp else "Unknown time"
                result = "Terminated" if entry.get("success") else "Failed"
                entries.append(
                    f"• {when} — {result}: {entry.get('device', 'Unknown device')} "
                    f"({entry.get('country', 'Unknown')})"
                )
            text = "\n".join(entries)
        await event.edit(text, buttons=[[Button.inline("🔙 Back", data="prot_main")]])
