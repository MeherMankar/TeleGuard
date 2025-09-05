"""TeleGuard - Telegram Account Manager Bot with OTP Destroyer Protection

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

from telethon import TelegramClient, events
from telethon.sessions import StringSession
import asyncio
import logging
import os
import re
from typing import Dict, Optional

from config import API_ID, API_HASH, BOT_TOKEN, MAX_ACCOUNTS
from database import init_db, get_session
from models import User, Account
from auth_handler import AuthManager
from otp_destroyer_enhanced import EnhancedOTPDestroyer
from menu_system import MenuSystem
from fullclient_manager import FullClientManager  # TODO: REVIEW - New import
from automation_engine import AutomationEngine  # TODO: REVIEW - New import
from telethon import functions, Button
from telethon_2fa_helpers import Secure2FAManager, SecureInputManager
from session_backup import SessionBackupManager  # TODO: REVIEW - session backup integration
from session_scheduler import SessionScheduler  # TODO: REVIEW - session backup integration
from channel_promotion import ChannelPromotion

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AccountManager:
    """Main bot class for managing Telegram accounts with OTP destroyer protection"""
    
    def __init__(self):
        self.bot = TelegramClient('bot', API_ID, API_HASH)
        self.user_clients: Dict[int, Dict[str, TelegramClient]] = {}
        self.pending_actions: Dict[int, Dict[str, str]] = {}
        self.auth_manager = AuthManager()
        self.otp_destroyer = EnhancedOTPDestroyer(self.bot)
        self.menu_system = MenuSystem(self.bot, self)
        self.fullclient_manager = FullClientManager(self.bot, self.user_clients)  # TODO: REVIEW - New manager
        self.automation_engine = AutomationEngine(self.user_clients, self.fullclient_manager)  # TODO: REVIEW - New engine
        self.secure_2fa = Secure2FAManager()
        self.secure_input = SecureInputManager()
        # TODO: REVIEW - session backup integration (optional)
        self.session_backup = None
        self.session_scheduler = None
        self.channel_promotion = ChannelPromotion(self.bot)
        
        # Only initialize session backup if enabled
        if os.environ.get('SESSION_BACKUP_ENABLED', 'false').lower() == 'true':
            self.session_backup = SessionBackupManager()
            self.session_scheduler = SessionScheduler()
        
    async def __aenter__(self):
        await self.start_bot()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def start_bot(self):
        """Initialize bot, database, and load existing sessions"""
        try:
            await init_db()
            
            # Run database migrations
            import sys
            from pathlib import Path
            scripts_path = Path(__file__).parent.parent / "scripts"
            sys.path.insert(0, str(scripts_path))
            
            from migrations import run_all_migrations
            await run_all_migrations()
            
            # TODO: REVIEW - Run full client migrations
            from fullclient_migrations import run_fullclient_migrations
            await run_fullclient_migrations()
            
            await self.bot.start(bot_token=BOT_TOKEN)
            await self.load_existing_sessions()
            self.register_handlers()
            
            # Set up menu system callbacks
            self.menu_system.setup_callback_handlers()
            
            # TODO: REVIEW - Start automation engine
            await self.automation_engine.start()
            
            # TODO: REVIEW - Start session scheduler (if enabled)
            if self.session_scheduler:
                await self.session_scheduler.start()
            
            logger.info("Bot started successfully")
        except Exception as e:
            logger.error("Bot startup failed")
            raise

    async def load_existing_sessions(self):
        """Load and start existing user sessions from database"""
        # TODO: REVIEW - session export / session-file handling
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account, User)
                    .join(User)
                    .where(Account.is_active == True)
                )
                
                for account, user in result:
                    try:
                        await self.start_user_client(
                            user.telegram_id, 
                            account.name, 
                            account.decrypt_session()
                        )
                    except Exception as e:
                        logger.error("Failed to load saved account session")
                        
        except Exception as e:
            logger.error("Failed to load saved user accounts")
    
    async def start_user_client(self, user_id: int, account_name: str, session_string: str):
        """Start a user client and set up OTP protection if enabled"""
        # TODO: REVIEW - session export / session-file handling
        try:
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
            await client.connect()
            
            if user_id not in self.user_clients:
                self.user_clients[user_id] = {}
            
            self.user_clients[user_id][account_name] = client
            
            # Set up enhanced OTP destroyer protection if enabled
            if await self._is_otp_protection_enabled(user_id, account_name):
                await self.otp_destroyer.setup_otp_listener(client, user_id, account_name)
            
            logger.info("User account connected successfully")
            
        except Exception as e:
            logger.error("Failed to connect user account")
            raise
    
    async def _is_otp_protection_enabled(self, user_id: int, account_name: str) -> bool:
        """Check if OTP protection is enabled for an account"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account.otp_destroyer_enabled)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.name == account_name)
                )
                return result.scalar_one_or_none() or False
        except Exception:
            return False
    
    async def setup_otp_protection(self, client: TelegramClient, user_id: int, account_name: str):
        """Set up real OTP destroyer using account.invalidateSignInCodes"""
        @client.on(events.NewMessage(chats=777000))  # Telegram service notifications
        async def otp_protection_handler(event):
            try:
                # Check if protection is still enabled
                protection_enabled = await self._is_otp_protection_enabled(user_id, account_name)
                if not protection_enabled:
                    logger.info(f"OTP protection disabled for {account_name}, ignoring message")
                    return
                
                message = event.message.message
                logger.info(f"Service message: {message[:100]}...")
                
                # Extract all possible OTP codes from message
                codes = self._extract_otp_codes(message)
                if not codes:
                    return
                
                logger.info(f"Found OTP codes: {codes} - DESTROYING them")
                
                # Use Telegram's official API to invalidate the codes
                from telethon import functions
                try:
                    result = await client(functions.account.InvalidateSignInCodesRequest(
                        codes=codes
                    ))
                    
                    if result:
                        # Notify bot owner
                        await self._send_protection_alert(user_id, account_name, codes)
                        logger.info(f"Successfully invalidated OTP codes {codes} for {account_name}")
                    else:
                        logger.warning(f"Failed to invalidate codes {codes}")
                        
                except Exception as e:
                    logger.error(f"Error calling invalidateSignInCodes: {e}")
                
            except Exception as e:
                logger.error(f"OTP protection error for {account_name}: {e}")
    
    def _extract_otp_codes(self, message: str) -> list[str]:
        """Extract all OTP codes from Telegram service message"""
        # Regex to capture 5-7 digit sequences possibly with hyphens
        code_pattern = re.compile(r'(?<!\d)(\d(?:-?\d){4,6})(?!\d)')
        
        found_codes = code_pattern.findall(message)
        if not found_codes:
            return []
        
        # Normalize codes (remove hyphens and whitespace)
        normalized_codes = []
        for code in found_codes:
            clean_code = re.sub(r'[^0-9]', '', code)
            if len(clean_code) >= 5:  # Valid OTP length
                normalized_codes.append(clean_code)
        
        # Remove duplicates
        return list(set(normalized_codes))
    
    async def _send_protection_alert(self, user_id: int, account_name: str, codes: list[str]):
        """Send OTP protection alert to user"""
        codes_str = ", ".join(codes)
        alert_message = (
            "🛡️ REAL OTP DESTROYER ACTIVATED\n"
            f"Account: {account_name}\n"
            f"Invalidated login codes: {codes_str}\n"
            "Unauthorized login attempt BLOCKED!\n\n"
            "✅ Codes are now permanently invalid on Telegram servers.\n"
            "❌ Attacker will see 'code expired/invalid' error."
        )
        try:
            await self.bot.send_message(user_id, alert_message)
        except Exception as e:
            logger.error("Failed to send security alert to user")

    async def run(self):
        """Main bot runner"""
        try:
            logger.info("Bot is running...")
            await self.bot.run_until_disconnected()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error("Bot encountered an error")
            raise
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            # TODO: REVIEW - Stop automation engine
            await self.automation_engine.stop()
            
            # TODO: REVIEW - Stop session scheduler (if enabled)
            if self.session_scheduler:
                await self.session_scheduler.stop()
            
            for user_clients in self.user_clients.values():
                for client in user_clients.values():
                    if client and client.is_connected():
                        await client.disconnect()
            
            if self.bot and self.bot.is_connected():
                await self.bot.disconnect()
                
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error("Error during bot shutdown")
    
    def register_handlers(self):
        """Register message handlers for bot commands"""
        @self.bot.on(events.NewMessage(pattern=r'/start'))
        async def start_handler(event):
            user_id = event.sender_id
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(select(User).where(User.telegram_id == user_id))
                user = result.scalar_one_or_none()
                is_new_user = user is None
                if not user:
                    user = User(telegram_id=user_id)
                    session.add(user)
                    await session.commit()
            
            # Send welcome message for new users
            if is_new_user:
                await self.channel_promotion.send_welcome_with_channel(user_id)
                return
            
            # Send main menu
            await self.menu_system.send_main_menu(user_id)

        @self.bot.on(events.NewMessage(pattern=r'/add'))
        async def add_handler(event):
            user_id = event.sender_id
            
            # Check if developer mode is enabled
            async with get_session() as session:
                from sqlalchemy import select, func
                result = await session.execute(select(User).where(User.telegram_id == user_id))
                user = result.scalar_one_or_none()
                if not user:
                    await event.reply("Please start the bot first with /start")
                    return
                
                if not user.developer_mode:
                    await event.reply("Use the menu system. Enable Developer Mode for text commands.")
                    return
                
                count_result = await session.execute(select(func.count(Account.id)).where(Account.owner_id == user.id))
                account_count = count_result.scalar()
                if account_count >= MAX_ACCOUNTS:
                    await event.reply(f"Maximum account limit ({MAX_ACCOUNTS}) reached.")
                    return
            
            self.pending_actions[user_id] = {"action": "add_account"}
            await event.reply("Please reply with the phone number for the new account.")

        @self.bot.on(events.NewMessage(pattern=r'/remove'))
        async def remove_handler(event):
            user_id = event.sender_id
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(select(User).where(User.telegram_id == user_id))
                user = result.scalar_one_or_none()
                if not user:
                    await event.reply("Please start the bot first with /start")
                    return
                accounts_result = await session.execute(select(Account).where(Account.owner_id == user.id))
                accounts = accounts_result.scalars().all()
                if not accounts:
                    await event.reply("You have no accounts to remove.")
                    return
            self.pending_actions[user_id] = {"action": "remove_account"}
            await event.reply("Reply with the account name to remove.")

        @self.bot.on(events.NewMessage(pattern=r'/accs'))
        async def list_accounts_handler(event):
            user_id = event.sender_id
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(select(User).where(User.telegram_id == user_id))
                user = result.scalar_one_or_none()
                if not user:
                    await event.reply("Please start the bot first with /start")
                    return
                accounts_result = await session.execute(select(Account).where(Account.owner_id == user.id))
                accounts = accounts_result.scalars().all()
                if not accounts:
                    await event.reply("You don't have any accounts added yet.")
                    return
                response = "Your accounts:\n"
                for acc in accounts:
                    status = "Active" if acc.is_active else "Inactive"
                    response += f"- {acc.name} ({acc.phone}) - {status}\n"
                await event.reply(response)

        @self.bot.on(events.NewMessage(pattern=r'/add_bot'))
        async def add_bot_handler(event):
            user_id = event.sender_id
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(select(User).where(User.telegram_id == user_id))
                user = result.scalar_one_or_none()
                if not user:
                    await event.reply("Please start the bot first with /start")
                    return
            await event.reply("Please send the bot token to add your bot.")

        @self.bot.on(events.NewMessage(pattern=r'/remove_bot'))
        async def remove_bot_handler(event):
            user_id = event.sender_id
            # TODO: Implement bot removal logic
            await event.reply("Reply to this message with the bot name to remove.")

        @self.bot.on(events.NewMessage(pattern=r'/rename'))
        async def rename_handler(event):
            user_id = event.sender_id
            self.pending_actions[user_id] = {"action": "rename_account"}
            await event.reply("Reply with the account name and new name, separated by a space. Example: oldname newname")

        @self.bot.on(events.NewMessage(func=lambda e: e.photo))
        async def photo_handler(event):
            user_id = event.sender_id
            
            if user_id not in self.pending_actions:
                return
                
            action = self.pending_actions[user_id].get("action")
            if action == "change_profile_photo":
                account_id = self.pending_actions[user_id].get("account_id")
                
                async with get_session() as session:
                    from sqlalchemy import select
                    result = await session.execute(select(Account).where(Account.owner_id == (await session.execute(select(User.id).where(User.telegram_id == user_id))).scalar(), Account.id == account_id))
                    account = result.scalar_one_or_none()
                    
                    if account:
                        try:
                            client = self.user_clients.get(user_id, {}).get(account.name)
                            if client:
                                # Download the photo
                                photo_path = await event.download_media()
                                
                                # Upload as profile photo
                                from telethon import functions
                                uploaded_file = await client.upload_file(photo_path)
                                await client(functions.photos.UploadProfilePhotoRequest(file=uploaded_file))
                                
                                # Clean up downloaded file
                                import os
                                if os.path.exists(photo_path):
                                    os.remove(photo_path)
                                
                                await event.reply("✅ Profile photo updated successfully!")
                            else:
                                await event.reply("❌ Account client not found")
                        except Exception as e:
                            await event.reply(f"❌ Failed to update profile photo: {e}")
                    else:
                        await event.reply("❌ Account not found")
                
                self.pending_actions.pop(user_id, None)

        @self.bot.on(events.NewMessage(incoming=True))
        async def reply_handler(event):
            user_id = event.sender_id
            message = event.raw_text.strip()
            
            # Skip commands
            if message.startswith('/'):
                return
                
            logger.info("User sent a message for pending action")
            
            if user_id not in self.pending_actions:
                logger.info("User sent message but no action was pending")
                return
                
            action = self.pending_actions[user_id]["action"]
            logger.info(f"Processing user action: {action.replace('_', ' ').title()}")
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(select(User).where(User.telegram_id == user_id))
                user = result.scalar_one_or_none()
                if not user:
                    await event.reply("Please start the bot first with /start")
                    self.pending_actions.pop(user_id, None)
                    return
                if action == "add_account":
                    phone = message
                    if not phone.startswith('+'):
                        await event.reply("Please provide phone number with country code (e.g., +1234567890)")
                        return
                    
                    try:
                        await self.auth_manager.start_auth(user_id, phone, use_otp_destroyer=False)
                        
                        self.pending_actions[user_id] = {
                            "action": "verify_otp", 
                            "phone": phone,
                            "otp_destroyer": False
                        }
                        
                        await event.reply(f"OTP sent to {phone}\nPlease reply with the verification code.")
                        return
                        
                    except Exception as e:
                        error_msg = str(e)
                        if "wait of" in error_msg and "seconds is required" in error_msg:
                            # Extract wait time
                            import re
                            wait_match = re.search(r'wait of (\d+) seconds', error_msg)
                            if wait_match:
                                wait_seconds = int(wait_match.group(1))
                                wait_minutes = wait_seconds // 60
                                wait_hours = wait_minutes // 60
                                
                                if wait_hours > 0:
                                    time_str = f"{wait_hours}h {wait_minutes % 60}m"
                                else:
                                    time_str = f"{wait_minutes}m"
                                
                                await event.reply(f"⏰ Rate limited! Please wait {time_str} before requesting OTP for this number again.\n\nTry using a different phone number or wait for the cooldown to expire.")
                            else:
                                await event.reply(f"Rate limited: {error_msg}")
                        else:
                            await event.reply(f"Error sending OTP: {error_msg}")
                        
                elif action == "verify_otp":
                    code = message
                    phone = self.pending_actions[user_id].get("phone")
                    
                    logger.info("User is verifying OTP code")
                    await event.reply(f"Verifying OTP {code}...")
                    
                    try:
                        session_string = await self.auth_manager.complete_auth(user_id, code)
                        logger.info("Account authentication completed successfully")
                        
                        if session_string == "OTP_DESTROYED":
                            await event.reply("OTP code destroyed successfully!")
                            self.pending_actions.pop(user_id, None)
                            return
                        
                        # Create account with encrypted session
                        acc = Account(name=phone, phone=phone, session_string="", owner_id=user.id)
                        acc.encrypt_session(session_string)
                        session.add(acc)
                        await session.commit()
                        logger.info("New account added to user's account list")
                        
                        # TODO: REVIEW - Store session in MongoDB backup system (if enabled)
                        if self.session_backup:
                            try:
                                self.session_backup.store_session(phone, session_string)
                                logger.info(f"Session backed up to MongoDB for {phone}")
                            except Exception as e:
                                logger.error(f"Failed to backup session for {phone}: {e}")
                        
                        # Start the client for this account
                        await self.start_user_client(user_id, phone, session_string)
                        
                        await event.reply(f"✅ Account {phone} added successfully!\nUse /toggle_protection to enable OTP destroyer.")
                        self.pending_actions.pop(user_id, None)
                        
                    except Exception as e:
                        logger.error(f"Auth error: {str(e)}")
                        if "Two-factor" in str(e):
                            self.pending_actions[user_id]["action"] = "verify_2fa"
                            await event.reply("🔐 Two-factor authentication required.\nReply with your 2FA password.")
                            return
                        else:
                            await event.reply(f"❌ Authentication failed: {str(e)}")
                            # Keep pending action for retry
                            pass
                            
                elif action == "verify_2fa":
                    password = message
                    phone = self.pending_actions[user_id].get("phone")
                    
                    await event.reply("Verifying 2FA password...")
                    
                    try:
                        session_string = await self.auth_manager.complete_auth(user_id, "", password)
                        
                        if session_string == "OTP_DESTROYED":
                            await event.reply("OTP code destroyed successfully!")
                            return
                        
                        acc = Account(name=phone, phone=phone, session_string="", owner_id=user.id)
                        acc.encrypt_session(session_string)
                        session.add(acc)
                        await session.commit()
                        
                        # TODO: REVIEW - Store session in MongoDB backup system (if enabled)
                        if self.session_backup:
                            try:
                                self.session_backup.store_session(phone, session_string)
                                logger.info(f"Session backed up to MongoDB for {phone}")
                            except Exception as e:
                                logger.error(f"Failed to backup session for {phone}: {e}")
                        
                        await self.start_user_client(user_id, phone, session_string)
                        
                        await event.reply(f"✅ Account {phone} added successfully with 2FA!\nUse /toggle_protection to enable OTP destroyer.")
                        
                    except Exception as e:
                        await event.reply(f"❌ 2FA failed: {str(e)}")
                        logger.error(f"2FA failed: {str(e)}")
                        
                elif action == "destroy_otp":
                    phone = message
                    if not phone.startswith('+'):
                        await event.reply("Please provide phone number with country code (e.g., +1234567890)")
                        return
                    
                    try:
                        await self.auth_manager.start_auth(user_id, phone, use_otp_destroyer=True)
                        
                        self.pending_actions[user_id] = {
                            "action": "destroy_code", 
                            "phone": phone
                        }
                        
                        await event.reply(f"OTP sent to {phone}\nReply with the OTP code to DESTROY it.")
                        return
                        
                    except Exception as e:
                        error_msg = str(e)
                        if "wait of" in error_msg and "seconds is required" in error_msg:
                            import re
                            wait_match = re.search(r'wait of (\d+) seconds', error_msg)
                            if wait_match:
                                wait_seconds = int(wait_match.group(1))
                                wait_minutes = wait_seconds // 60
                                wait_hours = wait_minutes // 60
                                
                                if wait_hours > 0:
                                    time_str = f"{wait_hours}h {wait_minutes % 60}m"
                                else:
                                    time_str = f"{wait_minutes}m"
                                
                                await event.reply(f"⏰ Rate limited! Please wait {time_str} before requesting OTP for this number again.")
                            else:
                                await event.reply(f"Rate limited: {error_msg}")
                        else:
                            await event.reply(f"Error sending OTP: {error_msg}")
                        
                elif action == "destroy_code":
                    code = message
                    phone = self.pending_actions[user_id].get("phone")
                    
                    try:
                        result = await self.auth_manager.complete_auth(user_id, code)
                        
                        if result == "OTP_DESTROYED":
                            await event.reply(f"SUCCESS: OTP code for {phone} has been destroyed!\nCheck for incomplete login alert in Telegram.")
                        else:
                            await event.reply("OTP code destroyed.")
                        
                    except Exception as e:
                        await event.reply(f"Error destroying code: {str(e)}")
                        
                elif action == "toggle_account_protection":
                    try:
                        account_num = int(message)
                        account_ids = self.pending_actions[user_id].get("accounts", [])
                        
                        if 1 <= account_num <= len(account_ids):
                            account_id = account_ids[account_num - 1]
                            
                            async with get_session() as db_session:
                                from sqlalchemy import select
                                result = await db_session.execute(select(Account).where(Account.id == account_id))
                                account = result.scalar_one_or_none()
                                if account:
                                    account.otp_destroyer_enabled = not account.otp_destroyer_enabled
                                    await db_session.commit()
                                    
                                    status = "enabled" if account.otp_destroyer_enabled else "disabled"
                                    await event.reply(f"OTP protection {status} for account {account.name}")
                                    
                                    # Restart client with new protection settings
                                    if account.otp_destroyer_enabled:
                                        await self.start_user_client(user_id, account.name, account.decrypt_session())
                                else:
                                    await event.reply("Account not found.")
                        else:
                            await event.reply("Invalid account number.")
                            
                    except ValueError:
                        await event.reply("Please enter a valid account number.")
                elif action == "remove_account":
                    name = message
                    from sqlalchemy import select
                    result = await session.execute(select(Account).where(Account.owner_id == user.id, Account.name == name))
                    acc = result.scalar_one_or_none()
                    if not acc:
                        await event.reply(f"No account found with name: {name}")
                    else:
                        await session.delete(acc)
                        await session.commit()
                        await event.reply(f"Account {name} removed.")
                elif action == "rename_account":
                    parts = message.split()
                    if len(parts) < 2:
                        await event.reply("Please provide both the current and new account names, separated by a space.")
                    else:
                        old_name, new_name = parts[0], ' '.join(parts[1:])
                        from sqlalchemy import select
                        result = await session.execute(select(Account).where(Account.owner_id == user.id, Account.name == old_name))
                        acc = result.scalar_one_or_none()
                        if not acc:
                            await event.reply(f"No account found with name: {old_name}")
                        else:
                            acc.name = new_name
                            await session.commit()
                            await event.reply(f"Account {old_name} renamed to {new_name}.")
                            
                # TODO: REVIEW - 2FA - Replaced insecure implementation with secure Telethon helper
                elif action == "set_2fa_password":
                    account_id = self.pending_actions[user_id].get("account_id")
                    password = message
                    
                    # Delete user's password message
                    try:
                        await event.delete()
                    except:
                        pass
                    
                    from sqlalchemy import select
                    result = await session.execute(select(Account).where(Account.owner_id == user.id, Account.id == account_id))
                    account = result.scalar_one_or_none()
                    
                    if account:
                        try:
                            client = self.user_clients.get(user_id, {}).get(account.name)
                            if not client:
                                await self.bot.send_message(user_id, "❌ Account client not found. Please restart the bot.")
                                return
                            
                            success, result_msg = await self.secure_2fa.set_2fa_password(
                                client, password, hint='Set via RambaZamba Bot'
                            )
                            
                            if success:
                                hashed_password = self.secure_2fa.hash_password_for_storage(password)
                                account.twofa_password = hashed_password
                                account.add_audit_entry({
                                    'action': 'set_2fa_password',
                                    'user_id': user_id,
                                    'result': True
                                })
                                await session.commit()
                                await self.bot.send_message(user_id, f"✅ 2FA password set successfully for {account.name}")
                            else:
                                await self.bot.send_message(user_id, f"❌ Failed to set 2FA: {result_msg}")
                            
                        except Exception as e:
                            logger.error(f"2FA setup error: {e}")
                            await self.bot.send_message(user_id, f"❌ Unexpected error: {type(e).__name__}")
                    else:
                        await self.bot.send_message(user_id, "❌ Account not found")
                        
                elif action == "change_2fa_current":
                    account_id = self.pending_actions[user_id].get("account_id")
                    current_password = message
                    
                    # Delete user's password message
                    try:
                        await event.delete()
                    except:
                        pass
                    
                    # Store current password and ask for new one
                    self.pending_actions[user_id] = {
                        "action": "change_2fa_new",
                        "account_id": account_id,
                        "current_password": current_password
                    }
                    
                    await self.bot.send_message(user_id, "🔑 **Change 2FA Password**\n\nNow reply with your new 2FA password:\n\n⚠️ Message will be deleted after processing for security.")
                    return
                    
                elif action == "change_2fa_new":
                    account_id = self.pending_actions[user_id].get("account_id")
                    current_password = self.pending_actions[user_id].get("current_password")
                    new_password = message
                    
                    # Delete user's password message
                    try:
                        await event.delete()
                    except:
                        pass
                    
                    from sqlalchemy import select
                    result = await session.execute(select(Account).where(Account.owner_id == user.id, Account.id == account_id))
                    account = result.scalar_one_or_none()
                    
                    if account:
                        try:
                            client = self.user_clients.get(user_id, {}).get(account.name)
                            if not client:
                                await self.bot.send_message(user_id, "❌ Account client not found. Please restart the bot.")
                                return
                            
                            success, result_msg = await self.secure_2fa.change_2fa_password(
                                client, current_password, new_password, hint='Changed via RambaZamba Bot'
                            )
                            
                            if success:
                                hashed_password = self.secure_2fa.hash_password_for_storage(new_password)
                                account.twofa_password = hashed_password
                                account.add_audit_entry({
                                    'action': 'change_2fa_password',
                                    'user_id': user_id,
                                    'result': True
                                })
                                await session.commit()
                                await self.bot.send_message(user_id, f"✅ 2FA password changed successfully for {account.name}")
                            else:
                                await self.bot.send_message(user_id, f"❌ Failed to change 2FA: {result_msg}")
                            
                        except Exception as e:
                            logger.error(f"2FA change error: {e}")
                            await self.bot.send_message(user_id, f"❌ Unexpected error: {type(e).__name__}")
                    else:
                        await self.bot.send_message(user_id, "❌ Account not found")
                        
                elif action == "remove_2fa_password":
                    account_id = self.pending_actions[user_id].get("account_id")
                    password = message
                    
                    # Delete user's password message
                    try:
                        await event.delete()
                    except:
                        pass
                    
                    from sqlalchemy import select
                    result = await session.execute(select(Account).where(Account.owner_id == user.id, Account.id == account_id))
                    account = result.scalar_one_or_none()
                    
                    if account:
                        try:
                            client = self.user_clients.get(user_id, {}).get(account.name)
                            if not client:
                                await self.bot.send_message(user_id, "❌ Account client not found. Please restart the bot.")
                                return
                            
                            success, result_msg = await self.secure_2fa.remove_2fa_password(client, password)
                            
                            if success:
                                account.twofa_password = None
                                account.add_audit_entry({
                                    'action': 'remove_2fa_password',
                                    'user_id': user_id,
                                    'result': True
                                })
                                await session.commit()
                                await self.bot.send_message(user_id, f"✅ 2FA password removed successfully for {account.name}\n\n⚠️ 2FA protection is now disabled.")
                            else:
                                await self.bot.send_message(user_id, f"❌ Failed to remove 2FA: {result_msg}")
                            
                        except Exception as e:
                            logger.error(f"2FA remove error: {e}")
                            await self.bot.send_message(user_id, f"❌ Unexpected error: {type(e).__name__}")
                    else:
                        await self.bot.send_message(user_id, "❌ Account not found")
                        
                elif action == "set_2fa_password_old":
                    account_id = self.pending_actions[user_id].get("account_id")
                    password = message
                    
                    # Check rate limiting
                    allowed, rate_msg = self.secure_2fa.check_rate_limit(user_id)
                    if not allowed:
                        await event.reply(f"❌ {rate_msg}")
                        return
                    
                    from sqlalchemy import select
                    result = await session.execute(select(Account).where(Account.owner_id == user.id, Account.id == account_id))
                    account = result.scalar_one_or_none()
                    
                    if account:
                        try:
                            # Get the client for this account
                            client = self.user_clients.get(user_id, {}).get(account.name)
                            if not client:
                                await event.reply("❌ Account client not found. Please restart the bot.")
                                return
                            
                            # Use secure 2FA helper instead of direct RPC
                            success, result_msg = await self.secure_2fa.set_2fa_password(
                                client, password, hint='Set via RambaZamba Bot'
                            )
                            
                            # Record attempt for rate limiting
                            self.secure_2fa.record_attempt(user_id, success)
                            
                            if success:
                                # Store hashed password in database
                                hashed_password = self.secure_2fa.hash_password_for_storage(password)
                                account.twofa_password = hashed_password
                                
                                # Add audit log entry
                                account.add_audit_entry({
                                    'action': 'set_2fa_password',
                                    'user_id': user_id,
                                    'result': True
                                })
                                
                                await session.commit()
                                await event.reply(f"✅ {result_msg} for {account.name}")
                            else:
                                await event.reply(f"❌ {result_msg}")
                            
                        except Exception as e:
                            logger.error(f"2FA setup error: {e}")
                            self.secure_2fa.record_attempt(user_id, False)
                            await event.reply(f"❌ Unexpected error: {type(e).__name__}")
                    else:
                        await event.reply("❌ Account not found")
                        
                elif action == "change_profile_name":
                    account_id = self.pending_actions[user_id].get("account_id")
                    name_parts = message.split(" ", 1)
                    first_name = name_parts[0]
                    last_name = name_parts[1] if len(name_parts) > 1 else ""
                    
                    from sqlalchemy import select
                    result = await session.execute(select(Account).where(Account.owner_id == user.id, Account.id == account_id))
                    account = result.scalar_one_or_none()
                    
                    if account:
                        try:
                            client = self.user_clients.get(user_id, {}).get(account.name)
                            if client:
                                from telethon import functions
                                # Get current profile to preserve bio
                                me = await client.get_me()
                                await client(functions.account.UpdateProfileRequest(
                                    first_name=first_name,
                                    last_name=last_name,
                                    about=me.about or ""
                                ))
                                
                                account.profile_first_name = first_name
                                account.profile_last_name = last_name
                                await session.commit()
                                
                                await event.reply(f"✅ Profile name updated to: {first_name} {last_name}")
                            else:
                                await event.reply("❌ Account client not found")
                        except Exception as e:
                            await event.reply(f"❌ Failed to update name: {e}")
                    else:
                        await event.reply("❌ Account not found")
                        
                elif action == "change_username":
                    account_id = self.pending_actions[user_id].get("account_id")
                    username = message.replace("@", "").strip()
                    
                    from sqlalchemy import select
                    result = await session.execute(select(Account).where(Account.owner_id == user.id, Account.id == account_id))
                    account = result.scalar_one_or_none()
                    
                    if account:
                        try:
                            client = self.user_clients.get(user_id, {}).get(account.name)
                            if client:
                                from telethon import functions
                                await client(functions.account.UpdateUsernameRequest(username=username))
                                
                                account.username = username
                                await session.commit()
                                
                                await event.reply(f"✅ Username updated to: @{username}")
                            else:
                                await event.reply("❌ Account client not found")
                        except Exception as e:
                            await event.reply(f"❌ Failed to update username: {e}")
                    else:
                        await event.reply("❌ Account not found")
                        
                elif action == "change_bio":
                    account_id = self.pending_actions[user_id].get("account_id")
                    bio = message[:70]  # Limit to 70 characters
                    
                    from sqlalchemy import select
                    result = await session.execute(select(Account).where(Account.owner_id == user.id, Account.id == account_id))
                    account = result.scalar_one_or_none()
                    
                    if account:
                        try:
                            client = self.user_clients.get(user_id, {}).get(account.name)
                            if client:
                                from telethon import functions
                                me = await client.get_me()
                                await client(functions.account.UpdateProfileRequest(
                                    first_name=me.first_name,
                                    last_name=me.last_name,
                                    about=bio
                                ))
                                
                                # Don't store personal data
                                await session.commit()
                                
                                await event.reply(f"✅ Bio updated to: {bio}")
                            else:
                                await event.reply("❌ Account client not found")
                        except Exception as e:
                            await event.reply(f"❌ Failed to update bio: {e}")
                    else:
                        await event.reply("❌ Account not found")
            
            self.pending_actions.pop(user_id, None)

        @self.bot.on(events.NewMessage(pattern=r'/me'))
        async def me_handler(event):
            user_id = event.sender_id
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(select(User).where(User.telegram_id == user_id))
                user = result.scalar_one_or_none()
                if not user:
                    await event.reply("Please start the bot first with /start")
                    return
                
                dev_mode = "Enabled" if user.developer_mode else "Disabled"
                response = (
                    f"⚙️ **Your Settings**\n\n"
                    f"Developer Mode: {dev_mode}\n"
                    f"OTP Forward: {user.otp_forward}\n"
                    f"OTP Destroy: {user.otp_destroy}\n"
                    f"Online Interval: {user.online_interval}s\n\n"
                    f"Use /start for the main menu."
                )
                await event.reply(response)
        
        @self.bot.on(events.NewMessage(pattern=r'/toggle_protection'))
        async def toggle_protection_handler(event):
            user_id = event.sender_id
            
            # Check developer mode
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(select(User).where(User.telegram_id == user_id))
                user = result.scalar_one_or_none()
                if not user or not user.developer_mode:
                    await event.reply("Use the menu system. Enable Developer Mode for text commands.")
                    return
            
            # Show menu instead
            await self.menu_system.send_accounts_list(user_id)
        
        @self.bot.on(events.NewMessage(pattern=r'/destroy'))
        async def manual_destroy_handler(event):
            user_id = event.sender_id
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(select(User).where(User.telegram_id == user_id))
                user = result.scalar_one_or_none()
                if not user:
                    await event.reply("Please start the bot first with /start")
                    return
            self.pending_actions[user_id] = {"action": "destroy_otp"}
            await event.reply("Manual OTP Destroyer\nReply with the phone number to destroy its OTP code.")
        
        @self.bot.on(events.NewMessage(pattern=r'/cancel'))
        async def cancel_handler(event):
            user_id = event.sender_id
            if user_id in self.pending_actions:
                # Cancel any pending auth
                self.auth_manager.cancel_auth(user_id)
                self.pending_actions.pop(user_id, None)
                await event.reply("Operation cancelled.")
            else:
                await event.reply("No operation to cancel.")
        
        @self.bot.on(events.NewMessage(pattern=r'/verify_session (.+)'))
        async def verify_session_handler(event):
            user_id = event.sender_id
            account_id = event.pattern_match.group(1).strip()
            
            # TODO: REVIEW - Session verification command
            try:
                from mongo_store import sessions_temp
                session_doc = sessions_temp.find_one({'account_id': account_id})
                
                if not session_doc:
                    await event.reply(f"❌ No session found for account {account_id}")
                    return
                
                github_status = "✅ Persisted" if session_doc.get('persisted_to_github') else "⏳ Pending"
                commit_sha = session_doc.get('github_commit', 'N/A')
                
                verification_text = f"""
🔍 **Session Verification for {account_id}**

SHA256: `{session_doc['sha256']}`
GitHub Status: {github_status}
Commit: `{commit_sha}`
Last Updated: {session_doc['last_updated']}

**Manual Verification:**
1. Download: `sessions/{account_id}.enc`
2. Verify signature: `gpg --verify manifests/sessions.json.sig manifests/sessions.json`
3. Check SHA256: `sha256sum sessions/{account_id}.enc`

**Repository:** {GITHUB_REPO or 'Not configured'}
                """
                
                await event.reply(verification_text)
                
            except Exception as e:
                await event.reply(f"❌ Verification failed: {e}")
        
        @self.bot.on(events.NewMessage(pattern=r'/backup_now'))
        async def backup_now_handler(event):
            user_id = event.sender_id
            
            # Check if user is admin
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(select(User).where(User.telegram_id == user_id))
                user = result.scalar_one_or_none()
                if not user or not user.is_admin:
                    await event.reply("❌ Admin access required")
                    return
            
            # TODO: REVIEW - Manual backup trigger
            if not self.session_scheduler:
                await event.reply("❌ Session backup not enabled")
                return
                
            await event.reply("🔄 Triggering manual session backup...")
            
            try:
                self.session_scheduler.trigger_push_now()
                await event.reply("✅ Manual backup job queued")
            except Exception as e:
                await event.reply(f"❌ Failed to trigger backup: {e}")
        
        @self.bot.on(events.NewMessage(pattern=r'/compact_now'))
        async def compact_now_handler(event):
            user_id = event.sender_id
            
            # Check if user is admin
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(select(User).where(User.telegram_id == user_id))
                user = result.scalar_one_or_none()
                if not user or not user.is_admin:
                    await event.reply("❌ Admin access required")
                    return
            
            # TODO: REVIEW - Manual history compaction trigger
            if not self.session_scheduler:
                await event.reply("❌ Session backup not enabled")
                return
                
            await event.reply("⚠️ Triggering history compaction (destructive operation)...")
            
            try:
                self.session_scheduler.trigger_compact_now()
                await event.reply("✅ History compaction job queued")
            except Exception as e:
                await event.reply(f"❌ Failed to trigger compaction: {e}")

        @self.bot.on(events.NewMessage(pattern=r'/support'))
        async def support_handler(event):
            support_text = (
                "🆘 **Support & Contact**\n\n"
                "Need help? Contact our support team:\n\n"
                "👨‍💻 **Developers:**\n"
                "• @Meher_Mankar\n"
                "• @Gutkesh\n\n"
                "📧 **Email:** https://t.me/ContactXYZrobot\n"
                "🐛 **Bug Reports:** Create an issue on GitHub\n\n"
                "⏰ **Response Time:** Usually within 24 hours"
            )
            await event.reply(support_text)

        @self.bot.on(events.NewMessage(pattern=r'/channel'))
        async def channel_handler(event):
            user_id = event.sender_id
            await self.channel_promotion.send_channel_promotion(user_id)

        @self.bot.on(events.NewMessage(pattern=r'/help'))
        async def help_handler(event):
            user_id = event.sender_id
            
            # Check developer mode for detailed help
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(select(User).where(User.telegram_id == user_id))
                user = result.scalar_one_or_none()
                
                if user and user.developer_mode:
                    help_text = """
🤖 **TeleGuard Account Manager**

**Menu System:**
Use /start to access the main menu with inline buttons.

**Developer Commands:**
/add - Add new account
/accs - List accounts  
/remove - Remove account
/toggle_protection - Toggle OTP destroyer
/verify_session <account_id> - Verify session backup
/help - Show this help
/support - Contact support team

**Admin Commands:**
/backup_now - Trigger manual session backup
/compact_now - Trigger history compaction

**OTP Destroyer:**
Automatically invalidates login codes to prevent unauthorized access.
Configure via Account Settings → OTP Settings in the menu.
                    """
                else:
                    help_text = """
🤖 **TeleGuard Account Manager**

Use /start to access the main menu.
All features are available through the inline menu system.

Enable Developer Mode in the menu for text commands.

💬 Need help? Use /support to contact our team.
                    """
            
            await event.reply(help_text)

async def main():
    """Main entry point"""
    async with AccountManager() as manager:
        await manager.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped")
    except Exception as e:
        logger.error("Application encountered an error")
        raise
