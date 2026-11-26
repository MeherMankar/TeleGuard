"""
Session Destroyer Handler
UI handlers for the Session Destroyer feature.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta, timezone
from telethon import Button, events

from ..sync.session_destroyer_db import SessionDestroyerDB
from ..services.protection_storage import ProtectionStorage
from ..core.mongo_database import mongodb
from .protection_menu import ProtectionMenu

logger = logging.getLogger(__name__)

class SessionDestroyerHandler:
    """Handles UI and callbacks for Session Destroyer"""

    def __init__(self, menu_system):
        self.menu = menu_system
        self.bot = menu_system.bot
        self.protection_menu = ProtectionMenu(menu_system.account_manager)

    async def show_submenu(self, user_id: int, message_id: Optional[int] = None):
        """Show per-account Session Destroyer controls."""
        try:
            from ..utils.crypto_utils import DataEncryption

            accounts = await mongodb.db.accounts.find(
                {"user_id": user_id, "is_active": True}
            ).to_list(length=None)
            settings_rows = []
            buttons = []
            enabled_count = 0
            for account_doc in accounts:
                account = DataEncryption.decrypt_account_data(account_doc)
                name = account.get("name") or account.get("phone") or "Account"
                account_id = str(account_doc["_id"])
                settings = await ProtectionStorage.get_account_settings(
                    user_id, account_id
                )
                enabled = bool(settings.get("enabled"))
                enabled_count += int(enabled)
                state = "🟢 ON" if enabled else "⚪ OFF"
                next_login = bool(settings.get("allow_next"))
                settings_rows.append(
                    f"• **{name}** — {state}"
                    + (" · next login will be kept" if next_login else "")
                )
                buttons.append(
                    [
                        Button.inline(
                            f"{'🔴 Turn off' if enabled else '🟢 Turn on'} · {name[:25]}",
                            f"sd:toggle:{account_id}",
                        ),
                        Button.inline(
                            f"🛡 Devices · {name[:18]}",
                            f"sd:trusted:{account_id}",
                        ),
                    ]
                )
                if enabled and not next_login:
                    buttons.append(
                        [
                            Button.inline(
                                "🔓 Trust next login · " + name[:16],
                                f"sd:allow_next:{account_id}",
                            )
                        ]
                    )
            text = (
                "🔥 **Session Destroyer — Per Account**\n\n"
                f"**Protected:** {enabled_count} of {len(accounts)} accounts\n\n"
                "Choose which Telegram accounts to monitor. Protection applies only "
                "to the selected account. Devices already present when enabled are "
                "kept; new devices may be terminated unless protected below.\n\n"
                + ("\n".join(settings_rows) if settings_rows else "No active accounts.")
            )
            buttons.extend(
                [
                    [Button.inline("📋 View Logs", "sd:logs")],
                    [Button.inline("🔙 Back", "menu:protection")],
                ]
            )
            
            if message_id:
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            else:
                await self.bot.send_message(user_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing Session Destroyer submenu: {e}")

    async def handle_callback(self, event, user_id: int, data: str):
        """Handle sd: callbacks"""
        try:
            parts = data.split(":")
            if len(parts) == 3 and parts[1] == "toggle":
                await self._toggle_account(event, user_id, parts[2])
            elif len(parts) == 3 and parts[1] == "allow_next":
                await self._allow_next_login(event, user_id, parts[2])
            elif data == "sd:logs":
                await self._show_logs(event, user_id)
            elif data == "sd:trusted":
                await self.protection_menu.send_trusted_sessions(
                    event, user_id, callback_prefix="sd"
                )
            elif len(parts) == 3 and parts[1] == "trusted":
                await self.protection_menu.send_trusted_sessions(
                    event,
                    user_id,
                    callback_prefix="sd",
                    account_id=parts[2],
                )
            elif len(parts) == 4 and parts[1] in {"protect", "unprotect"}:
                action, account_id, raw_hash = parts[1:]
                try:
                    session_hash = int(raw_hash)
                except ValueError:
                    await event.answer("⚠️ Invalid session selection", alert=True)
                    return
                updated = await self.protection_menu.set_session_trust(
                    user_id,
                    account_id,
                    session_hash,
                    action == "protect",
                )
                if not updated:
                    await event.answer(
                        "⚠️ Device is unavailable or cannot be changed.",
                        alert=True,
                    )
                else:
                    await event.answer(
                        "✅ Device protected"
                        if action == "protect"
                        else "🔓 Device protection removed"
                    )
                await self.protection_menu.send_trusted_sessions(
                    event,
                    user_id,
                    callback_prefix="sd",
                    account_id=account_id,
                )
            elif data == "sd:main":
                await self.show_submenu(user_id, event.message_id)
        except Exception as e:
            logger.error(f"Error in Session Destroyer callback: {e}")
            await event.answer("⚠️ Error processing request")

    async def _toggle_account(self, event, user_id: int, account_id: str):
        """Toggle Session Destroyer for one owned account."""
        protection_manager = getattr(
            self.menu.account_manager, "protection_manager", None
        )
        if not protection_manager:
            await event.answer("❌ Protection service unavailable", alert=True)
            return
        settings = await ProtectionStorage.get_account_settings(user_id, account_id)
        enabled = not settings.get("enabled", False)
        await protection_manager.toggle_session_destroyer(
            user_id, enabled, account_id
        )
        await event.answer(
            f"Session Destroyer {'enabled' if enabled else 'disabled'} for this account",
            alert=True,
        )
        await self.show_submenu(user_id, event.message_id)

    async def _allow_next_login(self, event, user_id: int, account_id: str):
        from bson import ObjectId

        account = await mongodb.db.accounts.find_one(
            {
                "_id": ObjectId(account_id),
                "user_id": user_id,
                "is_active": True,
            }
        )
        if not account:
            await event.answer("Account not found.", alert=True)
            return
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        await ProtectionStorage.update_account_settings(
            user_id,
            account_id,
            {"allow_next": True, "allow_next_until": expires_at},
        )
        await event.answer("Next login for this account will be kept for 5 minutes")
        await self.show_submenu(user_id, event.message_id)

    async def _show_logs(self, event, user_id: int):
        """Show recent destruction logs"""
        logs = await SessionDestroyerDB.get_logs(user_id)
        if not logs:
            await event.answer("📋 No logs found.", alert=True)
            return
            
        text = "📋 **Security Audit Log**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for log in logs:
            status = "✅ Terminated" if log.get("success") else "❌ Failed"
            timestamp = log.get("timestamp")
            ts = (
                timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if hasattr(timestamp, "strftime")
                else "Unknown time"
            )
            text += (
                f"📅 {ts}\n"
                f"🖥 {log.get('device', 'Unknown')} ({log.get('platform', 'Unknown')})\n"
                f"🌍 {log.get('country', 'Unknown')} | IP: {log.get('ip', 'Unknown')}\n"
                f"🛡 Status: {status}\n\n"
            )
            
        buttons = [[Button.inline("🔙 Back", "sd:main")]]
        await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
