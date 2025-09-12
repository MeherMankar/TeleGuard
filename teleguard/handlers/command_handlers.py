"""Essential handlers - all actions via buttons only"""

import logging

from telethon import Button, events

from ..core.config import MAX_ACCOUNTS
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class CommandHandlers:
    """Handles all bot command events"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.menu_system = bot_manager.menu_system
        self.auth_manager = bot_manager.auth_manager
        self.pending_actions = bot_manager.pending_actions
        self.user_clients = bot_manager.user_clients
        self.messaging_manager = bot_manager.messaging_manager

        # Initialize channel manager
        from .channel_manager import ChannelManager

        self.channel_manager = ChannelManager(bot_manager)

    def register_handlers(self):
        """Register only essential handlers - all actions via buttons"""

        @self.bot.on(events.NewMessage(pattern=r"/start"))
        async def start_handler(event):
            user_id = event.sender_id
            user = await mongodb.get_user(user_id)
            is_new_user = user is None
            if not user:
                await mongodb.create_user(user_id)

            if is_new_user:
                welcome_text = (
                    "🤖 **Welcome to TeleGuard!**\n\n"
                    "Your professional Telegram account manager with advanced OTP destroyer protection.\n\n"
                    "**🚀 Quick Start:**\n"
                    "1️⃣ Add your first account via '📱 Account Settings'\n"
                    "2️⃣ Enable OTP protection in '🛡️ OTP Manager'\n"
                    "3️⃣ Explore features using the menu below\n\n"
                    "**🛡️ Key Features:**\n"
                    "• Real-time OTP destroyer protection\n"
                    "• Multi-account management (up to 10)\n"
                    "• 2FA management & session control\n"
                    "• Activity simulation & automation\n"
                    "• Secure profile & channel management\n\n"
                    "**💬 Need Help?** Use '❓ Help' or contact @Meher_Mankar"
                )
            else:
                welcome_text = "🤖 **TeleGuard Account Manager**\n\nWelcome back! Use the menu below to manage your accounts."

            keyboard = self.menu_system.get_main_menu_keyboard(user_id)
            await event.reply(welcome_text, buttons=keyboard)

        # Cancel handler for interrupting text input flows
        @self.bot.on(events.NewMessage(pattern=r"/cancel"))
        async def cancel_handler(event):
            user_id = event.sender_id
            if user_id in self.pending_actions:
                self.auth_manager.cancel_auth(user_id)
                self.pending_actions.pop(user_id, None)
                await event.reply(
                    "❌ Operation cancelled. Use the menu buttons to continue."
                )
            else:
                await event.reply(
                    "ℹ️ No operation to cancel. Use the menu buttons below."
                )

    async def _send_account_selection(self, user_id: int):
        """Send account selection menu for channel management"""
        try:
            accounts = await mongodb.db.accounts.find(
                {"user_id": user_id, "is_active": True}
            ).to_list(length=None)

            if not accounts:
                text = "📱 **Channel Management**\n\nNo active accounts found. Add accounts first to manage channels."
                buttons = [[Button.inline("➕ Add Account", "account:add")]]
                await self.bot.send_message(user_id, text, buttons=buttons)
                return

            text = "📱 **Channel Management**\n\nSelect an account to manage channels:"
            buttons = []

            for account in accounts[:8]:  # Limit to 8 accounts
                status = "🔗" if account.get("is_active", False) else "🔴"
                button_text = f"{status} {account['name']}"
                buttons.append(
                    [Button.inline(button_text, f"manage:{account['phone']}")]
                )

            buttons.append([Button.inline("🔙 Back to Main Menu", "menu:main")])
            await self.bot.send_message(user_id, text, buttons=buttons)

        except Exception as e:
            logger.error(f"Failed to send account selection: {e}")
            await self.bot.send_message(user_id, "❌ Error loading accounts")
