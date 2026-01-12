"""Consolidated Admin Handlers for TeleGuard"""

import logging

from telethon import events

from ..core.database_manager import db_manager
from ..utils.cache_decorators import CacheManager

logger = logging.getLogger(__name__)


class AdminHandlers:
    """Handles all admin-only commands"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.session_scheduler = bot_manager.session_scheduler

    def register_handlers(self):
        """Register admin command handlers"""
        self._register_backup_handlers()
        self._register_cache_handlers()
        self._register_status_handlers()

    def _register_backup_handlers(self):
        """Register backup-related handlers"""
        self.bot.on(events.NewMessage(pattern=r"/backup_now"))(self._handle_backup_now)
        self.bot.on(events.NewMessage(pattern=r"/backup_settings"))(self._handle_backup_settings)
        self.bot.on(events.NewMessage(pattern=r"/backup_ids"))(self._handle_backup_ids)
        self.bot.on(events.NewMessage(pattern=r"/backup_sessions"))(self._handle_backup_sessions)
        self.bot.on(events.NewMessage(pattern=r"/test_backup"))(self._handle_test_backup)
        self.bot.on(events.NewMessage(pattern=r"/backup_all"))(self._handle_backup_all)
        self.bot.on(events.NewMessage(pattern=r"/migrate_encrypt_data"))(self._handle_migrate_encrypt)

    def _register_cache_handlers(self):
        """Register cache-related handlers"""
        self.bot.on(events.NewMessage(pattern=r"/cache_stats"))(self._handle_cache_stats)
        self.bot.on(events.NewMessage(pattern=r"/cache_warm (\d+)"))(self._handle_cache_warm)
        self.bot.on(events.NewMessage(pattern=r"/cache_clear"))(self._handle_cache_clear)
        self.bot.on(events.NewMessage(pattern=r"/cache_health"))(self._handle_cache_health)

    def _register_status_handlers(self):
        """Register status-related handlers"""
        self.bot.on(events.NewMessage(pattern=r"/backup_status"))(self._handle_backup_status)

    async def _check_admin(self, event):
        """Check if user is admin"""
        from ..core.config import ADMIN_IDS
        if event.sender_id not in ADMIN_IDS:
            await event.reply("❌ Admin access required")
            return False
        return True

    async def _check_backup_config(self, event):
        """Check if backup is configured"""
        from ..core.config import TELEGRAM_BACKUP_CHANNEL
        if not TELEGRAM_BACKUP_CHANNEL:
            await event.reply("❌ Telegram backup channel not configured")
            return False
        return True

    async def _handle_backup_now(self, event):
        if not await self._check_admin(event):
            return
        await event.reply("🔄 Starting manual backup...")
        try:
            if not await self._check_backup_config(event):
                return
            from ..utils.backups import TelegramBackup
            backup = TelegramBackup(self.bot)
            await backup.backup_user_settings()
            await event.reply("✅ Manual backup completed")
        except Exception as e:
            await event.reply(f"❌ Backup failed: {str(e)}")

    async def _handle_backup_settings(self, event):
        if not await self._check_admin(event):
            return
        await event.reply("🔄 Backing up user settings...")
        try:
            if not await self._check_backup_config(event):
                return
            from ..utils.backups import TelegramBackup
            backup = TelegramBackup(self.bot)
            await backup.backup_user_settings()
            await event.reply("✅ User settings backup completed")
        except Exception as e:
            await event.reply(f"❌ Settings backup failed: {str(e)}")

    async def _handle_backup_ids(self, event):
        if not await self._check_admin(event):
            return
        await event.reply("🔄 Backing up user IDs...")
        try:
            if not await self._check_backup_config(event):
                return
            from ..utils.backups import TelegramBackup
            backup = TelegramBackup(self.bot)
            await backup.backup_user_ids()
            await event.reply("✅ User IDs backup completed")
        except Exception as e:
            await event.reply(f"❌ IDs backup failed: {str(e)}")

    async def _handle_backup_sessions(self, event):
        if not await self._check_admin(event):
            return
        await event.reply("🔄 Backing up session files...")
        try:
            if not await self._check_backup_config(event):
                return
            from ..utils.backups import TelegramBackup
            backup = TelegramBackup(self.bot)
            await backup.backup_session_files()
            await event.reply("✅ Session files backup completed")
        except Exception as e:
            await event.reply(f"❌ Session backup failed: {str(e)}")

    async def _handle_test_backup(self, event):
        if not await self._check_admin(event):
            return
        await event.reply("🔄 Testing backup system...")
        try:
            from ..core.config import TELEGRAM_BACKUP_CHANNEL
            if not TELEGRAM_BACKUP_CHANNEL:
                await event.reply("❌ Telegram backup channel not configured")
                return
            channel_id = int(TELEGRAM_BACKUP_CHANNEL)
            test_message = f"🧪 Backup test from TeleGuard\nTimestamp: {__import__('datetime').datetime.now()}"
            await self.bot.send_message(channel_id, test_message)
            await event.reply(f"✅ Backup test successful!\nChannel: {TELEGRAM_BACKUP_CHANNEL}")
        except Exception as e:
            await event.reply(f"❌ Backup test failed: {str(e)}")

    async def _handle_backup_all(self, event):
        if not await self._check_admin(event):
            return
        await event.reply("🔄 Starting complete backup...")
        try:
            if not await self._check_backup_config(event):
                return
            from ..utils.backups import TelegramBackup
            backup = TelegramBackup(self.bot)
            await backup.backup_user_settings()
            await backup.backup_user_ids()
            await backup.backup_session_files()
            await event.reply("✅ Complete backup finished:\n• User settings backed up\n• User IDs backed up\n• Session files backed up")
        except Exception as e:
            await event.reply(f"❌ Complete backup failed: {str(e)}")

    async def _handle_migrate_encrypt(self, event):
        if not await self._check_admin(event):
            return
        await event.reply("🔄 Starting data encryption migration...")
        try:
            from ..core.mongo_database import mongodb
            from ..utils.data_encryption import DataEncryption
            users = await mongodb.db.users.find({}).to_list(length=None)
            user_count = 0
            for user in users:
                if not any(key.endswith("_enc") for key in user.keys()):
                    encrypted_data = DataEncryption.encrypt_user_data(user)
                    await mongodb.db.users.replace_one({"_id": user["_id"]}, encrypted_data)
                    user_count += 1
            accounts = await mongodb.db.accounts.find({}).to_list(length=None)
            account_count = 0
            for account in accounts:
                if not any(key.endswith("_enc") for key in account.keys()):
                    encrypted_data = DataEncryption.encrypt_account_data(account)
                    await mongodb.db.accounts.replace_one({"_id": account["_id"]}, encrypted_data)
                    account_count += 1
            await event.reply(f"✅ Migration completed!\n\n📊 **Results:**\n• Users migrated: {user_count}\n• Accounts migrated: {account_count}\n\n🔒 All user data is now encrypted")
        except Exception as e:
            await event.reply(f"❌ Migration failed: {str(e)}")
            logger.error(f"Data encryption migration failed: {e}", exc_info=True)

    async def _handle_cache_stats(self, event):
        if not await self._check_admin(event):
            return
        try:
            stats = await db_manager.get_cache_stats()
            if not stats:
                await event.reply("❌ Cache statistics unavailable (Redis disconnected)")
                return
            message = "📊 **Cache Performance Statistics**\n\n"
            message += f"🔹 **Memory Used:** {stats.get('memory_used', 'N/A')}\n"
            message += f"🔹 **Memory Peak:** {stats.get('memory_peak', 'N/A')}\n"
            message += f"🔹 **Connected Clients:** {stats.get('connected_clients', 0)}\n"
            message += f"🔹 **Total Commands:** {stats.get('total_commands_processed', 0)}\n\n"
            top_hits = stats.get("top_cache_hits", {})
            if top_hits:
                message += "🔥 **Top Cache Hits:**\n"
                for key, hits in list(top_hits.items())[:5]:
                    message += f"   • `{key}`: {hits} hits\n"
            else:
                message += "📝 No cache hit data available\n"
            performance = await CacheManager.get_cache_performance()
            recommendations = performance.get("recommendations", [])
            if recommendations:
                message += "\n💡 **Recommendations:**\n"
                for rec in recommendations:
                    message += f"   • {rec}\n"
            await event.reply(message)
        except Exception as e:
            await event.reply(f"❌ Error getting cache stats: {str(e)}")

    async def _handle_cache_warm(self, event):
        if not await self._check_admin(event):
            return
        try:
            target_user_id = int(event.pattern_match.group(1))
            await event.reply(f"🔄 Warming cache for user {target_user_id}...")
            await CacheManager.warm_user_cache(target_user_id)
            await event.reply(f"✅ Cache warmed successfully for user {target_user_id}")
        except ValueError:
            await event.reply("❌ Invalid user ID. Please provide a numeric user ID.")
        except Exception as e:
            await event.reply(f"❌ Error warming cache: {str(e)}")

    async def _handle_cache_clear(self, event):
        if not await self._check_admin(event):
            return
        await event.reply("⚠️ **WARNING**: This will clear ALL cache data!\n\nReply with 'CONFIRM' to proceed.")
        async def confirmation_handler(confirm_event):
            if confirm_event.sender_id == event.sender_id and confirm_event.text == "CONFIRM":
                try:
                    await db_manager.redis.flush_all()
                    await confirm_event.reply("✅ Cache cleared successfully!")
                except Exception as e:
                    await confirm_event.reply(f"❌ Error clearing cache: {str(e)}")
                self.bot.remove_event_handler(confirmation_handler)
            elif confirm_event.sender_id == event.sender_id:
                await confirm_event.reply("❌ Cache clear cancelled.")
                self.bot.remove_event_handler(confirmation_handler)
        self.bot.add_event_handler(confirmation_handler, events.NewMessage())

    async def _handle_cache_health(self, event):
        if not await self._check_admin(event):
            return
        try:
            health = await db_manager.health_check()
            message = "🏥 **Cache Health Status**\n\n"
            redis_status = "✅ Connected" if health.get("redis") else "❌ Disconnected"
            redis_ping = "✅ OK" if health.get("redis_ping") else "❌ Failed"
            message += f"🔹 **Redis Status:** {redis_status}\n"
            message += f"🔹 **Redis Ping:** {redis_ping}\n\n"
            mongo_status = "✅ Connected" if health.get("mongodb") else "❌ Disconnected"
            mongo_ping = "✅ OK" if health.get("mongodb_ping") else "❌ Failed"
            message += f"🔹 **MongoDB Status:** {mongo_status}\n"
            message += f"🔹 **MongoDB Ping:** {mongo_ping}\n\n"
            if health.get("redis") and health.get("mongodb"):
                message += "🟢 **Overall Status:** Healthy"
            elif health.get("mongodb"):
                message += "🟡 **Overall Status:** Degraded (No Cache)"
            else:
                message += "🔴 **Overall Status:** Critical"
            if health.get("cache_stats"):
                cache_stats = health["cache_stats"]
                message += f"\n\n📈 **Quick Stats:**\n"
                message += f"   • Memory: {cache_stats.get('memory_used', 'N/A')}\n"
                message += f"   • Clients: {cache_stats.get('connected_clients', 0)}\n"
            await event.reply(message)
        except Exception as e:
            await event.reply(f"❌ Error checking cache health: {str(e)}")

    async def _handle_backup_status(self, event):
        if not await self._check_admin(event):
            return
        try:
            from ..core.config import SESSION_BACKUP_ENABLED, TELEGRAM_BACKUP_CHANNEL
            status_text = "📊 **Backup System Status**\n\n"
            status_text += f"Session Backup: {'✅ Enabled' if SESSION_BACKUP_ENABLED else '❌ Disabled'}\n"
            status_text += f"Telegram Channel: {'✅ Configured' if TELEGRAM_BACKUP_CHANNEL else '❌ Not Set'}\n"
            status_text += f"Scheduler: {'✅ Running' if self.session_scheduler and self.session_scheduler.running else '❌ Not Running'}\n\n"
            if TELEGRAM_BACKUP_CHANNEL:
                status_text += f"**Channel ID:** `{TELEGRAM_BACKUP_CHANNEL}`\n\n"
            status_text += "**Available Commands:**\n"
            status_text += "• `/backup_now` - Direct backup to Telegram\n"
            status_text += "• `/backup_settings` - User settings to Telegram\n"
            status_text += "• `/backup_ids` - User IDs to Telegram\n"
            status_text += "• `/backup_sessions` - Session files to Telegram\n"
            status_text += "• `/backup_all` - All backup types\n"
            status_text += "• `/test_backup` - Test backup system\n"
            status_text += "• `/migrate_encrypt_data` - Encrypt existing data\n\n"
            status_text += "**Cache Commands:**\n"
            status_text += "• `/cache_stats` - Cache performance statistics\n"
            status_text += "• `/cache_warm <user_id>` - Warm cache for user\n"
            status_text += "• `/cache_clear` - Clear all cache data\n"
            status_text += "• `/cache_health` - Cache health status"
            await event.reply(status_text)
        except Exception as e:
            await event.reply(f"❌ Failed to get backup status: {e}")
