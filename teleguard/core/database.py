"""
TeleGuard Database Configuration - MongoDB Only

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

# This file is kept for compatibility but all database operations
# are now handled by mongo_database.py

from .mongo_database import init_db, mongodb


# Legacy compatibility - redirect to MongoDB
async def get_session():
    """Legacy compatibility function - use mongodb directly instead"""
    raise NotImplementedError("Use mongodb from mongo_database.py instead")


__all__ = ["init_db", "mongodb"]
