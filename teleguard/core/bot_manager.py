"""
Professional Bot Manager for TeleGuard
Centralized bot lifecycle management with dependency injection,
error handling, and modular component initialization.
Authors: @Meher_Mankar, @Gutkesh
Repository: https://github.com/mehermankar/teleguard
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional, Set

from telethon import TelegramClient
from telethon.sessions import StringSession

from ..utils.account_invalidation import init_account_invalidation_handler
from ..utils.logger import BotLogger
from ..utils.response_formatter import LogFormatter
from ..utils.session_protection import session_protection
from .config import config
from .exceptions import ConfigurationError, TeleGuardError
from .mongo_database import init_db, mongodb

logger = logging.getLogger(__name__)


class ComponentManager:
    """Manages bot components and their lifecycle"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.components: Dict[str, Any] = {}
        self.initialized_components: Set[str] = set()

    async def initialize_component(
        self, name: str, component_class, *args, **kwargs
    ) -> Any:
        """Initialize a component with error handling"""
        try:
            if name in self.initialized_components:
                return self.components[name]
            logger.debug(f"Initializing component: {name}")
            component = component_class(*args, **kwargs)
            if hasattr(component, "register_handlers"):
                await self._safe_call(
                    component.register_handlers, f"{name}.register_handlers"
                )
            if hasattr(component, "setup"):
                await self._safe_call(component.setup, f"{name}.setup")
            self.components[name] = component
            self.initialized_components.add(name)
            logger.debug(f"✅ Component initialized: {name}")
            return component
        except Exception as e:
            logger.error(f"❌ Failed to initialize component {name}: {e}")
            raise TeleGuardError(
                f"Component initialization failed: {name}", details={"error": str(e)}
            )

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
                if hasattr(component, "cleanup"):
                    await self._safe_call(component.cleanup, f"{name}.cleanup")
                elif hasattr(component, "stop"):
                    await self._safe_call(component.stop, f"{name}.stop")
                elif hasattr(component, "stop_automation_engine"):
                    await self._safe_call(
                        component.stop_automation_engine,
                        f"{name}.stop_automation_engine",
                    )
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
            "auto_reply": set(),
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
            # Initialize BotLogger with bot instance
            await BotLogger.init(self.bot)
            # Register bot commands with BotFather automatically
            try:
                from ..utils.command_registry import command_registry

                success = await command_registry.register_with_botfather(self.bot)
                if success:
                    print("Bot commands registered automatically")
                    logger.info(f"Registered {len(command_registry.COMMANDS)} commands")
            except Exception as e:
                logger.warning(f"Failed to register commands: {e}")
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
            try:
                await BotLogger.log_error(
                    "Bot Startup Failed", str(e), context="bot_manager.start_bot"
                )
            except BaseException:
                pass
            await self.cleanup()
            raise TeleGuardError("Bot startup failed", details={"error": str(e)})

    def _validate_configuration(self) -> None:
        if (
            not config.telegram.api_id
            or not config.telegram.api_hash
            or not config.telegram.bot_token
        ):
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
            raise TeleGuardError(
                "Database initialization failed", details={"error": str(e)}
            )

    async def _initialize_bot_client(self) -> None:
        try:
            from .device_snooper import DeviceSnooper

            device_params = DeviceSnooper.get_spoofed_device_params()

            session_name = f"teleguard_bot_{int(time.time())}"
            self.bot = TelegramClient(
                session_name,
                config.telegram.api_id,
                config.telegram.api_hash,
                **device_params,
            )
            await self._start_bot_with_retry()
            print("Bot authenticated")
            logger.info("Bot client initialized")
        except Exception as e:
            raise TeleGuardError(
                "Bot client initialization failed", details={"error": str(e)}
            )

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

                    wait_match = re.search(r"wait of (\d+) seconds", str(e))
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
            # Skip session loading ONLY on cloud platforms for faster startup
            # Check for actual cloud environment variables
            is_cloud = (
                os.getenv("DYNO")
                or os.getenv("KOYEB_DEPLOYMENT_ID")
                or os.getenv("RAILWAY_ENVIRONMENT")
            )
            if is_cloud and os.getenv("SKIP_SESSION_LOAD", "false").lower() == "true":
                print("Skipping session pre-load for faster startup (cloud mode)")
                logger.info("Session loading skipped - accounts will load on demand")
                return

            print("Loading user accounts...")
            logger.info("Loading existing user sessions...")

            # Auto-cleanup orphaned accounts first with timeout
            try:
                await asyncio.wait_for(self._auto_cleanup_accounts(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Auto-cleanup timed out, continuing...")
            except Exception as e:
                logger.warning(f"Auto-cleanup failed: {e}")

            # Get accounts with shorter timeout
            try:
                accounts = await asyncio.wait_for(
                    mongodb.db.accounts.find({"is_active": True}).to_list(length=None),
                    timeout=2.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Database query timed out, starting without accounts")
                print("No user accounts found (database timeout)")
                return
            except Exception as e:
                logger.error(f"Database error: {e}")
                print("No user accounts found (database error)")
                return

            loaded_count = 0
            # Limit to 3 accounts and shorter timeout for faster startup
            for account in accounts[:3]:
                if account.get("session_string"):
                    try:
                        await asyncio.wait_for(
                            self._start_user_client(
                                account["user_id"],
                                account.get("name", "Unknown"),
                                account["session_string"],
                            ),
                            timeout=2.0,  # Reduced timeout
                        )
                        loaded_count += 1
                    except asyncio.TimeoutError:
                        logger.warning(
                            f"Timeout loading client for {account.get('name')}"
                        )
                    except Exception as e:
                        error_msg = str(e).lower()
                        account_name = account.get("name", "Unknown")
                        phone = account.get("phone", "Unknown")

                        # Check if this is a session invalidation error
                        if any(
                            phrase in error_msg
                            for phrase in [
                                "auth_key_unregistered",
                                "auth_key_duplicated",
                                "401",
                                "406",
                                "authorization key",
                                "session_revoked",
                                "session expired",
                            ]
                        ):
                            print(
                                f"Account '{account_name}' has session conflict (likely other bot/client)"
                            )
                            # Handle session conflict
                            await self._handle_session_conflict_db(
                                account["_id"],
                                account["user_id"],
                                account_name,
                                phone,
                                str(e),
                            )
                        elif any(
                            phrase in error_msg
                            for phrase in [
                                "user_deactivated",
                                "failed to get valid user info",
                                "duplicated",
                                "session_password_needed",
                                "unauthorized",
                                "invalid session",
                            ]
                        ):
                            print(
                                f"Account '{account_name}' invalidated - will be removed"
                            )
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
            print(
                "Session loading timed out - bot will start without pre-loaded accounts"
            )
        except Exception as e:
            logger.error(f"Failed to load existing sessions: {e}")
            print(
                "Failed to load accounts - bot will start without pre-loaded accounts"
            )
            try:
                await BotLogger.log_error(
                    "Session Load Failed",
                    str(e),
                    context="bot_manager._load_existing_sessions",
                )
            except BaseException:
                pass

    async def _start_user_client(
        self, user_id: int, account_name: str, session_string: str
    ) -> None:
        try:
            # Validate and clean session string format before creating client
            if not session_string or not isinstance(session_string, str):
                raise ValueError("Invalid session string format")

            # Decode HTML entities if present (multiple times to handle double encoding)
            import html

            session_string = html.unescape(html.unescape(session_string))

            # Additional validation
            if len(session_string) < 50:
                raise ValueError("Session string too short")

            # Pre-validate session before creating client
            try:
                test_session = StringSession(session_string)
                if not test_session.auth_key:
                    logger.warning(
                        f"Session for {account_name} has no auth_key, marking for reauth"
                    )
                    await self._mark_account_for_reauth(
                        user_id, account_name, "No auth_key in session"
                    )
                    return
            except Exception as e:
                logger.warning(f"Session pre-validation failed for {account_name}: {e}")
                # Continue with conversion attempt if it's a Pyrogram session

            # Get proxy if assigned to account, or auto-assign default proxy
            proxy_dict = None
            try:
                from .proxy_manager import proxy_manager

                account = await mongodb.db.accounts.find_one(
                    {"user_id": user_id, "name": account_name}
                )

                # Auto-assign default proxy if account doesn't have one
                if account and not account.get("proxy_id"):
                    default_proxy = await proxy_manager.get_default_proxy(user_id)
                    if default_proxy:
                        proxy_id = str(default_proxy["_id"])
                        await proxy_manager.assign_proxy_to_account(
                            user_id, str(account["_id"]), proxy_id
                        )
                        logger.info(
                            f"Auto-assigned default proxy {
                                default_proxy['server']}:{
                                default_proxy['port']} to {account_name}"
                        )
                        account["proxy_id"] = proxy_id

                # Load proxy if assigned
                if account and account.get("proxy_id"):
                    proxy = await proxy_manager.get_account_proxy(str(account["_id"]))
                    if proxy:
                        proxy_dict = await proxy_manager.build_telethon_proxy(
                            proxy, str(account["_id"])
                        )
                        if proxy_dict:
                            logger.info(
                                f"Using proxy {
                                    proxy['server']}:{
                                    proxy['port']} for {account_name}"
                            )
                        else:
                            logger.warning(f"Failed to build proxy for {account_name}")
            except Exception as e:
                logger.warning(f"Failed to load/assign proxy for {account_name}: {e}")

            # Create client with session string and device spoofing
            from .device_snooper import DeviceSnooper

            device_params = DeviceSnooper.get_spoofed_device_params()

            # Create StringSession with better error handling
            try:
                string_session = StringSession(session_string)
            except ValueError as e:
                if "Not a valid string" in str(e):
                    # Try to convert Pyrogram session
                    from ..utils.session_utils import (
                        convert_pyrogram_to_telethon,
                        detect_session_type,
                    )

                    session_type = detect_session_type(session_string)
                    if session_type == "pyrogram":
                        logger.info(f"Converting Pyrogram session for {account_name}")
                        try:
                            converted_session, result = (
                                await convert_pyrogram_to_telethon(
                                    session_string,
                                    config.telegram.api_id,
                                    config.telegram.api_hash,
                                )
                            )
                            if converted_session:
                                # Update database with converted session
                                await mongodb.db.accounts.update_one(
                                    {"user_id": user_id, "name": account_name},
                                    {"$set": {"session_string": converted_session}},
                                )
                                # Use converted session
                                session_string = converted_session
                                string_session = StringSession(session_string)
                            else:
                                # Mark account as needing reauth instead of failing
                                logger.warning(
                                    f"Pyrogram session for {account_name} expired, marking for reauth"
                                )
                                await mongodb.db.accounts.update_one(
                                    {"user_id": user_id, "name": account_name},
                                    {
                                        "$set": {
                                            "needs_reauth": True,
                                            "is_active": False,
                                        }
                                    },
                                )
                                raise ValueError(
                                    f"Session expired - marked for reauth: {result}"
                                )
                        except Exception as conv_error:
                            logger.error(f"Pyrogram conversion error: {conv_error}")
                            raise ValueError(
                                f"Failed to convert Pyrogram session: {conv_error}"
                            )
                    else:
                        logger.error(
                            f"Session string details - Length: {
                                len(session_string)}, Type: {
                                type(session_string)}, Valid: {
                                session_string.isprintable() if isinstance(
                                    session_string, str) else False}"
                        )
                        raise ValueError(f"Invalid session string format: {e}")
                else:
                    logger.error(
                        f"Session string details - Length: {
                            len(session_string)}, Type: {
                            type(session_string)}, Valid: {
                            session_string.isprintable() if isinstance(
                                session_string, str) else False}"
                    )
                    raise ValueError(f"Invalid session string format: {e}")
            except Exception as e:
                logger.error(
                    f"Session string details - Length: {
                        len(session_string)}, Type: {
                        type(session_string)}, Valid: {
                        session_string.isprintable() if isinstance(
                            session_string, str) else False}"
                )
                raise ValueError(f"Invalid session string format: {e}")

            # Use Pyrogram for MTProto proxy connection, then convert to Telethon
            if proxy_dict and proxy_dict.get("type") == "mtproto":
                logger.warning(
                    f"MTProto proxy detected for {account_name} - skipping proxy (Telethon incompatible)"
                )
                # MTProto proxies are not compatible with Telethon's Connection._parse_proxy()
                # Skip proxy and connect directly
                proxy_dict = None

            # Create Telethon client
            client_params = {
                "connection_retries": 2,
                "retry_delay": 2,
                "timeout": 10,
                **device_params,
            }

            if proxy_dict:
                client_params["proxy"] = proxy_dict

            client = TelegramClient(
                string_session,
                config.telegram.api_id,
                config.telegram.api_hash,
                **client_params,
            )

            # Connect with shorter timeout and comprehensive error handling
            try:
                await asyncio.wait_for(client.connect(), timeout=5.0)

                # Test authorization before proceeding
                if not await client.is_user_authorized():
                    await client.disconnect()
                    logger.warning(
                        f"Session for {account_name} not authorized, likely due to session conflict"
                    )
                    await self._handle_session_conflict(
                        user_id,
                        account_name,
                        "Session not authorized - possible conflict with another bot/client",
                    )
                    return

                # Test the connection by getting basic info
                try:
                    from ..utils.network_helpers import get_user_info_safe

                    await get_user_info_safe(client)
                    logger.debug(f"Successfully validated user info for {account_name}")
                except Exception as e:
                    logger.error(
                        f"Failed to get valid user info for {account_name}: {e}"
                    )
                    await client.disconnect()
                    await self._mark_account_for_reauth(
                        user_id, account_name, f"Failed to get user info: {e}"
                    )
                    return

            except Exception as e:
                # Handle specific session errors with better recovery
                error_msg = str(e).lower()
                if any(
                    phrase in error_msg
                    for phrase in [
                        "auth_key_unregistered",
                        "auth_key_duplicated",
                        "401",
                        "406",
                        "authorization key",
                        "session_revoked",
                        "session expired",
                    ]
                ):
                    # Handle session conflicts (likely caused by other bots/clients)
                    logger.warning(f"Session conflict detected for {account_name}: {e}")
                    await self._handle_session_conflict(user_id, account_name, str(e))
                    return
                elif any(
                    phrase in error_msg
                    for phrase in [
                        "ip addresses",
                        "session file",
                        "failed to get valid user info",
                        "invalid session",
                        "user_deactivated",
                        "unauthorized",
                        "session_password_needed",
                    ]
                ):
                    # Handle other session issues
                    phone = await self._get_phone_for_account(user_id, account_name)
                    asyncio.create_task(
                        self._handle_session_invalidation(
                            user_id, account_name, phone, str(e)
                        )
                    )
                    logger.warning(
                        f"Account {account_name} invalidated and will be removed: {e}"
                    )
                try:
                    await client.disconnect()
                except Exception:
                    pass  # Ignore disconnect errors
                raise

            # Store client ONCE to avoid duplicate session references
            if user_id not in self.user_clients:
                self.user_clients[user_id] = {}
            self.user_clients[user_id][account_name] = client

            # Register session for protection
            session_id = f"{user_id}_{account_name}"
            session_protection.register_session(session_id, account_name)

            # Add to session monitor if available
            if hasattr(self, "session_monitor") and self.session_monitor:
                self.session_monitor.add_client_to_monitor(
                    user_id, account_name, client
                )

            # Mark account as active if connection successful
            account = await asyncio.wait_for(
                mongodb.db.accounts.find_one(
                    {"user_id": user_id, "name": account_name}
                ),
                timeout=2.0,
            )
            if account:
                await mongodb.db.accounts.update_one(
                    {"user_id": user_id, "name": account_name},
                    {"$unset": {"needs_reauth": ""}, "$set": {"is_active": True}},
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
            await asyncio.wait_for(self._initialize_core_components(), timeout=15.0)
            await asyncio.wait_for(self._initialize_handlers(), timeout=15.0)
            await asyncio.wait_for(self._initialize_services(), timeout=8.0)
            await asyncio.wait_for(self._initialize_workers(), timeout=3.0)

            # Initialize auto backup system
            try:
                from ..utils.backups import init_auto_backup, start_auto_backup

                init_auto_backup(self.bot)
                await start_auto_backup()
                print("  Auto backup system ready")
                logger.info("Auto backup system initialized")
            except Exception as e:
                logger.warning(f"Auto backup initialization failed: {e}")

            # Set up DM handlers for loaded sessions after all components are
            # initialized
            if self.dm_reply_handler:
                try:
                    await self.dm_reply_handler.refresh_all_handlers()
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
        from ..core.messaging import MessagingManager
        from ..core.otp_manager import OTPManager
        from ..handlers.auth_handler import AuthManager
        from ..handlers.menu_system import MenuSystem

        logger.info("Initializing auth manager...")
        self.auth_manager = await self.component_manager.initialize_component(
            "auth_manager", AuthManager, self
        )
        
        # Initialize DM reply commands BEFORE menu system so its handlers are registered first
        from ..handlers.dm_reply_commands import DMReplyCommands
        logger.info("Initializing DM reply commands...")
        self.dm_reply_commands = await self.component_manager.initialize_component(
            "dm_reply_commands", DMReplyCommands, self.bot, self
        )

        logger.info("Initializing menu system...")
        self.menu_system = await self.component_manager.initialize_component(
            "menu_system", MenuSystem, self.bot, self
        )

        logger.info("Initializing OTP manager...")
        self.otp_manager = await self.component_manager.initialize_component(
            "otp_manager", OTPManager, self
        )

        # Ensure OTP handlers are registered for existing clients
        if self.otp_manager and self.user_clients:
            try:
                self.otp_manager.register_handlers()
                logger.info("OTP handlers registered during initialization")
            except Exception as e:
                logger.warning(f"Failed to register OTP handlers during init: {e}")

        logger.info("Initializing messaging manager...")
        self.messaging_manager = await self.component_manager.initialize_component(
            "messaging_manager", MessagingManager, self
        )
        print("  OTP Destroyer ready")
        print("  Messaging system ready")
        print("  Menu system ready")

        # Verify OTP manager is working
        if self.otp_manager:
            handler_count = len(self.otp_manager.registered_handlers)
            if handler_count > 0:
                print(f"  OTP protection active for {handler_count} accounts")
            else:
                print("  OTP protection ready (no accounts loaded yet)")

        # Set unified_messaging as alias to messaging_manager for compatibility
        self.unified_messaging = self.messaging_manager
        # SessionMaster analytics and automation are integrated into handlers

    async def _initialize_handlers(self) -> None:
        from ..handlers.command_handlers import CommandHandlers
        from ..handlers.contact_export_handler import ContactExportHandler
        from ..handlers.contact_handler import ContactHandler
        from ..handlers.dm_reply_commands import DMReplyCommands
        from ..handlers.dm_reply_handler import DMReplyHandler
        from ..handlers.help_handler import HelpHandler
        from ..handlers.message_handlers import MessageHandlers
        from ..handlers.rate_limit_commands import RateLimitCommands
        from ..handlers.session_export_handler import SessionExportHandler
        from ..handlers.session_login_handler import SessionLoginHandler
        from ..handlers.start_handler import StartHandler

        self.command_handlers = await self.component_manager.initialize_component(
            "command_handlers", CommandHandlers, self
        )
        self.rate_limit_commands = await self.component_manager.initialize_component(
            "rate_limit_commands", RateLimitCommands, self
        )
        self.help_handler = await self.component_manager.initialize_component(
            "help_handler", HelpHandler, self
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
        # dm_reply_commands already initialized in _initialize_core_components
        self.dm_reply_handler = await self.component_manager.initialize_component(
            "dm_reply_handler", DMReplyHandler, self
        )
        self.contact_handler = await self.component_manager.initialize_component(
            "contact_handler", ContactHandler, self
        )
        self.contact_export_handler = await self.component_manager.initialize_component(
            "contact_export_handler", ContactExportHandler, self
        )

        # Initialize 2FA commands handler
        from ..handlers.twofa_commands import TwoFACommands

        self.twofa_commands = await self.component_manager.initialize_component(
            "twofa_commands", TwoFACommands, self.bot, self
        )

        # Initialize transfer ownership handler
        from ..handlers.transfer_ownership_handler import TransferOwnershipHandler

        self.transfer_ownership_handler = (
            await self.component_manager.initialize_component(
                "transfer_ownership_handler", TransferOwnershipHandler, self
            )
        )

        # Initialize auto-reply handler
        from ..handlers.auto_reply_handler import AutoReplyHandler

        self.auto_reply_handler = await self.component_manager.initialize_component(
            "auto_reply_handler", AutoReplyHandler, self
        )

        # Set up auto-reply handlers for existing clients
        if self.auto_reply_handler:
            try:
                self.auto_reply_handler.setup_auto_reply_handlers()
                handler_count = len(self.auto_reply_handler.handled_clients)
                print(f"  Auto-reply system ready ({handler_count} handlers)")
                logger.info(
                    f"Auto-reply handlers set up for existing clients: {handler_count}"
                )
            except Exception as e:
                logger.warning(f"Failed to set up auto-reply handlers: {e}")
                print("  Auto-reply system ready (no handlers yet)")

        # Initialize bulk sender
        from ..handlers.bulk_sender import BulkSender

        self.bulk_sender = await self.component_manager.initialize_component(
            "bulk_sender", BulkSender, self
        )

        # Initialize channel manager
        from ..handlers.channel_manager import ChannelManager

        self.channel_manager = await self.component_manager.initialize_component(
            "channel_manager", ChannelManager, self
        )

        # Initialize online maker
        from ..handlers.online_maker import OnlineMaker

        self.online_maker = await self.component_manager.initialize_component(
            "online_maker", OnlineMaker, self
        )

        # Initialize activity simulator
        from ..workers.activity_simulator import ActivitySimulator

        self.activity_simulator = await self.component_manager.initialize_component(
            "activity_simulator", ActivitySimulator, self
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

        from ..handlers.topic_actions_handler import TopicActionsHandler

        self.topic_actions_handler = await self.component_manager.initialize_component(
            "topic_actions_handler", TopicActionsHandler, self
        )

        from ..handlers.contact_share_handler import ContactShareHandler

        self.contact_share_handler = await self.component_manager.initialize_component(
            "contact_share_handler", ContactShareHandler, self
        )

        # Advanced SpamMaster with all features
        from ..handlers.advanced_spam_handler import AdvancedSpamHandler

        self.advanced_spam_handler = await self.component_manager.initialize_component(
            "advanced_spam_handler", AdvancedSpamHandler, self
        )

        # Initialize spam detector
        from pathlib import Path

        from ..utils.spam_detector import SpamDetector

        # Load appeal messages
        messages_file = Path(__file__).parent.parent / "data" / "appeal_messages.txt"
        appeal_messages = []
        try:
            if messages_file.exists():
                content = messages_file.read_text(encoding="utf-8")
                appeal_messages = [
                    msg.strip() for msg in content.split("\n\n") if msg.strip()
                ]
        except Exception as e:
            logger.warning(f"Failed to load appeal messages: {e}")

        self.spam_detector = SpamDetector(appeal_messages)
        logger.info(
            f"Spam detector initialized with {len(appeal_messages)} appeal messages"
        )

    async def _initialize_services(self) -> None:
        from ..core.automation import AutomationEngine
        from ..workers.activity_simulator import ActivitySimulator

        self.automation_engine = await self.component_manager.initialize_component(
            "automation_engine", AutomationEngine, self.user_clients, None
        )
        await self.component_manager.initialize_component(
            "activity_simulator", ActivitySimulator, self
        )
        print(
            f"  Smart spam detection ready ({
                len(
                    self.spam_detector.appeal_messages)} messages)"
        )

    async def _initialize_workers(self) -> None:
        """Initialize background workers"""
        if self.automation_engine:
            try:
                await self.automation_engine.start()
            except Exception as e:
                logger.warning(f"Automation engine start failed: {e}")

        # Initialize session monitor
        from ..workers.session_monitor import SessionMonitor

        self.session_monitor = SessionMonitor(self)
        await self.session_monitor.start_monitoring()

        # Initialize account invalidation handler
        from ..utils.account_invalidation import init_account_invalidation_handler

        self.account_invalidation_handler = init_account_invalidation_handler(self)

        # Start periodic cleanup task
        asyncio.create_task(self._periodic_cleanup_task())

    async def start_user_client(
        self, user_id: int, account_name: str, session_string: str
    ) -> None:
        """Public method to start a user client with timeout"""
        try:
            await asyncio.wait_for(
                self._start_user_client(user_id, account_name, session_string),
                timeout=15.0,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Timeout starting client for {account_name}")
            raise TimeoutError(f"Connection timeout after 15s")
        except Exception as e:
            logger.error(f"Failed to start client {account_name}: {e}")
            raise

    async def add_user_account(
        self, user_id: int, account_name: str, session_string: str
    ) -> bool:
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

            # Get the client that was just added
            client = self.user_clients.get(user_id, {}).get(account_name)

            # Setup OTP handler for the new client
            if self.otp_manager and client:
                await self.otp_manager.setup_handler_for_new_client(
                    user_id, account_name, client
                )
                logger.info(f"OTP handler setup completed for {account_name}")
            else:
                logger.warning(
                    f"Could not setup OTP handler - manager: {
                        bool(
                            self.otp_manager)}, client: {
                        bool(client)}"
                )
            # Setup DM reply handler - auto-refresh to ensure all handlers are
            # registered
            if self.dm_reply_handler and client:
                try:
                    await self.dm_reply_handler.setup_new_client_handler(
                        user_id, account_name, client
                    )
                    # Auto-refresh all handlers to ensure consistency
                    await self.dm_reply_handler.refresh_all_handlers()
                    logger.info(
                        f"DM handler setup and refresh completed for {account_name}"
                    )
                except Exception as dm_error:
                    logger.error(
                        f"Failed to setup DM handler for {account_name}: {dm_error}"
                    )

            # Setup auto-reply handler for the new client
            if self.auto_reply_handler and client:
                try:
                    await self.auto_reply_handler.setup_new_client_handler(
                        user_id, account_name, client
                    )
                    logger.info(
                        f"Auto-reply handler setup completed for {account_name}"
                    )
                except Exception as auto_reply_error:
                    logger.error(
                        f"Failed to setup auto-reply handler for {account_name}: {auto_reply_error}"
                    )

            # Use Activity Simulator for human-like behavior instead of constant pings
            if client and self.activity_simulator:
                try:
                    # Add account to activity simulator for natural behavior
                    await self.activity_simulator.add_account(
                        user_id, account_name, client
                    )
                    logger.info(f"Added {account_name} to activity simulator")
                except Exception as sim_error:
                    logger.warning(f"Failed to add to activity simulator: {sim_error}")
            logger.info(
                LogFormatter.format_user_action(
                    user_id, "account_added", {"account_name": account_name}
                )
            )
            # Log to logs bot
            try:
                phone = await self._get_phone_for_account(user_id, account_name)
                try:
                    user = await self.bot.get_entity(user_id)
                    username = user.username if hasattr(user, "username") else None
                except BaseException:
                    username = None
                await BotLogger.log_account_added(user_id, phone, username)
            except Exception as log_error:
                logger.error(f"Failed to log account addition: {log_error}")

            # Share with co-owners automatically
            try:
                await self._share_account_with_coowners(user_id, account_name)
            except Exception as coowner_error:
                logger.error(f"Failed to share account with co-owners: {coowner_error}")

            return True
        except Exception as e:
            logger.error(f"Failed to add user account: {e}")
            return False

    async def remove_account_by_id(self, user_id: int, account_id: str):
        """Remove account by ID with proper session termination"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return False, "Account not found"

            account_name = account.get("name", "Unknown")

            # Remove stored 2FA password for security
            try:
                from .database_manager import db_manager

                await db_manager.remove_2fa_password(user_id, account_id)
                logger.info(f"Removed stored 2FA password for account {account_name}")
            except Exception as e:
                logger.warning(f"Failed to remove 2FA password for {account_name}: {e}")

            # Terminate Telegram session and disconnect client
            if user_id in self.user_clients:
                for key in list(self.user_clients[user_id].keys()):
                    if key in [
                        account.get("name"),
                        account.get("phone"),
                        account.get("display_name"),
                    ]:
                        client = self.user_clients[user_id].pop(key, None)
                        if client and client.is_connected():
                            try:
                                # Terminate all active sessions for this account
                                from telethon.tl.functions.auth import LogOutRequest

                                await client(LogOutRequest())
                                logger.info(
                                    f"Terminated Telegram session for {account_name}"
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to terminate session for {account_name}: {e}"
                                )
                            finally:
                                # Always disconnect the client
                                await client.disconnect()

            # Remove from database
            await mongodb.db.accounts.delete_one({"_id": ObjectId(account_id)})

            logger.info(
                f"Removed account {account_name} for user {user_id} with session termination"
            )
            # Log to logs bot
            try:
                phone = account.get("phone", "Unknown")
                try:
                    user = await self.bot.get_entity(user_id)
                    username = user.username if hasattr(user, "username") else None
                except BaseException:
                    username = None
                await BotLogger.log_account_removed(user_id, phone, username)
            except Exception as log_error:
                logger.error(f"Failed to log account removal: {log_error}")
            return (
                True,
                f"Account {account_name} removed successfully with session logout",
            )
        except Exception as e:
            logger.error(f"Failed to remove account: {e}")
            return False, f"Failed to remove account: {str(e)}"

    async def remove_user_account(self, user_id: int, account_name: str) -> bool:
        """
        Remove a user account with proper session termination.
        Args:
            user_id: User's Telegram ID
            account_name: Account name
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get account ID for 2FA removal
            account = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "name": account_name}
            )

            if account:
                # Remove stored 2FA password for security
                try:
                    from .database_manager import db_manager

                    await db_manager.remove_2fa_password(user_id, str(account["_id"]))
                    logger.info(
                        f"Removed stored 2FA password for account {account_name}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to remove 2FA password for {account_name}: {e}"
                    )

            # Remove from session monitor
            if hasattr(self, "session_monitor") and self.session_monitor:
                self.session_monitor.remove_client_from_monitor(user_id, account_name)

            # Terminate Telegram session and disconnect client
            if (
                user_id in self.user_clients
                and account_name in self.user_clients[user_id]
            ):
                client = self.user_clients[user_id][account_name]
                if client.is_connected():
                    try:
                        # Terminate all active sessions for this account
                        from telethon.tl.functions.auth import LogOutRequest

                        await client(LogOutRequest())
                        logger.info(f"Terminated Telegram session for {account_name}")
                    except Exception as e:
                        logger.warning(
                            f"Failed to terminate session for {account_name}: {e}"
                        )
                    finally:
                        # Always disconnect the client
                        await client.disconnect()
                del self.user_clients[user_id][account_name]

            await mongodb.db.accounts.delete_one(
                {"user_id": user_id, "name": account_name}
            )
            logger.info(
                LogFormatter.format_user_action(
                    user_id,
                    "account_removed_with_logout",
                    {"account_name": account_name},
                )
            )
            return True
        except Exception as e:
            logger.error(f"Failed to remove user account: {e}")
            return False

    async def remove_account(self, account_id: str) -> bool:
        """
        Remove account by ID (alias for compatibility) with session termination.
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
            success, message = await self.remove_account_by_id(
                account["user_id"], str(account["_id"])
            )
            return success
        except Exception as e:
            logger.error(f"Failed to remove account {account_id}: {e}")
            return False

    async def get_accounts_needing_reauth(self, user_id: int) -> list:
        """Get accounts that need re-authentication"""
        try:
            accounts = await mongodb.db.accounts.find(
                {"user_id": user_id, "needs_reauth": True}
            ).to_list(length=None)
            return accounts
        except Exception as e:
            logger.error(f"Failed to get accounts needing reauth: {e}")
            return []

    async def clear_invalid_sessions(self, user_id: int) -> int:
        """Clear all invalid sessions for a user"""
        try:
            result = await mongodb.db.accounts.delete_many(
                {"user_id": user_id, "needs_reauth": True}
            )

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

            logger.info(
                f"Cleared {result.deleted_count} invalid sessions for user {user_id}"
            )
            return result.deleted_count
        except Exception as e:
            logger.error(f"Failed to clear invalid sessions: {e}")
            return 0

    def get_user_client(
        self, user_id: int, account_name: str
    ) -> Optional[TelegramClient]:
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

            # Stop MTProto bridges
            try:
                from .mtproto_bridge import mtproto_bridge

                await mtproto_bridge.stop_all_bridges()
                logger.info("MTProto bridges stopped")
            except Exception as e:
                logger.warning(f"MTProto bridge cleanup failed: {e}")

            # Stop session monitor
            if hasattr(self, "session_monitor") and self.session_monitor:
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
            print("\n" + "=" * 50)
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
        spam_stats = (
            self.spam_detector.get_detection_stats()
            if hasattr(self, "spam_detector")
            else {}
        )
        return {
            "running": self.is_running,
            "startup_complete": self.startup_complete,
            "total_users": len(self.user_clients),
            "total_clients": total_clients,
            "components_initialized": len(
                self.component_manager.initialized_components
            ),
            "bot_connected": self.bot.is_connected() if self.bot else False,
            "spam_detector_stats": spam_stats,
            "spam_detector_loaded": hasattr(self, "spam_detector")
            and self.spam_detector is not None,
        }

    async def send_smart_appeal(
        self, user_id: int, account_name: str, context: str = ""
    ) -> Dict:
        """Start smart spam appeal process by initiating SpamBot interaction"""
        try:
            client = self.get_user_client(user_id, account_name)
            if not client:
                return {"success": False, "error": "Account not found"}

            # Start the automated appeal process through spam_appeal_handler
            if hasattr(self, "spam_appeal_handler") and self.spam_appeal_handler:
                # Initialize appeal state
                self.spam_appeal_handler.active_appeals[user_id] = {
                    "account_name": account_name,
                    "context": context,
                    "state": "starting",
                    "mode": "auto",
                }

                # Start the appeal process
                await self.spam_appeal_handler._start_appeal_process(user_id)

                return {
                    "success": True,
                    "message": "Smart appeal process started",
                    "spam_type": "auto_detected",
                    "strategy": {"priority": "high"},
                }
            else:
                return {"success": False, "error": "Spam appeal handler not available"}

        except Exception as e:
            logger.error(f"Smart appeal failed: {e}")
            return {"success": False, "error": str(e)}

    async def _get_phone_for_account(self, user_id: int, account_name: str) -> str:
        """Get phone number for an account"""
        try:
            account = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "name": account_name}
            )
            return account.get("phone", "Unknown") if account else "Unknown"
        except Exception:
            return "Unknown"

    async def _auto_cleanup_accounts(self):
        """Automatically cleanup orphaned accounts during startup"""
        try:
            # Count accounts to cleanup with timeout
            inactive = await asyncio.wait_for(
                mongodb.db.accounts.count_documents({"is_active": False}), timeout=1.0
            )
            reauth = await asyncio.wait_for(
                mongodb.db.accounts.count_documents({"needs_reauth": True}), timeout=1.0
            )
            no_session = await asyncio.wait_for(
                mongodb.db.accounts.count_documents(
                    {"session_string": {"$exists": False}}
                ),
                timeout=1.0,
            )

            total_cleanup = inactive + reauth + no_session

            if total_cleanup > 0:
                print(f"Cleaning up {total_cleanup} orphaned accounts...")

                # Delete orphaned accounts with timeout
                result1 = await asyncio.wait_for(
                    mongodb.db.accounts.delete_many({"is_active": False}), timeout=1.0
                )
                result2 = await asyncio.wait_for(
                    mongodb.db.accounts.delete_many({"needs_reauth": True}), timeout=1.0
                )
                result3 = await asyncio.wait_for(
                    mongodb.db.accounts.delete_many(
                        {"session_string": {"$exists": False}}
                    ),
                    timeout=1.0,
                )

                total_deleted = (
                    result1.deleted_count
                    + result2.deleted_count
                    + result3.deleted_count
                )
                print(f"Removed {total_deleted} orphaned accounts")
                logger.info(f"Auto-cleanup removed {total_deleted} orphaned accounts")

        except asyncio.TimeoutError:
            logger.warning("Auto-cleanup timed out")
        except Exception as e:
            logger.warning(f"Auto-cleanup failed: {e}")

    async def _periodic_cleanup_task(self):
        """Run cleanup every 5 minutes"""
        while self.is_running:
            try:
                await asyncio.sleep(300)  # 5 minutes
                if not self.is_running:
                    break

                # Silent cleanup
                result1 = await mongodb.db.accounts.delete_many({"is_active": False})
                result2 = await mongodb.db.accounts.delete_many({"needs_reauth": True})
                result3 = await mongodb.db.accounts.delete_many(
                    {"session_string": {"$exists": False}}
                )

                total_deleted = (
                    result1.deleted_count
                    + result2.deleted_count
                    + result3.deleted_count
                )
                if total_deleted > 0:
                    logger.info(
                        f"Periodic cleanup removed {total_deleted} orphaned accounts"
                    )

            except Exception as e:
                logger.warning(f"Periodic cleanup error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry

    async def _handle_session_conflict(
        self, user_id: int, account_name: str, error_reason: str
    ):
        """Handle session conflicts caused by other bots/clients"""
        try:
            # Update database with conflict status
            await mongodb.db.accounts.update_one(
                {"user_id": user_id, "name": account_name},
                {
                    "$set": {
                        "session_conflict": True,
                        "is_active": False,
                        "last_error": error_reason,
                        "error_time": int(__import__("time").time()),
                        "conflict_count": (
                            {"$inc": 1}
                            if "conflict_count"
                            in await mongodb.db.accounts.find_one(
                                {"user_id": user_id, "name": account_name}
                            )
                            or {}
                            else 1
                        ),
                    }
                },
            )

            # Get phone for notification
            phone = await self._get_phone_for_account(user_id, account_name)

            # Notify user about session conflict
            await self._notify_user_session_conflict(
                user_id, account_name, phone, error_reason
            )

            logger.warning(
                f"Session conflict detected for {account_name}: {error_reason}"
            )

        except Exception as e:
            logger.error(f"Failed to handle session conflict: {e}")

    async def _handle_session_conflict_db(
        self, account_id, user_id: int, account_name: str, phone: str, error_reason: str
    ):
        """Handle session conflict with database ID"""
        try:
            await mongodb.db.accounts.update_one(
                {"_id": account_id},
                {
                    "$set": {
                        "session_conflict": True,
                        "is_active": False,
                        "last_error": error_reason,
                        "error_time": int(__import__("time").time()),
                    },
                    "$inc": {"conflict_count": 1},
                },
            )

            # Notify user about session conflict
            asyncio.create_task(
                self._notify_user_session_conflict(
                    user_id, account_name, phone, error_reason
                )
            )

        except Exception as e:
            logger.error(f"Failed to handle session conflict in DB: {e}")

    async def _mark_account_for_reauth(
        self, user_id: int, account_name: str, error_reason: str
    ):
        """Mark account for re-authentication and notify user"""
        try:
            # Update database
            await mongodb.db.accounts.update_one(
                {"user_id": user_id, "name": account_name},
                {
                    "$set": {
                        "needs_reauth": True,
                        "is_active": False,
                        "last_error": error_reason,
                        "error_time": int(__import__("time").time()),
                    }
                },
            )

            # Get phone for notification
            phone = await self._get_phone_for_account(user_id, account_name)

            # Notify user
            await self._notify_user_reauth_needed(
                user_id, account_name, phone, error_reason
            )

            logger.info(f"Marked account {account_name} for reauth: {error_reason}")

        except Exception as e:
            logger.error(f"Failed to mark account for reauth: {e}")

    async def _notify_user_session_conflict(
        self, user_id: int, account_name: str, phone: str, error_reason: str = ""
    ):
        """Notify user about session conflicts caused by other bots/clients"""
        try:
            error_type = (
                "AUTH_KEY_UNREGISTERED (401)"
                if "401" in error_reason or "unregistered" in error_reason.lower()
                else (
                    "AUTH_KEY_DUPLICATED (406)"
                    if "406" in error_reason or "duplicated" in error_reason.lower()
                    else "Session Conflict"
                )
            )

            message = (
                f"⚠️ **Session Conflict Detected**\n\n"
                f"📱 **Account:** {account_name} ({phone})\n"
                f"🔴 **Error:** {error_type}\n\n"
                f"**🤖 Likely Cause: Another Bot/Client**\n"
                f"• This account is being used by another bot or Telegram client\n"
                f"• Telegram only allows one active session per account\n"
                f"• When multiple bots use the same account, sessions get invalidated\n\n"
                f"**🔧 Solutions:**\n"
                f"1. **Stop other bots** using this account\n"
                f"2. **Use different accounts** for different bots\n"
                f"3. **Re-add account** after stopping conflicts\n"
                f"4. **Check for duplicate logins** on other devices\n\n"
                f"🚨 **Important:** Multiple bots on same account = constant session conflicts\n\n"
                f"💡 **Tip:** Use /start → Account Settings to manage accounts"
            )
            await self.bot.send_message(user_id, message)
            logger.info(
                f"Notified user {user_id} about session conflict for {account_name}"
            )
        except Exception as e:
            logger.error(f"Failed to notify user about session conflict: {e}")

    async def _notify_user_reauth_needed(
        self, user_id: int, account_name: str, phone: str, error_reason: str = ""
    ):
        """Notify user that account needs re-authentication"""
        try:
            error_type = (
                "AUTH_KEY_UNREGISTERED"
                if "401" in error_reason or "unregistered" in error_reason.lower()
                else (
                    "AUTH_KEY_DUPLICATED"
                    if "406" in error_reason or "duplicated" in error_reason.lower()
                    else "Session Error"
                )
            )

            message = (
                f"🔄 **Account Re-authentication Required**\n\n"
                f"📱 **Account:** {account_name} ({phone})\n"
                f"❌ **Error:** {error_type}\n\n"
                f"**What happened:**\n"
                f"• Your session has been invalidated by Telegram\n"
                f"• This can happen due to security checks, session expiry, or duplicate logins\n\n"
                f"**To fix this:**\n"
                f"1. Go to Account Settings\n"
                f"2. Remove the affected account\n"
                f"3. Add it again using phone number login\n"
                f"4. Or import a fresh session string\n\n"
                f"💡 **Tip:** Use /start → Account Settings to manage accounts"
            )
            await self.bot.send_message(user_id, message)
            logger.info(
                f"Notified user {user_id} about reauth needed for {account_name}"
            )
        except Exception as e:
            logger.error(f"Failed to notify user about reauth: {e}")

    async def _handle_session_invalidation(
        self, user_id: int, account_name: str, phone: str, error_message: str
    ):
        """Handle session invalidation by removing account and notifying user"""
        try:
            if self.account_invalidation_handler:
                await self.account_invalidation_handler.handle_account_invalidation(
                    user_id, account_name, phone, error_message
                )
        except Exception as e:
            logger.error(f"Failed to handle session invalidation: {e}")

    async def _keep_account_active(self, user_id: int, account_name: str, client):
        """Keep account active for 10 minutes after adding"""
        try:
            from telethon.tl.functions.account import UpdateStatusRequest

            # Send periodic status updates for 10 minutes
            for i in range(20):  # 20 iterations * 30 seconds = 10 minutes
                if not client.is_connected():
                    break

                try:
                    # Update online status
                    await client(UpdateStatusRequest(offline=False))
                    logger.debug(f"Sent activity ping {i + 1}/20 for {account_name}")
                except Exception as e:
                    logger.debug(f"Activity ping failed for {account_name}: {e}")
                    break

                await asyncio.sleep(30)  # Wait 30 seconds between pings

            logger.info(f"Completed 10-minute activity period for {account_name}")

        except Exception as e:
            logger.error(f"Error keeping account {account_name} active: {e}")

    async def _share_account_with_coowners(self, user_id: int, account_name: str):
        """Share newly added account with co-owners"""
        try:
            # Get user's co-owners
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if not user or not user.get("co_owners"):
                return

            co_owners = user.get("co_owners", [])
            if not co_owners:
                return

            # Get account details
            account = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "name": account_name}
            )
            if not account:
                return

            phone = account.get("phone", "Unknown")

            # Get 2FA password if exists
            twofa_password = None
            if account.get("twofa_password"):
                try:
                    from ..utils.data_encryption import decrypt_string

                    twofa_password = decrypt_string(account["twofa_password"])
                except BaseException:
                    pass

            # Add co-owners to account
            await mongodb.db.accounts.update_one(
                {"_id": account["_id"]},
                {"$addToSet": {"co_owners": {"$each": co_owners}}},
            )

            # Notify each co-owner
            for coowner_id in co_owners:
                try:
                    notification = (
                        f"🆕 **New Account Shared**\n\n"
                        f"User {user_id} added a new account and shared it with you!\n\n"
                        f"📱 **Account:** {account_name} ({phone})\n"
                    )

                    if twofa_password:
                        notification += f"🔐 **2FA Password:** `{twofa_password}`\n\n"
                    else:
                        notification += f"🔓 **2FA:** Not set\n\n"

                    notification += (
                        f"✅ **Co-Owner Access:**\n"
                        f"• You have full access to this account\n"
                        f"• Use /accs to view all shared accounts\n\n"
                        f"⚠️ Change 2FA password for security"
                    )

                    await self.bot.send_message(coowner_id, notification)
                    logger.info(
                        f"Notified co-owner {coowner_id} about new account {account_name}"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify co-owner {coowner_id}: {e}")

        except Exception as e:
            logger.error(f"Error sharing account with co-owners: {e}")
