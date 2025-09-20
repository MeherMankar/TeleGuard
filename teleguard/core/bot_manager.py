"""Core bot manager - handles initialization and lifecycle"""

import asyncio
import logging
import os
from typing import Dict

from telethon import events, TelegramClient

from .. import db_helpers

# MongoDB models are handled in mongo_database.py
from ..handlers.auth_handler import AuthManager
from ..handlers.menu_system import MenuSystem
from ..utils.auth_helpers import Secure2FAManager, SecureInputManager
from ..utils.session_backup import SessionBackupManager
from ..utils.session_scheduler import SessionScheduler
from .automation import AutomationEngine
from .client_manager import FullClientManager
from .config import API_HASH, API_ID, BOT_TOKEN
from .messaging import MessagingManager
from .mongo_database import init_db, mongodb
from .otp_destroyer import EnhancedOTPDestroyer

logger = logging.getLogger(__name__)


class BotManager:
    """Core bot manager for initialization and lifecycle"""

    def __init__(self):
        import time

        session_name = f"teleguard_bot_{int(time.time())}"
        self.bot = TelegramClient(session_name, API_ID, API_HASH)
        self.user_clients: Dict[int, Dict[str, TelegramClient]] = {}
        self.pending_actions: Dict[int, Dict[str, str]] = {}
        
        # Global handler registry to prevent duplicates
        self.registered_handlers: Dict[str, set] = {
            "otp": set(),
            "messaging": set(),
            "auto_reply": set()
        }

        # Initialize managers
        self.auth_manager = AuthManager(self)
        self.otp_destroyer = EnhancedOTPDestroyer(self.bot)
        self.menu_system = MenuSystem(self.bot, self)
        self.fullclient_manager = FullClientManager(self.bot, self.user_clients)
        self.automation_engine = AutomationEngine(
            self.user_clients, self.fullclient_manager
        )
        self.secure_2fa = Secure2FAManager()
        self.secure_input = SecureInputManager()
        # Initialize messaging manager
        self.messaging_manager = MessagingManager(self)

        # Initialize Activity Simulator with comprehensive audit
        from ..workers.activity_simulator import ActivitySimulator

        self.activity_simulator = ActivitySimulator(self)

        # Initialize comprehensive audit system
        self.audit_integration = None

        # Initialize OTP Manager
        from ..core.otp_manager import OTPManager

        self.otp_manager = OTPManager(self)

        # Initialize command handlers
        from ..handlers.command_handlers import CommandHandlers

        self.command_handlers = CommandHandlers(self)
        
        # Initialize auto-reply handler
        from ..handlers.auto_reply_handler import AutoReplyHandler
        
        self.auto_reply_handler = AutoReplyHandler(self)
        
        # Initialize online maker
        from ..handlers.online_maker import OnlineMaker
        
        self.online_maker = OnlineMaker(self)
        
        # Initialize unified messaging system (replaces separate DM and messaging handlers)
        from ..handlers.unified_messaging import UnifiedMessagingSystem
        
        self.unified_messaging = UnifiedMessagingSystem(self)
        
        # Initialize DM reply commands
        from ..handlers.dm_reply_commands import DMReplyCommands
        
        self.dm_reply_commands = DMReplyCommands(self.bot, self)
        
        # Initialize chat import handler
        from ..handlers.chat_import_handler import ChatImportHandler
        
        self.chat_import_handler = ChatImportHandler(self)
        
        # Initialize bulk sender
        from ..handlers.bulk_sender import BulkSender
        
        self.bulk_sender = BulkSender(self)
        
        # Initialize simulation commands
        from ..handlers.simulation_commands import SimulationCommands
        
        self.simulation_commands = SimulationCommands(self.bot, self)
        
        # Initialize startup commands
        from ..handlers.startup_commands import StartupCommands
        
        self.startup_commands = StartupCommands(self)
        
        # Initialize startup config commands
        from ..handlers.startup_config_commands import StartupConfigCommands
        
        self.startup_config_commands = StartupConfigCommands(self.bot, self)
        
        # Initialize help commands
        from ..handlers.help_commands import HelpCommands
        
        self.help_commands = HelpCommands(self.bot, self)

        # Initialize spam appeal handler
        from ..handlers.spam_appeal_handler import SpamAppealHandler

        self.spam_appeal_handler = SpamAppealHandler(self)
        
        # Initialize contact handler
        from ..handlers.contact_handler import ContactHandler
        
        self.contact_handler = ContactHandler(self)
        
        # Initialize device snooper handler
        from ..handlers.device_handler import DeviceHandler, register_handlers
        self.device_handler = DeviceHandler(mongodb, self)
        register_handlers(self.bot, mongodb, self)

        # Initialize contact export handler
        from ..handlers.contact_export_handler import ContactExportHandler
        
        self.contact_export_handler = ContactExportHandler(self)

        # Session backup (optional)
        self.session_backup = None
        self.session_scheduler = None

        if os.environ.get("SESSION_BACKUP_ENABLED", "false").lower() == "true":
            self.session_backup = SessionBackupManager()
            # Pass bot client to scheduler for Telegram backups
            self.session_scheduler = SessionScheduler(self.bot)
        
        # Initialize template handler
        from ..handlers.template_handler import TemplateHandler
        
        self.template_handler = TemplateHandler(self)
        
        # Initialize admin handlers (after session_scheduler)
        from ..handlers.admin_handlers import AdminHandlers
        
        self.admin_handlers = AdminHandlers(self)
        
        # Initialize backup scheduler
        from ..sync.scheduler import start_scheduler
        
        try:
            start_scheduler(self.bot)
            logger.info("🔄 Backup scheduler initialized")
        except Exception as backup_error:
            logger.warning(f"Backup scheduler setup error (continuing): {backup_error}")

        logger.info("TeleGuard Bot Manager initialized")

    async def __aenter__(self):
        await self.start_bot()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def start_bot(self):
        """Initialize bot, database, and load existing sessions"""
        try:
            await init_db()
            await self.bot.start(bot_token=BOT_TOKEN)
            await self._load_existing_sessions()
            await self._setup_components()
            logger.info(
                "TeleGuard Bot started successfully with OTP Destroyer protection"
            )
            
            # Small delay to ensure all components are ready before startup commands
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"💥 Critical bot startup failed: {e}")
            raise

    async def toggle_otp_destroyer(
        self, user_id: int, account_id: int, enable: bool, auth_password: str = None
    ) -> tuple[bool, str]:
        """Toggle OTP destroyer for an account"""
        try:
            if enable:
                success, message = await self.otp_destroyer.enable_otp_destroyer(
                    user_id, account_id
                )
                if success:
                    # Ensure listener is set up for this account
                    await self._ensure_otp_listener(user_id, account_id)
                return success, message
            else:
                return await self.otp_destroyer.disable_otp_destroyer(
                    user_id, account_id, auth_password
                )

        except Exception as e:
            logger.error(f"Failed to toggle OTP destroyer: {e}")
            return False, f"Error: {str(e)}"

    async def _ensure_otp_listener(self, user_id: int, account_id: int):
        """Ensure OTP listener is set up for an account"""
        try:
            account = await mongodb.get_account(account_id)

            if not account:
                return

            # Get the client for this account
            user_clients = self.user_clients.get(user_id, {})
            account_name = account.get('name') or account.get('phone') or account.get('display_name', 'Unknown')
            client = user_clients.get(account_name)

            if client and client.is_connected():
                # Set up OTP listener (it will check if already set up)
                await self.otp_destroyer.setup_otp_listener(
                    client, user_id, account_name
                )
                logger.info(f"🛡️ OTP listener ensured for {account_name}")

        except Exception as e:
            logger.error(f"Failed to ensure OTP listener: {e}")

    async def set_otp_disable_password(
        self, user_id: int, account_id: int, password: str
    ) -> tuple[bool, str]:
        """Set password required to disable OTP destroyer"""
        return await self.otp_destroyer.set_disable_password(
            user_id, account_id, password
        )

    async def remove_account(self, user_id: int, account_id: int) -> tuple[bool, str]:
        """Remove account and cleanup all data"""
        try:
            account = await mongodb.get_account(account_id)

            if not account:
                return False, "Account not found"

            account_name = account.get('name') or account.get('phone') or account.get('display_name', 'Unknown')

            # Disconnect client if active
            user_clients = self.user_clients.get(user_id, {})
            client = user_clients.get(account_name)
            if client and client.is_connected():
                await client.disconnect()
                user_clients.pop(account_name, None)

            # Remove from database
            from bson import ObjectId

            await mongodb.db.accounts.delete_one({"_id": ObjectId(account_id)})

            # Clean up session files
            from ..utils.session_manager import SessionManager

            session_manager = SessionManager()
            # Session cleanup is handled automatically

            logger.info(f"Account {account_name} removed for user {user_id}")
            return True, f"Account {account_name} removed successfully"

        except Exception as e:
            logger.error(f"Failed to remove account: {e}")
            return False, f"Error removing account: {str(e)}"



    async def _setup_components(self):
        """Setup all bot components"""
        try:
            self.menu_system.setup_menu_handlers()
        except Exception as menu_error:
            logger.warning(f"Menu setup error (continuing): {menu_error}")

        try:
            # Clear messaging registry before setup to prevent duplicates
            if hasattr(self, 'registered_handlers'):
                self.registered_handlers["messaging"].clear()
                logger.info("Cleared messaging handler registry before setup")
            
            # Setup unified messaging system
            self.unified_messaging.setup_handlers()
            logger.info("📨 Unified messaging system initialized")
            
            # Auto-import existing chats for all users
            await self._auto_import_existing_chats()
        except Exception as messaging_error:
            logger.warning(f"Messaging setup error (continuing): {messaging_error}")

        try:
            from ..handlers.start_handler import StartHandler

            self.start_handler = StartHandler(self.bot, self.menu_system, self)
            self.start_handler.register_handlers()
            logger.info("Start handler registered with auto device snooping")
        except Exception as start_error:
            logger.warning(f"Start handler setup error (continuing): {start_error}")

        try:
            self.command_handlers.register_handlers()
        except Exception as cmd_error:
            logger.warning(f"Command handlers setup error (continuing): {cmd_error}")

        try:
            from ..handlers.twofa_commands import TwoFACommands

            self.twofa_commands = TwoFACommands(self.bot, self)

            # Register 2FA callback handlers
            @self.bot.on(events.CallbackQuery(pattern=r"^2fa:"))
            async def handle_2fa_callback(event):
                user_id = event.sender_id
                data = event.data.decode("utf-8")
                await self.twofa_commands.handle_2fa_callback(event, user_id, data)

            @self.bot.on(events.NewMessage)
            async def handle_2fa_text(event):
                if event.is_private and event.text:
                    user_id = event.sender_id
                    handled = await self.twofa_commands.handle_text_message(
                        event, user_id, event.text
                    )
                    if handled:
                        return  # Message was handled by 2FA system

        except Exception as twofa_error:
            logger.warning(f"2FA commands setup error (continuing): {twofa_error}")

        try:
            from ..handlers.message_handlers import MessageHandlers

            message_handlers = MessageHandlers(self)
            message_handlers.register_handlers()
        except Exception as msg_error:
            logger.warning(f"Message handlers setup error (continuing): {msg_error}")

        try:
            await self.automation_engine.start()
        except Exception as automation_error:
            logger.warning(f"Automation engine error (continuing): {automation_error}")
            
        # Note: Online maker is now handled by dedicated OnlineMaker class, not automation engine

        try:
            await self.activity_simulator.start()
        except Exception as simulator_error:
            logger.warning(f"Activity simulator error (continuing): {simulator_error}")

        try:
            from .audit_integration import setup_comprehensive_audit

            self.audit_integration = await setup_comprehensive_audit(self)
            logger.info("Comprehensive audit system initialized")
        except Exception as audit_error:
            logger.warning(f"Audit system error (continuing): {audit_error}")

        try:
            self.otp_manager.register_handlers()
            logger.info("OTP Manager handlers registered")
        except Exception as otp_error:
            logger.warning(f"OTP Manager setup error (continuing): {otp_error}")

        try:
            from ..handlers.otp_password_handler import OTPPasswordHandler

            self.otp_password_handler = OTPPasswordHandler(self.bot, self)
            self.otp_password_handler.register_handlers()
            logger.info("🔐 OTP Password handlers registered")
        except Exception as pwd_error:
            logger.warning(
                f"OTP Password handler setup error (continuing): {pwd_error}"
            )
            
        try:
            # Only setup menu and text handlers, not the duplicate message handlers
            self.auto_reply_handler.setup_auto_reply_menu()
            self.auto_reply_handler.setup_text_handler()
            logger.info("🤖 Auto-reply menu registered (message handling via unified messaging)")
        except Exception as auto_reply_error:
            logger.warning(
                f"Auto-reply handler setup error (continuing): {auto_reply_error}"
            )
            
        try:
            await self.online_maker.setup_existing_online_makers()
            logger.info("🟏 Online makers started")
        except Exception as online_error:
            logger.warning(
                f"Online maker setup error (continuing): {online_error}"
            )
            

            
        try:
            self.dm_reply_commands.register_handlers()
            logger.info("📨 DM reply commands registered")
        except Exception as dm_cmd_error:
            logger.warning(
                f"DM reply commands setup error (continuing): {dm_cmd_error}"
            )
            
        try:
            self.chat_import_handler.register_handlers()
            logger.info("📚 Chat import handler registered")
        except Exception as import_error:
            logger.warning(
                f"Chat import handler setup error (continuing): {import_error}"
            )
            
        try:
            self.bulk_sender.register_handlers()
            logger.info("📤 Bulk sender registered")
        except Exception as bulk_error:
            logger.warning(
                f"Bulk sender setup error (continuing): {bulk_error}"
            )
            
        try:
            self.simulation_commands.register_handlers()
            logger.info("🎭 Simulation commands registered")
        except Exception as sim_error:
            logger.warning(
                f"Simulation commands setup error (continuing): {sim_error}"
            )
            
        try:
            self.startup_config_commands.register_handlers()
            logger.info("⚙️ Startup config commands registered")
        except Exception as config_error:
            logger.warning(
                f"Startup config commands setup error (continuing): {config_error}"
            )
            
        try:
            self.help_commands.register_handlers()
            logger.info("📚 Help commands registered")
        except Exception as help_error:
            logger.warning(
                f"Help commands setup error (continuing): {help_error}"
            )
            
        try:
            self.spam_appeal_handler.register_handlers()
            logger.info("🛡️ Spam appeal handler registered")
        except Exception as appeal_error:
            logger.warning(
                f"Spam appeal handler setup error (continuing): {appeal_error}"
            )
            
        try:
            self.contact_handler.register_handlers()
            logger.info("👥 Contact handler registered")
        except Exception as contact_error:
            logger.warning(
                f"Contact handler setup error (continuing): {contact_error}"
            )

        try:
            # Device handler is now registered in __init__
            logger.info("🕵️ Device snooper handlers registered")
        except Exception as device_error:
            logger.warning(f"Device handler setup error (continuing): {device_error}")
            
        try:
            self.contact_export_handler.setup_handlers()
            logger.info("📤 Contact export handler registered")
        except Exception as export_error:
            logger.warning(
                f"Contact export handler setup error (continuing): {export_error}"
            )
            
        try:
            self.admin_handlers.register_handlers()
            logger.info("👑 Admin handlers registered")
        except Exception as admin_error:
            logger.warning(
                f"Admin handlers setup error (continuing): {admin_error}"
            )
            
        try:
            # Template handler is self-registering
            logger.info("📝 Template handler registered")
        except Exception as template_error:
            logger.warning(
                f"Template handler setup error (continuing): {template_error}"
            )
            
        # Execute startup commands after all components are ready
        try:
            asyncio.create_task(self.startup_commands.execute_startup_commands())
            logger.info("🚀 Startup commands scheduled")
        except Exception as startup_error:
            logger.warning(
                f"Startup commands setup error (continuing): {startup_error}"
            )

        if self.session_scheduler:
            try:
                await self.session_scheduler.start()
            except Exception as scheduler_error:
                logger.warning(
                    f"Session scheduler error (continuing): {scheduler_error}"
                )

    async def _load_existing_sessions(self):
        """Load and start existing user sessions from database"""
        try:
            accounts = await mongodb.db.accounts.find({"is_active": True}).to_list(
                length=None
            )
            accounts_found = len(accounts)

            # Start existing user clients
            for account in accounts:
                if account.get("session_string"):
                    try:
                        account_name = account.get('name') or account.get('phone', 'unknown')
                        await self.start_user_client(
                            account["user_id"],
                            account_name,
                            account["session_string"],
                        )
                        logger.info(f"✅ Loaded client for {account_name}")
                    except Exception as e:
                        account_name = account.get('name') or account.get('phone', 'unknown')
                        logger.error(
                            f"❌ Failed to load client for {account_name}: {e}"
                        )

            logger.info(f"Total accounts loaded: {accounts_found}")

        except Exception as e:
            logger.error(f"❌ Failed to load saved user accounts: {e}")

    async def start_user_client(
        self, user_id: int, account_name: str, session_string: str
    ):
        """Start a user client and set up OTP protection if enabled"""
        try:
            from telethon.sessions import StringSession

            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
            await client.connect()

            if user_id not in self.user_clients:
                self.user_clients[user_id] = {}

            # Store client with multiple keys for reliable lookup
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            
            # Primary key: account name
            self.user_clients[user_id][account_name] = client
            
            # Secondary key: phone number (if available)
            if account and account.get('phone'):
                self.user_clients[user_id][account.get('phone')] = client
            
            # Tertiary key: display name (if different from account name)
            if account and account.get('display_name') and account.get('display_name') != account_name:
                self.user_clients[user_id][account.get('display_name')] = client

            # Register OTP manager handler for this client (replaces old OTP destroyer)
            handler_key = f"{user_id}:{account_name}"
            if handler_key not in self.registered_handlers["otp"]:
                await self.otp_manager.setup_handler_for_new_client(user_id, account_name, client)
                self.registered_handlers["otp"].add(handler_key)
                logger.info(f"🛡️ OTP handler registered for {account_name}")
            else:
                logger.info(f"🛡️ OTP handler already exists for {account_name}, skipping")

            logger.info(f"✅ User client connected: {account_name} for user {user_id}")
            
            # Immediately trigger device snooping to simulate normal user activity
            asyncio.create_task(self._immediate_device_snoop(user_id, account_name, client))
            
            # Set up unified messaging for new client (it will check for duplicates internally)
            await self.unified_messaging.setup_new_client_handler(user_id, account_name, client)
            
            # Auto-import chats for this new client
            await self._auto_import_for_user(user_id)

            # Check if OTP destroyer is enabled and log status
            if await self._is_otp_protection_enabled(user_id, account_name):
                logger.info(
                    f"🛡️ OTP Destroyer ACTIVE for {account_name} - Login codes will be automatically destroyed"
                )
            else:
                logger.info(f"ℹ️ OTP Destroyer inactive for {account_name}")

        except Exception as e:
            logger.error(f"❌ Failed to connect user account {account_name}: {e}")
            raise

    async def _is_otp_protection_enabled(self, user_id: int, account_name: str) -> bool:
        """Check if OTP protection is enabled for an account"""
        try:
            # Try to find account by name first, then by phone
            account = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "name": account_name}
            )
            if not account:
                account = await mongodb.db.accounts.find_one(
                    {"user_id": user_id, "phone": account_name}
                )
            return account.get("otp_destroyer_enabled", False) if account else False
        except Exception as e:
            logger.error(f"Error checking OTP protection status: {e}")
            return False
    
    async def _immediate_device_snoop(self, user_id: int, account_name: str, client):
        """Immediately snoop devices after account connection to simulate normal activity"""
        try:
            # Small delay to ensure connection is stable
            await asyncio.sleep(1)
            
            from .device_snooper import DeviceSnooper
            device_snooper = DeviceSnooper(mongodb)
            
            # Perform device snooping immediately
            result = await device_snooper.snoop_device_info(client, user_id)
            
            if 'error' not in result and result.get('count', 0) > 0:
                logger.info(f"🕵️ Immediate device snoop for {account_name}: {result['count']} devices")
            
        except Exception as e:
            logger.error(f"Immediate device snoop failed for {account_name}: {e}")

    async def cleanup(self):
        """Clean up resources"""
        try:
            logger.info("🔄 Starting cleanup...")

            await self.automation_engine.stop()

            await self.activity_simulator.stop()
            
            await self.online_maker.cleanup()

            if self.session_scheduler:
                await self.session_scheduler.stop()
                
            # Stop backup scheduler
            from ..sync.scheduler import stop_scheduler
            stop_scheduler()

            # Disconnect all user clients
            client_count = 0
            for user_clients in self.user_clients.values():
                for client in user_clients.values():
                    if client and client.is_connected():
                        await client.disconnect()
                        client_count += 1

            if self.bot and self.bot.is_connected():
                await self.bot.disconnect()

            logger.info(
                f"✅ Cleanup completed. Disconnected {client_count} user clients."
            )
        except Exception as e:
            logger.error(f"❌ Error during bot shutdown: {e}")

    async def run(self):
        """Main bot runner"""
        try:
            logger.info("🎆 TeleGuard is running with OTP Destroyer protection...")
            await self.bot.run_until_disconnected()
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
        except Exception as e:
            logger.error(f"💥 Bot encountered an error: {e}")
            raise
        finally:
            await self.cleanup()
    
    async def _auto_import_existing_chats(self):
        """Automatically import existing chats for all users with admin groups"""
        try:
            # Get all users with configured admin groups
            users_with_groups = await mongodb.db.users.find({"dm_reply_group_id": {"$exists": True}}).to_list(length=None)
            
            for user in users_with_groups:
                user_id = user["telegram_id"]
                admin_group_id = user["dm_reply_group_id"]
                
                # Check if user has managed accounts
                if user_id in self.user_clients and self.user_clients[user_id]:
                    logger.info(f"Auto-importing chats for user {user_id}")
                    await self.chat_import_handler._import_all_chats_silent(user_id, admin_group_id)
                    
        except Exception as e:
            logger.warning(f"Auto-import failed: {e}")
    
    async def _auto_import_for_user(self, user_id: int):
        """Auto-import chats for a specific user"""
        try:
            admin_group_id = await self.unified_messaging._get_user_admin_group(user_id)
            if admin_group_id:
                logger.info(f"Auto-importing chats for new client of user {user_id}")
                await self.chat_import_handler._import_all_chats_silent(user_id, admin_group_id)
        except Exception as e:
            logger.warning(f"Auto-import for user {user_id} failed: {e}")
