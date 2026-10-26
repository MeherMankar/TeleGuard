"""Scheduled messaging handler"""

import asyncio
import logging
from datetime import datetime

from telethon import Button, events

from ..core.mongo_database import mongodb
from ..utils.crypto_utils import DataEncryption

logger = logging.getLogger(__name__)


class ScheduledMessaging:
    def __init__(self, bot_manager):
        self.bot = bot_manager.bot
        self.bot_manager = bot_manager
        self.user_clients = bot_manager.user_clients
        self.scheduler_task = None

    def register_handlers(self):
        """Register scheduled messaging handlers"""
        self.bot.add_event_handler(
            self._show_schedule_menu, events.CallbackQuery(pattern=r"^schedule_msg$")
        )
        self.bot.add_event_handler(
            self._list_scheduled, events.CallbackQuery(pattern=r"^schedule_list$")
        )
        self.bot.add_event_handler(
            self._cancel_scheduled,
            events.CallbackQuery(pattern=r"^schedule_cancel:(.+)$"),
        )
        self.bot.add_event_handler(
            self._start_schedule_creation,
            events.CallbackQuery(pattern=r"^schedule_new$"),
        )
        self.bot.add_event_handler(
            self._select_schedule_account,
            events.CallbackQuery(pattern=r"^schedule_account:(.+)$"),
        )
        logger.info("Scheduled messaging handlers registered")

        # Start scheduler
        if not self.scheduler_task:
            self.scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def _start_schedule_creation(self, event):
        user_id = event.sender_id
        try:
            accounts = await mongodb.db.accounts.find(
                {"user_id": user_id, "is_active": True}
            ).to_list(length=None)
            if not accounts:
                await event.edit(
                    "⏰ **New Scheduled Message**\n\nNo active accounts are available.",
                    buttons=[[Button.inline("🔙 Back", "schedule_msg")]],
                )
                return

            buttons = []
            for account in accounts:
                account = DataEncryption.decrypt_account_data(account)
                buttons.append(
                    [
                        Button.inline(
                            account.get("name", "Account"),
                            f"schedule_account:{account['_id']}",
                        )
                    ]
                )
            buttons.append([Button.inline("🔙 Back", "schedule_msg")])
            await event.edit(
                "⏰ **New Scheduled Message**\n\nSelect the account to send from:",
                buttons=buttons,
            )
        except Exception:
            logger.exception("Failed to start scheduled-message creation")
            await event.answer("❌ Could not load accounts", alert=True)

    async def _select_schedule_account(self, event):
        user_id = event.sender_id
        account_id = event.pattern_match.group(1).decode()
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {
                    "_id": ObjectId(account_id),
                    "user_id": user_id,
                    "is_active": True,
                }
            )
            if not account:
                await event.answer("❌ Active account not found", alert=True)
                return

            account = DataEncryption.decrypt_account_data(account)
            account_name = account.get("name")
            if not account_name:
                await event.answer("❌ Account name is unavailable", alert=True)
                return

            self.bot_manager.pending_actions[user_id] = {
                "action": "schedule_recipient",
                "account_name": account_name,
            }
            await event.answer("📝 Enter the recipient")
            await self.bot.send_message(
                user_id, "📝 Reply with the username, phone, or chat ID:"
            )
        except Exception:
            logger.exception("Failed to select scheduled-message account")
            await event.answer("❌ Could not select account", alert=True)

    async def handle_pending_action(self, event, user_id: int, action: str, message: str):
        pending = self.bot_manager.pending_actions.get(user_id, {})
        value = message.strip()

        if action == "schedule_recipient":
            if not value:
                await event.reply("❌ Recipient cannot be empty. Enter a recipient:")
                return
            self.bot_manager.pending_actions[user_id] = {
                **pending,
                "action": "schedule_message",
                "recipient": value,
            }
            await event.reply("📝 Reply with the message content:")
            return

        if action == "schedule_message":
            if not value:
                await event.reply("❌ Message cannot be empty. Reply with the message:")
                return
            self.bot_manager.pending_actions[user_id] = {
                **pending,
                "action": "schedule_time",
                "message": value,
            }
            await event.reply(
                "⏰ Reply with the scheduled time in UTC as `YYYY-MM-DD HH:MM`:"
            )
            return

        if action == "schedule_time":
            try:
                scheduled_time = datetime.strptime(value, "%Y-%m-%d %H:%M")
            except ValueError:
                await event.reply("❌ Use UTC format `YYYY-MM-DD HH:MM`.")
                return
            if scheduled_time <= datetime.utcnow():
                await event.reply("❌ Scheduled time must be in the future.")
                return

            await mongodb.db.scheduled_messages.insert_one(
                {
                    "user_id": user_id,
                    "account_name": pending["account_name"],
                    "recipient": pending["recipient"],
                    "message": pending["message"],
                    "scheduled_time": scheduled_time,
                    "status": "pending",
                    "created_at": datetime.utcnow(),
                }
            )
            self.bot_manager.pending_actions.pop(user_id, None)
            await event.reply(
                f"✅ Message scheduled for {scheduled_time:%Y-%m-%d %H:%M} UTC."
            )

    async def _show_schedule_menu(self, event):
        """Show schedule menu"""
        buttons = [
            [Button.inline("📋 View Scheduled", "schedule_list")],
            [Button.inline("➕ New Schedule", "schedule_new")],
            [Button.inline("🔙 Back", "menu:messaging")],
        ]

        await event.edit(
            "⏰ **Scheduled Messaging**\n\n"
            "Schedule messages to be sent automatically at specific times.\n\n"
            "Select an option:",
            buttons=buttons,
        )

    async def _list_scheduled(self, event):
        """List scheduled messages"""
        user_id = event.sender_id

        try:
            scheduled = (
                await mongodb.db.scheduled_messages.find(
                    {"user_id": user_id, "status": "pending"}
                )
                .sort("scheduled_time", 1)
                .to_list(length=50)
            )

            if not scheduled:
                await event.edit(
                    "⏰ **Scheduled Messages**\n\n" "No scheduled messages.",
                    buttons=[[Button.inline("🔙 Back", "schedule_msg")]],
                )
                return

            text = "⏰ **Scheduled Messages**\n\n"
            buttons = []

            for msg in scheduled[:10]:
                time_str = msg["scheduled_time"].strftime("%Y-%m-%d %H:%M")
                recipient = msg.get("recipient", "Unknown")[:20]
                buttons.append(
                    [
                        Button.inline(
                            f"🗑️ {time_str} - {recipient}",
                            f"schedule_cancel:{msg['_id']}",
                        )
                    ]
                )

            buttons.append([Button.inline("🔙 Back", "schedule_msg")])

            await event.edit(
                text + f"Total: {len(scheduled)} messages\n\nClick to cancel:",
                buttons=buttons,
            )
        except Exception as e:
            logger.error(f"List scheduled error: {e}")
            await event.answer("❌ Error loading scheduled messages", alert=True)

    async def _cancel_scheduled(self, event):
        """Cancel scheduled message"""
        user_id = event.sender_id
        msg_id = event.pattern_match.group(1).decode()

        try:
            from bson import ObjectId

            result = await mongodb.db.scheduled_messages.update_one(
                {"_id": ObjectId(msg_id), "user_id": user_id},
                {"$set": {"status": "cancelled"}},
            )

            if result.modified_count > 0:
                await event.answer("✅ Scheduled message cancelled", alert=True)
            else:
                await event.answer("❌ Message not found", alert=True)

            await self._list_scheduled(event)
        except Exception as e:
            logger.error(f"Cancel scheduled error: {e}")
            await event.answer("❌ Error cancelling message", alert=True)

    async def _scheduler_loop(self):
        """Background scheduler loop"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                now = datetime.utcnow()
                due_messages = await mongodb.db.scheduled_messages.find(
                    {"status": "pending", "scheduled_time": {"$lte": now}}
                ).to_list(length=100)

                for msg in due_messages:
                    await self._send_scheduled_message(msg)
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")

    async def _send_scheduled_message(self, msg_data):
        """Send a scheduled message"""
        try:
            user_id = msg_data["user_id"]
            account_name = msg_data["account_name"]
            recipient = msg_data["recipient"]
            message = msg_data["message"]

            claim = await mongodb.db.scheduled_messages.update_one(
                {"_id": msg_data["_id"], "status": "pending"},
                {"$set": {"status": "sending", "attempted_at": datetime.utcnow()}},
            )
            if claim.modified_count != 1:
                return

            client = self.user_clients.get(user_id, {}).get(account_name)
            if not client:
                logger.error("Client not found for scheduled message")
                await mongodb.db.scheduled_messages.update_one(
                    {"_id": msg_data["_id"], "status": "sending"},
                    {"$set": {"status": "pending"}},
                )
                return

            await client.send_message(recipient, message)

            await mongodb.db.scheduled_messages.update_one(
                {"_id": msg_data["_id"], "status": "sending"},
                {"$set": {"status": "sent", "sent_time": datetime.utcnow()}},
            )
            try:
                account = await mongodb.db.accounts.find_one(
                    {"user_id": user_id, "name": account_name}
                )
                if account:
                    from ..services.messaging_stats import MessagingStats

                    await MessagingStats().record_message_sent(
                        user_id,
                        str(account["_id"]),
                        recipient,
                        "scheduled",
                    )
            except Exception:
                logger.exception(
                    "Scheduled message sent but its statistics could not be recorded"
                )

            await self.bot.send_message(
                user_id, f"✅ Scheduled message sent to {recipient}"
            )
        except Exception as e:
            logger.error(f"Send scheduled message error: {e}")
            await mongodb.db.scheduled_messages.update_one(
                {"_id": msg_data["_id"], "status": "sending"},
                {"$set": {"status": "failed", "error": str(e)}},
            )
