"""OTP Command Handlers for managing OTP forwarding and destroying"""

import logging

from telethon import events

from ..core.database import get_session
from ..core.models import Account, User

logger = logging.getLogger(__name__)


class OTPCommandHandlers:
    """Handles OTP-related commands"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot

    def register_handlers(self):
        """Register OTP command handlers"""

        @self.bot.on(events.NewMessage(pattern=r"/otpdestroyer\s+(on|off)"))
        async def otpdestroyer_handler(event):
            user_id = event.sender_id
            state = event.pattern_match.group(1).lower()
            enabled = state == "on"

            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id)
                    .limit(1)
                )
                account = result.scalar_one_or_none()

                if not account:
                    await event.reply("❌ No accounts found. Add an account first.")
                    return

                if hasattr(self.bot_manager, "otp_manager"):
                    (
                        success,
                        message,
                    ) = await self.bot_manager.otp_manager.set_destroyer_state(
                        user_id, account.name, enabled
                    )
                    await event.reply(f"🛡️ {message}")
                else:
                    await event.reply("❌ OTP Manager not available")

        @self.bot.on(events.NewMessage(pattern=r"/otpforward\s+(on|off)"))
        async def otpforward_handler(event):
            user_id = event.sender_id
            state = event.pattern_match.group(1).lower()
            enabled = state == "on"

            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id)
                    .limit(1)
                )
                account = result.scalar_one_or_none()

                if not account:
                    await event.reply("❌ No accounts found. Add an account first.")
                    return

                if hasattr(self.bot_manager, "otp_manager"):
                    (
                        success,
                        message,
                    ) = await self.bot_manager.otp_manager.set_forwarding_state(
                        user_id, account.name, enabled
                    )
                    await event.reply(f"📨 {message}")
                else:
                    await event.reply("❌ OTP Manager not available")

        @self.bot.on(events.NewMessage(pattern=r"/otptemp"))
        async def otptemp_handler(event):
            user_id = event.sender_id

            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account)
                    .join(User)
                    .where(User.telegram_id == user_id)
                    .limit(1)
                )
                account = result.scalar_one_or_none()

                if not account:
                    await event.reply("❌ No accounts found. Add an account first.")
                    return

                if hasattr(self.bot_manager, "otp_manager"):
                    success = (
                        await self.bot_manager.otp_manager.enable_temp_passthrough(
                            user_id, account.name
                        )
                    )

                    if success:
                        await event.reply(
                            "⏰ **OTP Passthrough Active**\n\n"
                            "Duration: 5 minutes\n"
                            "Status: OTPs will be forwarded but not deleted\n\n"
                            "Request your login code now!"
                        )
                    else:
                        await event.reply("❌ Failed to enable temporary passthrough")
                else:
                    await event.reply("❌ OTP Manager not available")
