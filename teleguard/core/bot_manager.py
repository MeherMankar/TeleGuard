"""
Professional Bot Manager for TeleGuard
Centralized bot lifecycle management with dependency injection,
error handling, and modular component initialization.
Authors: @Meher_Mankar, @Gutkesh
Repository: https://github.com/mehermankar/teleguard
"""
import asyncio
import logging
import time
from typing import Dict, Optional, Set, Any
from contextlib import asynccontextmanager
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from .config import config
from .exceptions import TeleGuardError, ConfigurationError
from .mongo_database import init_db, mongodb
from ..utils.response_formatter import LogFormatter
from ..utils.account_invalidation import init_account_invalidation_handler
logger = logging.getLogger(__name__)
class ComponentManager:
    """Manages bot components and their lifecycle"""
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.components: Dict[str, Any] = {}
        self.initialized_components: Set[str] = set()
    async def initialize_component(self, name: str, component_class, *args, **kwargs) -> Any:
        """Initialize a component with error handling"""
        try:
            if name in self.initialized_components:
                return self.components[name]
            logger.debug(f"Initializing component: {name}")
            component = component_class(*args, **kwargs)
            if hasattr(component, 'register_handlers'):
                await self._safe_call(component.register_handlers, f"{name}.register_handlers")
            if hasattr(component, 'setup'):
                await self._safe_call(component.setup, f"{name}.setup")
            self.components[name] = component
            self.initialized_components.add(name)
            logger.debug(f"✅ Component initialized: {name}")
            return component
        except Exception as e:
            logger.error(f"❌ Failed to initialize component {name}: {e}")
            raise TeleGuardError(f"Component initialization failed: {name}", details={'error': str(e)})
    async def _safe_call(self, method, method_name: str):
        """Safely call a method with error handling"""
        try:
            if asyncio.iscoroutinefunction(method):
                await method()
            else:
                method()
        except Exception as e:
            logger.warning(f"Error in {method_name}: {e}")
    async def cleanup_all(self):
        """Cleanup all components"""
        for name, component in self.components.items():
            try:
                if hasattr(component, 'cleanup'):
                    await self._safe_call(component.cleanup, f"{name}.cleanup")
                elif hasattr(component, 'stop'):
                    await self._safe_call(component.stop, f"{name}.stop")
                elif hasattr(component, 'stop_automation_engine'):
                    await self._safe_call(component.stop_automation_engine, f"{name}.stop_automation_engine")
            except Exception as e:
                logger.warning(f"Error cleaning up {name}: {e}")
class BotManager:
    """
    Professional bot manager with modular architecture.
    Handles bot lifecycle, component management, and provides
    a clean interface for all bot operations.
    """
    def __init__(self):
        self.bot: Optional[TelegramClient] = None
        self.user_clients: Dict[int, Dict[str, TelegramClient]] = {}
        self.pending_actions: Dict[int, Dict[str, Any]] = {}
        self.pending_2fa_storage: Dict[int, Dict[str, Any]] = {}
        self.component_manager = ComponentManager(self)
        self.registered_handlers: Dict[str, Set[str]] = {
            "otp": set(),
            "messaging": set(),
            "auto_reply": set()
        }
        self.start_time = time.time()
        self.auth_manager = None
        self.account_invalidation_handler = None
        self.otp_manager = None
        self.menu_system = None
        self.messaging_manager = None
        self.unified_messaging = None
        self.automation_engine = None
        self.session_login_handler = None
        self.session_operations_handler = None
        self.session_scheduler = None
        self.dm_reply_commands = None
        self.dm_reply_handler = None
        self.session_monitor = None

        # SessionMaster functionality is integrated into existing components
        self._is_running = False
        self._startup_complete = False
        self.spam_detector = None
    async def __aenter__(self):
        await self.start_bot()
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
    @property
    def is_running(self) -> bool:
        return self._is_running and self.bot and self.bot.is_connected()
    @property
    def startup_complete(self) -> bool:
        return self._startup_complete
    async def start_bot(self) -> None:
        """
        Initialize and start the bot with comprehensive error handling.
        Raises:
            ConfigurationError: If configuration is invalid
            TeleGuardError: If startup fails
        """
        try:
            print("Starting TeleGuard Bot...")
            logger.info("Starting TeleGuard Bot...")
            self._validate_configuration()
            await self._initialize_database()
            await self._initialize_bot_client()
            await self._load_existing_sessions()
            await self._initialize_components()
            # Initialize account invalidation handler
            self.account_invalidation_handler = init_account_invalidation_handler(self)
            # Mark as running
            self._is_running = True
            self._startup_complete = True
            print("TeleGuard Bot started successfully!")
            logger.info("TeleGuard Bot started successfully")
        except Exception as e:
            logger.error(f"Bot startup failed: {e}")
            await self.cleanup()
            raise TeleGuardError("Bot startup failed", details={'error': str(e)})
    def _validate_configuration(self) -> None:
        if not config.telegram.api_id or not config.telegram.api_hash or not config.telegram.bot_token:
            raise ConfigurationError("Telegram API credentials are incomplete")
        if not config.database.mongodb_uri:
            raise ConfigurationError("Database configuration is missing")
        if not config.security.admin_ids:
            logger.warning("No admin users configured")
    async def _initialize_database(self) -> None:
        try:
            await init_db()
            print("Database connected")
            logger.info("Database initialized")
        except Exception as e:
            raise TeleGuardError("Database initialization failed", details={'error': str(e)})
    async def _initialize_bot_client(self) -> None:
        try:
            session_name = f"teleguard_bot_{int(time.time())}"
            self.bot = TelegramClient(session_name, config.telegram.api_id, config.telegram.api_hash)
            await self._start_bot_with_retry()
            # Clear any existing handlers to prevent duplicates
            self.bot.remove_event_handler()
            print("Bot authenticated")
            logger.info("Bot client initialized")
        except Exception as e:
            raise TeleGuardError("Bot client initialization failed", details={'error': str(e)})
    async def _start_bot_with_retry(self) -> None:
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                await self.bot.start(bot_token=config.telegram.bot_token)
                return
            except Exception as e:
                if "FloodWaitError" in str(e) or "wait of" in str(e):
                    import re
                    wait_match = re.search(r'wait of (\d+) seconds', str(e))
                    if wait_match:
                        wait_time = min(int(wait_match.group(1)), 300)
                        logger.warning(f"Rate limited, waiting {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                        retry_count += 1
                        continue
                raise e
        raise TeleGuardError("Bot startup failed after retries")
    async def _load_existing_sessions(self) -> None:
        try:
            print("Loading user accounts...")
            logger.info("Loading existing user sessions...")
            accounts = await asyncio.wait_for(
                mongodb.db.accounts.find({"is_active": True}).to_list(length=None),
                timeout=5.0
            )
            loaded_count = 0
            for account in accounts[:5]:  # Limit to 5 accounts for faster startup
                if account.get("session_string"):
                    try:
                        await asyncio.wait_for(
                            self._start_user_client(
                                account["user_id"],
                                account.get('name', 'Unknown'),
                                account["session_string"]
                            ),
                            timeout=3.0
                        )
                        loaded_count += 1
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout loading client for {account.get('name')}")
                    except Exception as e:
                        error_msg = str(e).lower()
                        account_name = account.get('name', 'Unknown')
                        phone = account.get('phone', 'Unknown')
                        
                        # Check if this is a session invalidation error
                        if any(phrase in error_msg for phrase in [
                            "authorization key", "auth_key_unregistered", "session_revoked",
                            "user_deactivated", "failed to get valid user info", "duplicated",
                            "session_password_needed", "unauthorized", "invalid session"
                        ]):
                            print(f"Account '{account_name}' invalidated - will be removed")
                            # Handle account invalidation asynchronously
                            asyncio.create_task(
                                self._handle_session_invalidation(
                                    account["user_id"], account_name, phone, str(e)
                                )
                            )
                        else:
                            print(f"Could not load account '{account_name}'")
                        logger.warning(f"Failed to load client for {account_name}: {e}")
            if loaded_count > 0:
                print(f"Loaded {loaded_count} user account(s)")
            else:
                print("No user accounts found (add accounts via /start)")
            logger.info(f"Loaded {loaded_count} user sessions")
        except asyncio.TimeoutError:
            logger.warning("Timeout loading sessions, continuing without them")
            print("Session loading timed out - bot will start without pre-loaded accounts")
        except Exception as e:
            logger.error(f"Failed to load existing sessions: {e}")
        

    async def _start_user_client(self, user_id: int, account_name: str, session_string: str) -> None:
        try:
            # Validate session string format before creating client
            if not session_string or not isinstance(session_string, str):
                raise ValueError("Invalid session string format")
            
            # Create client with session string
            client = TelegramClient(
                StringSession(session_string), 
                config.telegram.api_id, 
                config.telegram.api_hash,

                connection_retries=2,
                retry_delay=2,
                timeout=10
            )
            
            # Connect with timeout and better error handling
            try:
                await asyncio.wait_for(client.connect(), timeout=5.0)
                
                # Test the connection by getting basic info
                try:
                    from ..utils.network_helpers import get_user_info_safe
                    user_info = await get_user_info_safe(client)
                    logger.debug(f"Successfully validated user info for {account_name}")
                except Exception as e:
                    logger.error(f"Failed to get valid user info for {account_name}: {e}")
                    raise ValueError(f"Failed to get valid user info for {account_name}")
                
            except Exception as e:
                # Handle specific session errors
                error_msg = str(e).lower()
                if any(phrase in error_msg for phrase in [
                    "authorization key", "ip addresses", "session file", 
                    "failed to get valid user info", "invalid session", "duplicated",
                    "auth_key_unregistered", "session_revoked", "user_deactivated",
                    "unauthorized", "session_password_needed"
                ]):
                    # Handle account invalidation
                    phone = await self._get_phone_for_account(user_id, account_name)
                    asyncio.create_task(
                        self._handle_session_invalidation(user_id, account_name, phone, str(e))
                    )
                    logger.warning(f"Account {account_name} invalidated and will be removed: {e}")
                try:
                    await client.disconnect()
                except Exception:
                    pass  # Ignore disconnect errors
                raise
            
            # Store client
            if user_id not in self.user_clients:
                self.user_clients[user_id] = {}
            self.user_clients[user_id][account_name] = client
            
            # Add to session monitor if available
            if hasattr(self, 'session_monitor') and self.session_monitor:
                self.session_monitor.add_client_to_monitor(user_id, account_name, client)
            
            # Add additional references for phone and display name
            account = await asyncio.wait_for(
                mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name}),
                timeout=2.0
            )
            if account:
                if account.get('phone'):
                    self.user_clients[user_id][account['phone']] = client
                if account.get('display_name') and account['display_name'] != account_name:
                    self.user_clients[user_id][account['display_name']] = client
                    
                # Mark account as active if connection successful
                await mongodb.db.accounts.update_one(
                    {"user_id": user_id, "name": account_name},
                    {"$unset": {"needs_reauth": ""}, "$set": {"is_active": True}}
                )
            
            logger.debug(f"Started client for user {user_id}, account {account_name}")
        except asyncio.TimeoutError:
            logger.warning(f"Timeout starting client for {account_name}")
            raise
        except Exception as e:
            logger.error(f"Failed to start user client {account_name}: {e}")
            raise
    async def _initialize_components(self) -> None:
        try:
            print("Initializing features...")
            logger.info("Initializing components...")
            await asyncio.wait_for(self._initialize_core_components(), timeout=30.0)
            await asyncio.wait_for(self._initialize_handlers(), timeout=30.0)
            await asyncio.wait_for(self._initialize_services(), timeout=15.0)
            await asyncio.wait_for(self._initialize_workers(), timeout=10.0)
            
            # Initialize auto backup system
            try:
                from ..utils.backups import init_auto_backup, start_auto_backup
                init_auto_backup(self.bot)
                await start_auto_backup()
                print("  Auto backup system ready")
                logger.info("Auto backup system initialized")
            except Exception as e:
                logger.warning(f"Auto backup initialization failed: {e}")
            
            # Set up DM handlers for loaded sessions after all components are initialized
            if self.dm_reply_handler:
                try:
                    await self.dm_reply_handler.setup_dm_handlers()
                    print("  DM Reply system ready")
                    logger.info("DM handlers set up for existing sessions")
                except Exception as e:
                    logger.warning(f"Failed to set up DM handlers: {e}")
            
            print("All features ready")
            logger.info("All components initialized")
        except asyncio.TimeoutError:
            logger.error("Component initialization timed out")
            raise TeleGuardError("Component initialization timeout")
        except Exception as e:
            logger.error(f"Component initialization failed: {e}")
            raise
    async def _initialize_core_components(self) -> None:
        print("  Setting up security features...")
        logger.info("Initializing core components...")
        from ..handlers.auth_handler import AuthManager
        from ..handlers.menu_system import MenuSystem
        from ..core.otp_manager import OTPManager
        from ..core.messaging import MessagingManager
        
        logger.info("Initializing auth manager...")
        self.auth_manager = await self.component_manager.initialize_component(
            "auth_manager", AuthManager, self
        )
        
        logger.info("Initializing menu system...")
        self.menu_system = await self.component_manager.initialize_component(
            "menu_system", MenuSystem, self.bot, self
        )
        
        logger.info("Initializing OTP manager...")
        self.otp_manager = await self.component_manager.initialize_component(
            "otp_manager", OTPManager, self
        )
        
        logger.info("Initializing messaging manager...")
        self.messaging_manager = await self.component_manager.initialize_component(
            "messaging_manager", MessagingManager, self
        )
        print("  OTP Destroyer ready")
        print("  Messaging system ready")
        print("  Menu system ready")
        
        # Set unified_messaging as alias to messaging_manager for compatibility
        self.unified_messaging = self.messaging_manager
        # SessionMaster analytics and automation are integrated into handlers
    async def _initialize_handlers(self) -> None:
        from ..handlers.command_handlers import CommandHandlers
        from ..handlers.start_handler import StartHandler
        from ..handlers.message_handlers import MessageHandlers
        from ..handlers.session_export_handler import SessionExportHandler
        from ..handlers.session_login_handler import SessionLoginHandler
        from ..handlers.dm_reply_commands import DMReplyCommands
        from ..handlers.dm_reply_handler import DMReplyHandler

        
        self.command_handlers = await self.component_manager.initialize_component(
            "command_handlers", CommandHandlers, self
        )
        await self.component_manager.initialize_component(
            "start_handler", StartHandler, self.bot, self.menu_system, self
        )
        await self.component_manager.initialize_component(
            "message_handlers", MessageHandlers, self
        )
        self.session_export_handler = await self.component_manager.initialize_component(
            "session_export_handler", SessionExportHandler, self
        )
        self.session_login_handler = await self.component_manager.initialize_component(
            "session_login_handler", SessionLoginHandler, self
        )
        self.dm_reply_commands = await self.component_manager.initialize_component(
            "dm_reply_commands", DMReplyCommands, self.bot, self
        )
        self.dm_reply_handler = await self.component_manager.initialize_component(
            "dm_reply_handler", DMReplyHandler, self
        )
        
        from ..handlers.admin_handlers import AdminHandlers
        self.admin_handlers = await self.component_manager.initialize_component(
            "admin_handlers", AdminHandlers, self
        )
        
        from ..handlers.developer_commands import DeveloperCommands
        self.developer_commands = await self.component_manager.initialize_component(
            "developer_commands", DeveloperCommands, self
        )
        
        from ..handlers.spam_appeal_handler import SpamAppealHandler
        self.spam_appeal_handler = await self.component_manager.initialize_component(
            "spam_appeal_handler", SpamAppealHandler, self
        )
        

        
        # Initialize spam detector
        from ..utils.spam_detector import SpamDetector
        from pathlib import Path
        
        # Load appeal messages
        messages_file = Path(__file__).parent.parent / "data" / "appeal_messages.txt"
        appeal_messages = []
        try:
            if messages_file.exists():
                content = messages_file.read_text(encoding='utf-8')
                appeal_messages = [msg.strip() for msg in content.split('\n\n') if msg.strip()]
        except Exception as e:
            logger.warning(f"Failed to load appeal messages: {e}")
        
        self.spam_detector = SpamDetector(appeal_messages)
        logger.info(f"Spam detector initialized with {len(appeal_messages)} appeal messages")

    async def _initialize_services(self) -> None:
        from ..core.automation import AutomationEngine
        from ..workers.activity_simulator import ActivitySimulator
        self.automation_engine = await self.component_manager.initialize_component(
            "automation_engine", AutomationEngine, self.user_clients, None
        )
        await self.component_manager.initialize_component(
            "activity_simulator", ActivitySimulator, self
        )
        print(f"  Smart spam detection ready ({len(self.spam_detector.appeal_messages)} messages)")
    async def _initialize_workers(self) -> None:
        """Initialize background workers"""
        if self.automation_engine:
            try:
                await self.automation_engine.start()
            except Exception as e:
                logger.warning(f"Automation engine start failed: {e}")
        
        # SessionMaster automation is integrated into existing handlers
        
        # Initialize session monitor
        from ..workers.session_monitor import SessionMonitor
        self.session_monitor = SessionMonitor(self)
        await self.session_monitor.start_monitoring()
        
        # Initialize account invalidation handler
        from ..utils.account_invalidation import init_account_invalidation_handler
        self.account_invalidation_handler = init_account_invalidation_handler(self)
    async def start_user_client(self, user_id: int, account_name: str, session_string: str) -> None:
        """Public method to start a user client"""
        await self._start_user_client(user_id, account_name, session_string)
    
    async def add_user_account(self, user_id: int, account_name: str, session_string: str) -> bool:
        """
        Add a new user account.
        Args:
            user_id: User's Telegram ID
            account_name: Account name
            session_string: Telethon session string
        Returns:
            True if successful, False otherwise
        """
        try:
            await self._start_user_client(user_id, account_name, session_string)
            if self.otp_manager:
                client = self.user_clients[user_id][account_name]
                await self.otp_manager.setup_handler_for_new_client(user_id, account_name, client)
            if self.dm_reply_handler:
                client = self.user_clients[user_id][account_name]
                await self.dm_reply_handler.setup_new_client_handler(user_id, account_name, client)
            logger.info(LogFormatter.format_user_action(
                user_id, "account_added", {"account_name": account_name}
            ))
            return True
        except Exception as e:
            logger.error(f"Failed to add user account: {e}")
            return False
    async def remove_account_by_id(self, user_id: int, account_id: str):
        """Remove account by ID"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            if not account:
                return False, "Account not found"
            
            account_name = account.get('name', 'Unknown')
            
            # Remove stored 2FA password for security
            try:
                from .database_manager import db_manager
                await db_manager.remove_2fa_password(user_id, account_id)
                logger.info(f"Removed stored 2FA password for account {account_name}")
            except Exception as e:
                logger.warning(f"Failed to remove 2FA password for {account_name}: {e}")
            
            # Disconnect client
            if user_id in self.user_clients:
                for key in list(self.user_clients[user_id].keys()):
                    if key in [account.get('name'), account.get('phone'), account.get('display_name')]:
                        client = self.user_clients[user_id].pop(key, None)
                        if client and client.is_connected():
                            await client.disconnect()
            
            # Remove from database
            await mongodb.db.accounts.delete_one({"_id": ObjectId(account_id)})
            
            logger.info(f"Removed account {account_name} for user {user_id}")
            return True, f"Account {account_name} removed successfully"
        except Exception as e:
            logger.error(f"Failed to remove account: {e}")
            return False, f"Failed to remove account: {str(e)}"
    
    async def remove_user_account(self, user_id: int, account_name: str) -> bool:
        """
        Remove a user account.
        Args:
            user_id: User's Telegram ID
            account_name: Account name
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get account ID for 2FA removal
            account = await mongodb.db.accounts.find_one({
                "user_id": user_id,
                "name": account_name
            })
            
            if account:
                # Remove stored 2FA password for security
                try:
                    from .database_manager import db_manager
                    await db_manager.remove_2fa_password(user_id, str(account['_id']))
                    logger.info(f"Removed stored 2FA password for account {account_name}")
                except Exception as e:
                    logger.warning(f"Failed to remove 2FA password for {account_name}: {e}")
            
            # Remove from session monitor
            if hasattr(self, 'session_monitor') and self.session_monitor:
                self.session_monitor.remove_client_from_monitor(user_id, account_name)
            
            # Disconnect client
            if user_id in self.user_clients and account_name in self.user_clients[user_id]:
                client = self.user_clients[user_id][account_name]
                if client.is_connected():
                    await client.disconnect()
                del self.user_clients[user_id][account_name]
            
            await mongodb.db.accounts.delete_one({
                "user_id": user_id,
                "name": account_name
            })
            logger.info(LogFormatter.format_user_action(
                user_id, "account_removed", {"account_name": account_name}
            ))
            return True
        except Exception as e:
            logger.error(f"Failed to remove user account: {e}")
            return False

    async def remove_account(self, account_id: str) -> bool:
        """
        Remove account by ID (alias for compatibility).
        Args:
            account_id: Account ID from database
        Returns:
            True if successful, False otherwise
        """
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id)})
            if not account:
                return False
            success, message = await self.remove_account_by_id(account["user_id"], str(account["_id"]))
            return success
        except Exception as e:
            logger.error(f"Failed to remove account {account_id}: {e}")
            return False
    
    async def get_accounts_needing_reauth(self, user_id: int) -> list:
        """Get accounts that need re-authentication"""
        try:
            accounts = await mongodb.db.accounts.find({
                "user_id": user_id,
                "needs_reauth": True
            }).to_list(length=None)
            return accounts
        except Exception as e:
            logger.error(f"Failed to get accounts needing reauth: {e}")
            return []
    
    async def clear_invalid_sessions(self, user_id: int) -> int:
        """Clear all invalid sessions for a user"""
        try:
            result = await mongodb.db.accounts.delete_many({
                "user_id": user_id,
                "needs_reauth": True
            })
            
            # Also remove from active clients
            if user_id in self.user_clients:
                invalid_clients = []
                for name, client in self.user_clients[user_id].items():
                    try:
                        if client.is_connected():
                            await client.disconnect()
                        invalid_clients.append(name)
                    except Exception:
                        pass
                
                for name in invalid_clients:
                    self.user_clients[user_id].pop(name, None)
            
            logger.info(f"Cleared {result.deleted_count} invalid sessions for user {user_id}")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Failed to clear invalid sessions: {e}")
            return 0
    def get_user_client(self, user_id: int, account_name: str) -> Optional[TelegramClient]:
        """Get user client by ID and account name"""
        return self.user_clients.get(user_id, {}).get(account_name)
    def get_user_clients(self, user_id: int) -> Dict[str, TelegramClient]:
        """Get all clients for a user"""
        return self.user_clients.get(user_id, {})
    async def cleanup(self) -> None:
        """Clean up all resources"""
        try:
            logger.info("Starting cleanup...")
            self._is_running = False
            
            # Stop session monitor
            if hasattr(self, 'session_monitor') and self.session_monitor:
                try:
                    await self.session_monitor.stop_monitoring()
                except Exception as e:
                    logger.warning(f"Session monitor cleanup failed: {e}")
            
            # Stop auto backup system
            try:
                from ..utils.backups import stop_auto_backup
                await stop_auto_backup()
            except Exception as e:
                logger.warning(f"Auto backup cleanup failed: {e}")
            
            # Cleanup components
            await self.component_manager.cleanup_all()
            # Disconnect user clients
            client_count = 0
            for user_clients in self.user_clients.values():
                for client in user_clients.values():
                    if client and client.is_connected():
                        await client.disconnect()
                        client_count += 1
            # Disconnect bot
            if self.bot and self.bot.is_connected():
                await self.bot.disconnect()
            logger.info(f"Cleanup completed. Disconnected {client_count} user clients")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    async def run(self) -> None:
        """Main bot runner"""
        try:
            if not self.is_running:
                raise TeleGuardError("Bot is not running")
            print("\nTeleGuard is now running!")
            print("Send /start to the bot to begin")
            print("OTP Destroyer protection is active")
            print("\n" + "="*50)
            logger.info("TeleGuard is running...")
            await self.bot.run_until_disconnected()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot runtime error: {e}")
            raise
        finally:
            await self.cleanup()
    def get_status(self) -> Dict[str, Any]:
        """Get bot status information"""
        total_clients = sum(len(clients) for clients in self.user_clients.values())
        spam_stats = self.spam_detector.get_detection_stats() if hasattr(self, 'spam_detector') else {}
        return {
            "running": self.is_running,
            "startup_complete": self.startup_complete,
            "total_users": len(self.user_clients),
            "total_clients": total_clients,
            "components_initialized": len(self.component_manager.initialized_components),
            "bot_connected": self.bot.is_connected() if self.bot else False,
            "spam_detector_stats": spam_stats,
            "spam_detector_loaded": hasattr(self, 'spam_detector') and self.spam_detector is not None
        }
    
    async def send_smart_appeal(self, user_id: int, account_name: str, context: str = "") -> Dict:
        """Start smart spam appeal process by initiating SpamBot interaction"""
        try:
            client = self.get_user_client(user_id, account_name)
            if not client:
                return {'success': False, 'error': 'Account not found'}
            
            # Start the automated appeal process through spam_appeal_handler
            if hasattr(self, 'spam_appeal_handler') and self.spam_appeal_handler:
                # Initialize appeal state
                self.spam_appeal_handler.active_appeals[user_id] = {
                    'account_name': account_name,
                    'context': context,
                    'state': 'starting',
                    'mode': 'auto'
                }
                
                # Start the appeal process
                await self.spam_appeal_handler._start_appeal_process(user_id)
                
                return {
                    'success': True,
                    'message': 'Smart appeal process started',
                    'spam_type': 'auto_detected',
                    'strategy': {'priority': 'high'}
                }
            else:
                return {'success': False, 'error': 'Spam appeal handler not available'}
            
        except Exception as e:
            logger.error(f"Smart appeal failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _get_phone_for_account(self, user_id: int, account_name: str) -> str:
        """Get phone number for an account"""
        try:
            account = await mongodb.db.accounts.find_one({
                "user_id": user_id,
                "name": account_name
            })
            return account.get('phone', 'Unknown') if account else 'Unknown'
        except Exception:
            return 'Unknown'
    
    async def _handle_session_invalidation(self, user_id: int, account_name: str, phone: str, error_message: str):
        """Handle session invalidation by removing account and notifying user"""
        try:
            if self.account_invalidation_handler:
                await self.account_invalidation_handler.handle_account_invalidation(
                    user_id, account_name, phone, error_message
                )
        except Exception as e:
            logger.error(f"Failed to handle session invalidation: {e}")

