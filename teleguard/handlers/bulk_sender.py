"""Bulk Message Sender - Send messages to multiple users at once"""

import asyncio
import logging
from typing import Dict, List

from telethon import events

from ..core.config import ADMIN_IDS
from ..core.mongo_database import mongodb
from ..core.rate_limiter import rate_limiter
from ..core.session_health import session_health

logger = logging.getLogger(__name__)


class BulkSender:
    """Handles bulk message sending operations"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        self.active_jobs = {}

    def register_handlers(self):
        """Register bulk sender command handlers"""
        self._register_main_command()
        self._register_list_command()
        self._register_contacts_command()
        self._register_all_command()
        self._register_jobs_command()
        self._register_stop_command()

    def _register_main_command(self):
        @self.bot.on(events.NewMessage(pattern=r"^/bulk_send$"))
        async def bulk_send_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
            await event.reply(
                "📤 **Bulk Message Sender**\n\n"
                "Send messages to multiple users at once.\n\n"
                "**Commands:**\n"
                "• `/bulk_send_list` - Send to a list of usernames/IDs\n"
                "• `/bulk_send_contacts` - Send to all contacts\n"
                "• `/bulk_send_all` - Send from ALL accounts\n"
                "• `/bulk_jobs` - View active jobs\n"
                "• `/bulk_stop <job_id>` - Stop a job\n\n"
                "**Format for list:**\n"
                "`/bulk_send_list account_name\n"
                "username1,username2,user_id3\n"
                "Your message here`\n\n"
                "**Button Format:**\n"
                "Add buttons using: `[Button Text](url)` or `[Button Text](callback_data)`\n"
                "Example: `Check this out [Visit Site](https://example.com) [More Info](info_callback)`"
            )

    def _register_list_command(self):
        @self.bot.on(events.NewMessage(pattern=r"^/bulk_send_list\s+(.+)"))
        async def bulk_send_list_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
            try:
                lines = event.text.split("\n", 2)
                if len(lines) < 3:
                    await event.reply(
                        "❌ Invalid format. Use:\n`/bulk_send_list account_name\nuser1,user2\nMessage`"
                    )
                    return
                account_name = lines[0].split()[1]
                targets = [t.strip() for t in lines[1].split(",")]
                message = lines[2]
                # Parse message and buttons
                message_text, buttons = self._parse_message_buttons(message)
                job_id = await self._start_bulk_job(
                    event.sender_id,
                    account_name,
                    targets,
                    message_text,
                    event,
                    buttons=buttons,
                )
                if job_id:
                    await event.reply(
                        f"✅ Bulk send job started: `{job_id}`\nSending to {
                            len(targets)} targets..."
                    )
            except Exception as e:
                await event.reply(f"❌ Error: {str(e)}")

    def _register_contacts_command(self):
        @self.bot.on(events.NewMessage(pattern=r"^/bulk_send_contacts\s+(\S+)\s+(.+)"))
        async def bulk_send_contacts_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
            try:
                parts = event.text.split(" ", 2)
                account_name = parts[1]
                message = parts[2]
                # Parse message and buttons
                message_text, buttons = self._parse_message_buttons(message)
                targets = await self._get_account_contacts(
                    event.sender_id, account_name
                )
                if not targets:
                    await event.reply("❌ No contacts found for this account")
                    return
                job_id = await self._start_bulk_job(
                    event.sender_id,
                    account_name,
                    targets,
                    message_text,
                    event,
                    buttons=buttons,
                )
                if job_id:
                    await event.reply(
                        f"✅ Bulk send job started: `{job_id}`\nSending to {
                            len(targets)} contacts..."
                    )
            except Exception as e:
                await event.reply(f"❌ Error: {str(e)}")

    def _register_all_command(self):
        @self.bot.on(events.NewMessage(pattern=r"^/bulk_send_all\s+(.+)"))
        async def bulk_send_all_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
            try:
                lines = event.text.split("\n", 1)
                if len(lines) < 2:
                    await event.reply(
                        "❌ Invalid format. Use:\n`/bulk_send_all\nuser1,user2\nMessage`"
                    )
                    return
                targets = [t.strip() for t in lines[0].split("\n")[0].split(",")]
                message = lines[1]
                user_accounts = list(self.user_clients.get(event.sender_id, {}).keys())
                if not user_accounts:
                    await event.reply("❌ No accounts found")
                    return
                await event.reply(
                    f"🚀 Starting bulk send from {
                        len(user_accounts)} accounts to {
                        len(targets)} targets..."
                )
                jobs = []
                for account_name in user_accounts:
                    job_id = await self._start_bulk_job(
                        event.sender_id,
                        account_name,
                        targets,
                        message,
                        event,
                        multi_account=True,
                    )
                    if job_id:
                        jobs.append(job_id)
                if jobs:
                    await event.reply(
                        f"✅ Started {len(jobs)} bulk jobs from all accounts"
                    )
            except Exception as e:
                await event.reply(f"❌ Error: {str(e)}")

    def _register_jobs_command(self):
        @self.bot.on(events.NewMessage(pattern=r"^/bulk_jobs$"))
        async def bulk_jobs_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
            user_jobs = [
                job
                for job in self.active_jobs.values()
                if job["user_id"] == event.sender_id
            ]
            if not user_jobs:
                await event.reply("📭 No active bulk jobs")
                return
            status_text = "📊 **Active Bulk Jobs:**\n\n"
            for job in user_jobs:
                progress = f"{job['sent']}/{job['total']}"
                account_info = (
                    f" [{job['account_name']}]" if job.get("multi_account") else ""
                )
                status_text += f"🔹 `{job['id'][:8]}` - {progress} ({job['status']}){account_info}\n"
            await event.reply(status_text)

    def _register_stop_command(self):
        @self.bot.on(events.NewMessage(pattern=r"^/bulk_stop\s+(\S+)$"))
        async def bulk_stop_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
            job_id = event.pattern_match.group(1)
            # Find job by partial ID
            full_job_id = None
            for jid in self.active_jobs:
                if jid.startswith(job_id):
                    full_job_id = jid
                    break
            if (
                not full_job_id
                or self.active_jobs[full_job_id]["user_id"] != event.sender_id
            ):
                await event.reply("❌ Job not found")
                return
            self.active_jobs[full_job_id]["status"] = "stopped"
            await event.reply(f"⏹️ Job `{job_id}` stopped")

    async def _start_bulk_job(
        self,
        user_id: int,
        account_name: str,
        targets: List[str],
        message: str,
        event,
        multi_account: bool = False,
        buttons: List = None,
    ) -> str:
        """Start a bulk sending job"""
        try:
            client = self.user_clients.get(user_id, {}).get(account_name)
            if not client:
                await event.reply(f"❌ Account `{account_name}` not found")
                return None

            # Get account phone for rate limiting
            account = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "name": account_name}
            )
            account_phone = account.get("phone") if account else account_name

            # Check rate limit
            can_perform, error_msg = rate_limiter.can_perform(
                account_phone, "bulk_send"
            )
            if not can_perform:
                await event.reply(error_msg)
                return None

            # Check session health
            is_healthy, health_msg = await session_health.check_session(
                client, account_phone
            )
            if not is_healthy:
                await event.reply(
                    f"⚠️ Session health check failed: {health_msg}\nProceed with caution."
                )

            # Record operation
            rate_limiter.record_operation(account_phone, "bulk_send")
            rate_limiter.record_operation(account_phone, "message", len(targets))
            import time

            job_id = f"bulk_{account_name}_{int(time.time())}"
            job = {
                "id": job_id,
                "user_id": user_id,
                "account_name": account_name,
                "targets": targets,
                "message": message,
                "buttons": buttons or [],
                "total": len(targets),
                "sent": 0,
                "failed": 0,
                "status": "running",
                "event": event,
                "multi_account": multi_account,
            }
            self.active_jobs[job_id] = job
            asyncio.create_task(self._execute_bulk_job(job_id, client))
            return job_id
        except Exception as e:
            logger.error(f"Failed to start bulk job: {e}")
            return None

    async def _execute_bulk_job(self, job_id: str, client):
        """Execute bulk sending job"""
        job = self.active_jobs.get(job_id)
        if not job:
            return
        status_msg = None
        try:
            status_msg = await self._send_initial_status(job)
            for i, target in enumerate(job["targets"]):
                if job["status"] != "running":
                    break
                await self._send_to_target(job, client, target, i, status_msg)
            job["status"] = "completed"
            await self._send_final_status(job, status_msg)
        except Exception as e:
            job["status"] = "error"
            logger.error(f"Bulk job error: {e}")
            if status_msg:
                await status_msg.edit(f"❌ **Campaign Failed**\n\nError: {str(e)}\nSent: {job['sent']}/{job['total']}")
        finally:
            await asyncio.sleep(3600)
            self.active_jobs.pop(job_id, None)

    async def _update_job_progress(self, job: Dict, final: bool = False):
        """Update job progress"""
        try:
            progress = f"{job['sent']}/{job['total']}"
            failed_text = f", {job['failed']} failed" if job["failed"] > 0 else ""
            if final:
                status_emoji = "✅" if job["status"] == "completed" else "⏹️"
                text = f"{status_emoji} **Bulk job completed**\n\n📊 **Results:**\n• Sent: {
                    job['sent']}\n• Failed: {
                    job['failed']}\n• Total: {
                    job['total']}"
            else:
                text = f"📤 **Bulk sending progress:** {progress}{failed_text}"
            await job["event"].reply(text)
        except Exception as e:
            logger.error(f"Failed to update job progress: {e}")

    async def _get_account_contacts(self, user_id: int, account_name: str) -> List[str]:
        """Get all contacts for an account"""
        try:
            client = self.user_clients.get(user_id, {}).get(account_name)
            if not client:
                return []
            contacts = []
            async for dialog in client.iter_dialogs():
                if dialog.is_user and not dialog.entity.bot:
                    if dialog.entity.username:
                        contacts.append(dialog.entity.username)
                    else:
                        contacts.append(str(dialog.entity.id))
            return contacts
        except Exception as e:
            logger.error(f"Failed to get contacts: {e}")
            return []

    async def _get_access_hash_from_any_account(
        self, user_id: int, target_user_id: int
    ):
        """Get access_hash for a user from any account that has them"""
        try:
            # Try all user's accounts
            for account_name, client in self.user_clients.get(user_id, {}).items():
                if not client or not client.is_connected():
                    continue

                try:
                    # Try to get entity from this account
                    entity = await client.get_entity(target_user_id)
                    if hasattr(entity, "access_hash") and entity.access_hash:
                        logger.info(f"Found access_hash from {account_name}")
                        return entity.access_hash
                except BaseException:
                    continue

            return None
        except Exception as e:
            logger.error(f"Failed to get access_hash: {e}")
            return None

    def _parse_message_buttons(self, message: str) -> tuple:
        """Parse message text and extract buttons"""
        import re

        # Find all button patterns: [Text](url_or_callback)
        button_pattern = r"\[([^\]]+)\]\(([^\)]+)\)"
        buttons = []
        for match in re.finditer(button_pattern, message):
            text = match.group(1)
            data = match.group(2)
            # Determine if it's URL or callback
            if data.startswith("http://") or data.startswith("https://"):
                button_type = "url"
            else:
                button_type = "callback"
            buttons.append({"text": text, "data": data, "type": button_type})
        clean_message = re.sub(button_pattern, "", message).strip()
        return clean_message, buttons

    async def _send_initial_status(self, job):
        return await job["event"].reply(
            f"\ud83d\ude80 **Campaign Started**\\n\\n"
            f"Account: {job['account_name']}\\n"
            f"Total Users: {job['total']}\\n"
            f"Sent: 0/{job['total']}\\n"
            f"Progress: \u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591 0%"
        )

    async def _send_final_status(self, job, status_msg):
        if status_msg:
            await status_msg.edit(
                f"\u2705 **Campaign Completed**\\n\\n"
                f"Account: {job['account_name']}\\n"
                f"Total Users: {job['total']}\\n"
                f"Sent: {job['sent']}/{job['total']}\\n"
                f"Failed: {job['failed']}\\n"
                f"Progress: \u25a0\u25a0\u25a0\u25a0\u25a0\u25a0\u25a0\u25a0\u25a0\u25a0 100%"
            )

    async def _send_to_target(self, job, client, target, index, status_msg):
        try:
            entity = await self._resolve_target(job, client, target)
            if not entity:
                job["failed"] += 1
                return
            await self._send_message_to_entity(job, client, entity)
            job["sent"] += 1
            logger.info(f"\u2705 Sent to {target} ({job['sent']}/{job['total']})")
            await self._record_and_update_progress(job, index, status_msg)
            import random
            await asyncio.sleep(random.uniform(8, 15))
        except Exception as e:
            await self._handle_send_error(job, target, e, status_msg)

    async def _resolve_target(self, job, client, target):
        try:
            if target.startswith("@"):
                return await client.get_entity(target)
            elif target.isdigit():
                user_id = int(target)
                try:
                    return await client.get_entity(user_id)
                except BaseException:
                    access_hash = await self._get_access_hash_from_any_account(job["user_id"], user_id)
                    if access_hash:
                        from telethon.tl.types import InputPeerUser
                        logger.info(f"Using access_hash for user {user_id}")
                        return InputPeerUser(user_id, access_hash)
                    logger.warning(f"No access_hash found for {user_id}")
                    return None
            else:
                return await client.get_entity(target)
        except Exception as e:
            logger.error(f"Failed to resolve {target}: {e}")
            return None

    async def _send_message_to_entity(self, job, client, entity):
        if job["buttons"]:
            from telethon.tl.types import KeyboardButtonCallback, KeyboardButtonUrl, ReplyInlineMarkup
            keyboard_rows = []
            current_row = []
            for btn in job["buttons"]:
                button = KeyboardButtonUrl(btn["text"], btn["data"]) if btn["type"] == "url" else KeyboardButtonCallback(btn["text"], btn["data"].encode())
                current_row.append(button)
                if len(current_row) >= 2:
                    keyboard_rows.append(current_row)
                    current_row = []
            if current_row:
                keyboard_rows.append(current_row)
            markup = ReplyInlineMarkup(keyboard_rows) if keyboard_rows else None
            await client.send_message(entity, job["message"], buttons=markup)
        else:
            await client.send_message(entity, job["message"])

    async def _record_and_update_progress(self, job, index, status_msg):
        account = await mongodb.db.accounts.find_one({"user_id": job["user_id"], "name": job["account_name"]})
        if account:
            rate_limiter.record_operation(account.get("phone", job["account_name"]), "message")
        if (index + 1) % 5 == 0 or (index + 1) == job["total"]:
            progress_pct = int((job["sent"] / job["total"]) * 100)
            progress_bar = "\u25a0" * (progress_pct // 10) + "\u2591" * (10 - progress_pct // 10)
            if status_msg:
                try:
                    await status_msg.edit(
                        f"\ud83d\udce4 **Campaign Running**\\n\\n"
                        f"Account: {job['account_name']}\\n"
                        f"Total Users: {job['total']}\\n"
                        f"Sent: {job['sent']}/{job['total']}\\n"
                        f"Failed: {job['failed']}\\n"
                        f"Progress: {progress_bar} {progress_pct}%"
                    )
                except BaseException:
                    pass

    async def _handle_send_error(self, job, target, error, status_msg):
        job["failed"] += 1
        error_msg = str(error)
        logger.error(f"\u274c Failed to send to {target}: {error_msg}")
        if "FloodWaitError" in error_msg or "FLOOD_WAIT" in error_msg:
            import re
            wait_match = re.search(r"(\\d+)", error_msg)
            if wait_match:
                wait_time = int(wait_match.group(1))
                if status_msg:
                    await status_msg.edit(f"\u23f8\ufe0f **Rate Limited**\\n\\nWaiting {wait_time} seconds...\\nSent: {job['sent']}/{job['total']}")
                await asyncio.sleep(wait_time)
