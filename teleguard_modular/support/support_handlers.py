"""Menu system - help module"""
import json
import logging
from typing import List, Optional
from telethon import Button, events
from ..core.config import ADMIN_IDS
from ..core.mongo_database import mongodb
from .secure_2fa_handlers import Secure2FAHandlers
from ..utils.network_helpers import format_display_name, format_phone_number


    async def _handle_help(self, event):
        """Handle Help menu"""
        user_id = event.sender_id
        
        # Delete previous messages to avoid collision
        await self._cleanup_old_messages(user_id)
        
        user = await mongodb.db.users.find_one({"telegram_id": user_id})
        
        # Get user stats for personalized help
        account_count = await mongodb.db.accounts.count_documents({"user_id": user_id})
        otp_enabled = await mongodb.db.accounts.count_documents({"user_id": user_id, "otp_destroyer_enabled": True})
        
        security_score = int((otp_enabled/max(account_count, 1))*100) if account_count > 0 else 0
        status_emoji = "🟢" if security_score >= 80 else "🟡" if security_score >= 50 else "🔴"
        
        text = (
            "❓ **TeleGuard Help & Support Center**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 **Your Dashboard:**\n"
            f"• 📱 **Accounts:** {account_count} configured\n"
            f"• 🛡️ **Protection:** {otp_enabled}/{account_count} secured\n"
            f"• {status_emoji} **Security Score:** {security_score}%\n\n"
            "🚀 **Quick Setup (2 minutes):**\n"
            "1️⃣ **Add Account** → `📱 Account Settings` → `Add Account`\n"
            "2️⃣ **Enable Security** → `🛡️ OTP Manager` → `Enable Destroyer`\n"
            "3️⃣ **Configure Features** → Explore messaging & automation\n\n"
            "🎯 **Feature Overview:**\n"
            "• 🛡️ **Security** - OTP protection, 2FA, session monitoring\n"
            "• 💬 **Messaging** - Auto-reply, templates, bulk sending\n"
            "• 📱 **Management** - Profile updates, channel tools\n"
            "• 📊 **Analytics** - Activity logs, performance insights\n\n"
            "💡 **Pro Tips:**\n"
            "• Enable OTP Destroyer on all accounts for maximum security\n"
            "• Use DM Reply for centralized message management\n"
            "• Monitor audit logs weekly for security insights"
        )
        buttons = [
            [
                Button.inline("📖 Complete Guide", "help:guide"),
                Button.inline("🛡️ Security Guide", "help:security"),
            ],
            [
                Button.inline("⚙️ Feature Guide", "help:features"),
                Button.inline("🔧 Troubleshooting", "help:troubleshoot"),
            ],
            [
                Button.inline("❓ FAQ", "help:faq"),
                Button.inline("📞 Contact Support", "help:contact"),
            ],
            [
                Button.inline("🆘 Emergency Help", "help:emergency"),
                Button.inline("📚 Commands", "help:commands"),
            ],
            [
                Button.inline("📨 Chat Import", "menu:import"),
            ],
        ]
        from ..core.config import ADMIN_IDS
        if user and user_id in ADMIN_IDS:
            dev_mode = user.get("developer_mode", False)
            dev_text = "🔴 Disable Dev Mode" if dev_mode else "⚙️ Enable Dev Mode"
            buttons.append([Button.inline(dev_text, "help:toggle_dev")])
        buttons.append([Button.inline("🔙 Back to Main Menu", "menu:main")])
        if hasattr(event, 'message_id'):
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
        else:
            await self.bot.send_message(user_id, text, buttons=buttons)
    async def _handle_support(self, event):
        """Handle Support menu"""
        # Delete previous messages to avoid collision
        await self._cleanup_old_messages(event.sender_id)
        
        text = (
            "🆘 **TeleGuard Support Center**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👨💻 **Development Team:**\n"
            "• **@Meher_Mankar** - Lead Developer & Founder\n"
            "• **@Gutkesh** - Core Developer & Security Expert\n\n"
            "🎯 **Get Instant Help:**\n"
            "• 💬 **Live Support:** @ContactXYZrobot\n"
            "• 🐛 **Bug Reports:** GitHub Issues Portal\n"
            "• 📚 **Documentation:** Complete Wiki Guide\n"
            "• ⚡ **Response Time:** < 6 hours (usually faster)\n\n"
            "🔧 **Self-Help Checklist:**\n"
            "✅ Check Help section for instant solutions\n"
            "✅ Try `/start` to refresh the bot\n"
            "✅ Verify accounts are properly connected\n"
            "✅ Review troubleshooting guide first\n\n"
            "🚨 **Emergency Support:** Contact developers directly for critical issues"
        )
        buttons = [
            [
                Button.inline("💬 Contact Support", "support:contact"),
                Button.inline("🐛 Report Bug", "support:bug"),
            ],
            [
                Button.inline("📚 Documentation", "support:docs"),
                Button.inline("💡 Feature Request", "support:feature"),
            ],
            [
                Button.inline("📊 System Status", "support:status"),
                Button.inline("🔄 Updates", "support:updates"),
            ],
            [
                Button.inline("🔙 Back to Main Menu", "menu:main"),
            ],
        ]
        if hasattr(event, 'message_id'):
            await self.bot.edit_message(event.sender_id, event.message_id, text, buttons=buttons)
        else:
            await self.bot.send_message(event.sender_id, text, buttons=buttons)
    async def _get_account_age_info(self, user_id: int, account_name: str, account_data: dict = None) -> str:
        """Get account age information using ID-based estimation"""
        try:
            from ..utils.account_age_estimator import AccountAgeEstimator
            from datetime import timezone, datetime
            
            # Skip invalid cached data
            cached_age = account_data.get('age_days') if account_data else None
            if cached_age and cached_age > 0:
                years = cached_age // 365
                months = (cached_age % 365) // 30
                days = (cached_age % 365) % 30
                return f"Age: {years}y {months}m {days}d ({cached_age} days)"
            
            # Get Telegram user ID
            telegram_user_id = account_data.get('telegram_user_id') if account_data else None
            if not telegram_user_id:
                telegram_user_id = await self._get_telegram_user_id(user_id, account_name)
            
            if telegram_user_id:
                telegram_user_id = int(telegram_user_id)
                creation_date, method = await AccountAgeEstimator.estimate_creation_date(telegram_user_id)
                
                if creation_date:
                    now = datetime.now(timezone.utc)
                    if creation_date.tzinfo is None:
                        creation_date = creation_date.replace(tzinfo=timezone.utc)
                    age_days = max(0, (now - creation_date).days)
                    
                    await self._update_account_age_cache(user_id, account_name, creation_date, age_days, telegram_user_id)
                    
                    years = age_days // 365
                    months = (age_days % 365) // 30
                    days = (age_days % 365) % 30
                    return f"Age: {years}y {months}m {days}d ({age_days} days)"
            
            return "Age: Unknown"
        except Exception as e:
            logger.error(f"Error getting account age for {account_name}: {e}")
            return "Age: Unknown"
    
    async def _get_telegram_user_id(self, user_id: int, account_name: str) -> Optional[int]:
        """Get Telegram user ID from connected client"""
        try:
            if hasattr(self.account_manager, 'user_clients') and user_id in self.account_manager.user_clients:
                user_clients = self.account_manager.user_clients[user_id]
                
                # Try all possible client keys
                for key in [account_name] + list(user_clients.keys()):
                    client = user_clients.get(key)
                    if client:
                        try:
                            if not client.is_connected():
                                await client.connect()
                            me = await client.get_me()
                            if me:
                                return me.id
                        except:
                            continue
            return None
        except Exception:
            return None
    
    async def _update_account_age_cache(self, user_id: int, account_name: str, creation_date, age_days: int, telegram_user_id: int):
        """Update account age cache in database"""
        try:
            from datetime import datetime, timezone
            
            update_data = {
                'creation_date': creation_date,
                'age_days': age_days,
                'telegram_user_id': telegram_user_id,
                'last_age_update': datetime.now(timezone.utc)
            }
            
            await mongodb.db.accounts.update_one(
                {'user_id': user_id, 'name': account_name},
                {'$set': update_data}
            )
        except Exception as e:
            logger.debug(f"Error updating age cache for {account_name}: {e}")
    
    async def _update_single_account_age(self, user_id: int, account: dict):
        """Update age for a single account"""
        try:
            from ..utils.account_age_estimator import AccountAgeEstimator
            from datetime import datetime, timezone
            
            account_name = account.get('name')
            phone = account.get('phone')
            
            if not account_name:
                return
            
            # Try to get client
            client = None
            if hasattr(self.account_manager, 'user_clients') and user_id in self.account_manager.user_clients:
                user_clients = self.account_manager.user_clients[user_id]
                client = user_clients.get(account_name) or user_clients.get(phone)
            
            if client and hasattr(client, 'is_connected') and client.is_connected():
                me = await client.get_me()
                telegram_user_id = int(me.id)
                
                creation_date, method = await AccountAgeEstimator.estimate_creation_date(telegram_user_id)
                
                if creation_date:
                    now = datetime.now(timezone.utc)
                    if creation_date.tzinfo is None:
                        creation_date = creation_date.replace(tzinfo=timezone.utc)
                    age_days = max(0, (now - creation_date).days)
                    
                    await mongodb.db.accounts.update_one(
                        {'_id': account['_id']},
                        {'$set': {
                            'creation_date': creation_date,
                            'age_days': age_days,
                            'telegram_user_id': telegram_user_id,
                            'last_age_update': datetime.now(timezone.utc)
                        }}
                    )
        except Exception as e:
            logger.debug(f"Error updating age for {account.get('name')}: {e}")
    



