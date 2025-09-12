"""
TeleGuard Database Models - MongoDB Schema Reference

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

# This file is kept for reference but all database operations
# are now handled by MongoDB through mongo_database.py

# MongoDB Collections Schema Reference:

# users collection:
# {
#   "_id": ObjectId,
#   "telegram_id": int,
#   "is_admin": bool,
#   "otp_forward": bool,
#   "otp_destroy": bool,
#   "online_interval": int,
#   "developer_mode": bool,
#   "main_menu_message_id": int,
#   "created_at": datetime,
#   "updated_at": datetime
# }

# accounts collection:
# {
#   "_id": ObjectId,
#   "user_id": int,
#   "name": str,
#   "phone": str,
#   "session_string": str (encrypted),
#   "is_active": bool,
#   "otp_destroyer_enabled": bool,
#   "otp_forward_enabled": bool,
#   "profile_first_name": str,
#   "profile_last_name": str,
#   "username": str,
#   "about": str,
#   "online_maker_enabled": bool,
#   "online_maker_interval": int,
#   "audit_log": list,
#   "created_at": datetime,
#   "updated_at": datetime
# }


# Legacy compatibility - all models are now handled by MongoDB
class LegacyModelError(Exception):
    """Raised when trying to use legacy SQLAlchemy models"""

    pass


def __getattr__(name):
    """Catch any attempts to use old SQLAlchemy models"""
    if name in [
        "User",
        "Account",
        "Bot",
        "CoOwner",
        "SudoUser",
        "AutomationJob",
        "MessageTemplate",
        "AuditEvent",
    ]:
        raise LegacyModelError(
            f"Model {name} is no longer available. Use MongoDB operations through mongo_database.py"
        )
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
