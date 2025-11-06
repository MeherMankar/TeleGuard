"""
URGENT FIX FOR MENU BUTTONS NOT WORKING

The issue is that menu text handlers are not being triggered.
This is a direct fix that bypasses the complex async setup.
"""

# Add this to menu_system.py in the setup_menu_handlers method:

def setup_menu_handlers_DIRECT_FIX(self):
    """Direct fix - register handlers immediately without async complexity"""
    from telethon import events
    from teleguard.core.config import ADMIN_IDS
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Register missing handlers first
    from .missing_handlers import register_missing_handlers
    register_missing_handlers(self)
    
    # DIRECT TEXT HANDLER - No async wrapper
    @self.bot.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and e.text))
    async def direct_menu_handler(event):
        text = event.text.strip()
        user_id = event.sender_id
        
        logger.info(f"DIRECT HANDLER: Got text '{text}' from {user_id}")
        
        try:
            if text in ["📱 Account Settings", "Account Settings"]:
                await self.handlers.handle_account_settings(event)
            elif text in ["🛡️ OTP Manager", "OTP Manager"]:
                await self.handlers.handle_otp_manager(event)
            elif text in ["💬 Messaging", "Messaging"]:
                await self.handlers.handle_messaging(event)
            elif text in ["📢 Channels", "Channels"]:
                await self.handlers.handle_channels(event)
            elif text in ["👥 Contacts", "Contacts"]:
                await self._handle_contacts(event)
            elif text in ["🎯 SpamMaster", "SpamMaster"]:
                await self._handle_spam_master(event)
            elif text in ["🧹 Cleanup", "Cleanup"]:
                await self.handlers.handle_cleanup(event)
            elif text in ["❓ Help", "Help"]:
                await self.handlers.handle_help(event)
            elif text in ["🆘 Support", "Support"]:
                await self.handlers.handle_support(event)
            elif text in ["⚙️ Developer Panel", "⚙️ Developer", "Developer Panel", "Developer"]:
                if user_id in ADMIN_IDS:
                    await self.handlers.handle_developer(event)
                else:
                    await event.reply("❌ Access denied")
        except Exception as e:
            logger.error(f"Menu handler error: {e}", exc_info=True)
            await event.reply("❌ Error processing menu")
    
    # DIRECT CALLBACK HANDLER
    @self.bot.on(events.CallbackQuery())
    async def direct_callback_handler(event):
        try:
            user_id = event.sender_id
            data = event.data.decode("utf-8")
            logger.info(f"DIRECT CALLBACK: {data} from {user_id}")
            await self.router.route_callback(event, user_id, data)
        except Exception as e:
            logger.error(f"Callback error: {e}", exc_info=True)
            await event.answer("❌ Error")
    
    logger.info("✅ DIRECT handlers registered!")
    self._menu_text_handler = direct_menu_handler
    self._callback_handler = direct_callback_handler
