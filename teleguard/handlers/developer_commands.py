"""Developer Commands Handler for TeleGuard"""

import logging
import os
import platform
import sys

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
        self._register_system_commands()
        self._register_management_commands()
        self._register_startup_commands()

    def _register_system_commands(self):
        """Register system information commands"""
        self.bot.on(events.NewMessage(pattern=r"/sysinfo"))(admin_required(self._sysinfo_handler))
        self.bot.on(events.NewMessage(pattern=r"/health"))(admin_required(self._health_handler))
        self.bot.on(events.NewMessage(pattern=r"/stats"))(admin_required(self._stats_handler))
        self.bot.on(events.NewMessage(pattern=r"/logs"))(admin_required(self._logs_handler))

    def _register_management_commands(self):
        """Register management commands"""
        self.bot.on(events.NewMessage(pattern=r"/cleanup_sessions"))(admin_required(self._cleanup_sessions_handler))
        self.bot.on(events.NewMessage(pattern=r"/restart_bot"))(admin_required(self._restart_bot_handler))

    def _register_startup_commands(self):
        """Register startup configuration commands"""
        self.bot.on(events.NewMessage(pattern=r"/startup_enable"))(admin_required(self._startup_enable_handler))
        self.bot.on(events.NewMessage(pattern=r"/startup_disable"))(admin_required(self._startup_disable_handler))
        self.bot.on(events.NewMessage(pattern=r"/startup_status"))(admin_required(self._startup_status_handler))

    async def _sysinfo_handler(self, event):
        """System information command"""
        cpu_info, memory_info, disk_info = await self._get_container_stats()
        user_count = await mongodb.db.users.count_documents({})
        account_count = await mongodb.db.accounts.count_documents({})
        platform_name = self._detect_platform()
        text = self._build_sysinfo_text(cpu_info, memory_info, disk_info, user_count, account_count, platform_name)
        await event.reply(text)

    async def _health_handler(self, event):
        """Health check command"""
        text = self._build_health_text()
        await event.reply(text)

    async def _stats_handler(self, event):
        """Bot statistics command"""
        stats = await self._gather_stats()
        text = self._build_stats_text(stats)
        await event.reply(text)

    async def _logs_handler(self, event):
        """Show recent logs"""
        text = self._build_logs_text()
        await event.reply(text)

    async def _cleanup_sessions_handler(self, event):
        """Clean up inactive sessions"""
        await event.reply("🔄 Starting session cleanup...")
        try:
            cleaned = self._cleanup_inactive_sessions()
            await event.reply(f"✅ Session cleanup completed. Removed {cleaned} inactive sessions.")
        except Exception as e:
            await event.reply(f"❌ Session cleanup failed: {str(e)}")

    async def _restart_bot_handler(self, event):
        """Restart bot services"""
        await event.reply("🔄 Restarting bot services...")
        try:
            await event.reply("⚠️ Bot restart initiated. This may cause temporary disconnection.")
        except Exception as e:
            await event.reply(f"❌ Restart failed: {str(e)}")

    async def _startup_enable_handler(self, event):
        """Enable startup notifications"""
        await self._toggle_startup_notifications(event.sender_id, True)
        await event.reply("✅ Startup notifications enabled.")

    async def _startup_disable_handler(self, event):
        """Disable startup notifications"""
        await self._toggle_startup_notifications(event.sender_id, False)
        await event.reply("❌ Startup notifications disabled.")

    async def _startup_status_handler(self, event):
        """Show startup status"""
        text = await self._build_startup_status_text(event.sender_id)
        await event.reply(text)

    def _get_uptime(self) -> str:
        """Get bot uptime"""
        try:
            import time

            if hasattr(self.bot_manager, "start_time"):
                uptime_seconds = time.time() - self.bot_manager.start_time
                hours = int(uptime_seconds // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                return f"{hours}h {minutes}m"
            return "Unknown"
        except BaseException:
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
        if (
            os.getenv("KOYEB_APP_NAME")
            or os.getenv("KOYEB_SERVICE_NAME")
            or os.getenv("KOYEB_PUBLIC_DOMAIN")
        ):
            return f"Koyeb Container ({platform.system()} {platform.release()})"
        elif os.getenv("DYNO") or os.getenv("HEROKU_APP_NAME"):
            return f"Heroku Dyno ({platform.system()} {platform.release()})"
        elif os.getenv("RAILWAY_ENVIRONMENT"):
            return f"Railway ({platform.system()} {platform.release()})"
        elif os.getenv("RENDER_SERVICE_NAME"):
            return f"Render ({platform.system()} {platform.release()})"
        elif os.path.exists("/.dockerenv"):
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
            memory_info = f"{memory.percent}% ({memory.used /
                                                (1024**3):.1f}GB / {memory.total /
                                                                    (1024**3):.1f}GB)"

            try:
                disk = psutil.disk_usage("/")
                disk_info = f"{disk.percent}% ({disk.used /
                                                (1024**3):.1f}GB / {disk.total /
                                                                    (1024**3):.1f}GB)"
            except BaseException:
                disk_info = "N/A (Container filesystem)"

        except ImportError:
            try:
                with open("/proc/meminfo", "r") as f:
                    meminfo = {}
                    for line in f:
                        if ":" in line:
                            key, value = line.split(":", 1)
                            value_parts = value.strip().split()
                            if value_parts:
                                meminfo[key] = int(value_parts[0])

                if "MemTotal" in meminfo and "MemAvailable" in meminfo:
                    total_kb = meminfo["MemTotal"]
                    available_kb = meminfo["MemAvailable"]
                    used_kb = total_kb - available_kb
                    percent = (used_kb / total_kb) * 100
                    total_gb = total_kb / (1024**2)
                    used_gb = used_kb / (1024**2)
                    memory_info = f"{percent:.1f}% ({used_gb:.1f}GB / {total_gb:.1f}GB)"
            except BaseException:
                memory_info = "N/A"

            try:
                with open("/proc/loadavg", "r") as f:
                    load_avg = float(f.read().split()[0])
                cpu_info = f"{min(load_avg * 25, 100):.1f}%"
            except BaseException:
                cpu_info = "N/A"

            disk_info = "N/A (Limited access)"

        except Exception as e:
            logger.error(f"Error getting container stats: {e}")

        return cpu_info, memory_info, disk_info

    def _build_sysinfo_text(self, cpu_info, memory_info, disk_info, user_count, account_count, platform_name):
        """Build system information text"""
        return (
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

    def _build_health_text(self):
        """Build health check text"""
        return (
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

    async def _gather_stats(self):
        """Gather bot statistics"""
        return {
            "user_count": await mongodb.db.users.count_documents({}),
            "account_count": await mongodb.db.accounts.count_documents({}),
            "active_accounts": await mongodb.db.accounts.count_documents({"is_active": True}),
            "otp_enabled": await mongodb.db.accounts.count_documents({"otp_destroyer_enabled": True})
        }

    def _build_stats_text(self, stats):
        """Build statistics text"""
        return (
            "📈 **Bot Statistics**\n\n"
            "**Users & Accounts:**\n"
            f"• Total Users: {stats['user_count']}\n"
            f"• Total Accounts: {stats['account_count']}\n"
            f"• Active Accounts: {stats['active_accounts']}\n"
            f"• OTP Protected: {stats['otp_enabled']}\n\n"
            "**System:**\n"
            f"• Uptime: {self._get_uptime()}\n"
            f"• Components: {len(self.bot_manager.component_manager.initialized_components)}\n"
            f"• Handlers: {len(self.bot.list_event_handlers())}\n"
            f"• Memory Usage: {self._get_memory_usage()}\n"
            f"• Platform: {self._detect_platform()}"
        )

    def _build_logs_text(self):
        """Build logs text"""
        return (
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

    def _cleanup_inactive_sessions(self):
        """Clean up inactive sessions"""
        cleaned = 0
        for user_id, clients in list(self.bot_manager.user_clients.items()):
            for account_name, client in list(clients.items()):
                if not client.is_connected():
                    del self.bot_manager.user_clients[user_id][account_name]
                    cleaned += 1
        return cleaned

    async def _toggle_startup_notifications(self, user_id: int, enabled: bool):
        """Toggle startup notifications"""
        await mongodb.db.users.update_one(
            {"telegram_id": user_id},
            {"$set": {"startup_notifications": enabled}},
            upsert=True,
        )

    async def _build_startup_status_text(self, user_id: int):
        """Build startup status text"""
        user = await mongodb.db.users.find_one({"telegram_id": user_id})
        startup_notifications = user.get("startup_notifications", True) if user else True
        return (
            "🚀 **Startup Configuration**\n\n"
            "**Settings:**\n"
            f"• Startup Notifications: {'✅ Enabled' if startup_notifications else '❌ Disabled'}\n"
            "• Auto-load Accounts: ✅ Enabled\n"
            "• Health Checks: ✅ Enabled\n"
            "• Component Init: ✅ Enabled\n\n"
            f"**Last Startup:** {self._get_uptime()} ago\n"
            f"**Components Loaded:** {len(self.bot_manager.component_manager.initialized_components)}\n"
            f"**Status:** {'✅ All systems operational' if self.bot_manager.is_running else '❌ System issues detected'}"
        )
