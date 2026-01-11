"""Scheduled messaging handler"""

import asyncio
import logging
from datetime import datetime

from telethon import Button, events

from ..core.mongo_database import mongodb

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
        logger.info("Scheduled messaging handlers registered")

        # Start scheduler
        if not self.scheduler_task:
            self.scheduler_task = asyncio.create_task(self._scheduler_loop())

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

            client = self.user_clients.get(user_id, {}).get(account_name)
            if not client:
                logger.error(f"Client not found for scheduled message")
                return

            await client.send_message(recipient, message)

            await mongodb.db.scheduled_messages.update_one(
                {"_id": msg_data["_id"]},
                {"$set": {"status": "sent", "sent_time": datetime.utcnow()}},
            )

            await self.bot.send_message(
                user_id, f"✅ Scheduled message sent to {recipient}"
            )
        except Exception as e:
            logger.error(f"Send scheduled message error: {e}")
            await mongodb.db.scheduled_messages.update_one(
                {"_id": msg_data["_id"]},
                {"$set": {"status": "failed", "error": str(e)}},
            )
