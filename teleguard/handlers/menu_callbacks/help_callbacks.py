"""Help, support, and developer menu callbacks."""

from telethon import Button

from ...core.config import ADMIN_IDS
from ...core.mongo_database import mongodb
from .base_callback import BaseCallback

REPOSITORY_URL = "https://github.com/mehermankar/teleguard"
ISSUES_URL = f"{REPOSITORY_URL}/issues/new"


class HelpCallbacks(BaseCallback):
    async def _show(self, event, user_id, text, buttons, alert=None):
        await self.bot.edit_message(
            user_id, event.message_id, text, buttons=buttons
        )
        await event.answer(alert or "")

    @staticmethod
    def _back_buttons(menu_callback="menu:help"):
        return [[Button.inline("🔙 Back", menu_callback)]]

    async def handle_callback(self, event, user_id, data):
        """Handle help-related callbacks."""
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else "main"
        pages = {
            "guide": (
                "📖 **Getting Started**\n\n"
                "1. Add a Telegram account from **📱 Account Settings**.\n"
                "2. Configure protection from **🛡️ Protection Manager**.\n"
                "3. Open each feature menu to configure it before use.\n\n"
                "If account login or a feature fails, check the troubleshooting "
                "guide or contact support."
            ),
            "security": (
                "🛡️ **Security Guide**\n\n"
                "• Enable OTP Destroyer for accounts where you want incoming "
                "login codes removed after processing.\n"
                "• Review and revoke unfamiliar Telegram sessions.\n"
                "• Keep your Telegram 2FA password and bot credentials private.\n"
                "• Never send login codes, session files, or session strings to support.\n\n"
                "Manage account protection in **🛡️ Protection Manager**."
            ),
            "features": (
                "⚙️ **Feature Guide**\n\n"
                "• **Account Settings** — manage connected Telegram accounts.\n"
                "• **Protection Manager** — configure OTP and session protection.\n"
                "• **Messaging / Channels / Contacts** — manage the corresponding "
                "account tools.\n"
                "• **Cleanup** — review and run supported cleanup actions.\n"
                "• **Proxy Manager** — manage account proxy connections.\n\n"
                "Use the main menu to open a feature and see its available actions."
            ),
            "troubleshoot": (
                "🔧 **Troubleshooting**\n\n"
                "• If a menu is stale, use **/start** to reopen the main menu.\n"
                "• If an account is disconnected, check its login and session in "
                "**Account Settings**.\n"
                "• If a protection action does not run, confirm the account is "
                "connected and the relevant toggle is enabled.\n"
                "• If a callback appears stuck, reopen the menu and try once more.\n\n"
                "For persistent errors, report the affected feature and the "
                "non-sensitive error text. Do not include credentials or session data."
            ),
            "faq": (
                "❓ **Frequently Asked Questions**\n\n"
                "**Where do I start?** Open Account Settings, connect an account, "
                "then configure the feature you need.\n\n"
                "**Where are OTP and session controls?** Open Protection Manager.\n\n"
                "**Can support recover my session?** Do not share session files or "
                "login codes; support cannot safely use them.\n\n"
                "**How do I report a bug?** Use the Report Bug button in Support."
            ),
            "contact": (
                "📞 **Contact Support**\n\n"
                "Use the support bot for assistance, or open a GitHub issue for a "
                "reproducible bug. Include the feature name and steps to reproduce, "
                "but remove phone numbers, login codes, API keys, and session data."
            ),
            "emergency": (
                "🆘 **Account Security Help**\n\n"
                "If you suspect an account is compromised:\n"
                "1. Secure the Telegram account directly in Telegram settings.\n"
                "2. Terminate unfamiliar Telegram sessions.\n"
                "3. Change your 2FA password if it may be exposed.\n"
                "4. Disable affected TeleGuard automations and review connected "
                "accounts.\n\n"
                "Never send a login code or session string to anyone."
            ),
            "commands": (
                "📚 **Command Reference**\n\n"
                "• `/start` — open the main menu.\n"
                "• `/help` — show help (where enabled).\n"
                "• `/import_chats` and `/import_help` — chat import tools.\n"
                "• `/bulk_send`, `/bulk_send_list`, `/bulk_send_contacts`, "
                "`/bulk_send_all` — messaging commands.\n"
                "• `/bulk_jobs` and `/bulk_stop` — inspect or stop bulk jobs.\n"
                "Most features are accessed from the main menu; available commands "
                "depend on your account and permissions."
            ),
        }
        if action == "toggle_dev":
            if user_id not in ADMIN_IDS:
                await event.answer("❌ You don't have access to Developer tools.", alert=True)
                return

            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            new_mode = not bool(user.get("developer_mode", False) if user else False)
            await mongodb.db.users.update_one(
                {"telegram_id": user_id},
                {"$set": {"developer_mode": new_mode}},
                upsert=True,
            )
            await self.menu_system.handlers.handle_help(event)
            await event.answer(
                f"⚙️ Developer mode {'enabled' if new_mode else 'disabled'}"
            )
            return

        if action == "main":
            await self.menu_system.handlers.handle_help(event)
        elif action in pages:
            buttons = self._back_buttons()
            if action in ("guide", "security", "features", "troubleshoot"):
                buttons.insert(
                    0,
                    [
                        Button.inline("🏠 Open Main Menu", "menu:main"),
                        Button.inline("🆘 Support", "support:main"),
                    ],
                )
            elif action == "contact":
                buttons.insert(
                    0,
                    [
                        Button.url("💬 Contact Support", "https://t.me/ContactXYZrobot"),
                        Button.url("🐛 Report a Bug", ISSUES_URL),
                    ],
                )
            elif action == "emergency":
                buttons.insert(0, [Button.inline("🆘 Support", "support:main")])
            await self._show(event, user_id, pages[action], buttons)
        else:
            await event.answer("❌ Unknown help page.", alert=True)

    async def handle_support_callback(self, event, user_id, data):
        """Handle support-related callbacks."""
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else "main"
        if action == "main":
            await self.menu_system.handlers.handle_support(event)
            await event.answer("")
            return

        pages = {
            "contact": (
                "💬 **Contact Support**\n\n"
                "Describe the issue and the feature involved. Never send login "
                "codes, passwords, API keys, session files, or session strings."
            ),
            "bug": (
                "🐛 **Report a Bug**\n\n"
                "Open an issue with the steps to reproduce, expected behavior, "
                "actual behavior, and a redacted error message. Do not attach "
                "credentials or account/session data."
            ),
            "docs": (
                "📚 **Documentation**\n\n"
                "The project README contains setup, feature, and contribution "
                "information. Feature-specific guidance is also available from "
                "the Help menu."
            ),
            "feature": (
                "💡 **Request a Feature**\n\n"
                "Describe the problem the feature would solve, the expected "
                "behavior, and any relevant constraints."
            ),
            "status": (
                "📊 **Service Status**\n\n"
                "This menu does not have an external service-health monitor. "
                "The bot responded to this request; individual Telegram or "
                "database operations may still be unavailable."
            ),
            "updates": (
                "🔄 **Project Updates**\n\n"
                "View the repository for current project activity and releases."
            ),
        }
        if action not in pages:
            await event.answer("❌ Unknown support page.", alert=True)
            return

        buttons = []
        if action in ("contact",):
            buttons.append([Button.url("💬 Open Support Bot", "https://t.me/ContactXYZrobot")])
        elif action in ("bug", "feature"):
            issue_url = ISSUES_URL
            if action == "feature":
                issue_url += "?labels=enhancement"
            buttons.append([Button.url("🐛 Open GitHub Issues", issue_url)])
        elif action == "docs":
            buttons.append(
                [Button.url("📚 Open Project README", f"{REPOSITORY_URL}#readme")]
            )
        elif action == "updates":
            buttons.append(
                [Button.url("🔄 View Releases", f"{REPOSITORY_URL}/releases")]
            )
        buttons.extend(self._back_buttons("support:main"))
        await self._show(event, user_id, pages[action], buttons)

    async def handle_developer_callback(self, event, user_id, data):
        """Handle administrator-only developer callbacks."""
        if user_id not in ADMIN_IDS:
            await event.answer("❌ You don't have access to Developer tools.", alert=True)
            return

        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else "main"
        if action == "main":
            await self.menu_system.handlers.handle_developer(event)
            await event.answer("")
            return

        if action == "toggle":
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            new_mode = not bool(user.get("developer_mode", False) if user else False)
            await mongodb.db.users.update_one(
                {"telegram_id": user_id},
                {"$set": {"developer_mode": new_mode}},
                upsert=True,
            )
            await self.menu_system.handlers.handle_developer(event)
            await event.answer(
                f"⚙️ Developer mode {'enabled' if new_mode else 'disabled'}"
            )
            return

        developer_commands = getattr(self.account_manager, "developer_commands", None)
        if developer_commands is None:
            await self._show(
                event,
                user_id,
                "⚠️ Developer diagnostics are not initialized.",
                self._back_buttons("dev:main"),
            )
            return

        text = None
        if action == "sysinfo":
            cpu, memory, disk = await developer_commands._get_container_stats()
            users = await mongodb.db.users.count_documents({})
            accounts = await mongodb.db.accounts.count_documents({})
            text = developer_commands._build_sysinfo_text(
                cpu,
                memory,
                disk,
                users,
                accounts,
                developer_commands._detect_platform(),
            )
        elif action == "logs":
            text = developer_commands._build_logs_text()
        elif action == "dbstats":
            stats = await developer_commands._gather_stats()
            text = developer_commands._build_stats_text(stats)
        elif action == "perf":
            cpu, memory, disk = await developer_commands._get_container_stats()
            text = (
                "⚡ **Performance Snapshot**\n\n"
                f"• CPU: {cpu}\n"
                f"• Memory: {memory}\n"
                f"• Disk: {disk}\n"
                f"• Uptime: {developer_commands._get_uptime()}"
            )
        elif action == "maintenance":
            cleaned = developer_commands._cleanup_inactive_sessions()
            text = (
                "🔧 **Session Maintenance**\n\n"
                f"Removed {cleaned} disconnected client reference(s) from the "
                "runtime manager. Persisted session files were not changed."
            )
        elif action == "restart":
            text = (
                "🔄 **Restart Status**\n\n"
                "A restart is not implemented by this control panel. Restart the "
                "application using its deployment or process manager."
            )
        elif action == "startup":
            text = await developer_commands._build_startup_status_text(user_id)
        elif action == "commands":
            text = (
                "📚 **Developer Commands**\n\n"
                "`/sysinfo` — system information\n"
                "`/health` — health check\n"
                "`/stats` — bot statistics\n"
                "`/logs` — runtime diagnostics\n"
                "`/cleanup_sessions` — remove disconnected client references\n"
                "`/startup_enable`, `/startup_disable`, `/startup_status` — "
                "startup notification settings\n\n"
                "These commands are restricted to configured administrators."
            )
        else:
            await event.answer("❌ Unknown developer action.", alert=True)
            return

        await self._show(
            event,
            user_id,
            text,
            self._back_buttons("dev:main"),
        )
