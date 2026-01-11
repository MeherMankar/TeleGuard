"""OTP management callbacks"""

from .base_callback import BaseCallback


class OTPCallbacks(BaseCallback):
    async def handle_otp_callback(self, event, user_id, data):
        """Delegate to menu_system"""
        await self.menu_system._handle_otp_callback(event, user_id, data)

    async def handle_otp_setting(self, event, user_id, data):
        """Delegate to menu_system"""
        await self.menu_system._handle_otp_setting_callback(event, user_id, data)
