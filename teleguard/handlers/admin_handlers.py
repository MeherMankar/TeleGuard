"""Consolidated Admin Handlers for TeleGuard"""
import logging
from telethon import events
from ..core.database_manager import db_manager
from ..utils.cache_decorators import CacheManager
from ..utils.authorization import admin_required

logger = logging.getLogger(__name__)

class AdminHandlers:
    """Handles all admin-only commands"""
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.session_scheduler = bot_manager.session_scheduler
    def register_handlers(self):
        """Register admin command handlers"""
        @self.bot.on(events.NewMessage(pattern=r"/backup_now"))
        async def backup_now_handler(event):
            user_id = event.sender_id
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
                await event.reply("❌ Admin access required")
                return
            
            await event.reply("🔄 Starting manual backup...")
            try:
                from ..utils.backups import TelegramBackup
                from ..core.config import TELEGRAM_BACKUP_CHANNEL
                
                if not TELEGRAM_BACKUP_CHANNEL:
                    await event.reply("❌ Telegram backup channel not configured")
                    return
                
                backup = TelegramBackup(self.bot)
                await backup.backup_user_settings()
                await event.reply("✅ Manual backup completed")
            except Exception as e:
                await event.reply(f"❌ Backup failed: {str(e)}")
        @self.bot.on(events.NewMessage(pattern=r"/backup_settings"))
        async def backup_settings_handler(event):
            user_id = event.sender_id
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
                await event.reply("❌ Admin access required")
                return
            
            await event.reply("🔄 Backing up user settings...")
            try:
                from ..utils.backups import TelegramBackup
                from ..core.config import TELEGRAM_BACKUP_CHANNEL
                
                if not TELEGRAM_BACKUP_CHANNEL:
                    await event.reply("❌ Telegram backup channel not configured")
                    return
                
                backup = TelegramBackup(self.bot)
                await backup.backup_user_settings()
                await event.reply("✅ User settings backup completed")
            except Exception as e:
                await event.reply(f"❌ Settings backup failed: {str(e)}")
        @self.bot.on(events.NewMessage(pattern=r"/backup_ids"))
        async def backup_ids_handler(event):
            user_id = event.sender_id
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
                await event.reply("❌ Admin access required")
                return
            
            await event.reply("🔄 Backing up user IDs...")
            try:
                from ..utils.backups import TelegramBackup
                from ..core.config import TELEGRAM_BACKUP_CHANNEL
                
                if not TELEGRAM_BACKUP_CHANNEL:
                    await event.reply("❌ Telegram backup channel not configured")
                    return
                
                backup = TelegramBackup(self.bot)
                await backup.backup_user_ids()
                await event.reply("✅ User IDs backup completed")
            except Exception as e:
                await event.reply(f"❌ IDs backup failed: {str(e)}")
        @self.bot.on(events.NewMessage(pattern=r"/backup_sessions"))
        async def backup_sessions_handler(event):
            user_id = event.sender_id
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
                await event.reply("❌ Admin access required")
                return
            
            await event.reply("🔄 Backing up session files...")
            try:
                from ..utils.backups import TelegramBackup
                from ..core.config import TELEGRAM_BACKUP_CHANNEL
                
                if not TELEGRAM_BACKUP_CHANNEL:
                    await event.reply("❌ Telegram backup channel not configured")
                    return
                
                backup = TelegramBackup(self.bot)
                await backup.backup_session_files()
                await event.reply("✅ Session files backup completed")
            except Exception as e:
                await event.reply(f"❌ Session backup failed: {str(e)}")
        @self.bot.on(events.NewMessage(pattern=r"/test_backup"))
        async def test_backup_handler(event):
            user_id = event.sender_id
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
                await event.reply("❌ Admin access required")
                return
            
            await event.reply("🔄 Testing backup system...")
            try:
                from ..core.config import TELEGRAM_BACKUP_CHANNEL
                
                if not TELEGRAM_BACKUP_CHANNEL:
                    await event.reply("❌ Telegram backup channel not configured")
                    return
                
                # Test channel access
                channel_id = int(TELEGRAM_BACKUP_CHANNEL)
                test_message = f"🧪 Backup test from TeleGuard\nTimestamp: {__import__('datetime').datetime.now()}"
                
                await self.bot.send_message(channel_id, test_message)
                await event.reply(f"✅ Backup test successful!\nChannel: {TELEGRAM_BACKUP_CHANNEL}")
            except Exception as e:
                await event.reply(f"❌ Backup test failed: {str(e)}")
        @self.bot.on(events.NewMessage(pattern=r"/backup_all"))
        async def backup_all_handler(event):
            user_id = event.sender_id
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
                await event.reply("❌ Admin access required")
                return
            
            await event.reply("🔄 Starting complete backup...")
            try:
                from ..utils.backups import TelegramBackup
                from ..core.config import TELEGRAM_BACKUP_CHANNEL
                
                if not TELEGRAM_BACKUP_CHANNEL:
                    await event.reply("❌ Telegram backup channel not configured")
                    return
                
                backup = TelegramBackup(self.bot)
                
                # Backup all data types
                await backup.backup_user_settings()
                await backup.backup_user_ids()
                await backup.backup_session_files()
                
                await event.reply("✅ Complete backup finished:\n• User settings backed up\n• User IDs backed up\n• Session files backed up")
            except Exception as e:
                await event.reply(f"❌ Complete backup failed: {str(e)}")
        @self.bot.on(events.NewMessage(pattern=r"/migrate_encrypt_data"))
        async def migrate_encrypt_data_handler(event):
            user_id = event.sender_id
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
                await event.reply("❌ Admin access required")
                return
            await event.reply("🔄 Starting data encryption migration...")
            try:
                from ..utils.data_encryption import DataEncryption
                from ..core.mongo_database import mongodb
                # Migrate users
                users = await mongodb.db.users.find({}).to_list(length=None)
                user_count = 0
                for user in users:
                    if not any(key.endswith('_enc') for key in user.keys()):
                        encrypted_data = DataEncryption.encrypt_user_data(user)
                        await mongodb.db.users.replace_one({"_id": user["_id"]}, encrypted_data)
                        user_count += 1
                # Migrate accounts
                accounts = await mongodb.db.accounts.find({}).to_list(length=None)
                account_count = 0
                for account in accounts:
                    if not any(key.endswith('_enc') for key in account.keys()):
                        encrypted_data = DataEncryption.encrypt_account_data(account)
                        await mongodb.db.accounts.replace_one({"_id": account["_id"]}, encrypted_data)
                        account_count += 1
                await event.reply(f"✅ Migration completed!\n\n📊 **Results:**\n• Users migrated: {user_count}\n• Accounts migrated: {account_count}\n\n🔒 All user data is now encrypted")
            except Exception as e:
                await event.reply(f"❌ Migration failed: {str(e)}")
                logger.error(f"Data encryption migration failed: {e}", exc_info=True)

        # Cache Admin Commands
        @self.bot.on(events.NewMessage(pattern=r"/cache_stats"))
        async def cache_stats_handler(event):
            user_id = event.sender_id
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
                await event.reply("❌ Admin access required")
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
                top_hits = stats.get('top_cache_hits', {})
                if top_hits:
                    message += "🔥 **Top Cache Hits:**\n"
                    for key, hits in list(top_hits.items())[:5]:
                        message += f"   • `{key}`: {hits} hits\n"
                else:
                    message += "📝 No cache hit data available\n"
                performance = await CacheManager.get_cache_performance()
                recommendations = performance.get('recommendations', [])
                if recommendations:
                    message += "\n💡 **Recommendations:**\n"
                    for rec in recommendations:
                        message += f"   • {rec}\n"
                await event.reply(message)
            except Exception as e:
                await event.reply(f"❌ Error getting cache stats: {str(e)}")

        @self.bot.on(events.NewMessage(pattern=r"/cache_warm (\d+)"))
        async def cache_warm_handler(event):
            user_id = event.sender_id
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
                await event.reply("❌ Admin access required")
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

        @self.bot.on(events.NewMessage(pattern=r"/cache_clear"))
        async def cache_clear_handler(event):
            user_id = event.sender_id
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
                await event.reply("❌ Admin access required")
                return
            await event.reply("⚠️ **WARNING**: This will clear ALL cache data!\n\nReply with 'CONFIRM' to proceed.")
            
            async def confirmation_handler(confirm_event):
                if confirm_event.sender_id == event.sender_id and confirm_event.text == 'CONFIRM':
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

        @self.bot.on(events.NewMessage(pattern=r"/cache_health"))
        async def cache_health_handler(event):
            user_id = event.sender_id
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
                await event.reply("❌ Admin access required")
                return
            try:
                health = await db_manager.health_check()
                message = "🏥 **Cache Health Status**\n\n"
                redis_status = "✅ Connected" if health.get('redis') else "❌ Disconnected"
                redis_ping = "✅ OK" if health.get('redis_ping') else "❌ Failed"
                message += f"🔹 **Redis Status:** {redis_status}\n"
                message += f"🔹 **Redis Ping:** {redis_ping}\n\n"
                mongo_status = "✅ Connected" if health.get('mongodb') else "❌ Disconnected"
                mongo_ping = "✅ OK" if health.get('mongodb_ping') else "❌ Failed"
                message += f"🔹 **MongoDB Status:** {mongo_status}\n"
                message += f"🔹 **MongoDB Ping:** {mongo_ping}\n\n"
                if health.get('redis') and health.get('mongodb'):
                    message += "🟢 **Overall Status:** Healthy"
                elif health.get('mongodb'):
                    message += "🟡 **Overall Status:** Degraded (No Cache)"
                else:
                    message += "🔴 **Overall Status:** Critical"
                if health.get('cache_stats'):
                    cache_stats = health['cache_stats']
                    message += f"\n\n📈 **Quick Stats:**\n"
                    message += f"   • Memory: {cache_stats.get('memory_used', 'N/A')}\n"
                    message += f"   • Clients: {cache_stats.get('connected_clients', 0)}\n"
                await event.reply(message)
            except Exception as e:
                await event.reply(f"❌ Error checking cache health: {str(e)}")
        @self.bot.on(events.NewMessage(pattern=r"/backup_status"))
        async def backup_status_handler(event):
            user_id = event.sender_id
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
                await event.reply("❌ Admin access required")
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
