"""Startup Commands - Automatically executed when bot starts"""

import asyncio
import logging
from ..core.config import ADMIN_IDS
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class StartupCommands:
    """Handle automatic startup commands"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        
    async def execute_startup_commands(self):
        """Execute all startup commands automatically"""
        try:
            logger.info("🚀 Executing startup commands...")
            
            # Get all admin users
            admin_users = await self._get_admin_users()
            
            for admin_id in admin_users:
                try:
                    # Send startup notification
                    await self._send_startup_notification(admin_id)
                    
                    # Auto-enable features if configured
                    await self._auto_enable_features(admin_id)
                    
                    # Send status summary
                    await self._send_status_summary(admin_id)
                    
                except Exception as e:
                    logger.error(f"Startup command failed for admin {admin_id}: {e}")
            
            logger.info("✅ Startup commands completed")
            
        except Exception as e:
            logger.error(f"Startup commands execution failed: {e}")
    
    async def _get_admin_users(self):
        """Get list of admin users who have used the bot"""
        try:
            # Get users from database who have accounts
            users = await mongodb.db.users.find({}).to_list(length=None)
            admin_users = [user["telegram_id"] for user in users if user["telegram_id"] in ADMIN_IDS]
            
            # If no users in DB, use all ADMIN_IDS
            if not admin_users:
                admin_users = ADMIN_IDS
                
            return admin_users
            
        except Exception as e:
            logger.error(f"Failed to get admin users: {e}")
            return ADMIN_IDS
    
    async def _send_startup_notification(self, admin_id: int):
        """Send startup notification to admin"""
        try:
            # Count managed accounts
            account_count = await mongodb.db.accounts.count_documents({"user_id": admin_id, "is_active": True})
            
            startup_text = (
                f"🎆 **TeleGuard Bot Started Successfully!**\n\n"
                f"📱 **Your Accounts:** {account_count} active\n"
                f"🛡️ **OTP Destroyer:** Active\n"
                f"📨 **Unified Messaging:** Ready\n"
                f"🎭 **Activity Simulator:** Running\n"
                f"📤 **Bulk Sender:** Available\n\n"
                f"Type `/help` for commands or use the menu below."
            )
            
            await self.bot.send_message(admin_id, startup_text)
            logger.info(f"Startup notification sent to {admin_id}")
            
        except Exception as e:
            logger.error(f"Failed to send startup notification to {admin_id}: {e}")
    
    async def _auto_enable_features(self, admin_id: int):
        """Auto-enable features based on user preferences"""
        try:
            # Get user preferences
            user = await mongodb.db.users.find_one({"telegram_id": admin_id})
            if not user:
                return
            
            auto_features = user.get("auto_startup_features", {})
            
            # Auto-enable online maker if configured
            if auto_features.get("online_maker", False):
                accounts = await mongodb.db.accounts.find({"user_id": admin_id, "is_active": True}).to_list(length=None)
                for account in accounts:
                    if not account.get("online_maker_enabled", False):
                        await mongodb.db.accounts.update_one(
                            {"_id": account["_id"]},
                            {"$set": {"online_maker_enabled": True}}
                        )
                        await self.bot_manager.online_maker.start_online_maker(admin_id, account["name"])
                
                if accounts:
                    await self.bot.send_message(admin_id, f"🟢 Auto-enabled online maker for {len(accounts)} accounts")
            
            # Auto-enable activity simulator if configured
            if auto_features.get("activity_simulator", False):
                accounts = await mongodb.db.accounts.find({"user_id": admin_id, "is_active": True}).to_list(length=None)
                enabled_count = 0
                for account in accounts:
                    if not account.get("simulation_enabled", False):
                        await mongodb.db.accounts.update_one(
                            {"_id": account["_id"]},
                            {"$set": {"simulation_enabled": True}}
                        )
                        await self.bot_manager.activity_simulator._start_account_simulation(
                            admin_id, account["_id"], account["name"]
                        )
                        enabled_count += 1
                
                if enabled_count > 0:
                    await self.bot.send_message(admin_id, f"🎭 Auto-enabled activity simulator for {enabled_count} accounts")
            
        except Exception as e:
            logger.error(f"Failed to auto-enable features for {admin_id}: {e}")
    
    async def _send_status_summary(self, admin_id: int):
        """Send comprehensive status summary"""
        try:
            # Get account statistics
            total_accounts = await mongodb.db.accounts.count_documents({"user_id": admin_id, "is_active": True})
            otp_enabled = await mongodb.db.accounts.count_documents({"user_id": admin_id, "otp_destroyer_enabled": True})
            online_maker_enabled = await mongodb.db.accounts.count_documents({"user_id": admin_id, "online_maker_enabled": True})
            simulation_enabled = await mongodb.db.accounts.count_documents({"user_id": admin_id, "simulation_enabled": True})
            auto_reply_enabled = await mongodb.db.accounts.count_documents({"user_id": admin_id, "auto_reply_enabled": True})
            
            # Check admin group configuration
            user = await mongodb.db.users.find_one({"telegram_id": admin_id})
            has_admin_group = bool(user and user.get("dm_reply_group_id"))
            
            # Get topic mappings count
            topic_count = 0
            if has_admin_group:
                topic_count = await mongodb.db.topic_mappings.count_documents({"admin_group_id": user["dm_reply_group_id"]})
            
            status_text = (
                f"📊 **System Status Summary**\n\n"
                f"📱 **Accounts:** {total_accounts} total\n"
                f"🛡️ **OTP Protection:** {otp_enabled}/{total_accounts}\n"
                f"🟢 **Online Maker:** {online_maker_enabled}/{total_accounts}\n"
                f"🎭 **Activity Sim:** {simulation_enabled}/{total_accounts}\n"
                f"🤖 **Auto-Reply:** {auto_reply_enabled}/{total_accounts}\n\n"
                f"📨 **DM System:**\n"
                f"• Admin Group: {'✅ Configured' if has_admin_group else '❌ Not set'}\n"
                f"• Active Topics: {topic_count}\n\n"
                f"🚀 **All systems operational!**"
            )
            
            await self.bot.send_message(admin_id, status_text)
            
        except Exception as e:
            logger.error(f"Failed to send status summary to {admin_id}: {e}")
    
    async def set_auto_startup_feature(self, admin_id: int, feature: str, enabled: bool) -> bool:
        """Set auto-startup feature preference"""
        try:
            await mongodb.db.users.update_one(
                {"telegram_id": admin_id},
                {"$set": {f"auto_startup_features.{feature}": enabled}},
                upsert=True
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to set auto startup feature: {e}")
            return False