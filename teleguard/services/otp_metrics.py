"""
OTP Metrics Service
Tracks and aggregates OTP destroyer statistics
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class OTPMetrics:
    """Service for tracking OTP destroyer statistics"""
    
    @staticmethod
    async def record_block(account_id: str, reason: str = "otp_destroyed", metadata: Dict = None) -> bool:
        """
        Record an OTP block event
        
        Args:
            account_id: Account identifier
            reason: Reason for block (otp_destroyed, temp_passthrough, etc.)
            metadata: Additional metadata about the block
            
        Returns:
            bool: Success status
        """
        try:
            date = datetime.utcnow().strftime("%Y-%m-%d")
            
            await mongodb.db.otp_stats.update_one(
                {"account_id": account_id, "date": date},
                {
                    "$inc": {"blocked_count": 1},
                    "$setOnInsert": {
                        "created_at": datetime.utcnow(),
                        "allowed_count": 0
                    },
                    "$set": {
                        "last_block": datetime.utcnow(),
                        "last_reason": reason
                    },
                    "$push": {
                        "recent_blocks": {
                            "$each": [{
                                "timestamp": datetime.utcnow(),
                                "reason": reason,
                                "metadata": metadata or {}
                            }],
                            "$slice": -10  # Keep only last 10 blocks
                        }
                    }
                },
                upsert=True
            )
            
            logger.info(f"Recorded OTP block for account {account_id}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record OTP block: {e}")
            return False
    
    @staticmethod
    async def record_allow(account_id: str, reason: str = "temp_passthrough", metadata: Dict = None) -> bool:
        """
        Record an OTP allow event (when temp passthrough is active)
        
        Args:
            account_id: Account identifier
            reason: Reason for allowing
            metadata: Additional metadata
            
        Returns:
            bool: Success status
        """
        try:
            date = datetime.utcnow().strftime("%Y-%m-%d")
            
            await mongodb.db.otp_stats.update_one(
                {"account_id": account_id, "date": date},
                {
                    "$inc": {"allowed_count": 1},
                    "$setOnInsert": {
                        "created_at": datetime.utcnow(),
                        "blocked_count": 0
                    },
                    "$set": {
                        "last_allow": datetime.utcnow(),
                        "last_allow_reason": reason
                    }
                },
                upsert=True
            )
            
            logger.info(f"Recorded OTP allow for account {account_id}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record OTP allow: {e}")
            return False
    
    @staticmethod
    async def get_global_stats(start_date: str = None, end_date: str = None) -> Dict:
        """
        Get global OTP statistics
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            Dict with global statistics
        """
        try:
            # Default to last 30 days if no dates provided
            if not start_date:
                start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
            if not end_date:
                end_date = datetime.utcnow().strftime("%Y-%m-%d")
            
            # Aggregate pipeline
            pipeline = [
                {"$match": {"date": {"$gte": start_date, "$lte": end_date}}},
                {"$group": {
                    "_id": None,
                    "total_blocked": {"$sum": "$blocked_count"},
                    "total_allowed": {"$sum": "$allowed_count"},
                    "unique_accounts": {"$addToSet": "$account_id"},
                    "active_days": {"$addToSet": "$date"}
                }},
                {"$project": {
                    "total_blocked": 1,
                    "total_allowed": 1,
                    "unique_accounts": {"$size": "$unique_accounts"},
                    "active_days": {"$size": "$active_days"}
                }}
            ]
            
            result = await mongodb.db.otp_stats.aggregate(pipeline).to_list(1)
            
            if not result:
                return {
                    "total_blocked": 0,
                    "total_allowed": 0,
                    "unique_accounts": 0,
                    "active_days": 0,
                    "period": f"{start_date} to {end_date}"
                }
            
            stats = result[0]
            stats["period"] = f"{start_date} to {end_date}"
            
            # Get top accounts
            top_accounts = await OTPMetrics.get_top_blocked_accounts(start_date, end_date, limit=5)
            stats["top_accounts"] = top_accounts
            
            # Get recent activity sparkline (last 7 days)
            sparkline = await OTPMetrics.get_activity_sparkline(7)
            stats["sparkline"] = sparkline
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get global stats: {e}")
            return {"error": str(e)}
    
    @staticmethod
    async def get_account_stats(account_id: str, start_date: str = None, end_date: str = None) -> Dict:
        """
        Get statistics for a specific account
        
        Args:
            account_id: Account identifier
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            Dict with account statistics
        """
        try:
            if not start_date:
                start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
            if not end_date:
                end_date = datetime.utcnow().strftime("%Y-%m-%d")
            
            pipeline = [
                {"$match": {
                    "account_id": account_id,
                    "date": {"$gte": start_date, "$lte": end_date}
                }},
                {"$group": {
                    "_id": None,
                    "total_blocked": {"$sum": "$blocked_count"},
                    "total_allowed": {"$sum": "$allowed_count"},
                    "active_days": {"$sum": 1},
                    "last_activity": {"$max": "$last_block"}
                }}
            ]
            
            result = await mongodb.db.otp_stats.aggregate(pipeline).to_list(1)
            
            if not result:
                return {
                    "account_id": account_id,
                    "total_blocked": 0,
                    "total_allowed": 0,
                    "active_days": 0,
                    "last_activity": None,
                    "period": f"{start_date} to {end_date}"
                }
            
            stats = result[0]
            stats["account_id"] = account_id
            stats["period"] = f"{start_date} to {end_date}"
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get account stats: {e}")
            return {"error": str(e)}
    
    @staticmethod
    async def get_top_blocked_accounts(start_date: str = None, end_date: str = None, limit: int = 10) -> List[Dict]:
        """
        Get accounts with most blocks
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            limit: Number of top accounts to return
            
        Returns:
            List of account statistics
        """
        try:
            if not start_date:
                start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
            if not end_date:
                end_date = datetime.utcnow().strftime("%Y-%m-%d")
            
            pipeline = [
                {"$match": {"date": {"$gte": start_date, "$lte": end_date}}},
                {"$group": {
                    "_id": "$account_id",
                    "total_blocked": {"$sum": "$blocked_count"},
                    "total_allowed": {"$sum": "$allowed_count"},
                    "last_activity": {"$max": "$last_block"}
                }},
                {"$sort": {"total_blocked": -1}},
                {"$limit": limit}
            ]
            
            results = await mongodb.db.otp_stats.aggregate(pipeline).to_list(limit)
            
            return [{
                "account_id": r["_id"],
                "blocked": r["total_blocked"],
                "allowed": r["total_allowed"],
                "last_activity": r["last_activity"]
            } for r in results]
            
        except Exception as e:
            logger.error(f"Failed to get top accounts: {e}")
            return []
    
    @staticmethod
    async def get_activity_sparkline(days: int) -> str:
        """
        Generate ASCII sparkline for recent activity
        
        Args:
            days: Number of days to include
            
        Returns:
            ASCII sparkline string
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days-1)
            
            # Get daily totals
            pipeline = [
                {"$match": {
                    "date": {
                        "$gte": start_date.strftime("%Y-%m-%d"),
                        "$lte": end_date.strftime("%Y-%m-%d")
                    }
                }},
                {"$group": {
                    "_id": "$date",
                    "total": {"$sum": "$blocked_count"}
                }},
                {"$sort": {"_id": 1}}
            ]
            
            results = await mongodb.db.otp_stats.aggregate(pipeline).to_list(days)
            
            # Create daily map
            daily_counts = {}
            for r in results:
                daily_counts[r["_id"]] = r["total"]
            
            # Generate sparkline
            values = []
            for i in range(days):
                date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
                values.append(daily_counts.get(date, 0))
            
            if not values or max(values) == 0:
                return "▁" * days  # All zeros
            
            # Normalize to 0-7 range for sparkline chars
            max_val = max(values)
            chars = "▁▂▃▄▅▆▇█"
            
            sparkline = ""
            for val in values:
                if val == 0:
                    sparkline += "▁"
                else:
                    index = min(7, int((val / max_val) * 7))
                    sparkline += chars[index]
            
            return sparkline
            
        except Exception as e:
            logger.error(f"Failed to generate sparkline: {e}")
            return "▁" * days

# Global instance
otp_metrics = OTPMetrics()
