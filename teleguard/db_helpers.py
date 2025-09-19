"""Database helper functions for TeleGuard"""

import os
import time
from typing import Any, Dict

from cryptography.fernet import Fernet

from .utils.logger import get_logger

logger = get_logger(__name__)

# Global database instance (set by main.py)
db = None


def get_fernet():
    """Get Fernet encryption instance if key is available"""
    fernet_key = os.getenv("FERNET_KEY")
    if fernet_key:
        return Fernet(fernet_key.encode())
    return None


def decrypt_with_fernet(fernet_instance, encrypted_data):
    """Decrypt data using Fernet instance"""
    if not fernet_instance or not encrypted_data:
        return encrypted_data
    
    try:
        return fernet_instance.decrypt(encrypted_data.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to decrypt with Fernet: {e}")
        return encrypted_data


def save_user_settings(user_id: int, settings: Dict[str, Any]):
    """Save user settings to database"""

    def update_settings(current_data):
        users = current_data.setdefault("users", {})
        users[str(user_id)] = {**settings, "updated_at": int(time.time())}
        return current_data

    try:
        db.safe_update_json(
            "db/user_settings.json",
            update_settings,
            f"Update settings for user {user_id}",
        )
        logger.info("Saved user settings", user_id=user_id)
    except Exception as e:
        logger.error("Failed to save user settings", user_id=user_id, error=str(e))
        raise


def load_user_settings(user_id: int) -> Dict[str, Any]:
    """Load user settings from database"""
    try:
        data, _ = db.get_json("db/user_settings.json")
        users = data.get("users", {})
        return users.get(str(user_id), {})
    except Exception as e:
        logger.error("Failed to load user settings", user_id=user_id, error=str(e))
        return {}


def add_account(user_id: int, phone: str, session_data: Dict[str, Any]):
    """Add account to database"""

    def update_accounts(current_data):
        accounts = current_data.setdefault("accounts", {})
        user_accounts = accounts.setdefault(str(user_id), {})

        user_accounts[phone] = {
            "phone": phone,
            "session_data": session_data,
            "added_at": int(time.time()),
            "status": "active",
        }
        return current_data

    fernet = get_fernet()

    try:
        db.safe_update_json(
            "db/accounts.json.enc" if fernet else "db/accounts.json",
            update_accounts,
            f"Add account {phone} for user {user_id}",
        )
        logger.info("Added account", user_id=user_id, phone=phone)
    except Exception as e:
        logger.error(
            "Failed to add account", user_id=user_id, phone=phone, error=str(e)
        )
        raise


def get_user_accounts(user_id: int) -> Dict[str, Any]:
    """Get all accounts for a user"""
    fernet = get_fernet()

    try:
        data, _ = db.get_json(
            "db/accounts.json.enc" if fernet else "db/accounts.json"
        )
        
        # Decrypt if needed
        if fernet and isinstance(data, str):
            try:
                import json
                decrypted_str = fernet.decrypt(data.encode()).decode()
                data = json.loads(decrypted_str)
            except Exception as e:
                logger.error(f"Failed to decrypt accounts data: {e}")
                data = {"accounts": {}}
        accounts = data.get("accounts", {})
        return accounts.get(str(user_id), {})
    except Exception as e:
        logger.error("Failed to load user accounts", user_id=user_id, error=str(e))
        return {}


def remove_account(user_id: int, phone: str):
    """Remove account from database"""

    def update_accounts(current_data):
        accounts = current_data.get("accounts", {})
        user_accounts = accounts.get(str(user_id), {})

        if phone in user_accounts:
            del user_accounts[phone]

        return current_data

    fernet = get_fernet()

    try:
        db.safe_update_json(
            "db/accounts.json.enc" if fernet else "db/accounts.json",
            update_accounts,
            f"Remove account {phone} for user {user_id}",
        )
        logger.info("Removed account", user_id=user_id, phone=phone)
    except Exception as e:
        logger.error(
            "Failed to remove account", user_id=user_id, phone=phone, error=str(e)
        )
        raise


def save_audit_log(user_id: int, action: str, details: Dict[str, Any]):
    """Save audit log entry"""

    def update_audit(current_data):
        logs = current_data.setdefault("logs", [])
        logs.append(
            {
                "user_id": user_id,
                "action": action,
                "details": details,
                "timestamp": int(time.time()),
            }
        )

        # Keep only last 1000 entries
        if len(logs) > 1000:
            logs[:] = logs[-1000:]

        return current_data

    try:
        db.safe_update_json(
            "db/audit_log.json", update_audit, f"Audit: {action} by user {user_id}"
        )
    except Exception as e:
        logger.error(
            "Failed to save audit log", user_id=user_id, action=action, error=str(e)
        )
