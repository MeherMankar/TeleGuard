"""Sessions Handler for managing active Telegram sessions"""

import logging

from telethon import Button

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


async def handle_sessions_list(
    bot, account_manager, user_id: int, account_id: str, message_id: int
):
    """Handle sessions list display"""
    try:
        if hasattr(account_manager, "fullclient_manager"):
            (
                success,
                sessions,
            ) = await account_manager.fullclient_manager.list_active_sessions(
                user_id, account_id
            )

            if success and sessions:
                text = f"🔐 **Active Sessions**\n\n"

                for session in sessions[:8]:
                    device = session.get("device", "Unknown")
                    platform = session.get("platform", "Unknown")
                    country = session.get("country", "Unknown")
                    current = "🟢 Current" if session.get("current") else "🔴 Other"

                    text += f"{current} {device} ({platform})\n"
                    text += f"📍 {country}\n\n"

                buttons = [
                    [
                        Button.inline(
                            "🗑️ Terminate All Others",
                            f"sessions:terminate_all:{account_id}",
                        )
                    ],
                    [Button.inline("🔄 Refresh", f"sessions:list:{account_id}")],
                    [Button.inline("🔙 Back", f"account:manage:{account_id}")],
                ]
            else:
                text = "🔐 **Active Sessions**\n\nFailed to load sessions."
                buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
        else:
            text = "🔐 **Active Sessions**\n\nService unavailable."
            buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]

        try:
            await bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            if "not modified" in str(e).lower():
                pass
            else:
                raise e

    except Exception as e:
        logger.error(f"Sessions error: {e}")
        text = "❌ Error loading sessions"
        buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
        await bot.edit_message(user_id, message_id, text, buttons=buttons)


async def handle_terminate_all(
    bot, account_manager, user_id: int, account_id: str, message_id: int
):
    """Handle terminate all sessions"""
    try:
        if hasattr(account_manager, "fullclient_manager"):
            (
                success,
                message,
            ) = await account_manager.fullclient_manager.terminate_all_sessions(
                user_id, account_id
            )

            if success:
                text = f"🗑️ **Sessions Terminated**\n\n{message}"
            else:
                text = f"❌ **Failed to Terminate**\n\n{message}"
        else:
            text = "❌ **Service Unavailable**\n\nSession management not available."

        buttons = [
            [Button.inline("🔄 Refresh Sessions", f"sessions:list:{account_id}")],
            [Button.inline("🔙 Back", f"account:manage:{account_id}")],
        ]

        try:
            await bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            if "not modified" in str(e).lower():
                pass
            else:
                raise e

    except Exception as e:
        logger.error(f"Terminate sessions error: {e}")
        text = "❌ Error terminating sessions"
        buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
        await bot.edit_message(user_id, message_id, text, buttons=buttons)
