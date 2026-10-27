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
            [Button.inline("🔐 Manage Trusted Sessions", data="prot_trusted")],
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

    async def send_trusted_sessions(
        self, event, user_id: int, callback_prefix: str = "prot"
    ):
        """Display live sessions and controls to trust or untrust each session."""
        from telethon.tl.functions.account import GetAuthorizationsRequest
        from ..utils.crypto_utils import DataEncryption

        settings = await ProtectionStorage.get_settings(user_id)
        trusted_hashes = set(settings.get("trusted_hashes", []))
        accounts = await mongodb.db.accounts.find(
            {"user_id": user_id, "is_active": True}
        ).to_list(length=None)
        session_rows = []
        failed_accounts = 0

        for account_doc in accounts:
            account = DataEncryption.decrypt_account_data(account_doc)
            client = self.bot_manager.get_client(user_id, account)
            if not client or not client.is_connected():
                continue
            try:
                result = await client(GetAuthorizationsRequest())
            except Exception:
                failed_accounts += 1
                logger.exception(
                    "Failed to load sessions for protection settings (user %s)",
                    user_id,
                )
                continue

            account_name = account.get("name") or account.get("phone") or "Account"
            session_rows.extend(
                (account_name, authorization)
                for authorization in result.authorizations
            )

        if not session_rows:
            text = "🔐 **Trusted Sessions**\n\n"
            if failed_accounts:
                text += (
                    f"Could not load sessions for {failed_accounts} account(s). "
                    "Reconnect those accounts and try again."
                )
            else:
                text += "No sessions are currently available from connected accounts."
            await event.edit(
                text,
                buttons=[
                    [Button.inline("🔄 Refresh", data=f"{callback_prefix}:trusted")],
                    [Button.inline("🔙 Back", data=f"{callback_prefix}:main")],
                ],
            )
            return

        lines = ["🔐 **Trusted Sessions**", ""]
        buttons = []
        for account_name, authorization in session_rows[:20]:
            is_current = bool(authorization.current)
            is_trusted = is_current or authorization.hash in trusted_hashes
            if is_current:
                state = "🛡 Current session (always kept)"
            elif is_trusted:
                state = "🛡 Trusted"
            else:
                state = "⚠️ Untrusted"
            device = getattr(authorization, "device_model", None) or "Unknown device"
            platform = getattr(authorization, "platform", None) or "Unknown platform"
            lines.append(
                f"• **{account_name}** — {device} ({platform})\n  {state}"
            )
            if not is_current:
                action = "untrust" if is_trusted else "trust"
                label = "🔓 Untrust" if is_trusted else "🛡 Trust"
                buttons.append(
                    [
                        Button.inline(
                            f"{label}: {device[:24]}",
                            data=f"{callback_prefix}:{action}:{authorization.hash}",
                        )
                    ]
                )

        if len(session_rows) > 20:
            lines.extend(["", f"Showing 20 of {len(session_rows)} sessions."])
        if failed_accounts:
            lines.extend(
                ["", f"⚠️ Session lookup failed for {failed_accounts} account(s)."]
            )
        lines.extend(
            [
                "",
                "Trust sessions you recognize. Untrusted sessions may be "
                "terminated when Session Destroyer is enabled.",
            ]
        )
        buttons.extend(
            [
                [Button.inline("🔄 Refresh", data=f"{callback_prefix}:trusted")],
                [Button.inline("🔙 Back", data=f"{callback_prefix}:main")],
            ]
        )
        await event.edit("\n".join(lines), buttons=buttons)

    async def set_session_trust(self, user_id: int, session_hash: int, trusted: bool):
        """Change trust only for a live session belonging to this user."""
        from telethon.tl.functions.account import GetAuthorizationsRequest
        from ..utils.crypto_utils import DataEncryption

        accounts = await mongodb.db.accounts.find(
            {"user_id": user_id, "is_active": True}
        ).to_list(length=None)
        lookup_failed = False
        found = False
        target_is_current = False

        for account_doc in accounts:
            account = DataEncryption.decrypt_account_data(account_doc)
            client = self.bot_manager.get_client(user_id, account)
            if not client or not client.is_connected():
                continue
            try:
                result = await client(GetAuthorizationsRequest())
            except Exception:
                lookup_failed = True
                logger.exception(
                    "Failed to verify session trust action (user %s)", user_id
                )
                continue

            for authorization in result.authorizations:
                if authorization.hash == session_hash:
                    found = True
                    target_is_current = bool(authorization.current)
                    break
            else:
                continue
            break

        if lookup_failed and not found:
            raise RuntimeError("Could not verify the requested session.")
        if not found:
            return False
        if target_is_current and not trusted:
            return False

        if trusted:
            await ProtectionStorage.add_trusted_hash(user_id, session_hash)
            await mongodb.db.session_destroyer_pending.delete_many(
                {"user_id": user_id, "hash": session_hash}
            )
        else:
            await ProtectionStorage.add_untrusted_hash(user_id, session_hash)
            await mongodb.db.session_destroyer_pending.delete_many(
                {"user_id": user_id, "hash": session_hash}
            )
        return True
