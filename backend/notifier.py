"""
WebSocket notifier — called by the bot to push real-time events to the webapp.
Import this anywhere in the bot codebase to push events.

Usage:
    from backend.notifier import notify
    await notify(user_id, {"type": "new_message", "chat_id": 123, "text": "hi"})
    await notify(user_id, {"type": "session_revoked", "account_id": "...", "session_hash": "..."})
    await notify(user_id, {"type": "security_alert", "message": "Unauthorized session destroyed"})
    await notify(user_id, {"type": "account_added", "phone": "+91..."})
    await notify(user_id, {"type": "account_removed", "name": "..."})
    await notify(user_id, {"type": "otp_event", "phone": "+91...", "action": "destroyed"})
"""

import logging

logger = logging.getLogger(__name__)


async def notify(user_id: int, event: dict) -> None:
    """Push a WebSocket event to all webapp connections for this user."""
    try:
        from backend.websocket.manager import manager
        await manager.send_personal_message(event, user_id)
    except Exception as e:
        logger.debug(f"WebSocket notify failed (webapp may not be connected): {e}")


async def broadcast(event: dict) -> None:
    """Push a WebSocket event to ALL connected webapp users."""
    try:
        from backend.websocket.manager import manager
        await manager.broadcast(event)
    except Exception as e:
        logger.debug(f"WebSocket broadcast failed: {e}")
