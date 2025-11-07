"""Messaging Statistics Service for TeleGuard"""
import logging
from datetime import datetime, timedelta
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class MessagingStats:
    """Handles messaging statistics and analytics"""
    
    def __init__(self):
        self.db = mongodb.db
    
    async def record_message_sent(self, user_id: int, account_id: str, target: str, message_type: str = "message"):
        """Record a sent message"""
        try:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Update daily stats
            await self.db.message_stats.update_one(
                {"user_id": user_id, "account_id": account_id, "date": today},
                {
                    "$inc": {"messages_sent": 1},
                    "$addToSet": {"targets": target},
                    "$set": {"last_updated": datetime.utcnow()}
                },
                upsert=True
            )
            
            # Log the message
            await self.db.messages_log.insert_one({
                "user_id": user_id,
                "account_id": account_id,
                "target": target,
                "type": message_type,
                "timestamp": datetime.utcnow().timestamp(),
                "date": today
            })
            
        except Exception as e:
            logger.error(f"Error recording message: {e}")
    
    async def record_auto_reply(self, user_id: int, account_id: str, sender: str):
        """Record an auto-reply"""
        try:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            await self.db.message_stats.update_one(
                {"user_id": user_id, "account_id": account_id, "date": today},
                {
                    "$inc": {"auto_replies": 1},
                    "$set": {"last_updated": datetime.utcnow()}
                },
                upsert=True
            )
            
            await self.record_message_sent(user_id, account_id, sender, "auto_reply")
            
        except Exception as e:
            logger.error(f"Error recording auto-reply: {e}")
    
    async def record_template_used(self, user_id: int, account_id: str, template_name: str):
        """Record template usage"""
        try:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            await self.db.message_stats.update_one(
                {"user_id": user_id, "account_id": account_id, "date": today},
                {
                    "$inc": {"templates_used": 1},
                    "$addToSet": {"template_names": template_name},
                    "$set": {"last_updated": datetime.utcnow()}
                },
                upsert=True
            )
            
        except Exception as e:
            logger.error(f"Error recording template usage: {e}")
    
    async def get_user_stats(self, user_id: int, days: int = 7):
        """Get messaging statistics for user"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            stats = await self.db.message_stats.find({
                "user_id": user_id,
                "date": {"$gte": start_date}
            }).to_list(length=None)
            
            total_messages = sum(s.get('messages_sent', 0) for s in stats)
            total_auto_replies = sum(s.get('auto_replies', 0) for s in stats)
            total_templates = sum(s.get('templates_used', 0) for s in stats)
            unique_targets = set()
            for s in stats:
                unique_targets.update(s.get('targets', []))
            
            return {
                'total_messages': total_messages,
                'total_auto_replies': total_auto_replies,
                'total_templates': total_templates,
                'unique_conversations': len(unique_targets),
                'days_active': len(stats),
                'avg_messages_per_day': total_messages / max(days, 1)
            }
            
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {
                'total_messages': 0,
                'total_auto_replies': 0,
                'total_templates': 0,
                'unique_conversations': 0,
                'days_active': 0,
                'avg_messages_per_day': 0
            }
    
    async def get_recent_messages(self, user_id: int, limit: int = 20):
        """Get recent message history"""
        try:
            messages = await self.db.messages_log.find(
                {"user_id": user_id}
            ).sort("timestamp", -1).limit(limit).to_list(length=limit)
            
            return messages
            
        except Exception as e:
            logger.error(f"Error getting recent messages: {e}")
            return []
