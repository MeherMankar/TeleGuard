"""Admin command handlers"""

import logging

from telethon import events

from ..core.database import get_session
from ..core.models import User

logger = logging.getLogger(__name__)


class AdminHandlers:
    """Handles admin-only commands"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.session_scheduler = bot_manager.session_scheduler

    def register_handlers(self):
        """Register admin command handlers"""

        @self.bot.on(events.NewMessage(pattern=r"/backup_now"))
        async def backup_now_handler(event):
            user_id = event.sender_id

            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(User).where(User.telegram_id == user_id)
                )
                user = result.scalar_one_or_none()
                if not user or not user.is_admin:
                    await event.reply("❌ Admin access required")
                    return

            if not self.session_scheduler:
                await event.reply("❌ Session backup not enabled")
                return

            await event.reply("🔄 Triggering manual session backup...")

            try:
                self.session_scheduler.trigger_push_now()
                await event.reply("✅ Manual backup job queued")
            except Exception as e:
                await event.reply(f"❌ Failed to trigger backup: {e}")

        @self.bot.on(events.NewMessage(pattern=r"/compact_now"))
        async def compact_now_handler(event):
            user_id = event.sender_id

            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(User).where(User.telegram_id == user_id)
                )
                user = result.scalar_one_or_none()
                if not user or not user.is_admin:
                    await event.reply("❌ Admin access required")
                    return

            if not self.session_scheduler:
                await event.reply("❌ Session backup not enabled")
                return

            await event.reply(
                "⚠️ Triggering history compaction (destructive operation)..."
            )

            try:
                self.session_scheduler.trigger_compact_now()
                await event.reply("✅ History compaction job queued")
            except Exception as e:
                await event.reply(f"❌ Failed to trigger compaction: {e}")

        @self.bot.on(events.NewMessage(pattern=r"/topic_status"))
        async def topic_status_handler(event):
            user_id = event.sender_id

            if user_id not in self.topic_routers:
                await event.reply("❌ Topic routing not configured for your account")
                return

            try:
                router = self.topic_routers[user_id]
                status = await router.get_status()

                status_text = f"""
🔄 **Your Topic Routing Status**

Running: {'✅' if status['running'] else '❌'}
Manager Forum: {status['manager_forum_chat_id']}
Managed Accounts: {len(status['managed_accounts'])}

**Accounts:**
"""

                for account_id in status["managed_accounts"]:
                    queue_length = status["queue_lengths"].get(account_id, 0)
                    status_text += f"• {account_id}: {queue_length} queued messages\\n"

                await event.reply(status_text)

            except Exception as e:
                await event.reply(f"❌ Failed to get status: {e}")

        @self.bot.on(events.NewMessage(pattern=r"/debug_topics"))
        async def debug_topics_handler(event):
            user_id = event.sender_id

            if user_id not in self.topic_routers:
                await event.reply("❌ No topic router found for your account")
                return

            try:
                router = self.topic_routers[user_id]
                status = await router.get_status()

                debug_text = f"""
🔍 **Debug: Topic Routing Status**

Running: {status['running']}
Forum ID: {status['manager_forum_chat_id']}
Managed Accounts: {len(status['managed_accounts'])}

**Accounts with Listeners:**
"""

                for account_id in status["managed_accounts"]:
                    has_listener = account_id in router.inbound_listeners
                    has_worker = account_id in router.sender_workers
                    debug_text += f"• {account_id}: Listener={has_listener}, Worker={has_worker}\\n"

                if user_id in self.bot_manager.user_clients:
                    debug_text += f"\\n**User Clients:** {list(self.bot_manager.user_clients[user_id].keys())}\\n"
                else:
                    debug_text += f"\\n**User Clients:** None found\\n"

                await event.reply(debug_text)

            except Exception as e:
                await event.reply(f"❌ Debug error: {e}")
