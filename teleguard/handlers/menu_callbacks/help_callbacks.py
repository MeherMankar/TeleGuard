"""Help and support callbacks"""

import logging

from telethon import Button

from .base_callback import BaseCallback

logger = logging.getLogger(__name__)


class HelpCallbacks(BaseCallback):
    async def handle_callback(self, event, user_id, data):
        """Handle help-related callbacks"""
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else "main"

        if action == "guide":
            text = "📖 **Complete Guide**\n\nComprehensive TeleGuard documentation coming soon!"
            buttons = [[Button.inline("🔙 Back to Help", "menu:help")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "security":
            text = "🛡️ **Security Guide**\n\nSecurity best practices and OTP protection guide coming soon!"
            buttons = [[Button.inline("🔙 Back to Help", "menu:help")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "features":
            text = "⚙️ **Feature Guide**\n\nDetailed feature documentation coming soon!"
            buttons = [[Button.inline("🔙 Back to Help", "menu:help")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "troubleshoot":
            text = "🔧 **Troubleshooting**\n\nCommon issues and solutions coming soon!"
            buttons = [[Button.inline("🔙 Back to Help", "menu:help")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "faq":
            text = "❓ **FAQ**\n\nFrequently asked questions coming soon!"
            buttons = [[Button.inline("🔙 Back to Help", "menu:help")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "contact":
            text = "📞 **Contact Support**\n\nContact information and support channels coming soon!"
            buttons = [[Button.inline("🔙 Back to Help", "menu:help")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "emergency":
            text = "🆘 **Emergency Help**\n\nEmergency support procedures coming soon!"
            buttons = [[Button.inline("🔙 Back to Help", "menu:help")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "commands":
            text = "📚 **Command Reference**\n\nComplete command list coming soon!"
            buttons = [[Button.inline("🔙 Back to Help", "menu:help")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "toggle_dev":
            from teleguard.core.mongo_database import mongodb

            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if user:
                current_mode = user.get("developer_mode", False)
                new_mode = not current_mode
                await mongodb.db.users.update_one(
                    {"telegram_id": user_id}, {"$set": {"developer_mode": new_mode}}
                )
                status = "enabled" if new_mode else "disabled"
                await event.answer(f"⚙️ Developer mode {status}")
                # Refresh help menu
                await self.menu_system.handlers.handle_help(
                    type(
                        "Event",
                        (),
                        {
                            "sender_id": user_id,
                            "message_id": event.message_id,
                            "reply": lambda x, buttons=None: self.bot.edit_message(
                                user_id, event.message_id, x, buttons=buttons
                            ),
                        },
                    )()
                )

    async def handle_support_callback(self, event, user_id, data):
        """Handle support-related callbacks"""
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else "main"

        if action == "main":
            await self.menu_system.handlers.handle_support(event)
        elif action == "contact":
            text = "💬 **Contact Support**\n\nReach out to @ContactXYZrobot for assistance!"
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "bug":
            text = "🐛 **Report Bug**\n\nBug reporting system coming soon!"
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "docs":
            text = "📚 **Documentation**\n\nFull documentation coming soon!"
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "feature":
            text = "💡 **Feature Request**\n\nFeature request system coming soon!"
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "status":
            text = "📊 **System Status**\n\n🟢 All systems operational!"
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "updates":
            text = "🔄 **Updates**\n\nLatest updates and changelog coming soon!"
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )

    async def handle_developer_callback(self, event, user_id, data):
        """Handle developer-related callbacks"""
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else "main"

        if action == "main":
            await self.menu_system.handlers.handle_developer(event)
        elif action == "toggle":
            from teleguard.core.mongo_database import mongodb

            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if user:
                current_mode = user.get("developer_mode", False)
                new_mode = not current_mode
                await mongodb.db.users.update_one(
                    {"telegram_id": user_id}, {"$set": {"developer_mode": new_mode}}
                )
                status = "enabled" if new_mode else "disabled"
                await event.answer(f"⚙️ Developer mode {status}")
                # Refresh developer menu
                await self.menu_system.handlers.handle_developer(
                    type(
                        "Event",
                        (),
                        {
                            "sender_id": user_id,
                            "message_id": event.message_id,
                            "reply": lambda x, buttons=None: self.bot.edit_message(
                                user_id, event.message_id, x, buttons=buttons
                            ),
                        },
                    )()
                )
        elif action == "sysinfo":
            text = "📊 **System Dashboard**\n\nSystem information coming soon!"
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "logs":
            text = "📋 **System Logs**\n\nLog viewer coming soon!"
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "dbstats":
            text = "🗄️ **Database Tools**\n\nDatabase statistics coming soon!"
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "perf":
            text = "⚡ **Performance Monitor**\n\nPerformance metrics coming soon!"
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "maintenance":
            text = "🔧 **Maintenance Tools**\n\nMaintenance options coming soon!"
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "restart":
            text = "🔄 **System Restart**\n\nRestart functionality coming soon!"
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "startup":
            text = "🚀 **Startup Config**\n\nStartup configuration coming soon!"
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
        elif action == "commands":
            text = "📚 **Command Reference**\n\nDeveloper command list coming soon!"
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            await self.bot.edit_message(
                user_id, event.message_id, text, buttons=buttons
            )
