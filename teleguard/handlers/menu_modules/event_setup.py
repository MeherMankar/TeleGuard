"""Event handler setup"""
import logging
from telethon import events
from ...core.config import ADMIN_IDS

logger = logging.getLogger(__name__)

class EventSetup:
    def __init__(self, menu_system):
        self.menu = menu_system
        self.bot = menu_system.bot
    
    def setup_text_handlers(self):
        @self.bot.on(events.NewMessage(func=lambda e: e.is_private and e.text and e.text.strip() in ["📱 Account Settings", "Account Settings", "🛡️ OTP Manager", "OTP Manager", "💬 Messaging", "Messaging", "📨 DM Reply", "DM Reply", "📢 Channels", "Channels", "👥 Contacts", "Contacts", "🎯 SpamMaster", "SpamMaster", "🧹 Cleanup", "Cleanup", "❓ Help", "Help", "🆘 Support", "Support", "⚙️ Developer", "Developer"]))
        async def menu_text_handler(event):
            user_id = event.sender_id
            text = event.text.strip()
            try:
                if text in ["📱 Account Settings", "Account Settings"]:
                    await self.menu.handlers.handle_account_settings(event)
                elif text in ["🛡️ OTP Manager", "OTP Manager"]:
                    await self.menu.handlers.handle_otp_manager(event)
                elif text in ["💬 Messaging", "Messaging"]:
                    await self.menu.handlers.handle_messaging(event)
                elif text in ["📨 DM Reply", "DM Reply"]:
                    await self.menu._handle_dm_reply(event)
                elif text in ["📢 Channels", "Channels"]:
                    await self.menu.handlers.handle_channels(event)
                elif text in ["👥 Contacts", "Contacts"]:
                    await self.menu._handle_contacts(event)
                elif text in ["🎯 SpamMaster", "SpamMaster"]:
                    await self.menu._handle_spam_master(event)
                elif text in ["🧹 Cleanup", "Cleanup"]:
                    await self.menu.handlers.handle_cleanup(event)
                elif text in ["❓ Help", "Help"]:
                    await self.menu.handlers.handle_help(event)
                elif text in ["🆘 Support", "Support"]:
                    await self.menu.handlers.handle_support(event)
                elif text in ["⚙️ Developer", "Developer", "⚙️ Developer Panel", "Developer Panel"]:
                    if user_id not in ADMIN_IDS:
                        await event.reply("❌ You don't have access to Developer tools.")
                        return
                    await self.menu.handlers.handle_developer(event)
            except Exception as e:
                logger.error(f"Menu handler error for {text}: {e}")
                await event.reply("❌ Error processing menu action")
        self.menu._menu_text_handler = menu_text_handler
    
    def setup_callback_handler(self):
        @self.bot.on(events.CallbackQuery)
        async def callback_handler(event):
            try:
                user_id = event.sender_id
                data = event.data.decode("utf-8")
                logger.info(f"Callback from {user_id}: {data}")
                await self.menu.router.route_callback(event, user_id, data)
            except Exception as e:
                logger.error(f"Callback handler error: {e}")
                await event.answer("❌ Service temporarily unavailable", alert=True)
        self.menu._callback_handler = callback_handler
