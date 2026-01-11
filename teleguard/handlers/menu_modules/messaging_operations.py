"""Messaging operations"""

import logging

from telethon import Button

from ...core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class MessagingOperations:
    def __init__(self, menu_system):
        self.menu = menu_system
        self.bot = menu_system.bot
        self.account_manager = menu_system.account_manager

    async def send_message_menu(self, user_id, message_id):
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        if not accounts:
            text = "📤 **Send Message**\n\nNo accounts found. Add accounts first."
            buttons = [[Button.inline("🔙 Back", "menu:messaging")]]
        else:
            text = "📤 **Send Message**\n\nSelect account to send from:"
            buttons = []
            for account in accounts:
                status = "✅" if account.get("is_active", False) else "❌"
                button_text = f"{status} {account['name']}"
                buttons.append(
                    [Button.inline(button_text, f"msg:compose:{str(account['_id'])}")]
                )
            buttons.append([Button.inline("🔙 Back", "menu:messaging")])
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def send_autoreply_menu(self, user_id, message_id):
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(100)
        if not accounts:
            text = "🤖 **Advanced Auto-Reply System**\n\n❌ No accounts found. Add accounts first."
            buttons = [[Button.inline("🔙 Back", "menu:messaging")]]
        else:
            enabled_count = sum(
                1 for acc in accounts if acc.get("auto_reply_enabled", False)
            )
            settings = (
                await mongodb.db.auto_reply_settings.find_one({"user_id": user_id})
                or {}
            )
            keyword_status = (
                "🟢 On" if settings.get("keyword_replies_enabled", False) else "🔴 Off"
            )
            time_status = (
                "🟢 On"
                if settings.get("time_based_replies_enabled", False)
                else "🔴 Off"
            )
            text = f"🤖 **Advanced Auto-Reply System**\n\n📱 Accounts: {enabled_count}/{
                len(accounts)} enabled\n🔑 Keyword Replies: {keyword_status}\n⏰ Time-based Replies: {time_status}\n\nConfigure your automatic responses:"
            buttons = [
                [Button.inline("📱 Toggle Per Account", "auto_reply:toggle")],
                [Button.inline("🔑 Keyword Settings", "auto_reply:keyword_settings")],
                [Button.inline("⏰ Time Settings", "auto_reply:time_settings")],
                [Button.inline("📊 View Stats", "auto_reply:analytics")],
                [Button.inline("🗑️ Reset All", "auto_reply:reset")],
                [Button.inline("🔙 Back", "menu:messaging")],
            ]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def send_templates_menu(self, user_id, message_id):
        text = "📝 **Advanced Message Templates**\n\nUse the new advanced template system with:\n\n✨ **Features:**\n• Dynamic variables ({name}, {username}, {time}, {date})\n• Rich media support (images, videos)\n• Template categories\n• Quick reply buttons\n• Step-by-step creation wizard\n\nUse `/templates` command to access the advanced system."
        buttons = [
            [Button.inline("🚀 Open Advanced Templates", "template:main")],
            [Button.inline("🔙 Back", "menu:messaging")],
        ]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def send_bulk_sender_menu(self, user_id, message_id):
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        if not accounts:
            text = "📨 **Bulk Message Sender**\n\nNo accounts found. Add accounts first to use bulk messaging."
            buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
        else:
            active_jobs = 0
            if hasattr(self.account_manager, "bulk_sender"):
                user_jobs = [
                    job
                    for job in self.account_manager.bulk_sender.active_jobs.values()
                    if job["user_id"] == user_id
                ]
                active_jobs = len(user_jobs)
            text = f"📨 **Bulk Message Sender**\n\nSend messages to multiple users at once.\n\n📊 **Status:**\n• Available accounts: {
                len(accounts)}\n• Active jobs: {active_jobs}\n\n**Choose bulk sending method:**"
            buttons = [
                [Button.inline("📋 Send to List", "bulk:send_list")],
                [Button.inline("👥 Send to Contacts", "bulk:send_contacts")],
                [Button.inline("🌐 Send from All Accounts", "bulk:send_all")],
            ]
            if active_jobs > 0:
                buttons.append([Button.inline("📊 View Active Jobs", "bulk:jobs")])
            buttons.extend(
                [
                    [Button.inline("❓ Help & Commands", "bulk:help")],
                    [Button.inline("🔙 Back to Messaging", "menu:messaging")],
                ]
            )
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def start_bulk_list_flow(self, user_id, event):
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        if not accounts:
            await event.answer("❌ No accounts found")
            return
        text = "📋 **Bulk Send to List**\n\nStep 1: Select account to send from:\n\n"
        buttons = []
        for acc in accounts:
            status = "✅" if acc.get("is_active", False) else "❌"
            buttons.append(
                [
                    Button.inline(
                        f"{status} {acc['name']}",
                        f"bulk_list_account:{str(acc['_id'])}",
                    )
                ]
            )
        buttons.append([Button.inline("🔙 Back to Bulk Sender", "msg:bulk")])
        await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        await event.answer("📋 Select account")

    async def start_bulk_contacts_flow(self, user_id, event):
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        if not accounts:
            await event.answer("❌ No accounts found")
            return
        text = "👥 **Bulk Send to Contacts**\n\nStep 1: Select account to send from:\n\nThis will send to ALL contacts of the selected account."
        buttons = []
        for acc in accounts:
            status = "✅" if acc.get("is_active", False) else "❌"
            buttons.append(
                [
                    Button.inline(
                        f"{status} {acc['name']}",
                        f"bulk_contacts_account:{str(acc['_id'])}",
                    )
                ]
            )
        buttons.append([Button.inline("🔙 Back to Bulk Sender", "msg:bulk")])
        await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        await event.answer("👥 Select account")

    async def start_bulk_all_flow(self, user_id, event):
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        if not accounts:
            await event.answer("❌ No accounts found")
            return
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "bulk_all_targets"
            }
        text = f"🌐 **Bulk Send from All Accounts**\n\nThis will send from ALL {
            len(accounts)} accounts.\n\nStep 1: Reply with target usernames/IDs (comma-separated):\n\n**Examples:**\n• @username1,@username2,@username3\n• +1234567890,@username,123456789\n\nReply with the targets:"
        await self.bot.edit_message(user_id, event.message_id, text)
        await event.answer("🌐 Reply with targets")

    async def show_bulk_jobs(self, user_id, message_id):
        if not hasattr(self.account_manager, "bulk_sender"):
            text = "❌ Bulk sender not available"
            buttons = [[Button.inline("🔙 Back to Bulk Sender", "msg:bulk")]]
        else:
            user_jobs = [
                job
                for job in self.account_manager.bulk_sender.active_jobs.values()
                if job["user_id"] == user_id
            ]
            if not user_jobs:
                text = "📊 **Active Bulk Jobs**\n\n💭 No active jobs found."
                buttons = [[Button.inline("🔙 Back to Bulk Sender", "msg:bulk")]]
            else:
                text = f"📊 **Active Bulk Jobs** ({len(user_jobs)})\n\n"
                buttons = []
                for job in user_jobs:
                    progress = f"{job['sent']}/{job['total']}"
                    status_emoji = "✅" if job["status"] == "running" else "❌"
                    account_info = (
                        f" [{job['account_name']}]" if job.get("multi_account") else ""
                    )
                    text += f"{status_emoji} **Job {job['id'][:8]}**{account_info}\n   Progress: {progress} ({job['status']})\n"
                    if job["failed"] > 0:
                        text += f"   Failed: {job['failed']}\n"
                    text += "\n"
                    if job["status"] == "running":
                        buttons.append(
                            [
                                Button.inline(
                                    f"⏹️ Stop {job['id'][:8]}",
                                    f"bulk:stop:{str(job['id'])}",
                                )
                            ]
                        )
                buttons.append([Button.inline("🔄 Refresh", "bulk:jobs")])
                buttons.append([Button.inline("🔙 Back to Bulk Sender", "msg:bulk")])
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def show_bulk_help(self, user_id, message_id):
        text = "❓ **Bulk Sender Help**\n\n**Available Commands:**\n• `/bulk_send` - Show bulk sender help\n• `/bulk_send_list account_name` - Send to specific users\n• `/bulk_send_contacts account_name` - Send to all contacts\n• `/bulk_send_all` - Send from ALL accounts\n• `/bulk_jobs` - View active jobs\n• `/bulk_stop <job_id>` - Stop a job\n\n**Format for list sending:**\n`/bulk_send_list account_name\nusername1,username2,user_id3\nYour message here`\n\n**Button Format:**\nAdd buttons using: `[Button Text](url)` or `[Button Text](callback_data)`\nExample: `Check this out [Visit Site](https://example.com) [More Info](info_callback)`\n\n**Tips:**\n• Use the menu buttons for easier setup\n• Commands provide more advanced options\n• Jobs run in background with progress updates"
        buttons = [[Button.inline("🔙 Back to Bulk Sender", "msg:bulk")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
