"""
Device Snooping Handler for TeleGuard

Handles UI and logic for device monitoring, history, and session termination.
"""

import logging
from telethon import Button, events
from ..core.device_snooper import DeviceSnooper
from ..core.mongo_database import mongodb
from ..utils.network_helpers import format_display_name

logger = logging.getLogger(__name__)

class DeviceHandler:
    def __init__(self, db, bot_manager):
        self.db = db
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.snooper = DeviceSnooper(db)
        self.user_clients = bot_manager.user_clients

    async def device_menu(self, event):
        """Shows the main device snooper menu."""
        user_id = event.sender_id
        accounts = await mongodb.db.accounts.find({"user_id": user_id, "is_active": True}).to_list(length=None)
        
        if not accounts:
            text = "🕵️ **Device Snooper**\n\nNo active accounts found. Add accounts first to monitor device information."
            buttons = [
                [Button.inline("➕ Add Account", "account:add")],
                [Button.inline("🔙 Back to Main Menu", "menu:main")],
            ]
        else:
            text = (
                "🕵️ **Device Snooper**\n\n"
                "Monitor and track device information from your Telegram sessions:\n\n"
                "🔍 **Scan Devices** - Get current device info\n"
                "📱 **Device History** - View stored device data\n"
                "⚠️ **Suspicious Devices** - Detect potential threats\n"
                "🔒 **Terminate Sessions** - End suspicious sessions\n\n"
                f"📊 **Status:** {len(accounts)} accounts available for monitoring"
            )
            
            buttons = [
                [Button.inline("🔍 Scan Devices", "device:scan")],
                [Button.inline("📱 Device History", "device:history")],
                [Button.inline("⚠️ Suspicious Devices", "device:suspicious")],
                [Button.inline("🔒 Terminate Sessions", "device:terminate")],
                [Button.inline("🔙 Back to Main Menu", "menu:main")]
            ]
        
        if hasattr(event, 'edit'):
            await event.edit(text, buttons=buttons)
        else:
            await event.reply(text, buttons=buttons)

    async def _select_account(self, event, action: str):
        """Helper to show account selection menu."""
        user_id = event.sender_id
        accounts = await mongodb.db.accounts.find({"user_id": user_id, "is_active": True}).to_list(length=None)

        if not accounts:
            await event.edit("No active accounts found.", buttons=[[Button.inline("🔙 Back", "device:menu")]])
            return

        buttons = []
        for acc in accounts:
            display_name = format_display_name(acc)
            buttons.append([Button.inline(f"📱 {display_name}", f"device:{action}_account:{acc['_id']}")])
        
        buttons.append([Button.inline("🔙 Back", "device:menu")])
        
        action_title = action.replace("_", " ").title()
        await event.edit(f"🕵️ **{action_title}**\n\nSelect an account:", buttons=buttons)

    async def scan_devices(self, event, account_id=None):
        """Scan active devices for an account."""
        user_id = event.sender_id
        if not account_id:
            await self._select_account(event, "scan")
            return

        await event.edit("🔍 Scanning for devices... please wait.")
        
        from bson import ObjectId
        account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
        if not account:
            await event.edit("❌ Account not found.")
            return

        client = self._get_client_for_account(user_id, account)
        if not client:
            await event.edit("❌ Account not connected.")
            return

        result = await self.snooper.snoop_device_info(client, user_id)
        
        if 'error' in result:
            await event.edit(f"❌ Error scanning devices: {result['error']}")
            return

        text = f"🔍 **Active Devices for {format_display_name(account)}** ({result['count']} found)\n\n"
        if not result['devices']:
            text += "No active devices found."
        else:
            for dev in result['devices']:
                device_emoji = self._get_device_emoji(dev.get('device_type', 'Unknown'))
                current_marker = " (Current)" if dev.get('current') else ""
                text += f"{device_emoji} **{dev.get('device_model', 'Unknown')}**{current_marker}\n"
                text += f"   OS: {dev.get('os_name', 'N/A')} {dev.get('os_version', 'N/A')}\n"
                text += f"   App: {dev.get('app_name', 'N/A')} {dev.get('app_version', 'N/A')}\n"
                text += f"   IP: {dev.get('ip', 'N/A')} ({dev.get('country', 'N/A')})\n"
                if dev.get('date_active'):
                    text += f"   Last Active: {dev['date_active'].strftime('%Y-%m-%d %H:%M')}\n\n"
                else:
                    text += "\n"

        buttons = [
            [Button.inline("🔄 Refresh", f"device:scan_account:{account_id}")],
            [Button.inline("🔙 Back", "device:scan")]
        ]
        await event.edit(text, buttons=buttons)

    async def show_device_history(self, event, account_id=None):
        """Show device history for an account."""
        user_id = event.sender_id
        if not account_id:
            await self._select_account(event, "history")
            return

        await event.edit("📚 Loading device history... please wait.")
        
        from bson import ObjectId
        account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
        if not account:
            await event.edit("❌ Account not found.")
            return

        result = await self.snooper.get_device_history(user_id)
        
        if 'error' in result:
            await event.edit(f"❌ Error loading history: {result['error']}")
            return

        text = f"📚 **Device History for {format_display_name(account)}** ({result['count']} found)\n\n"
        if not result['devices']:
            text += "No device history found."
        else:
            for dev in result['devices']:
                device_emoji = self._get_device_emoji(dev.get('device_type', 'Unknown'))
                text += f"{device_emoji} **{dev.get('device_model', 'Unknown')}**\n"
                text += f"   OS: {dev.get('os_name', 'N/A')} {dev.get('os_version', 'N/A')}\n"
                if dev.get('date_active'):
                    text += f"   Last Active: {dev['date_active'].strftime('%Y-%m-%d %H:%M')}\n\n"
                else:
                    text += "\n"

        buttons = [
            [Button.inline("🔄 Refresh", f"device:history_account:{account_id}")],
            [Button.inline("🔙 Back", "device:history")]
        ]
        await event.edit(text, buttons=buttons)

    async def show_suspicious_devices(self, event, account_id=None):
        """Show suspicious devices for an account."""
        user_id = event.sender_id
        if not account_id:
            await self._select_account(event, "suspicious")
            return

        await event.edit("⚠️ Detecting suspicious devices... please wait.")
        
        from bson import ObjectId
        account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
        if not account:
            await event.edit("❌ Account not found.")
            return

        suspicious_devices = await self.snooper.detect_suspicious_devices(user_id)
        
        text = f"⚠️ **Suspicious Devices for {format_display_name(account)}** ({len(suspicious_devices)} found)\n\n"
        if not suspicious_devices:
            text += "✅ No suspicious devices detected."
        else:
            for item in suspicious_devices:
                dev = item['device']
                reasons = ", ".join(item['reasons'])
                device_emoji = self._get_device_emoji(dev.get('device_type', 'Unknown'))
                text += f"{device_emoji} **{dev.get('device_model', 'Unknown')}**\n"
                text += f"   Reasons: {reasons}\n\n"

        buttons = [
            [Button.inline("🔄 Refresh", f"device:suspicious_account:{account_id}")],
            [Button.inline("🔙 Back", "device:suspicious")]
        ]
        await event.edit(text, buttons=buttons)

    def _get_client_for_account(self, user_id, account):
        """Helper to get a connected client for an account."""
        account_name = account.get('name') or account.get('phone')
        client = self.user_clients.get(user_id, {}).get(account_name)
        if client and client.is_connected():
            return client
        return None

    def _get_device_emoji(self, device_type: str) -> str:
        """Get an emoji for a device type."""
        emoji_map = {
            'Mobile': '📱',
            'Tablet': '📲',
            'Laptop': '💻',
            'Desktop': '🖥️',
            'Web': '🌐',
            'Computer': '🖱️',
            'Unknown': '❓'
        }
        return emoji_map.get(device_type, '❓')

def register_handlers(bot, db, bot_manager):
    """Register device snooping handlers."""
    handler = DeviceHandler(db, bot_manager)

    @bot.on(events.CallbackQuery(pattern=b"device:"))
    async def device_callback_handler(event):
        user_id = event.sender_id
        data = event.data.decode('utf-8')
        parts = data.split(':')
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else None

        if action == "menu":
            await handler.device_menu(event)
        elif action == "scan":
            await handler.scan_devices(event)
        elif action == "scan_account":
            await handler.scan_devices(event, account_id)
        elif action == "history":
            await handler.show_device_history(event)
        elif action == "history_account":
            await handler.show_device_history(event, account_id)
        elif action == "suspicious":
            await handler.show_suspicious_devices(event)
        elif action == "suspicious_account":
            await handler.show_suspicious_devices(event, account_id)
        # Add terminate logic here if needed
        else:
            await event.answer("Unknown action")