"""Inline menu system for account management

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import logging
from typing import Optional, List
from telethon import Button, events
from database import get_session
from models import User, Account
from secure_2fa_handlers import Secure2FAHandlers

logger = logging.getLogger(__name__)

class MenuSystem:
    """Handles inline keyboard menus and callback queries"""
    
    def __init__(self, bot_instance, account_manager=None):
        self.bot = bot_instance
        self.account_manager = account_manager
        self.secure_2fa_handlers = Secure2FAHandlers(bot_instance, account_manager)
        
    def get_main_menu_buttons(self) -> List[List[Button]]:
        """Get main menu inline keyboard"""
        return [
            [Button.inline("📱 Account Settings", "menu:accounts")],
            [Button.inline("💬 Messaging", "menu:messaging")],
            [Button.inline("❓ Help", "menu:help"), Button.inline("🆘 Support", "menu:support")],
            [Button.inline("⚙️ Developer", "menu:dev")]
        ]
    
    def get_account_menu_buttons(self, account_id: int) -> List[List[Button]]:
        """Get account-specific menu buttons"""
        return [
            [Button.inline("👤 Profile Settings", f"profile:manage:{account_id}"), Button.inline("🛡️ OTP Destroyer", f"otp:toggle:{account_id}")],
            [Button.inline("🔑 2FA Settings", f"2fa:status:{account_id}"), Button.inline("🔐 Active Sessions", f"sessions:list:{account_id}")],
            [Button.inline("🟢 Online Maker", f"online:toggle:{account_id}"), Button.inline("⚡ Automation", f"automation:manage:{account_id}")],
            [Button.inline("📋 View Audit Log", f"otp:audit:{account_id}")],
            [Button.inline("🔙 Back to Accounts", "menu:accounts")]
        ]
    
    def get_otp_settings_buttons(self, account_id: int, destroyer_enabled: bool) -> List[List[Button]]:
        """Get OTP settings menu"""
        destroyer_text = "🛡️ Disable OTP Destroyer" if destroyer_enabled else "🛡️ Enable OTP Destroyer"
        destroyer_action = f"otp:disable:{account_id}" if destroyer_enabled else f"otp:enable:{account_id}"
        
        return [
            [Button.inline(destroyer_text, destroyer_action)],
            [Button.inline("📋 View Audit Log", f"otp:audit:{account_id}")],
            [Button.inline("🔒 Security Settings", f"otp:security:{account_id}")],
            [Button.inline("🔙 Back", "menu:accounts")]
        ]
    
    async def send_main_menu(self, user_id: int, edit_message_id: Optional[int] = None) -> int:
        """Send or update main menu"""
        try:
            buttons = self.get_main_menu_buttons()
            text = "🤖 **TeleGuard Account Manager**\n\nSelect an option:"
            
            if edit_message_id:
                await self.bot.edit_message(user_id, edit_message_id, text, buttons=buttons)
                return edit_message_id
            else:
                message = await self.bot.send_message(user_id, text, buttons=buttons)
                
                # Store menu message ID
                async with get_session() as session:
                    from sqlalchemy import select
                    result = await session.execute(select(User).where(User.telegram_id == user_id))
                    user = result.scalar_one_or_none()
                    if user:
                        user.main_menu_message_id = message.id
                        await session.commit()
                
                return message.id
                
        except Exception as e:
            logger.error(f"Failed to send main menu: {e}")
            return 0
    
    async def send_accounts_list(self, user_id: int, edit_message_id: Optional[int] = None):
        """Send accounts list with management options"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account, User)
                    .join(User)
                    .where(User.telegram_id == user_id)
                )
                
                accounts = []
                for account, user in result:
                    accounts.append(account)
                
                if not accounts:
                    text = "📱 **Account Management**\n\nNo accounts found. Add your first account to get started."
                    buttons = [
                        [Button.inline("➕ Add Account", "account:add")],
                        [Button.inline("🔙 Back to Main", "menu:main")]
                    ]
                else:
                    text = "📱 **Account Management**\n\nSelect an account to manage:"
                    buttons = []
                    
                    for account in accounts:
                        status = "🟢" if account.is_active else "🔴"
                        destroyer_status = "🛡️" if account.otp_destroyer_enabled else "⚪"
                        button_text = f"{status}{destroyer_status} {account.name}"
                        buttons.append([Button.inline(button_text, f"account:manage:{account.id}")])
                    
                    buttons.append([Button.inline("➕ Add Account", "account:add")])
                    buttons.append([Button.inline("🔙 Back to Main", "menu:main")])
                
                if edit_message_id:
                    await self.bot.edit_message(user_id, edit_message_id, text, buttons=buttons)
                else:
                    await self.bot.send_message(user_id, text, buttons=buttons)
                    
        except Exception as e:
            logger.error(f"Failed to send accounts list: {e}")
    
    async def send_account_management(self, user_id: int, account_id: int, edit_message_id: Optional[int] = None):
        """Send account management menu"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()
                
                if not account:
                    await self.bot.send_message(user_id, "❌ Account not found")
                    return
                
                destroyer_status = "🟢 Enabled" if account.otp_destroyer_enabled else "🔴 Disabled"
                last_destroyed = account.otp_destroyed_at or "Never"
                
                text = (
                    f"📱 **Account: {account.name}**\n\n"
                    f"📞 Phone: {account.phone}\n"
                    f"🛡️ OTP Destroyer: {destroyer_status}\n"
                    f"🕒 Last Destroyed: {last_destroyed}\n\n"
                    f"Select an action:"
                )
                
                buttons = self.get_account_menu_buttons(account_id)
                
                if edit_message_id:
                    await self.bot.edit_message(user_id, edit_message_id, text, buttons=buttons)
                else:
                    await self.bot.send_message(user_id, text, buttons=buttons)
                    
        except Exception as e:
            logger.error(f"Failed to send account management: {e}")
    
    async def send_otp_settings(self, user_id: int, account_id: int, edit_message_id: Optional[int] = None):
        """Send OTP settings menu"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()
                
                if not account:
                    await self.bot.send_message(user_id, "❌ Account not found")
                    return
                
                destroyer_status = "🟢 Enabled" if account.otp_destroyer_enabled else "🔴 Disabled"
                has_password = "🔒 Set" if account.otp_destroyer_disable_auth else "⚪ Not Set"
                
                text = (
                    f"🛡️ **OTP Settings: {account.name}**\n\n"
                    f"Status: {destroyer_status}\n"
                    f"Disable Password: {has_password}\n"
                    f"Last Activity: {account.otp_destroyed_at or 'Never'}\n\n"
                    f"Select an action:"
                )
                
                buttons = self.get_otp_settings_buttons(account_id, account.otp_destroyer_enabled)
                
                if edit_message_id:
                    await self.bot.edit_message(user_id, edit_message_id, text, buttons=buttons)
                else:
                    await self.bot.send_message(user_id, text, buttons=buttons)
                    
        except Exception as e:
            logger.error(f"Failed to send OTP settings: {e}")
    
    async def send_audit_log(self, user_id: int, account_id: int):
        """Send audit log for account"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()
                
                if not account:
                    await self.bot.send_message(user_id, "❌ Account not found")
                    return
                
                audit_log = account.get_audit_log()
                
                if not audit_log:
                    text = f"📋 **Audit Log: {account.name}**\n\nNo audit entries found."
                else:
                    text = f"📋 **Audit Log: {account.name}**\n\n"
                    
                    # Show last 10 entries
                    for entry in audit_log[-10:]:
                        timestamp = entry.get('timestamp', 0)
                        action = entry.get('action', 'unknown')
                        
                        import time
                        time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
                        
                        if action == 'invalidate_codes':
                            codes = entry.get('codes', [])
                            result = entry.get('result', False)
                            status = "✅" if result else "❌"
                            text += f"{status} {time_str}: Destroyed codes {codes}\n"
                        elif action == 'enable_otp_destroyer':
                            text += f"🟢 {time_str}: OTP Destroyer enabled\n"
                        elif action == 'disable_otp_destroyer':
                            text += f"🔴 {time_str}: OTP Destroyer disabled\n"
                        else:
                            text += f"ℹ️ {time_str}: {action}\n"
                
                buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
                await self.bot.send_message(user_id, text, buttons=buttons)
                
        except Exception as e:
            logger.error(f"Failed to send audit log: {e}")
    
    def setup_callback_handlers(self):
        """Set up callback query handlers"""
        
        @self.bot.on(events.CallbackQuery)
        async def callback_handler(event):
            try:
                user_id = event.sender_id
                data = event.data.decode('utf-8')
                
                logger.info(f"Callback from {user_id}: {data}")
                
                if data == "menu:main":
                    await self.send_main_menu(user_id, event.message_id)
                    
                elif data == "menu:accounts":
                    await self.send_accounts_list(user_id, event.message_id)
                    
                elif data == "menu:otp":
                    await self.send_otp_menu(user_id, event.message_id)
                    
                elif data == "menu:sessions":
                    await self._send_sessions_menu(user_id, event.message_id)
                    
                elif data == "menu:2fa":
                    await self._send_2fa_menu(user_id, event.message_id)
                    
                elif data == "menu:online":
                    await self._send_online_menu(user_id, event.message_id)
                    
                elif data.startswith("account:manage:"):
                    account_id = int(data.split(":")[2])
                    await self.send_account_management(user_id, account_id, event.message_id)
                    
                elif data.startswith("otp:"):
                    await self._handle_otp_callback(event, user_id, data)
                    
                elif data == "menu:help":
                    await self._send_help_menu(user_id, event.message_id)
                    
                elif data == "menu:dev":
                    await self._toggle_developer_mode(user_id, event.message_id)
                    
                elif data == "menu:support":
                    await self._send_support_menu(user_id, event.message_id)
                    
                elif data.startswith("2fa:"):
                    await self._handle_2fa_callback(event, user_id, data)
                    
                elif data.startswith(("2fa_input:", "2fa_current:", "2fa_remove:", "2fa_new:")):
                    await self.secure_2fa_handlers.handle_secure_2fa_input(event, user_id, data)
                    
                elif data == "menu:profile":
                    await self._send_profile_menu(user_id, event.message_id)
                    
                elif data == "menu:groups":
                    await self._send_groups_menu(user_id, event.message_id)
                    
                elif data == "menu:messaging":
                    await self._send_messaging_menu(user_id, event.message_id)
                    
                elif data == "menu:automation":
                    await self._send_automation_menu(user_id, event.message_id)
                    
                elif data == "menu:analytics":
                    await self._send_analytics_menu(user_id, event.message_id)
                    
                elif data.startswith("profile:"):
                    await self._handle_profile_callback(event, user_id, data)
                    
                elif data.startswith("sessions:"):
                    await self._handle_sessions_callback(event, user_id, data)
                    
                elif data.startswith("online:"):
                    await self._handle_online_callback(event, user_id, data)
                    
                elif data.startswith("automation:"):
                    await self._handle_automation_callback(event, user_id, data)
                    
                elif data == "account:add":
                    await self._handle_add_account(event, user_id)
                    
                elif data.startswith("msg:"):
                    await self._handle_messaging_callback(event, user_id, data)
                    
                elif data.startswith("autoreply:"):
                    await self._handle_autoreply_callback(event, user_id, data)
                    
                elif data.startswith("template:"):
                    await self._handle_template_callback(event, user_id, data)
                
                await event.answer()
                
            except Exception as e:
                logger.error(f"Callback handler error: {e}")
                await event.answer("❌ Error processing request")
    
    async def _handle_otp_callback(self, event, user_id: int, data: str):
        """Handle OTP-related callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = int(parts[2]) if len(parts) > 2 else 0
        
        if action == "toggle":
            # Toggle OTP destroyer for account
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()
                
                if account:
                    account.otp_destroyer_enabled = not account.otp_destroyer_enabled
                    await session.commit()
                    
                    status = "enabled" if account.otp_destroyer_enabled else "disabled"
                    await event.answer(f"🛡️ OTP Destroyer {status}!")
                    await self.send_account_management(user_id, account_id, event.message_id)
                else:
                    await event.answer("❌ Account not found")
        
        elif action == "enable":
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()
                
                if account:
                    account.otp_destroyer_enabled = True
                    await session.commit()
                    await event.answer("🛡️ OTP Destroyer enabled!")
                    await self.send_otp_settings(user_id, account_id, event.message_id)
                else:
                    await event.answer("❌ Account not found")
                
        elif action == "disable":
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()
                
                if account:
                    account.otp_destroyer_enabled = False
                    await session.commit()
                    await event.answer("🔴 OTP Destroyer disabled!")
                    await self.send_otp_settings(user_id, account_id, event.message_id)
                else:
                    await event.answer("❌ Account not found")
            
        elif action == "audit":
            await self.send_audit_log(user_id, account_id)
            
        elif action == "setpass":
            await event.answer("🔒 Set disable password - feature coming soon")
            
        elif action == "security":
            await self._send_security_menu(user_id, account_id, event.message_id)
            
        elif action == "settings":
            await self.send_otp_settings(user_id, account_id, event.message_id)
    
    async def _send_help_menu(self, user_id: int, message_id: int):
        """Send help menu"""
        text = (
            "❓ **Help & Information**\n\n"
            "🛡️ **OTP Destroyer**: Automatically invalidates login codes to prevent unauthorized access\n\n"
            "📱 **Account Management**: Add, remove, and configure your Telegram accounts\n\n"
            "🔐 **Security**: All data is encrypted and stored securely\n\n"
            "⚙️ **Developer Mode**: Access advanced features and text commands"
        )
        buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _toggle_developer_mode(self, user_id: int, message_id: int):
        """Toggle developer mode"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(select(User).where(User.telegram_id == user_id))
                user = result.scalar_one_or_none()
                
                if user:
                    user.developer_mode = not user.developer_mode
                    await session.commit()
                    
                    status = "enabled" if user.developer_mode else "disabled"
                    text = f"⚙️ **Developer Mode**\n\nDeveloper mode {status}.\n\n"
                    
                    if user.developer_mode:
                        text += "You now have access to text commands:\n/add, /remove, /accs, /toggle_protection, etc."
                    else:
                        text += "Text commands are now hidden. Use the menu system."
                    
                    buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
                    await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                    
        except Exception as e:
            logger.error(f"Failed to toggle developer mode: {e}")
    
    async def send_otp_menu(self, user_id: int, edit_message_id: Optional[int] = None):
        """Send OTP management menu"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account, User)
                    .join(User)
                    .where(User.telegram_id == user_id)
                )
                
                accounts = []
                for account, user in result:
                    accounts.append(account)
                
                if not accounts:
                    text = "🛡️ **OTP Settings**\n\nNo accounts found. Add accounts first."
                    buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
                else:
                    text = "🛡️ **OTP Settings**\n\nSelect an account to configure OTP destroyer:"
                    buttons = []
                    
                    for account in accounts:
                        status = "🟢" if account.otp_destroyer_enabled else "🔴"
                        button_text = f"{status} {account.name}"
                        buttons.append([Button.inline(button_text, f"otp:settings:{account.id}")])
                    
                    buttons.append([Button.inline("🔙 Back to Main", "menu:main")])
                
                if edit_message_id:
                    await self.bot.edit_message(user_id, edit_message_id, text, buttons=buttons)
                else:
                    await self.bot.send_message(user_id, text, buttons=buttons)
                    
        except Exception as e:
            logger.error(f"Failed to send OTP menu: {e}")
    
    async def _send_sessions_menu(self, user_id: int, message_id: int):
        """Send sessions management menu"""
        text = (
            "🔐 **Session Management**\n\n"
            "Manage your account sessions and security.\n\n"
            "Features coming soon:"
            "• Export session strings\n"
            "• Import sessions\n"
            "• Session health check"
        )
        buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _send_2fa_menu(self, user_id: int, message_id: int):
        """Send 2FA settings menu"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account, User)
                    .join(User)
                    .where(User.telegram_id == user_id)
                )
                
                accounts = []
                for account, user in result:
                    accounts.append(account)
                
                if not accounts:
                    text = "🔑 **2FA Settings**\n\nNo accounts found. Add accounts first."
                    buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
                else:
                    text = "🔑 **2FA Settings**\n\nSelect an account to manage 2FA:"
                    buttons = []
                    
                    for account in accounts:
                        has_2fa = "🔒" if account.twofa_password else "⚪"
                        button_text = f"{has_2fa} {account.name}"
                        buttons.append([Button.inline(button_text, f"2fa:status:{account.id}")])
                    
                    buttons.append([Button.inline("🔙 Back to Main", "menu:main")])
                
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                    
        except Exception as e:
            logger.error(f"Failed to send 2FA menu: {e}")
    
    async def _send_online_menu(self, user_id: int, message_id: int):
        """Send online maker menu"""
        text = (
            "🟢 **Online Maker**\n\n"
            "Keep your accounts online automatically.\n\n"
            "Features coming soon:"
            "• Auto-online intervals\n"
            "• Custom status messages\n"
            "• Schedule management"
        )
        buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _send_security_menu(self, user_id: int, account_id: int, message_id: int):
        """Send security settings menu"""
        text = (
            "🔒 **Security Settings**\n\n"
            "Advanced security options for OTP destroyer.\n\n"
            "Features coming soon:"
            "• Disable password protection\n"
            "• Audit log retention\n"
            "• Alert preferences"
        )
        buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _send_profile_menu(self, user_id: int, message_id: int):
        """Send profile management menu"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account, User)
                    .join(User)
                    .where(User.telegram_id == user_id)
                )
                
                accounts = []
                for account, user in result:
                    accounts.append(account)
                
                if not accounts:
                    text = "👤 **Profile Manager**\n\nNo accounts found. Add accounts first."
                    buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
                else:
                    text = "👤 **Profile Manager**\n\nSelect an account to manage profile:"
                    buttons = []
                    
                    for account in accounts:
                        username_display = f"@{account.username}" if account.username else "No username"
                        button_text = f"👤 {account.name} ({username_display})"
                        buttons.append([Button.inline(button_text, f"profile:manage:{account.id}")])
                    
                    buttons.append([Button.inline("🔙 Back to Main", "menu:main")])
                
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                    
        except Exception as e:
            logger.error(f"Failed to send profile menu: {e}")
    
    async def _send_groups_menu(self, user_id: int, message_id: int):
        """Send groups and channels menu"""
        text = (
            "👥 **Groups & Channels**\n\n"
            "Manage groups and channels for your accounts.\n\n"
            "Features coming soon:"
            "• Create channels/groups\n"
            "• Manage members and admins\n"
            "• Post and schedule content\n"
            "• Invite link management"
        )
        buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _send_messaging_menu(self, user_id: int, message_id: int):
        """Send messaging menu"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account, User)
                    .join(User)
                    .where(User.telegram_id == user_id)
                )
                
                accounts = []
                for account, user in result:
                    accounts.append(account)
                
                if not accounts:
                    text = "💬 **Messaging**\n\nNo accounts found. Add accounts first to use messaging features."
                    buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
                else:
                    text = "💬 **Messaging**\n\nSelect messaging action:"
                    buttons = [
                        [Button.inline("📤 Send Message", "msg:send")],
                        [Button.inline("🔄 Auto Reply", "msg:autoreply")],
                        [Button.inline("📝 Message Templates", "msg:templates")],
                        [Button.inline("🔙 Back to Main", "menu:main")]
                    ]
                
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                    
        except Exception as e:
            logger.error(f"Failed to send messaging menu: {e}")
    
    async def _send_automation_menu(self, user_id: int, message_id: int):
        """Send automation menu"""
        text = (
            "⚡ **Automation**\n\n"
            "Automate account actions and workflows.\n\n"
            "Available features:"
            "• Online maker (keep accounts online)\n"
            "• Auto-reply rules\n"
            "• Scheduled posts\n"
            "• Auto-join/leave groups"
        )
        buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _send_analytics_menu(self, user_id: int, message_id: int):
        """Send analytics menu"""
        text = (
            "📊 **Analytics**\n\n"
            "View account statistics and activity.\n\n"
            "Features coming soon:"
            "• Account health monitoring\n"
            "• Session activity logs\n"
            "• OTP destroyer statistics\n"
            "• Automation performance"
        )
        buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _send_support_menu(self, user_id: int, message_id: int):
        """Send support menu"""
        text = (
            "🆘 **Support & Contact**\n\n"
            "Need help? Contact our support team:\n\n"
            "👨💻 **Developers:**\n"
            "• @Meher_Mankar\n"
            "• @Gutkesh\n\n"
            "📧 **Email:** https://t.me/ContactXYZrobot\n"
            "🐛 **Bug Reports:** Create an issue on GitHub\n\n"
            "⏰ **Response Time:** Usually within 24 hours\n\n"
            "💬 **Tips:**\n"
            "• Include error messages when reporting bugs\n"
            "• Describe steps to reproduce issues\n"
            "• Check /help for common solutions first"
        )
        buttons = [[Button.inline("🔙 Back to Main", "menu:main")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _handle_2fa_callback(self, event, user_id: int, data: str):
        """Handle 2FA-related callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = int(parts[2]) if len(parts) > 2 else 0
        
        if action == "set":
            # Handle password setting with text input
            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {
                    "action": "set_2fa_password",
                    "account_id": account_id
                }
                
                text = (
                    "🔑 **Set 2FA Password**\n\n"
                    "Reply with your new 2FA password:\n\n"
                    "⚠️ This will set the actual 2FA password on Telegram!\n"
                    "⚠️ Message will be deleted after processing for security."
                )
                
                await event.answer("🔑 Reply with password")
                await self.bot.send_message(user_id, text)
        
        elif action == "change":
            # Handle password change with text input
            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {
                    "action": "change_2fa_current",
                    "account_id": account_id
                }
                
                text = (
                    "🔑 **Change 2FA Password**\n\n"
                    "Reply with your current 2FA password:\n\n"
                    "⚠️ Message will be deleted after processing for security."
                )
                
                await event.answer("🔑 Enter current password")
                await self.bot.send_message(user_id, text)
        
        elif action == "remove":
            # Handle password removal with text input
            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {
                    "action": "remove_2fa_password",
                    "account_id": account_id
                }
                
                text = (
                    "🔑 **Remove 2FA Password**\n\n"
                    "Reply with your current 2FA password to remove it:\n\n"
                    "⚠️ This will disable 2FA protection!\n"
                    "⚠️ Message will be deleted after processing for security."
                )
                
                await event.answer("🔑 Enter password to remove")
                await self.bot.send_message(user_id, text)
        
        elif action == "status":
            # Show 2FA status
            await self.secure_2fa_handlers.show_2fa_status(user_id, account_id, event.message_id)
    
    async def _handle_profile_callback(self, event, user_id: int, data: str):
        """Handle profile-related callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = int(parts[2]) if len(parts) > 2 else 0
        
        if action == "manage":
            await self._send_profile_management(user_id, account_id, event.message_id)
        elif action == "name":
            await self._handle_profile_name_change(user_id, account_id, event)
        elif action == "username":
            await self._handle_profile_username_change(user_id, account_id, event)
        elif action == "bio":
            await self._handle_profile_bio_change(user_id, account_id, event)
        elif action == "photo":
            await self._handle_profile_photo_change(user_id, account_id, event)
    
    async def _handle_sessions_callback(self, event, user_id: int, data: str):
        """Handle sessions-related callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = int(parts[2]) if len(parts) > 2 else 0
        
        if action == "list":
            await self._send_sessions_list(user_id, account_id, event.message_id)
    
    async def _handle_online_callback(self, event, user_id: int, data: str):
        """Handle online maker callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = int(parts[2]) if len(parts) > 2 else 0
        
        if action == "toggle":
            await self._toggle_online_maker(user_id, account_id, event.message_id)
    
    async def _handle_automation_callback(self, event, user_id: int, data: str):
        """Handle automation callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = int(parts[2]) if len(parts) > 2 else 0
        
        if action == "manage":
            await self._send_automation_management(user_id, account_id, event.message_id)
    
    async def _send_profile_management(self, user_id: int, account_id: int, message_id: int):
        """Send profile management options for specific account"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()
                
                if not account:
                    await self.bot.send_message(user_id, "❌ Account not found")
                    return
                
                username_display = f"@{account.username}" if account.username else "Not set"
                name_display = f"{account.profile_first_name or ''} {account.profile_last_name or ''}" or "Not set"
                
                text = (
                    f"👤 **Profile: {account.name}**\n\n"
                    f"📞 Phone: {account.phone}\n"
                    f"👤 Name: {name_display}\n"
                    f"🆔 Username: {username_display}\n"
                    f"📝 Bio: {account.about or 'Not set'}\n\n"
                    f"Select what to update:"
                )
                
                buttons = [
                    [Button.inline("🖼️ Change Photo", f"profile:photo:{account_id}"), Button.inline("👤 Change Name", f"profile:name:{account_id}")],
                    [Button.inline("🆔 Set Username", f"profile:username:{account_id}"), Button.inline("📝 Update Bio", f"profile:bio:{account_id}")],
                    [Button.inline("🔙 Back", "menu:profile")]
                ]
                
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                    
        except Exception as e:
            logger.error(f"Failed to send profile management: {e}")
    
    async def _send_sessions_list(self, user_id: int, account_id: int, message_id: int):
        """Send active sessions list"""
        text = (
            f"🔐 **Active Sessions**\n\n"
            f"Loading session information...\n\n"
            f"This will show all active login sessions for the account."
        )
        buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _toggle_online_maker(self, user_id: int, account_id: int, message_id: int):
        """Toggle online maker for account"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()
                
                if account:
                    account.online_maker_enabled = not account.online_maker_enabled
                    await session.commit()
                    
                    status = "enabled" if account.online_maker_enabled else "disabled"
                    text = f"🟢 **Online Maker {status.title()}**\n\nAccount: {account.name}\nStatus: {status}\nInterval: {account.online_maker_interval}s"
                    buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
                    await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                    
        except Exception as e:
            logger.error(f"Failed to toggle online maker: {e}")
    
    async def _send_automation_management(self, user_id: int, account_id: int, message_id: int):
        """Send automation management for account"""
        text = (
            f"⚡ **Automation Management**\n\n"
            f"Configure automation rules and jobs.\n\n"
            f"Available options:"
            f"• Online maker\n"
            f"• Auto-reply rules\n"
            f"• Scheduled actions"
        )
        buttons = [
            [Button.inline("🟢 Online Maker", f"online:toggle:{account_id}")],
            [Button.inline("🔙 Back", f"account:manage:{account_id}")]
        ]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _handle_profile_name_change(self, user_id: int, account_id: int, event):
        """Handle profile name change request"""
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "change_profile_name",
                "account_id": account_id
            }
            
            text = (
                "👤 **Change Profile Name**\n\n"
                "Reply with your new name (first and last name):\n"
                "Example: John Doe\n\n"
                "Or send just first name: John"
            )
            
            await event.answer("👤 Reply with new name")
            await self.bot.send_message(user_id, text)
    
    async def _handle_profile_username_change(self, user_id: int, account_id: int, event):
        """Handle username change request"""
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "change_username",
                "account_id": account_id
            }
            
            text = (
                "🆔 **Set Username**\n\n"
                "Reply with your new username (without @):\n"
                "Example: johndoe123\n\n"
                "⚠️ Username must be unique and follow Telegram rules"
            )
            
            await event.answer("🆔 Reply with username")
            await self.bot.send_message(user_id, text)
    
    async def _handle_profile_bio_change(self, user_id: int, account_id: int, event):
        """Handle bio change request"""
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "change_bio",
                "account_id": account_id
            }
            
            text = (
                "📝 **Update Bio**\n\n"
                "Reply with your new bio/about text:\n\n"
                "Maximum 70 characters for bio."
            )
            
            await event.answer("📝 Reply with bio text")
            await self.bot.send_message(user_id, text)
    
    async def _handle_profile_photo_change(self, user_id: int, account_id: int, event):
        """Handle profile photo change request"""
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "change_profile_photo",
                "account_id": account_id
            }
            
            text = (
                "🖼️ **Change Profile Photo**\n\n"
                "Send a photo to set as your profile picture.\n\n"
                "The photo will be automatically resized and cropped."
            )
            
            await event.answer("🖼️ Send a photo")
            await self.bot.send_message(user_id, text)
    
    async def _handle_add_account(self, event, user_id: int):
        """Handle add account request"""
        try:
            # Check account limit
            async with get_session() as session:
                from sqlalchemy import select, func
                from config import MAX_ACCOUNTS
                
                result = await session.execute(select(User).where(User.telegram_id == user_id))
                user = result.scalar_one_or_none()
                if not user:
                    await event.answer("❌ Please start the bot first")
                    return
                
                count_result = await session.execute(select(func.count(Account.id)).where(Account.owner_id == user.id))
                account_count = count_result.scalar()
                if account_count >= MAX_ACCOUNTS:
                    await event.answer(f"❌ Maximum account limit ({MAX_ACCOUNTS}) reached")
                    return
            
            if self.account_manager:
                self.account_manager.pending_actions[user_id] = {"action": "add_account"}
                
                text = (
                    "➕ **Add New Account**\n\n"
                    "Reply with the phone number for the new account.\n\n"
                    "Format: +1234567890 (include country code)"
                )
                
                await event.answer("➕ Reply with phone number")
                await self.bot.send_message(user_id, text)
            else:
                await event.answer("❌ Service unavailable")
                
        except Exception as e:
            logger.error(f"Failed to handle add account: {e}")
            await event.answer("❌ Error processing request")
    
    async def _handle_messaging_callback(self, event, user_id: int, data: str):
        """Handle messaging-related callbacks"""
        parts = data.split(":")
        action = parts[1]
        
        if action == "send":
            await self._send_message_menu(user_id, event.message_id)
        elif action == "autoreply":
            await self._send_autoreply_menu(user_id, event.message_id)
        elif action == "templates":
            await self._send_templates_menu(user_id, event.message_id)
        elif action == "account":
            account_id = int(parts[2])
            await self._send_account_messaging(user_id, account_id, event.message_id)
        elif action == "compose":
            account_id = int(parts[2])
            await self._handle_compose_message(user_id, account_id, event)
    
    async def _send_message_menu(self, user_id: int, message_id: int):
        """Send message composition menu"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account, User)
                    .join(User)
                    .where(User.telegram_id == user_id)
                )
                
                accounts = []
                for account, user in result:
                    accounts.append(account)
                
                if not accounts:
                    text = "📤 **Send Message**\n\nNo accounts found. Add accounts first."
                    buttons = [[Button.inline("🔙 Back", "menu:messaging")]]
                else:
                    text = "📤 **Send Message**\n\nSelect account to send from:"
                    buttons = []
                    
                    for account in accounts:
                        status = "🟢" if account.is_active else "🔴"
                        button_text = f"{status} {account.name}"
                        buttons.append([Button.inline(button_text, f"msg:compose:{account.id}")])
                    
                    buttons.append([Button.inline("🔙 Back", "menu:messaging")])
                
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                    
        except Exception as e:
            logger.error(f"Failed to send message menu: {e}")
    
    async def _send_autoreply_menu(self, user_id: int, message_id: int):
        """Send auto-reply management menu"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account, User)
                    .join(User)
                    .where(User.telegram_id == user_id)
                )
                
                accounts = []
                for account, user in result:
                    accounts.append(account)
                
                if not accounts:
                    text = "🔄 **Auto Reply**\n\nNo accounts found. Add accounts first."
                    buttons = [[Button.inline("🔙 Back", "menu:messaging")]]
                else:
                    text = "🔄 **Auto Reply**\n\nSelect account to configure auto-reply:"
                    buttons = []
                    
                    for account in accounts:
                        status = "🟢" if account.is_active else "🔴"
                        auto_status = "🤖" if getattr(account, 'auto_reply_enabled', False) else "⚪"
                        button_text = f"{status}{auto_status} {account.name}"
                        buttons.append([Button.inline(button_text, f"autoreply:manage:{account.id}")])
                    
                    buttons.append([Button.inline("🔙 Back", "menu:messaging")])
                
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                    
        except Exception as e:
            logger.error(f"Failed to send auto-reply menu: {e}")
    
    async def _send_templates_menu(self, user_id: int, message_id: int):
        """Send message templates menu"""
        text = (
            "📝 **Message Templates**\n\n"
            "Create and manage reusable message templates.\n\n"
            "Available actions:"
            "• Create new template\n"
            "• Edit existing templates\n"
            "• Use template in message\n"
            "• Delete templates"
        )
        buttons = [
            [Button.inline("➕ Create Template", "template:create")],
            [Button.inline("📋 View Templates", "template:list")],
            [Button.inline("🔙 Back", "menu:messaging")]
        ]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _handle_compose_message(self, user_id: int, account_id: int, event):
        """Handle message composition request"""
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "compose_message_target",
                "account_id": account_id
            }
            
            text = (
                "📤 **Compose Message**\n\n"
                "Reply with the target (username, phone, or chat ID):\n\n"
                "Examples:\n"
                "• @username\n"
                "• +1234567890\n"
                "• -1001234567890 (for groups/channels)"
            )
            
            await event.answer("📤 Reply with target")
            await self.bot.send_message(user_id, text)
    
    async def _handle_autoreply_callback(self, event, user_id: int, data: str):
        """Handle auto-reply callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = int(parts[2]) if len(parts) > 2 else 0
        
        if action == "manage":
            await self._send_autoreply_management(user_id, account_id, event.message_id)
        elif action == "toggle":
            await self._toggle_autoreply(user_id, account_id, event)
        elif action == "set":
            await self._set_autoreply_message(user_id, account_id, event)
    
    async def _handle_template_callback(self, event, user_id: int, data: str):
        """Handle template callbacks"""
        parts = data.split(":")
        action = parts[1]
        
        if action == "create":
            await self._create_template(user_id, event)
        elif action == "list":
            await self._list_templates(user_id, event.message_id)
        elif action == "use":
            template_id = int(parts[2])
            await self._use_template(user_id, template_id, event)
    
    async def _send_autoreply_management(self, user_id: int, account_id: int, message_id: int):
        """Send auto-reply management for specific account"""
        try:
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id, Account.id == account_id)
                )
                account = result.scalar_one_or_none()
                
                if not account:
                    await self.bot.send_message(user_id, "❌ Account not found")
                    return
                
                auto_enabled = getattr(account, 'auto_reply_enabled', False)
                auto_message = getattr(account, 'auto_reply_message', 'Not set')
                
                text = (
                    f"🔄 **Auto Reply: {account.name}**\n\n"
                    f"Status: {'🟢 Enabled' if auto_enabled else '🔴 Disabled'}\n"
                    f"Message: {auto_message[:50]}{'...' if len(auto_message) > 50 else ''}\n\n"
                    f"Configure auto-reply settings:"
                )
                
                toggle_text = "🔴 Disable" if auto_enabled else "🟢 Enable"
                buttons = [
                    [Button.inline(f"{toggle_text} Auto Reply", f"autoreply:toggle:{account_id}")],
                    [Button.inline("📝 Set Message", f"autoreply:set:{account_id}")],
                    [Button.inline("🔙 Back", "msg:autoreply")]
                ]
                
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
                    
        except Exception as e:
            logger.error(f"Failed to send auto-reply management: {e}")
    
    async def _toggle_autoreply(self, user_id: int, account_id: int, event):
        """Toggle auto-reply for account"""
        await event.answer("🔄 Auto-reply toggled")
        await self._send_autoreply_management(user_id, account_id, event.message_id)
    
    async def _set_autoreply_message(self, user_id: int, account_id: int, event):
        """Set auto-reply message"""
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "set_autoreply_message",
                "account_id": account_id
            }
            
            text = (
                "📝 **Set Auto-Reply Message**\n\n"
                "Reply with the message to send automatically:\n\n"
                "This message will be sent to anyone who messages this account."
            )
            
            await event.answer("📝 Reply with message")
            await self.bot.send_message(user_id, text)
    
    async def _use_template(self, user_id: int, template_id: int, event):
        """Use a template for messaging"""
        try:
            templates = await self.account_manager.messaging_manager.get_templates(user_id)
            template = next((t for t in templates if t[0] == template_id), None)
            
            if template:
                _, name, content = template
                
                if self.account_manager:
                    self.account_manager.pending_actions[user_id] = {
                        "action": "use_template_target",
                        "template_content": content,
                        "template_name": name
                    }
                    
                    text = (
                        f"📝 **Using Template: {name}**\n\n"
                        f"Content: {content[:100]}{'...' if len(content) > 100 else ''}\n\n"
                        f"Reply with the target (username, phone, or chat ID):"
                    )
                    
                    await event.answer(f"📝 Using template: {name}")
                    await self.bot.send_message(user_id, text)
            else:
                await event.answer("❌ Template not found")
                
        except Exception as e:
            logger.error(f"Failed to use template: {e}")
            await event.answer("❌ Error using template")
    
    async def _create_template(self, user_id: int, event):
        """Create message template"""
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "create_template_name"
            }
            
            text = (
                "➕ **Create Template**\n\n"
                "Reply with a name for your template:\n\n"
                "Example: greeting, promotion, support"
            )
            
            await event.answer("➕ Reply with template name")
            await self.bot.send_message(user_id, text)
    
    async def _list_templates(self, user_id: int, message_id: int):
        """List user templates"""
        try:
            templates = await self.account_manager.messaging_manager.get_templates(user_id)
            
            if not templates:
                text = (
                    "📋 **Your Templates**\n\n"
                    "No templates found. Create your first template!\n\n"
                    "Templates allow you to save and reuse messages quickly."
                )
                buttons = [
                    [Button.inline("➕ Create Template", "template:create")],
                    [Button.inline("🔙 Back", "menu:messaging")]
                ]
            else:
                text = f"📋 **Your Templates** ({len(templates)})\n\n"
                buttons = []
                
                for template_id, name, content in templates:
                    preview = content[:30] + "..." if len(content) > 30 else content
                    button_text = f"📝 {name}: {preview}"
                    buttons.append([Button.inline(button_text, f"template:use:{template_id}")])
                
                buttons.append([Button.inline("➕ Create Template", "template:create")])
                buttons.append([Button.inline("🔙 Back", "menu:messaging")])
            
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Failed to list templates: {e}")
            text = "❌ Error loading templates"
            buttons = [[Button.inline("🔙 Back", "menu:messaging")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)