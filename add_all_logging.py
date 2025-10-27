"""
Script to add comprehensive logging to all user actions.
Run this to add BotLogger calls throughout the codebase.
"""

# This file documents all the places where logging needs to be added:

LOGGING_LOCATIONS = {
    "sessions_handler.py": [
        "After session termination - log_session_terminated()",
    ],
    "online_maker.py": [
        "After enabling online maker - log_online_maker_toggled(enabled=True)",
        "After disabling online maker - log_online_maker_toggled(enabled=False)",
    ],
    "auto_reply_handler.py": [
        "After enabling auto-reply - log_auto_reply_toggled(enabled=True)",
        "After disabling auto-reply - log_auto_reply_toggled(enabled=False)",
    ],
    "channel_manager.py": [
        "After successful channel join - log_channel_joined()",
        "After successful channel leave - log_channel_left()",
    ],
    "command_handlers.py": [
        "After contacts export - log_contacts_exported(count=len(contacts))",
    ],
    "twofa_manager.py": [
        "After setting 2FA - log_2fa_set()",
        "After changing 2FA - log_2fa_changed()",
        "After removing 2FA - log_2fa_removed()",
    ],
    "message_handlers.py": [
        "After profile name update - log_profile_updated(field='Name')",
        "After username update - log_profile_updated(field='Username')",
        "After bio update - log_profile_updated(field='Bio')",
        "After photo update - log_profile_updated(field='Photo')",
    ],
}

# Template for adding logging:
LOGGING_TEMPLATE = """
# Log to logs bot
try:
    from ..utils.bot_logger import BotLogger
    phone = account.get('phone', 'Unknown')
    try:
        user = await self.bot.get_entity(user_id)
        username = user.username if hasattr(user, 'username') else None
    except:
        username = None
    await BotLogger.log_ACTION_NAME(user_id, phone, username)
except Exception:
    pass
"""

print("Add the logging template to each location listed above.")
print("Replace ACTION_NAME with the appropriate method from BotLogger.")
