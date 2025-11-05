"""Utility helper functions"""
import json
import logging

logger = logging.getLogger(__name__)

class UtilityHelpers:
    @staticmethod
    def parse_callback(callback_data):
        if not callback_data:
            return {}
        try:
            parsed = json.loads(callback_data)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        parts = callback_data.split(':')
        action = parts[0] if parts else ''
        subaction = parts[1] if len(parts) > 1 else None
        rest = parts[2:] if len(parts) > 2 else []
        out = {"action": action, "subaction": subaction, "parts": rest}
        if rest:
            out["id"] = rest[0]
        if subaction and not rest:
            out.setdefault("name", subaction if action == "account" and subaction not in ("add","list","remove","manage","refresh") else None)
        return out
    
    @staticmethod
    def format_display_name(account):
        def _get(obj, key):
            if obj is None:
                return None
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)
        first = _get(account, "first_name") or _get(account, "first")
        last = _get(account, "last_name") or _get(account, "last")
        username = _get(account, "username")
        display_name_field = _get(account, "display_name")
        user_id = _get(account, "id") or _get(account, "_id") or _get(account, "user_id")
        phone = _get(account, "phone")
        if display_name_field:
            base = display_name_field
        else:
            name = " ".join(p for p in (first, last) if p)
            if name:
                base = name
            elif username:
                base = f"@{username}"
            elif phone:
                base = phone
            elif user_id:
                base = f"ID:{user_id}"
            else:
                base = "Unknown"
        if base == "Unknown":
            logger.debug(f"Account row for unknown display -> {account}")
        return base
