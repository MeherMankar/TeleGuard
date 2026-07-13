"""
Media Dump Handler
==================
Admin command to dump all DB-tracked media (photos/videos) from a source
chat into a destination Telegram channel, organised per category.

Supports:
• Forum topics per category  (when target is a supergroup with Topics enabled)
• Flat channel dump          (one category per message batch, no topics)
• Per-user or global dump    (admin can target any user's saved media)
• Pause / resume             (state saved in MongoDB)
• Rate-limited sending       (flood-safe)

Commands
--------
/dump                  – interactive wizard (private chat with bot)
/dump_status           – show all running/paused dump jobs
/dump_cancel <job_id>  – cancel a specific dump job

DB schema – collection: ``media_dump_jobs``
{
    "_id":          ObjectId,
    "job_id":       str  (short UUID),
    "admin_id":     int,
    "target_user":  int  (whose media to dump, None = all users),
    "source_chat":  int | None (None = Saved Messages),
    "dest_channel": int,
    "use_topics":   bool,
    "categories":   list[str]  ([] = all),
    "status":       "pending"|"running"|"paused"|"done"|"cancelled",
    "last_offset":  int  (last processed media _id, for resume),
    "sent":         int,
    "skipped":      int,
    "failed":       int,
    "created_at":   datetime,
    "updated_at":   datetime,
}

DB schema – collection: ``media_index``
{
    "_id":          ObjectId,
    "user_id":      int,
    "file_id":      str,
    "file_unique":  str,
    "media_type":   "photo"|"video"|"document"|"animation",
    "category":     str,
    "source_chat":  int,
    "message_id":   int,
    "caption":      str | None,
    "saved_at":     datetime,
}
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from telethon import Button, events
from telethon.errors import FloodWaitError

from ..core.mongo_database import mongodb
from ..utils.authorization import admin_required

logger = logging.getLogger(__name__)

# ── constants ──────────────────────────────────────────────────────────────────
BATCH_SIZE = 20          # media items per DB query page
SEND_DELAY = 0.8         # seconds between each send (flood safety)
CATEGORY_DELAY = 2.0     # seconds between categories
PROGRESS_EVERY = 25      # send a progress update every N items


# ── helper ─────────────────────────────────────────────────────────────────────

def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── main class ─────────────────────────────────────────────────────────────────

class DumpHandler:
    """Handles the /dump family of commands."""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        # job_id -> asyncio.Task
        self._running: dict[str, asyncio.Task] = {}

    # ── registration ───────────────────────────────────────────────────────────

    def register_handlers(self):
        self.bot.on(events.NewMessage(pattern=r"^/dump$"))(
            admin_required(self._cmd_dump)
        )
        self.bot.on(events.NewMessage(pattern=r"^/dump_status$"))(
            admin_required(self._cmd_dump_status)
        )
        self.bot.on(events.NewMessage(pattern=r"^/dump_cancel\s+(\S+)$"))(
            admin_required(self._cmd_dump_cancel)
        )
        # Callback buttons from the wizard
        self.bot.on(events.CallbackQuery(pattern=rb"^dump:"))(
            self._cb_dump
        )

    # ── /dump wizard ───────────────────────────────────────────────────────────

    async def _cmd_dump(self, event):
        """Entry point — show interactive wizard."""
        categories = await self._get_distinct_categories()
        cat_text = "\n".join(f"  • `{c}`" for c in categories) if categories else "  _none yet_"

        text = (
            "📦 **Media Dump Wizard**\n\n"
            "This will forward all indexed media to a channel, organised by category.\n\n"
            f"**Available categories ({len(categories)}):**\n{cat_text}\n\n"
            "**Step 1** — Choose what to dump:"
        )
        buttons = [
            [Button.inline("📂 All categories", b"dump:all_cats")],
            [Button.inline("🗂 Pick a category", b"dump:pick_cat")],
            [Button.inline("❌ Cancel", b"dump:cancel_wizard")],
        ]
        await event.reply(text, buttons=buttons)

    async def _cb_dump(self, event):
        """Handle all dump: callback queries from the wizard."""
        data = event.data.decode()
        parts = data.split(":", 2)          # ["dump", action, *extra]
        action = parts[1] if len(parts) > 1 else ""
        extra  = parts[2] if len(parts) > 2 else ""
        admin_id = event.sender_id

        if action == "cancel_wizard":
            await event.edit("❌ Dump wizard cancelled.")
            return

        if action == "all_cats":
            await self._wizard_ask_destination(event, admin_id, categories=[])
            return

        if action == "pick_cat":
            categories = await self._get_distinct_categories()
            if not categories:
                await event.edit("❌ No categories found in the media index.")
                return
            buttons = [
                [Button.inline(c, f"dump:cat_sel:{c}".encode())]
                for c in categories[:20]   # Telegram button limit safety
            ]
            buttons.append([Button.inline("❌ Cancel", b"dump:cancel_wizard")])
            await event.edit("🗂 **Select a category to dump:**", buttons=buttons)
            return

        if action == "cat_sel":
            await self._wizard_ask_destination(event, admin_id, categories=[extra])
            return

        if action == "dest_saved":
            # extra = "all_cats" or a category name stored in pending state
            job_meta = await self._get_pending_wizard(admin_id)
            if not job_meta:
                await event.edit("❌ Session expired. Please run /dump again.")
                return
            await self._wizard_ask_topics(event, admin_id, job_meta, source_chat=None)
            return

        if action == "dest_chat":
            job_meta = await self._get_pending_wizard(admin_id)
            if not job_meta:
                await event.edit("❌ Session expired. Please run /dump again.")
                return
            await event.edit(
                "💬 **Enter the source chat ID or username** (the chat whose media to dump):\n\n"
                "Reply with the chat ID (e.g. `-1001234567890`) or username (`@mychannel`)."
            )
            await self._store_pending_wizard(admin_id, {**job_meta, "awaiting": "source_chat"})
            return

        if action == "topics_yes":
            job_meta = await self._get_pending_wizard(admin_id)
            if not job_meta:
                await event.edit("❌ Session expired. Please run /dump again.")
                return
            await self._wizard_ask_channel(event, admin_id, {**job_meta, "use_topics": True})
            return

        if action == "topics_no":
            job_meta = await self._get_pending_wizard(admin_id)
            if not job_meta:
                await event.edit("❌ Session expired. Please run /dump again.")
                return
            await self._wizard_ask_channel(event, admin_id, {**job_meta, "use_topics": False})
            return

        if action == "confirm":
            job_meta = await self._get_pending_wizard(admin_id)
            if not job_meta:
                await event.edit("❌ Session expired. Please run /dump again.")
                return
            await self._start_dump_job(event, admin_id, job_meta)
            return

        if action == "cancel_job":
            job_id = extra
            await self._cancel_job(event, admin_id, job_id)
            return

    # ── wizard steps ───────────────────────────────────────────────────────────

    async def _wizard_ask_destination(self, event, admin_id: int, categories: list):
        await self._store_pending_wizard(admin_id, {"categories": categories})
        cat_label = ", ".join(categories) if categories else "all categories"
        buttons = [
            [Button.inline("💾 Saved Messages", b"dump:dest_saved")],
            [Button.inline("💬 Specific chat/channel", b"dump:dest_chat")],
            [Button.inline("❌ Cancel", b"dump:cancel_wizard")],
        ]
        await event.edit(
            f"📦 **Dump: {cat_label}**\n\n**Step 2** — Where is the media stored?",
            buttons=buttons,
        )

    async def _wizard_ask_topics(self, event, admin_id: int, job_meta: dict, source_chat):
        meta = {**job_meta, "source_chat": source_chat}
        await self._store_pending_wizard(admin_id, meta)
        buttons = [
            [Button.inline("✅ Yes — use forum topics", b"dump:topics_yes")],
            [Button.inline("❌ No — flat channel", b"dump:topics_no")],
            [Button.inline("↩️ Cancel", b"dump:cancel_wizard")],
        ]
        await event.edit(
            "📦 **Step 3** — Does the destination channel use **Forum Topics**?\n\n"
            "If yes, each category will be sent to its own topic.\n"
            "If no, category headers will be sent as text separators.",
            buttons=buttons,
        )

    async def _wizard_ask_channel(self, event, admin_id: int, job_meta: dict):
        await self._store_pending_wizard(admin_id, {**job_meta, "awaiting": "dest_channel"})
        await event.edit(
            "📦 **Step 4** — Send the **destination channel ID** (where to dump media):\n\n"
            "Example: `-1001234567890`\n\n"
            "The bot must be an **admin** in that channel."
        )

    # ── text message continuation (for wizard chat input steps) ────────────────

    def register_text_listener(self):
        """Called once after __init__ to attach the freeform text handler."""
        self.bot.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))(
            self._handle_wizard_text
        )

    async def _handle_wizard_text(self, event):
        """Handle free-text replies during the dump wizard flow."""
        from ..core.config import ADMIN_IDS
        if event.sender_id not in ADMIN_IDS:
            return
        admin_id = event.sender_id
        job_meta = await self._get_pending_wizard(admin_id)
        if not job_meta or "awaiting" not in job_meta:
            return

        awaiting = job_meta.pop("awaiting")
        text = (event.text or "").strip()

        if awaiting == "source_chat":
            try:
                source_chat = int(text) if text.lstrip("-").isdigit() else text
                await self._store_pending_wizard(admin_id, {**job_meta, "source_chat": source_chat})
                buttons = [
                    [Button.inline("✅ Yes — forum topics", b"dump:topics_yes")],
                    [Button.inline("❌ No — flat", b"dump:topics_no")],
                ]
                await event.reply(
                    f"✅ Source chat set to `{source_chat}`\n\n"
                    "**Step 3** — Does the destination channel use **Forum Topics**?",
                    buttons=buttons,
                )
            except Exception:
                await event.reply("❌ Invalid chat ID. Please try again or run /dump to restart.")
            return

        if awaiting == "dest_channel":
            try:
                dest_channel = int(text) if text.lstrip("-").isdigit() else text
                meta = {**job_meta, "dest_channel": dest_channel}
                await self._store_pending_wizard(admin_id, meta)
                # Show confirmation
                await self._show_confirmation(event, admin_id, meta)
            except Exception:
                await event.reply("❌ Invalid channel ID. Please try again.")
            return

    async def _show_confirmation(self, event, admin_id: int, meta: dict):
        cats = ", ".join(meta.get("categories") or []) or "all"
        src  = meta.get("source_chat") or "Saved Messages"
        dst  = meta.get("dest_channel", "?")
        topics = "Yes" if meta.get("use_topics") else "No"
        total = await self._count_media(
            categories=meta.get("categories"),
            source_chat=meta.get("source_chat"),
        )
        job_id = _short_id()
        await self._store_pending_wizard(admin_id, {**meta, "job_id": job_id})
        buttons = [
            [Button.inline("🚀 Start dump", b"dump:confirm")],
            [Button.inline("❌ Cancel", b"dump:cancel_wizard")],
        ]
        await event.reply(
            f"📦 **Confirm Dump**\n\n"
            f"• Categories: `{cats}`\n"
            f"• Source: `{src}`\n"
            f"• Destination: `{dst}`\n"
            f"• Forum topics: `{topics}`\n"
            f"• **Total media items:** `{total}`\n\n"
            "Ready to start?",
            buttons=buttons,
        )

    # ── job execution ──────────────────────────────────────────────────────────

    async def _start_dump_job(self, event, admin_id: int, meta: dict):
        """Create a DB job record and launch the async worker."""
        job_id = meta.get("job_id") or _short_id()
        categories = meta.get("categories") or []
        source_chat = meta.get("source_chat")
        dest_channel = meta.get("dest_channel")
        use_topics = meta.get("use_topics", False)

        if not dest_channel:
            await event.edit("❌ Destination channel not set. Please run /dump again.")
            return

        job_doc = {
            "job_id": job_id,
            "admin_id": admin_id,
            "source_chat": source_chat,
            "dest_channel": dest_channel,
            "use_topics": use_topics,
            "categories": categories,
            "status": "running",
            "last_offset": None,
            "sent": 0,
            "skipped": 0,
            "failed": 0,
            "created_at": _now(),
            "updated_at": _now(),
        }
        await mongodb.db.media_dump_jobs.insert_one(job_doc)
        await self._clear_pending_wizard(admin_id)

        task = asyncio.create_task(
            self._dump_worker(job_id, admin_id, job_doc),
            name=f"dump-{job_id}",
        )
        self._running[job_id] = task

        await event.edit(
            f"🚀 **Dump job `{job_id}` started!**\n\n"
            f"I'll send progress updates here.\n"
            f"Use `/dump_cancel {job_id}` to stop."
        )

    async def _dump_worker(self, job_id: str, admin_id: int, job: dict):
        """Background worker that streams media to the destination channel."""
        dest = job["dest_channel"]
        use_topics = job["use_topics"]
        categories = job["categories"] or await self._get_distinct_categories()
        source_chat = job.get("source_chat")

        # Resolve destination entity once
        try:
            dest_entity = await self.bot.get_entity(dest)
        except Exception as e:
            await self._finish_job(job_id, admin_id, "failed", f"Cannot access destination: {e}")
            return

        # topic_map: category -> topic_id (created on demand)
        topic_map: dict[str, int] = {}
        sent = job.get("sent", 0)
        skipped = job.get("skipped", 0)
        failed = job.get("failed", 0)

        for category in categories:
            # Check cancellation
            if not await self._is_running(job_id):
                return

            # Resolve or create topic
            topic_id: Optional[int] = None
            if use_topics:
                topic_id = await self._get_or_create_topic(dest_entity, category, topic_map)

            # Send category header (flat mode)
            if not use_topics:
                try:
                    await self.bot.send_message(
                        dest_entity,
                        f"━━━━━━━━━━━━━━━━━━━━\n📂 **Category: {category}**\n━━━━━━━━━━━━━━━━━━━━",
                    )
                except Exception:
                    pass

            # Stream media in batches
            offset_id = job.get("last_offset")
            query: dict = {"category": category}
            if source_chat is not None:
                query["source_chat"] = int(source_chat) if str(source_chat).lstrip("-").isdigit() else source_chat
            if offset_id:
                query["_id"] = {"$gt": ObjectId(offset_id)}

            cursor = mongodb.db.media_index.find(query).sort("_id", 1)

            async for media_doc in cursor:
                if not await self._is_running(job_id):
                    return

                success = await self._send_media_item(
                    media_doc, dest_entity, topic_id
                )
                if success:
                    sent += 1
                else:
                    failed += 1

                # Persist progress
                await mongodb.db.media_dump_jobs.update_one(
                    {"job_id": job_id},
                    {"$set": {
                        "last_offset": str(media_doc["_id"]),
                        "sent": sent,
                        "skipped": skipped,
                        "failed": failed,
                        "updated_at": _now(),
                    }},
                )

                # Progress notification
                if (sent + failed) % PROGRESS_EVERY == 0:
                    await self.bot.send_message(
                        admin_id,
                        f"📊 Dump `{job_id}` — category **{category}**\n"
                        f"✅ Sent: {sent}  ❌ Failed: {failed}",
                    )

                await asyncio.sleep(SEND_DELAY)

            await asyncio.sleep(CATEGORY_DELAY)

        await self._finish_job(
            job_id, admin_id, "done",
            f"✅ Dump `{job_id}` complete!\n\n"
            f"• Sent: {sent}\n• Failed: {failed}\n• Skipped: {skipped}",
        )

    async def _send_media_item(self, doc: dict, dest_entity, topic_id: Optional[int]) -> bool:
        """Send a single media item to the destination. Returns True on success."""
        file_id = doc.get("file_id")
        caption = doc.get("caption") or ""
        if not file_id:
            return False

        kwargs: dict = {}
        if topic_id:
            kwargs["reply_to"] = topic_id

        for attempt in range(3):
            try:
                await self.bot.send_file(
                    dest_entity,
                    file=file_id,
                    caption=caption or None,
                    **kwargs,
                )
                return True
            except FloodWaitError as e:
                logger.warning(f"FloodWait {e.seconds}s during dump")
                await asyncio.sleep(e.seconds + 1)
            except Exception as e:
                if attempt == 2:
                    logger.warning(f"Failed to send media {file_id}: {e}")
                    return False
                await asyncio.sleep(2 ** attempt)
        return False

    # ── topic management ───────────────────────────────────────────────────────

    async def _get_or_create_topic(
        self, dest_entity, category: str, topic_map: dict
    ) -> Optional[int]:
        """Return (and cache) the topic_id for a category, creating it if needed."""
        if category in topic_map:
            return topic_map[category]

        # Verify forum is enabled
        is_forum = getattr(dest_entity, "forum", False)
        if not is_forum:
            logger.warning(
                f"Destination {dest_entity.id} doesn't have topics — "
                "falling back to flat mode for this category"
            )
            return None

        try:
            from telethon.tl.functions.channels import CreateForumTopicRequest
            result = await self.bot(
                CreateForumTopicRequest(
                    channel=dest_entity,
                    title=f"📂 {category}",
                )
            )
            # The first message in the topic IS the topic header
            topic_id = result.updates[0].id if result.updates else None
            if topic_id:
                topic_map[category] = topic_id
                logger.info(f"Created topic '{category}' → id={topic_id}")
                return topic_id
        except Exception as e:
            logger.warning(f"Could not create topic for '{category}': {e}")
        return None

    # ── /dump_status ───────────────────────────────────────────────────────────

    async def _cmd_dump_status(self, event):
        jobs = await mongodb.db.media_dump_jobs.find(
            {"admin_id": event.sender_id}
        ).sort("created_at", -1).limit(10).to_list(None)

        if not jobs:
            await event.reply("📭 No dump jobs found.")
            return

        lines = ["📦 **Recent Dump Jobs**\n"]
        for j in jobs:
            icon = {"running": "🔄", "done": "✅", "cancelled": "🛑", "failed": "❌", "paused": "⏸"}.get(j["status"], "❓")
            cats = ", ".join(j.get("categories") or []) or "all"
            lines.append(
                f"{icon} `{j['job_id']}` — {j['status']}\n"
                f"   cats={cats} | sent={j.get('sent',0)} | failed={j.get('failed',0)}\n"
            )

        running_ids = list(self._running.keys())
        if running_ids:
            lines.append(f"\n⚡ Active tasks: {', '.join(f'`{x}`' for x in running_ids)}")

        await event.reply("\n".join(lines))

    # ── /dump_cancel ───────────────────────────────────────────────────────────

    async def _cmd_dump_cancel(self, event):
        job_id = event.pattern_match.group(1)
        await self._cancel_job(event, event.sender_id, job_id)

    async def _cancel_job(self, event_or_none, admin_id: int, job_id: str):
        task = self._running.pop(job_id, None)
        if task:
            task.cancel()
        await mongodb.db.media_dump_jobs.update_one(
            {"job_id": job_id, "admin_id": admin_id},
            {"$set": {"status": "cancelled", "updated_at": _now()}},
        )
        msg = f"🛑 Dump job `{job_id}` cancelled."
        if event_or_none is not None:
            try:
                await event_or_none.edit(msg)
            except Exception:
                await event_or_none.reply(msg)
        else:
            await self.bot.send_message(admin_id, msg)

    # ── internal helpers ───────────────────────────────────────────────────────

    async def _get_distinct_categories(self) -> list[str]:
        try:
            return await mongodb.db.media_index.distinct("category")
        except Exception:
            return []

    async def _count_media(
        self,
        categories: Optional[list] = None,
        source_chat=None,
    ) -> int:
        query: dict = {}
        if categories:
            query["category"] = {"$in": categories}
        if source_chat is not None:
            query["source_chat"] = source_chat
        try:
            return await mongodb.db.media_index.count_documents(query)
        except Exception:
            return 0

    async def _is_running(self, job_id: str) -> bool:
        """Return False if the job has been cancelled externally."""
        doc = await mongodb.db.media_dump_jobs.find_one({"job_id": job_id})
        if not doc:
            return False
        return doc.get("status") == "running"

    async def _finish_job(self, job_id: str, admin_id: int, status: str, msg: str):
        self._running.pop(job_id, None)
        await mongodb.db.media_dump_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": status, "updated_at": _now()}},
        )
        try:
            await self.bot.send_message(admin_id, msg)
        except Exception:
            pass

    # ── wizard state (short-lived, stored in memory via Redis-like pattern) ────
    # We use a dedicated MongoDB collection for simplicity & persistence.

    async def _store_pending_wizard(self, admin_id: int, data: dict):
        await mongodb.db.dump_wizard_state.update_one(
            {"admin_id": admin_id},
            {"$set": {"admin_id": admin_id, "data": data, "updated_at": _now()}},
            upsert=True,
        )

    async def _get_pending_wizard(self, admin_id: int) -> Optional[dict]:
        doc = await mongodb.db.dump_wizard_state.find_one({"admin_id": admin_id})
        return doc["data"] if doc else None

    async def _clear_pending_wizard(self, admin_id: int):
        await mongodb.db.dump_wizard_state.delete_one({"admin_id": admin_id})
