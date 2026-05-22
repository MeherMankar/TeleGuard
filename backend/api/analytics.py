import logging
from fastapi import APIRouter, Depends, HTTPException

from backend.auth.jwt import get_current_user_id
from teleguard.core.mongo_database import mongodb
from teleguard.core.client_manager import get_client_manager
from teleguard.sync.session_destroyer_db import SessionDestroyerDB

router = APIRouter(prefix="/analytics", tags=["Analytics"])
logger = logging.getLogger(__name__)


def _get_bot_manager():
    try:
        from teleguard.core.bot_manager import bot_manager
        return bot_manager
    except Exception:
        return None


@router.get("/dashboard")
async def get_dashboard_data(user_id: int = Depends(get_current_user_id)):
    try:
        total_accounts = await mongodb.db.accounts.count_documents({"user_id": user_id})
        active_accounts = await mongodb.db.accounts.count_documents({"user_id": user_id, "is_active": True})

        # Count live connected clients from bot_manager
        active_sessions = 0
        bot_manager = _get_bot_manager()
        if bot_manager:
            user_clients = bot_manager.user_clients.get(user_id, {})
            for client in user_clients.values():
                if client.is_connected():
                    active_sessions += 1

        # Fallback to client_manager
        if active_sessions == 0:
            client_manager = get_client_manager()
            if client_manager:
                for key, client in client_manager.clients.items():
                    if key.startswith(f"{user_id}_") and client.is_connected():
                        active_sessions += 1

        user_doc = await mongodb.db.users.find_one({"telegram_id": user_id})
        messages_sent = user_doc.get("messages_sent_count", 0) if user_doc else 0

        destroyer_stats = await SessionDestroyerDB.get_stats(user_id)
        destroyed_sessions = destroyer_stats.get("destroyed_count", 0)

        logs = await SessionDestroyerDB.get_logs(user_id, limit=5)
        activities = []
        for log in logs:
            activities.append({
                "type": "security_alert",
                "message": f"Destroyed session from {log.get('device', 'Unknown')} ({log.get('ip', 'Unknown')})",
                "timestamp": log.get("timestamp").isoformat() if log.get("timestamp") else None,
            })

        return {
            "stats": {
                "totalAccounts": total_accounts,
                "activeAccounts": active_accounts,
                "activeSessions": active_sessions,
                "messagesSent": messages_sent,
                "destroyedSessions": destroyed_sessions,
            },
            "recentActivities": activities,
        }
    except Exception as e:
        logger.error(f"Error fetching dashboard data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
