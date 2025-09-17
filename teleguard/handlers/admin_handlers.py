"""Admin command handlers"""

import logging

from telethon import events

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
            
            # Check admin access
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
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
        
        @self.bot.on(events.NewMessage(pattern=r"/backup_settings"))
        async def backup_settings_handler(event):
            user_id = event.sender_id
            
            # Check admin access
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
                await event.reply("❌ Admin access required")
                return

            if not self.session_scheduler or not self.session_scheduler.bot_client:
                await event.reply("❌ Telegram backup not enabled")
                return

            await event.reply("🔄 Triggering manual user settings backup...")

            try:
                self.session_scheduler.trigger_user_settings_push_now()
                await event.reply("✅ User settings backup job queued")
            except Exception as e:
                await event.reply(f"❌ Failed to trigger settings backup: {e}")
        
        @self.bot.on(events.NewMessage(pattern=r"/backup_ids"))
        async def backup_ids_handler(event):
            user_id = event.sender_id
            
            # Check admin access
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
                await event.reply("❌ Admin access required")
                return

            if not self.session_scheduler or not self.session_scheduler.bot_client:
                await event.reply("❌ Telegram backup not enabled")
                return

            await event.reply("🔄 Triggering manual user IDs backup...")

            try:
                self.session_scheduler.trigger_user_ids_push_now()
                await event.reply("✅ User IDs backup job queued")
            except Exception as e:
                await event.reply(f"❌ Failed to trigger IDs backup: {e}")
        
        @self.bot.on(events.NewMessage(pattern=r"/backup_sessions"))
        async def backup_sessions_handler(event):
            user_id = event.sender_id
            
            # Check admin access
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
                await event.reply("❌ Admin access required")
                return

            if not self.session_scheduler or not self.session_scheduler.bot_client:
                await event.reply("❌ Telegram backup not enabled")
                return

            await event.reply("🔄 Triggering manual session files backup...")

            try:
                self.session_scheduler.trigger_session_files_push_now()
                await event.reply("✅ Session files backup job queued")
            except Exception as e:
                await event.reply(f"❌ Failed to trigger session files backup: {e}")

        @self.bot.on(events.NewMessage(pattern=r"/compact_now"))
        async def compact_now_handler(event):
            user_id = event.sender_id
            
            # Check admin access
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
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

        @self.bot.on(events.NewMessage(pattern=r"/backup_all"))
        async def backup_all_handler(event):
            user_id = event.sender_id
            
            # Check admin access
            from ..core.config import ADMIN_IDS
            if user_id not in ADMIN_IDS:
                await event.reply("❌ Admin access required")
                return

            if not self.session_scheduler:
                await event.reply("❌ Session backup not enabled")
                return

            await event.reply("🔄 Triggering all backup jobs...")

            try:
                # Trigger all backup types
                self.session_scheduler.trigger_push_now()  # Sessions to GitHub
                if self.session_scheduler.bot_client:
                    self.session_scheduler.trigger_user_settings_push_now()  # Settings
                    self.session_scheduler.trigger_user_ids_push_now()  # IDs
                    self.session_scheduler.trigger_session_files_push_now()  # Session files
                
                await event.reply("✅ All backup jobs queued:\n• Sessions → GitHub\n• Settings → Telegram (encrypted)\n• User IDs → Telegram\n• Session Files → Telegram (encrypted)")
            except Exception as e:
                await event.reply(f"❌ Failed to trigger backups: {e}")

        @self.bot.on(events.NewMessage(pattern=r"/migrate_encrypt_data"))
        async def migrate_encrypt_data_handler(event):
            user_id = event.sender_id
            
            # Check admin access
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
                await event.reply(f"❌ Migration failed: {e}")

        @self.bot.on(events.NewMessage(pattern=r"/backup_status"))
        async def backup_status_handler(event):
            user_id = event.sender_id
            
            # Check admin access
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
                status_text += "• `/backup_now` - Sessions to GitHub\n"
                status_text += "• `/backup_settings` - User settings to Telegram\n"
                status_text += "• `/backup_ids` - User IDs to Telegram\n"
                status_text += "• `/backup_sessions` - Session files to Telegram\n"
                status_text += "• `/backup_all` - All backup types\n"
                status_text += "• `/compact_now` - Compact GitHub history\n"
                status_text += "• `/migrate_encrypt_data` - Encrypt existing data"
                
                await event.reply(status_text)
                
            except Exception as e:
                await event.reply(f"❌ Failed to get backup status: {e}")
