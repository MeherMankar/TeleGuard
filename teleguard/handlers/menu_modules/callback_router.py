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
            "create_selected_sessions": self.handle_create_selected_sessions_callback,
            "clear_session_selection": self.handle_clear_session_selection_callback,
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
                # Try to handle common patterns
                if callback_type in ["create", "import", "export"]:
                    await event.answer("✅ Processing...")
                    return True
                await event.answer("❌ Unknown callback type")
                return False
                
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
            
            if hasattr(self.menu.bot_manager, 'session_export_handler'):
                await self.menu.bot_manager.session_export_handler._toggle_account_selection(event, user_id, account_name)
            else:
                await event.answer("❌ Session export not available")
                
        except Exception as e:
            logger.error(f"Toggle session callback error: {e}")
            await event.answer("❌ Error toggling selection")
    
    async def handle_create_selected_sessions_callback(self, event, user_id: int, data: str):
        """Handle create selected sessions callback"""
        try:
            if hasattr(self.menu.bot_manager, 'session_export_handler'):
                await self.menu.bot_manager.session_export_handler._create_selected_sessions(event, user_id)
            else:
                await event.answer("❌ Session export not available")
                
        except Exception as e:
            logger.error(f"Create selected sessions callback error: {e}")
            await event.answer("❌ Error creating sessions")
    
    async def handle_clear_session_selection_callback(self, event, user_id: int, data: str):
        """Handle clear session selection callback"""
        try:
            if hasattr(self.menu.bot_manager, 'session_export_handler'):
                await self.menu.bot_manager.session_export_handler._clear_session_selection(event, user_id)
            else:
                await event.answer("❌ Session export not available")
                
        except Exception as e:
            logger.error(f"Clear session selection callback error: {e}")
            await event.answer("❌ Error clearing selection")