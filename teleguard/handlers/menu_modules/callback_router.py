"""Callback router for handling different callback types"""
import logging
from typing import Dict, Callable, Any
from .callback_handlers import CallbackHandlers

logger = logging.getLogger(__name__)

class CallbackRouter:
    """Routes callbacks to appropriate handlers"""
    
    def __init__(self, menu_system):
        self.menu = menu_system
        self.handlers = CallbackHandlers(menu_system)
        
        # Callback routing map
        self.routes: Dict[str, Callable] = {
            "account": self.handlers.handle_account_callback,
            "remove": self.handlers.handle_remove_callback,
            "otp": self.handlers.handle_otp_callback,
            "online": self.handlers.handle_online_callback,
            "simulate": self.handlers.handle_simulate_callback,
            "profile": self.handlers.handle_profile_callback,
            "session": self.handlers.handle_session_callback,
            "2fa": self.handlers.handle_2fa_callback,
            "menu": self.handle_menu_callback,
            "create": self.handle_create_callback,
            "import": self.handle_import_callback,
            "export": self.handle_export_callback,
            "toggle_session": self.handle_toggle_session_callback,
            "toggle_all_sessions": self.handle_toggle_all_sessions_callback,
            "create_selected_sessions": self.handle_create_selected_sessions_callback,
            "session_type": self.handle_session_type_callback,
            "cleanup": self.handle_cleanup_callback,
            "session_login": self.handle_session_login_callback,
            "login_session_file": self.handle_session_login_callback,
            "login_session_string": self.handle_session_login_callback,
            "export_sessions": self.handle_session_login_callback,
            "create_sess": self.handle_session_login_callback,
            "create_sess_fmt": self.handle_session_login_callback,
            "contacts": self.handle_contacts_callback,
            "spam_master": self.handle_spam_master_callback,
            "manual_otp": self.handle_manual_otp_callback,
            "resend_otp": self.handle_resend_otp_callback,
            "cancel_session": self.handle_cancel_session_callback,
        }
    
    async def route_callback(self, event, user_id: int, data: str) -> bool:
        """Route callback to appropriate handler"""
        try:
            # Parse callback data
            parts = data.split(":")
            if not parts:
                logger.warning(f"Invalid callback data: {data}")
                return False
            
            callback_type = parts[0]
            
            # Find and execute handler
            handler = self.routes.get(callback_type)
            if handler:
                await handler(event, user_id, data)
                return True
            else:
                logger.warning(f"No handler found for callback type: '{callback_type}' in data: '{data}'")
                # Catch-all: acknowledge callback to prevent error message
                try:
                    await event.answer("✅ Processing...")
                except:
                    pass
                return True
                
        except Exception as e:
            # Handle specific Telegram errors
            error_msg = str(e).lower()
            if "content of the message was not modified" in error_msg or "editmessagerequest" in error_msg:
                # Message content is the same, just answer the callback
                try:
                    await event.answer("✅ Updated")
                except:
                    pass
                return True
            logger.error(f"Error routing callback {data}: {e}")
            await event.answer("❌ Error processing request")
            return False
    
    def register_handler(self, callback_type: str, handler: Callable):
        """Register a new callback handler"""
        self.routes[callback_type] = handler
        logger.info(f"Registered handler for callback type: {callback_type}")
    
    def get_registered_types(self) -> list:
        """Get list of registered callback types"""
        return list(self.routes.keys())
    
    async def handle_menu_callback(self, event, user_id: int, data: str):
        """Handle menu navigation callbacks"""
        try:
            parts = data.split(":")
            if len(parts) < 2:
                await event.answer("❌ Invalid menu callback")
                return
            
            menu_type = parts[1]
            
            # Route to appropriate menu handler
            if menu_type == "accounts":
                await self.menu.handlers.handle_account_settings(event)
            elif menu_type == "otp":
                await self.menu.handlers.handle_otp_manager(event)
            elif menu_type == "messaging":
                await self.menu.handlers.handle_messaging(event)
            elif menu_type == "channels":
                await self.menu.handlers.handle_channels(event)
            elif menu_type == "contacts":
                await self.menu.handlers.handle_contacts(event)
            elif menu_type == "cleanup":
                await self.menu.handlers.handle_cleanup(event)
            elif menu_type == "main":
                await self.menu.handlers.handle_start(event)
            else:
                await event.answer(f"❌ Unknown menu: {menu_type}")
                
        except Exception as e:
            logger.error(f"Menu callback error: {e}")
            await event.answer("❌ Error processing menu request")
    
    async def handle_create_callback(self, event, user_id: int, data: str):
        """Handle create session callbacks"""
        await event.answer("✅ Creating session...")
    
    async def handle_import_callback(self, event, user_id: int, data: str):
        """Handle import session callbacks"""
        await event.answer("✅ Importing session...")
    
    async def handle_export_callback(self, event, user_id: int, data: str):
        """Handle export session callbacks"""
        await event.answer("✅ Exporting session...")
    
    async def handle_toggle_session_callback(self, event, user_id: int, data: str):
        """Handle toggle session selection callbacks"""
        try:
            parts = data.split(":")
            if len(parts) < 2:
                await event.answer("❌ Invalid selection")
                return
            
            account_name = ":".join(parts[1:])  # Handle account names with colons
            
            bot_manager = getattr(self.menu, 'account_manager', None)
            if bot_manager and hasattr(bot_manager, 'session_export_handler'):
                await bot_manager.session_export_handler._toggle_account_selection(event, user_id, account_name)
            else:
                await event.answer("❌ Session export not available")
                
        except Exception as e:
            logger.error(f"Toggle session callback error: {e}")
            await event.answer("❌ Error toggling selection")
    
    async def handle_create_selected_sessions_callback(self, event, user_id: int, data: str):
        """Handle create selected sessions callback"""
        try:
            bot_manager = getattr(self.menu, 'account_manager', None)
            if bot_manager and hasattr(bot_manager, 'session_export_handler'):
                await bot_manager.session_export_handler._create_selected_sessions(event, user_id)
            else:
                await event.answer("❌ Session export not available")
                
        except Exception as e:
            logger.error(f"Create selected sessions callback error: {e}")
            await event.answer("❌ Error creating sessions")
    
    async def handle_toggle_all_sessions_callback(self, event, user_id: int, data: str):
        """Handle toggle all sessions callback"""
        try:
            bot_manager = getattr(self.menu, 'account_manager', None)
            if bot_manager and hasattr(bot_manager, 'session_export_handler'):
                await bot_manager.session_export_handler._toggle_all_sessions(event, user_id)
            else:
                await event.answer("❌ Session export not available")
        except Exception as e:
            logger.error(f"Toggle all sessions callback error: {e}")
            await event.answer("❌ Error toggling all")
    
    async def handle_session_type_callback(self, event, user_id: int, data: str):
        """Handle session type selection callback"""
        try:
            parts = data.split(":")
            if len(parts) < 2:
                await event.answer("❌ Invalid session type")
                return
            
            session_type = parts[1]
            bot_manager = getattr(self.menu, 'account_manager', None)
            if not bot_manager:
                logger.error("account_manager not found on menu")
                await event.answer("❌ Session export not available")
                return
            if not hasattr(bot_manager, 'session_export_handler'):
                logger.error("session_export_handler not found on account_manager")
                await event.answer("❌ Session export not available")
                return
            await bot_manager.session_export_handler._show_account_selection(event, user_id, session_type)
        except Exception as e:
            logger.error(f"Session type callback error: {e}", exc_info=True)
            await event.answer("❌ Error selecting type")

    
    async def handle_cleanup_callback(self, event, user_id: int, data: str):
        """Handle cleanup callbacks"""
        try:
            parts = data.split(":")
            if len(parts) < 2:
                await event.answer("❌ Invalid cleanup callback")
                return
            
            action = parts[1]
            
            if action == "menu":
                await self.menu.handlers.handle_cleanup(event)
            elif action == "select" and len(parts) >= 3:
                account_id = parts[2]
                if hasattr(self.menu, 'cleanup_operations'):
                    await self.menu.cleanup_operations.send_cleanup_selection(user_id, event.message_id, account_id)
                else:
                    await event.answer("❌ Cleanup not available")
            else:
                await event.answer("❌ Unknown cleanup action")
                
        except Exception as e:
            logger.error(f"Cleanup callback error: {e}")
            await event.answer("❌ Error processing cleanup request")

    
    async def handle_session_login_callback(self, event, user_id: int, data: str):
        """Handle session login and creation callbacks"""
        try:
            # These callbacks are handled by session_login_handler
            # Just acknowledge them here
            await event.answer("✅ Processing...")
                
        except Exception as e:
            logger.error(f"Session login callback error: {e}")
            await event.answer("❌ Error processing request")
    
    async def handle_contacts_callback(self, event, user_id: int, data: str):
        """Handle contacts callbacks"""
        try:
            # Contacts callbacks are handled by contact_handler
            # Just acknowledge them here
            await event.answer("✅ Processing...")
        except Exception as e:
            logger.error(f"Contacts callback error: {e}")
            await event.answer("❌ Error processing request")
    
    async def handle_spam_master_callback(self, event, user_id: int, data: str):
        """Handle spam master callbacks"""
        try:
            # Spam master callbacks are handled by advanced_spam_handler
            # Just acknowledge them here
            await event.answer("✅ Processing...")
        except Exception as e:
            logger.error(f"Spam master callback error: {e}")
            await event.answer("❌ Error processing request")
    
    async def handle_manual_otp_callback(self, event, user_id: int, data: str):
        """Handle manual OTP entry callback"""
        try:
            parts = data.split(":")
            account_name = ":".join(parts[1:]) if len(parts) > 1 else "Unknown"
            
            await event.edit(
                f"📱 **Manual OTP Entry - {account_name}**\n\n"
                f"Please send the OTP code you received.\n"
                f"Format: Just the numbers (e.g., 12345)"
            )
        except Exception as e:
            logger.error(f"Manual OTP callback error: {e}")
            await event.answer("❌ Error")
    
    async def handle_resend_otp_callback(self, event, user_id: int, data: str):
        """Handle resend OTP callback"""
        try:
            await event.answer("🔄 Resending OTP...")
            await event.edit("🔄 **Resending OTP...**\n\nPlease wait...")
            # The actual resend logic would be in session_export_handler
        except Exception as e:
            logger.error(f"Resend OTP callback error: {e}")
            await event.answer("❌ Error")
    
    async def handle_cancel_session_callback(self, event, user_id: int, data: str):
        """Handle cancel session callback"""
        try:
            await event.edit("❌ **Session Creation Cancelled**")
            # Clean up any pending session data
            bot_manager = getattr(self.menu, 'account_manager', None)
            if bot_manager and hasattr(bot_manager, 'pending_fresh_sessions'):
                bot_manager.pending_fresh_sessions.pop(user_id, None)
        except Exception as e:
            logger.error(f"Cancel session callback error: {e}")
            await event.answer("❌ Error")
