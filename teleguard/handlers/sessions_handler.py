"""Sessions Handler for managing active Telegram sessions"""

import logging

from telethon import Button

logger = logging.getLogger(__name__)


async def handle_sessions_list(bot, account_manager, user_id: int, account_id: str, message_id: int):
    """Handle sessions list display"""
    try:
        text, buttons = await _build_sessions_response(account_manager, user_id, account_id)
        await _safe_edit_message(bot, user_id, message_id, text, buttons)
    except Exception as e:
        logger.error(f"Sessions error: {e}")
        await _handle_sessions_error(bot, user_id, message_id, account_id)


async def handle_terminate_all(bot, account_manager, user_id: int, account_id: str, message_id: int):
    """Handle terminate all sessions"""
    try:
        text, buttons = await _build_terminate_response(account_manager, user_id, account_id)
        await _safe_edit_message(bot, user_id, message_id, text, buttons)
    except Exception as e:
        logger.error(f"Terminate sessions error: {e}")
        await _handle_terminate_error(bot, user_id, message_id, account_id)


async def _build_sessions_response(account_manager, user_id: int, account_id: str):
    """Build sessions list response"""
    if not hasattr(account_manager, "fullclient_manager"):
        return "🔐 **Active Sessions**\n\nService unavailable.", [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
    
    success, sessions = await account_manager.fullclient_manager.list_active_sessions(user_id, account_id)
    
    if not success or not sessions:
        return "🔐 **Active Sessions**\n\nFailed to load sessions.", [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
    
    text = "🔐 **Active Sessions**\n\n"
    for session in sessions[:8]:
        device = session.get("device", "Unknown")
        platform = session.get("platform", "Unknown")
        country = session.get("country", "Unknown")
        current = "🟢 Current" if session.get("current") else "🔴 Other"
        text += f"{current} {device} ({platform})\n📍 {country}\n\n"
    
    buttons = [
        [Button.inline("🗑️ Terminate All Others", f"sessions:terminate_all:{account_id}")],
        [Button.inline("🔄 Refresh", f"sessions:list:{account_id}")],
        [Button.inline("🔙 Back", f"account:manage:{account_id}")],
    ]
    return text, buttons


async def _build_terminate_response(account_manager, user_id: int, account_id: str):
    """Build terminate sessions response"""
    if not hasattr(account_manager, "fullclient_manager"):
        text = "❌ **Service Unavailable**\n\nSession management not available."
    else:
        success, message = await account_manager.fullclient_manager.terminate_all_sessions(user_id, account_id)
        text = f"🗑️ **Sessions Terminated**\n\n{message}" if success else f"❌ **Failed to Terminate**\n\n{message}"
    
    buttons = [
        [Button.inline("🔄 Refresh Sessions", f"sessions:list:{account_id}")],
        [Button.inline("🔙 Back", f"account:manage:{account_id}")],
    ]
    return text, buttons


async def _safe_edit_message(bot, user_id: int, message_id: int, text: str, buttons):
    """Safely edit message, ignoring 'not modified' errors"""
    try:
        await bot.edit_message(user_id, message_id, text, buttons=buttons)
    except Exception as e:
        if "not modified" not in str(e).lower():
            raise


async def _handle_sessions_error(bot, user_id: int, message_id: int, account_id: str):
    """Handle sessions list error"""
    text = "❌ Error loading sessions"
    buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
    await bot.edit_message(user_id, message_id, text, buttons=buttons)


async def _handle_terminate_error(bot, user_id: int, message_id: int, account_id: str):
    """Handle terminate sessions error"""
    text = "❌ Error terminating sessions"
    buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
    await bot.edit_message(user_id, message_id, text, buttons=buttons)
