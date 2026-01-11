"""Account operations"""

import logging

from ...core.mongo_database import mongodb
from ...utils.network_helpers import format_display_name, format_phone_number

logger = logging.getLogger(__name__)


class AccountOperations:
    def __init__(self, menu_system):
        self.menu = menu_system
        self.bot = menu_system.bot
        self.account_manager = menu_system.account_manager

    async def send_account_management(self, user_id, account_id, edit_message_id=None):
        from bson import ObjectId

        account = await mongodb.db.accounts.find_one(
            {"_id": ObjectId(account_id), "user_id": user_id}
        )
        if not account:
            await self.bot.send_message(user_id, "❌ Account not found")
            return
        destroyer_status = (
            "🛡️ Enabled"
            if account.get("otp_destroyer_enabled", False)
            else "❌ Disabled"
        )
        simulation_status = (
            "✅ Active" if account.get("simulation_enabled", False) else "❌ Inactive"
        )
        online_maker_status = (
            "✅ Enabled"
            if account.get("online_maker_enabled", False)
            else "❌ Disabled"
        )
        last_destroyed = account.get("otp_destroyed_at", "Never")
        display_name = format_display_name(account)
        text = f"📱 **Account: {display_name}**\n\n📞 Phone: {
            format_phone_number(
                account['phone'])}\n🛡️ OTP Destroyer: {destroyer_status}\n🎭 Activity Sim: {simulation_status}\n🟢 Online Maker: {online_maker_status}\n🕒 Last Destroyed: {last_destroyed}\n\nSelect an action:"
        buttons = self.menu.get_account_menu_buttons(account_id, account)
        if edit_message_id:
            await self.bot.edit_message(user_id, edit_message_id, text, buttons=buttons)
        else:
            await self.bot.send_message(user_id, text, buttons=buttons)

    async def send_otp_account_management(
        self, user_id, account_id, edit_message_id=None
    ):
        from bson import ObjectId

        account = await mongodb.db.accounts.find_one(
            {"_id": ObjectId(account_id), "user_id": user_id}
        )
        if not account:
            await self.bot.send_message(user_id, "❌ Account not found")
            return
        destroyer_status = (
            "🛡️ Active" if account.get("otp_destroyer_enabled", False) else "❌ Inactive"
        )
        forward_status = (
            "🛡️ Active" if account.get("otp_forward_enabled", False) else "❌ Inactive"
        )
        import time

        temp_active = False
        if account.get("otp_temp_passthrough", False):
            expiry = account.get("temp_passthrough_expiry", 0)
            if time.time() < expiry:
                temp_active = True
        if temp_active:
            remaining = int(expiry - time.time())
            minutes = remaining // 60
            seconds = remaining % 60
            temp_status = (
                f"⏰ Active - Forward ON, Destroyer OFF ({minutes}m {seconds}s left)"
            )
        else:
            temp_status = "⚪ Inactive"
        has_password = (
            "🛡️ Set" if account.get("otp_destroyer_disable_auth") else "❌ Not Set"
        )
        display_name = format_display_name(account)
        text = f"🛡️ **OTP Manager: {display_name}**\n\n📞 Phone: {
            format_phone_number(
                account['phone'])}\n\n🛡️ **Destroyer**: {destroyer_status}\n📤 **Forward**: {forward_status}\n⏰ **Temp OTP**: {temp_status}\n🔒 **Password**: {has_password}\n\n🕒 Last Activity: {
            account.get(
                'otp_destroyed_at',
                'Never')}\n\nSelect an action:"
        buttons = self.menu.get_otp_account_buttons(account_id, account)
        if edit_message_id:
            await self.bot.edit_message(user_id, edit_message_id, text, buttons=buttons)
        else:
            await self.bot.send_message(user_id, text, buttons=buttons)
