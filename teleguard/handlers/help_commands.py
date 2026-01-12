"""Comprehensive Help System - All supported commands"""

import logging

from telethon import events

from ..core.config import ADMIN_IDS

logger = logging.getLogger(__name__)


class HelpCommands:
    """Complete help system for all bot commands"""

    def __init__(self, bot, bot_manager):
        self.bot = bot
        self.bot_manager = bot_manager

    def register_handlers(self):
        """Register help command handlers"""
        self.bot.on(events.NewMessage(pattern=r"^/help$"))(self._help_command)
        self.bot.on(events.NewMessage(pattern=r"^/help2$"))(self._help2_command)
        self.bot.on(events.NewMessage(pattern=r"^/commands$"))(self._commands_list)
        self.bot.on(events.NewMessage(pattern=r"^/features$"))(self._features_overview)

    async def _help_command(self, event):
        """Main help command"""
        if not event.is_private or event.sender_id not in ADMIN_IDS:
            return
        await event.reply(self._get_help_text())

    async def _help2_command(self, event):
        """Extended help command"""
        if not event.is_private or event.sender_id not in ADMIN_IDS:
            return
        await event.reply(self._get_help2_text())

    async def _commands_list(self, event):
        """List all commands"""
        if not event.is_private or event.sender_id not in ADMIN_IDS:
            return
        await event.reply(self._get_commands_text())

    async def _features_overview(self, event):
        """Show features overview"""
        if not event.is_private or event.sender_id not in ADMIN_IDS:
            return
        await event.reply(self._get_features_text())

    def _get_help_text(self):
        """Get main help text"""
        return (
            "📚 **TeleGuard - Complete Command List**\n\n"
            "**📱 Account Management:**\n"
            "• Use menu buttons for account operations\n\n"
            "**🛡️ OTP Destroyer:**\n"
            "• Use menu buttons for OTP management\n\n"
            "**📨 Messaging & DM System:**\n"
            "• `/set_dm_group` - Configure admin group\n"
            "• `/import_chats` - Import existing conversations\n"
            "• `/check_admin_group` - Verify group setup\n"
            "• `/import_help` - Chat import help\n\n"
            "**📤 Bulk Messaging:**\n"
            "• `/bulk_send` - Bulk sender help\n"
            "• `/bulk_send_list account_name` - Send to user list\n"
            "• `/bulk_send_contacts account_name message` - Send to contacts\n"
            "• `/bulk_send_all` - Send from ALL accounts\n"
            "• `/bulk_jobs` - View active jobs\n"
            "• `/bulk_stop job_id` - Stop bulk job\n\n"
            "**🎭 Activity Simulation:**\n"
            "• `/sim_stats` - Simulation statistics\n"
            "• `/sim_help` - Simulation help\n\n"
            "Type `/help2` for more commands..."
        )

    def _get_help2_text(self):
        """Get extended help text"""
        return (
            "📚 **TeleGuard - More Commands**\n\n"
            "**🟢 Online Status:**\n"
            "• `/force_offline` - Force all accounts offline\n"
            "• `/force_offline account_name` - Force specific account offline\n\n"
            "**🚀 Startup Configuration:**\n"
            "• `/startup_config` - Startup settings\n"
            "• `/auto_online on/off` - Auto-enable online maker\n"
            "• `/auto_sim on/off` - Auto-enable activity simulator\n"
            "• `/startup_status` - View startup settings\n\n"
            "**🔧 System Commands:**\n"
            "• `/help` - Main help (page 1)\n"
            "• `/help2` - This help (page 2)\n"
            "• `/commands` - All commands list\n"
            "• `/features` - Feature overview\n\n"
            "💡 **Tips:**\n"
            "• Use menu buttons for most operations\n"
            "• Commands are case-sensitive\n"
            "• All activities are logged for transparency\n"
            "• Check logs for troubleshooting"
        )

    def _get_commands_text(self):
        """Get all commands text"""
        return (
            "⚡ **All TeleGuard Commands**\n\n"
            "**DM & Messaging:**\n"
            "`/set_dm_group`, `/import_chats`, `/check_admin_group`, `/import_help`\n\n"
            "**Bulk Messaging:**\n"
            "`/bulk_send`, `/bulk_send_list`, `/bulk_send_contacts`, `/bulk_send_all`, `/bulk_jobs`, `/bulk_stop`\n\n"
            "**Activity Simulation:**\n"
            "`/sim_stats`, `/sim_help`\n\n"
            "**Online Status:**\n"
            "`/force_offline`\n\n"
            "**Startup Config:**\n"
            "`/startup_config`, `/auto_online`, `/auto_sim`, `/startup_status`\n\n"
            "**Help & Info:**\n"
            "`/help`, `/help2`, `/commands`, `/features`\n\n"
            "**Menu Operations:**\n"
            "• Account management via menu buttons\n"
            "• OTP destroyer via menu buttons\n"
            "• 2FA management via menu buttons"
        )

    def _get_features_text(self):
        """Get features overview text"""
        return (
            "🚀 **TeleGuard Features Overview**\n\n"
            "**🛡️ Security:**\n"
            "• OTP Destroyer - Auto-invalidate login codes\n"
            "• 2FA Management - Set/change/remove 2FA\n"
            "• Session Monitoring - View active sessions\n\n"
            "**📱 Account Management:**\n"
            "• Multi-account support (up to 10)\n"
            "• Profile management (names, photos, bios)\n"
            "• Account switching and control\n\n"
            "**📨 Messaging System:**\n"
            "• Unified DM forwarding with topics\n"
            "• Auto-reply system\n"
            "• Message templates\n"
            "• Bulk messaging with buttons\n\n"
            "**🎭 Automation:**\n"
            "• Activity simulation (human-like behavior)\n"
            "• Online maker (keep accounts online)\n"
            "• Scheduled actions\n"
            "• Auto-startup features\n\n"
            "**📊 Management:**\n"
            "• Real-time statistics\n"
            "• Comprehensive logging\n"
            "• Health monitoring\n"
            "• Cloud deployment ready"
        )
