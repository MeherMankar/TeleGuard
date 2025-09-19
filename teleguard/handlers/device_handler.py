"""
Device Snooping Handler for TeleGuard
Handles device monitoring commands and notifications
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from ..core.device_snooper import DeviceSnooper
from ..utils.database import Database

from ..core.account_manager import AccountManager

logger = logging.getLogger(__name__)

class DeviceHandler:
    def __init__(self, db: Database, account_manager: AccountManager):
        self.db = db
        self.account_manager = account_manager
        self.device_snooper = DeviceSnooper(db)
    
    async def device_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show device snooping menu"""
        keyboard = [
            [InlineKeyboardButton("🔍 Scan Devices", callback_data="device_scan")],
            [InlineKeyboardButton("📱 Device History", callback_data="device_history")],
            [InlineKeyboardButton("⚠️ Suspicious Devices", callback_data="device_suspicious")],
            [InlineKeyboardButton("🔒 Terminate Sessions", callback_data="device_terminate")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        
        text = "🕵️ **Device Snooping**\n\n" \
               "Monitor and track device information from your Telegram sessions:\n\n" \
               "🔍 **Scan Devices** - Get current device info\n" \
               "📱 **Device History** - View stored device data\n" \
               "⚠️ **Suspicious Devices** - Detect potential threats\n" \
               "🔒 **Terminate Sessions** - End suspicious sessions"
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def scan_devices(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Scan devices for all user accounts"""
        user_id = update.effective_user.id
        await update.callback_query.answer("Scanning devices...")
        
        try:
            accounts = await self.account_manager.get_user_accounts(user_id)
            if not accounts:
                await update.callback_query.edit_message_text("❌ No accounts found. Add accounts first.")
                return
            
            total_devices = 0
            results = []
            
            for account in accounts:
                client = await self.account_manager.get_client(user_id, account['phone'])
                if client:
                    device_info = await self.device_snooper.snoop_device_info(client, user_id)
                    total_devices += device_info.get('count', 0)
                    results.append(f"📱 {account['phone']}: {device_info.get('count', 0)} devices")
            
            text = f"🔍 **Device Scan Complete**\n\n" \
                   f"📊 **Total Devices Found**: {total_devices}\n\n" + \
                   "\n".join(results)
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="device_menu")]]
            await update.callback_query.edit_message_text(
                text, 
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Device scan failed: {e}")
            await update.callback_query.edit_message_text(f"❌ Scan failed: {str(e)}")
    
    async def show_device_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show device history"""
        user_id = update.effective_user.id
        
        try:
            history = await self.device_snooper.get_device_history(user_id)
            devices = history.get('devices', [])
            
            if not devices:
                text = "📱 **Device History**\n\n❌ No device data found."
            else:
                text = f"📱 **Device History**\n\n📊 **Total Devices**: {len(devices)}\n\n"
                
                for i, device in enumerate(devices[:5]):  # Show first 5
                    device_emoji = self._get_device_emoji(device.get('device_type', 'Unknown'))
                    text += f"**Device {i+1}:**\n" \
                           f"{device_emoji} {device.get('device_type', 'Unknown')}: {device.get('device_model', 'Unknown')}\n" \
                           f"💻 OS: {device.get('os_name', 'Unknown')} {device.get('os_version', '')}\n" \
                           f"🏗️ Arch: {device.get('os_architecture', 'Unknown')}\n" \
                           f"🌍 Location: {device.get('country', 'Unknown')}\n" \
                           f"📅 Last Active: {device.get('date_active', 'Unknown')}\n\n"
                
                if len(devices) > 5:
                    text += f"... and {len(devices) - 5} more devices"
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="device_menu")]]
            await update.callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Device history failed: {e}")
            await update.callback_query.edit_message_text(f"❌ Failed to load history: {str(e)}")
    
    async def show_suspicious_devices(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show suspicious devices"""
        user_id = update.effective_user.id
        
        try:
            suspicious = await self.device_snooper.detect_suspicious_devices(user_id)
            
            if not suspicious:
                text = "⚠️ **Suspicious Devices**\n\n✅ No suspicious devices detected."
            else:
                text = f"⚠️ **Suspicious Devices**\n\n🚨 **Found {len(suspicious)} suspicious devices:**\n\n"
                
                for i, item in enumerate(suspicious[:3]):  # Show first 3
                    device = item['device']
                    reasons = item['reasons']
                    
                    device_emoji = self._get_device_emoji(device.get('device_type', 'Unknown'))
                    text += f"**Device {i+1}:**\n" \
                           f"{device_emoji} {device.get('device_type', 'Unknown')}: {device.get('device_model', 'Unknown')}\n" \
                           f"💻 {device.get('os_name', 'Unknown')} {device.get('os_version', '')}\n" \
                           f"🌍 {device.get('country', 'Unknown')}\n" \
                           f"⚠️ Reasons: {', '.join(reasons)}\n\n"
            
            keyboard = [
                [InlineKeyboardButton("🔒 Terminate Suspicious", callback_data="device_terminate")],
                [InlineKeyboardButton("🔙 Back", callback_data="device_menu")]
            ]
            
            await update.callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Suspicious device check failed: {e}")
            await update.callback_query.edit_message_text(f"❌ Check failed: {str(e)}")
    
    async def terminate_sessions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Terminate suspicious sessions"""
        user_id = update.effective_user.id
        await update.callback_query.answer("Terminating suspicious sessions...")
        
        try:
            accounts = await self.account_manager.get_user_accounts(user_id)
            total_terminated = 0
            
            for account in accounts:
                client = await self.account_manager.get_client(user_id, account['phone'])
                if client:
                    result = await self.device_snooper.terminate_suspicious_sessions(client, user_id)
                    total_terminated += result.get('terminated_count', 0)
            
            text = f"🔒 **Session Termination Complete**\n\n" \
                   f"✅ Terminated {total_terminated} suspicious sessions"
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="device_menu")]]
            await update.callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Session termination failed: {e}")
            await update.callback_query.edit_message_text(f"❌ Termination failed: {str(e)}")
    
    def _get_device_emoji(self, device_type: str) -> str:
        """Get emoji for device type"""
        emoji_map = {
            'Mobile': '📱',
            'Tablet': '📱',
            'Laptop': '💻',
            'Desktop': '🖥️',
            'Web': '🌐',
            'Computer': '💻',
            'Unknown': '❓'
        }
        return emoji_map.get(device_type, '❓')

def register_handlers(application, db: Database, account_manager: AccountManager):
    """Register device snooping handlers"""
    handler = DeviceHandler(db, account_manager)
    
    application.add_handler(CallbackQueryHandler(handler.device_menu, pattern="^device_menu$"))
    application.add_handler(CallbackQueryHandler(handler.scan_devices, pattern="^device_scan$"))
    application.add_handler(CallbackQueryHandler(handler.show_device_history, pattern="^device_history$"))
    application.add_handler(CallbackQueryHandler(handler.show_suspicious_devices, pattern="^device_suspicious$"))
    application.add_handler(CallbackQueryHandler(handler.terminate_sessions, pattern="^device_terminate$"))