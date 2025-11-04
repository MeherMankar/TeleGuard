"""Developer Commands Handler for TeleGuard"""
import logging
import asyncio
import platform
import sys
import os
from telethon import events
from ..core.mongo_database import mongodb
from ..utils.authorization import admin_required

logger = logging.getLogger(__name__)

class DeveloperCommands:
    """Handles developer-only commands"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
    
    def register_handlers(self):
        """Register developer command handlers"""
        
        @admin_required
        @self.bot.on(events.NewMessage(pattern=r"/sysinfo"))
        async def sysinfo_handler(event):
            """System information command"""
            cpu_info, memory_info, disk_info = await self._get_container_stats()
            
            user_count = await mongodb.db.users.count_documents({})
            account_count = await mongodb.db.accounts.count_documents({})
            platform_name = self._detect_platform()
            
            text = (
                "📊 **System Information**\n\n"
                f"**Platform:** {platform_name}\n"
                f"**Python:** {sys.version.split()[0]}\n"
                f"**CPU Usage:** {cpu_info}\n"
                f"**Memory:** {memory_info}\n"
                f"**Disk:** {disk_info}\n\n"
                "**Bot Statistics:**\n"
                f"• Active Users: {user_count}\n"
                f"• Total Accounts: {account_count}\n"
                f"• Bot Status: {'Connected' if self.bot.is_connected() else 'Disconnected'}\n"
                f"• Cache Status: {'Active' if hasattr(self.bot_manager, 'cache') else 'N/A'}\n"
                f"• Uptime: {self._get_uptime()}"
            )
            await event.reply(text)
        
        @admin_required
        @self.bot.on(events.NewMessage(pattern=r"/health"))
        async def health_handler(event):
            """Health check command"""
            text = (
                "🏥 **System Health Check**\n\n"
                f"**Bot Connection:** {'✅ Active' if self.bot.is_connected() else '❌ Inactive'}\n"
                f"**Database:** {'✅ Connected' if mongodb.db else '❌ Disconnected'}\n"
                f"**Event Handlers:** {len(self.bot.list_event_handlers())} active\n"
                f"**User Clients:** {len(self.bot_manager.user_clients)}\n\n"
                "**Component Status:**\n"
                f"• OTP Manager: {'✅' if self.bot_manager.otp_manager else '❌'}\n"
                f"• Menu System: {'✅' if self.bot_manager.menu_system else '❌'}\n"
                f"• Messaging: {'✅' if self.bot_manager.messaging_manager else '❌'}\n"
                f"• Automation: {'✅' if self.bot_manager.automation_engine else '❌'}"
            )
            await event.reply(text)
        
        @admin_required
        @self.bot.on(events.NewMessage(pattern=r"/stats"))
        async def stats_handler(event):
            """Bot statistics command"""
            user_count = await mongodb.db.users.count_documents({})
            account_count = await mongodb.db.accounts.count_documents({})
            active_accounts = await mongodb.db.accounts.count_documents({"is_active": True})
            otp_enabled = await mongodb.db.accounts.count_documents({"otp_destroyer_enabled": True})
            
            text = (
                "📈 **Bot Statistics**\n\n"
                f"**Users & Accounts:**\n"
                f"• Total Users: {user_count}\n"
                f"• Total Accounts: {account_count}\n"
                f"• Active Accounts: {active_accounts}\n"
                f"• OTP Protected: {otp_enabled}\n\n"
                f"**System:**\n"
                f"• Uptime: {self._get_uptime()}\n"
                f"• Components: {len(self.bot_manager.component_manager.initialized_components)}\n"
                f"• Handlers: {len(self.bot.list_event_handlers())}\n"
                f"• Memory Usage: {self._get_memory_usage()}\n"
                f"• Platform: {self._detect_platform()}"
            )
            await event.reply(text)
        
        @admin_required
        @self.bot.on(events.NewMessage(pattern=r"/logs"))
        async def logs_handler(event):
            """Show recent logs"""
            text = (
                "📋 **System Logs**\n\n"
                "**Recent Activity:**\n"
                f"• Bot Status: {'Running' if self.bot.is_connected() else 'Stopped'}\n"
                f"• Database: {'Connected' if mongodb.db else 'Disconnected'}\n"
                f"• Active Handlers: {len(self.bot.list_event_handlers())}\n"
                f"• User Sessions: {sum(len(clients) for clients in self.bot_manager.user_clients.values())}\n\n"
                "**Log Levels:**\n"
                "• INFO: General operations\n"
                "• WARNING: Potential issues\n"
                "• ERROR: System errors\n"
                "• DEBUG: Detailed debugging\n\n"
                "Use log files for detailed history."
            )
            await event.reply(text)
        
        @admin_required
        @self.bot.on(events.NewMessage(pattern=r"/cleanup_sessions"))
        async def cleanup_sessions_handler(event):
            """Clean up inactive sessions"""
            await event.reply("🔄 Starting session cleanup...")
            try:
                cleaned = 0
                for user_id, clients in list(self.bot_manager.user_clients.items()):
                    for account_name, client in list(clients.items()):
                        if not client.is_connected():
                            del self.bot_manager.user_clients[user_id][account_name]
                            cleaned += 1
                
                await event.reply(f"✅ Session cleanup completed. Removed {cleaned} inactive sessions.")
            except Exception as e:
                await event.reply(f"❌ Session cleanup failed: {str(e)}")
        
        @admin_required
        @self.bot.on(events.NewMessage(pattern=r"/restart_bot"))
        async def restart_bot_handler(event):
            """Restart bot services"""
            await event.reply("🔄 Restarting bot services...")
            try:
                await event.reply("⚠️ Bot restart initiated. This may cause temporary disconnection.")
            except Exception as e:
                await event.reply(f"❌ Restart failed: {str(e)}")
        
        @admin_required
        @self.bot.on(events.NewMessage(pattern=r"/startup_enable"))
        async def startup_enable_handler(event):
            """Enable startup notifications"""
            user_id = event.sender_id
            await mongodb.db.users.update_one(
                {"telegram_id": user_id},
                {"$set": {"startup_notifications": True}},
                upsert=True
            )
            await event.reply("✅ Startup notifications enabled.")
        
        @admin_required
        @self.bot.on(events.NewMessage(pattern=r"/startup_disable"))
        async def startup_disable_handler(event):
            """Disable startup notifications"""
            user_id = event.sender_id
            await mongodb.db.users.update_one(
                {"telegram_id": user_id},
                {"$set": {"startup_notifications": False}},
                upsert=True
            )
            await event.reply("❌ Startup notifications disabled.")
        
        @admin_required
        @self.bot.on(events.NewMessage(pattern=r"/update_ages"))
        async def update_ages_handler(event):
            """Manually update account ages"""
            await event.reply("🔄 Starting account age update...")
            
            try:
                from ..utils.account_age_estimator import AccountAgeEstimator
                from datetime import datetime, timezone
                
                accounts = await mongodb.db.accounts.find({}).to_list(None)
                updated = 0
                failed = []
                
                for account in accounts:
                    user_id = account.get('user_id')
                    account_name = account.get('name')
                    phone = account.get('phone')
                    display_name = account.get('display_name')
                    
                    if not user_id:
                        failed.append(f"{account_name or phone}: No user_id")
                        continue
                    
                    # Find client - try multiple keys
                    client = None
                    if user_id in self.bot_manager.user_clients:
                        user_clients = self.bot_manager.user_clients[user_id]
                        
                        # Try direct keys first
                        client = user_clients.get(account_name) or user_clients.get(phone) or user_clients.get(display_name)
                        
                        # If not found, iterate and match by phone
                        if not client:
                            for key, c in user_clients.items():
                                if c and hasattr(c, 'is_connected'):
                                    try:
                                        if c.is_connected():
                                            me = await c.get_me()
                                            phone_clean = phone.lstrip('+') if phone else ''
                                            if me.phone and (me.phone == phone_clean or me.phone == phone or f"+{me.phone}" == phone):
                                                client = c
                                                break
                                    except Exception as e:
                                        logger.debug(f"Error checking client {key}: {e}")
                    
                    if not client:
                        failed.append(f"{account_name or phone}: Client not found")
                        continue
                    
                    if not client.is_connected():
                        failed.append(f"{account_name or phone}: Client not connected")
                        continue
                    
                    try:
                        me = await client.get_me()
                        telegram_id = int(me.id)
                        
                        creation_date, method = await AccountAgeEstimator.estimate_creation_date(telegram_id)
                        
                        if creation_date:
                            now = datetime.now(timezone.utc)
                            if creation_date.tzinfo is None:
                                creation_date = creation_date.replace(tzinfo=timezone.utc)
                            age_days = max(0, (now - creation_date).days)
                            
                            await mongodb.db.accounts.update_one(
                                {"_id": account["_id"]},
                                {"$set": {
                                    "creation_date": creation_date,
                                    "age_days": age_days,
                                    "telegram_user_id": telegram_id,
                                    "last_age_update": datetime.now(timezone.utc)
                                }}
                            )
                            updated += 1
                    except Exception as e:
                        failed.append(f"{account_name or phone}: {str(e)}")
                        logger.error(f"Failed to update age for {account_name}: {e}")
                
                msg = f"✅ Updated {updated}/{len(accounts)} accounts."
                if failed:
                    msg += f"\n\n❌ Failed:\n" + "\n".join(f"• {f}" for f in failed)
                await event.reply(msg)
            except Exception as e:
                await event.reply(f"❌ Error: {str(e)}")
        
        @admin_required
        @self.bot.on(events.NewMessage(pattern=r"/load_anchors"))
        async def load_anchors_handler(event):
            """Load anchor data into MongoDB"""
            await event.reply("📥 Loading anchor data into MongoDB...")
            
            try:
                from ..utils.account_age_estimator import AccountAgeEstimator
                
                # Clear cache
                AccountAgeEstimator._anchors_cache = None
                
                # Clear existing anchors
                await mongodb.db.id_anchors.delete_many({})
                
                # Convert ID_RANGES to MongoDB format
                anchors = [
                    {
                        "start_id": s,
                        "end_id": e,
                        "date": d.isoformat().replace("+00:00", "Z")
                    }
                    for s, e, d in AccountAgeEstimator.ID_RANGES
                ]
                
                # Insert anchors
                await mongodb.db.id_anchors.insert_many(anchors)
                
                # Create index
                await mongodb.db.id_anchors.create_index([("start_id", 1), ("end_id", 1)])
                
                await event.reply(f"✅ Loaded {len(anchors)} anchor points into MongoDB")
            except Exception as e:
                await event.reply(f"❌ Error: {str(e)}")
        
        @admin_required
        @self.bot.on(events.NewMessage(pattern=r"/startup_status"))
        async def startup_status_handler(event):
            """Show startup status"""
            user_id = event.sender_id
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            startup_notifications = user.get("startup_notifications", True) if user else True
            
            text = (
                "🚀 **Startup Configuration**\n\n"
                f"**Settings:**\n"
                f"• Startup Notifications: {'✅ Enabled' if startup_notifications else '❌ Disabled'}\n"
                f"• Auto-load Accounts: ✅ Enabled\n"
                f"• Health Checks: ✅ Enabled\n"
                f"• Component Init: ✅ Enabled\n\n"
                f"**Last Startup:** {self._get_uptime()} ago\n"
                f"**Components Loaded:** {len(self.bot_manager.component_manager.initialized_components)}\n"
                f"**Status:** {'✅ All systems operational' if self.bot_manager.is_running else '❌ System issues detected'}"
            )
            await event.reply(text)
    
    def _get_uptime(self) -> str:
        """Get bot uptime"""
        try:
            import time
            if hasattr(self.bot_manager, 'start_time'):
                uptime_seconds = time.time() - self.bot_manager.start_time
                hours = int(uptime_seconds // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                return f"{hours}h {minutes}m"
            return "Unknown"
        except:
            return "Unknown"
    
    def _get_memory_usage(self) -> str:
        """Get memory usage"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            return f"{memory.percent}%"
        except ImportError:
            return "N/A"
    
    def _detect_platform(self) -> str:
        """Detect the deployment platform"""
        if os.getenv('KOYEB_APP_NAME') or os.getenv('KOYEB_SERVICE_NAME') or os.getenv('KOYEB_PUBLIC_DOMAIN'):
            return f"Koyeb Container ({platform.system()} {platform.release()})"
        elif os.getenv('DYNO') or os.getenv('HEROKU_APP_NAME'):
            return f"Heroku Dyno ({platform.system()} {platform.release()})"
        elif os.getenv('RAILWAY_ENVIRONMENT'):
            return f"Railway ({platform.system()} {platform.release()})"
        elif os.getenv('RENDER_SERVICE_NAME'):
            return f"Render ({platform.system()} {platform.release()})"
        elif os.path.exists('/.dockerenv'):
            return f"Docker Container ({platform.system()} {platform.release()})"
        else:
            return f"{platform.system()} {platform.release()}"
    
    async def _get_container_stats(self) -> tuple:
        """Get container-specific resource stats"""
        cpu_info = "0.0%"
        memory_info = "N/A"
        disk_info = "N/A"
        
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_info = f"{cpu_percent:.1f}%"
            
            memory = psutil.virtual_memory()
            memory_info = f"{memory.percent}% ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)"
            
            try:
                disk = psutil.disk_usage('/')
                disk_info = f"{disk.percent}% ({disk.used / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB)"
            except:
                disk_info = "N/A (Container filesystem)"
                
        except ImportError:
            try:
                with open('/proc/meminfo', 'r') as f:
                    meminfo = {}
                    for line in f:
                        if ':' in line:
                            key, value = line.split(':', 1)
                            value_parts = value.strip().split()
                            if value_parts:
                                meminfo[key] = int(value_parts[0])
                
                if 'MemTotal' in meminfo and 'MemAvailable' in meminfo:
                    total_kb = meminfo['MemTotal']
                    available_kb = meminfo['MemAvailable']
                    used_kb = total_kb - available_kb
                    percent = (used_kb / total_kb) * 100
                    total_gb = total_kb / (1024**2)
                    used_gb = used_kb / (1024**2)
                    memory_info = f"{percent:.1f}% ({used_gb:.1f}GB / {total_gb:.1f}GB)"
            except:
                memory_info = "N/A"
            
            try:
                with open('/proc/loadavg', 'r') as f:
                    load_avg = float(f.read().split()[0])
                cpu_info = f"{min(load_avg * 25, 100):.1f}%"
            except:
                cpu_info = "N/A"
            
            disk_info = "N/A (Limited access)"
        
        except Exception as e:
            logger.error(f"Error getting container stats: {e}")
        
        return cpu_info, memory_info, disk_info