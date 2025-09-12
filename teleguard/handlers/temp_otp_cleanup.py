"""Temp OTP cleanup handler"""

import asyncio
import logging
import time
from bson import ObjectId
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

async def cleanup_temp_otp(user_id: int, account_id: str, expiry_time: float):
    """Clean up expired temp OTP after 5 minutes"""
    try:
        await asyncio.sleep(300)  # Wait 5 minutes
        
        # Check if temp OTP is still active and matches our expiry time
        account = await mongodb.db.accounts.find_one({
            "_id": ObjectId(account_id),
            "user_id": user_id,
            "temp_passthrough_expiry": expiry_time
        })
        
        if account and account.get("otp_temp_passthrough", False):
            # Restore original destroyer state and disable temp passthrough
            original_destroyer_state = account.get("original_destroyer_state", True)
            
            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {
                    "$set": {"otp_destroyer_enabled": original_destroyer_state},
                    "$unset": {
                        "otp_temp_passthrough": "",
                        "temp_passthrough_expiry": "",
                        "original_destroyer_state": ""
                    }
                }
            )
            
            await mongodb.add_audit_entry(account_id, {
                "action": "temp_passthrough_expired",
                "timestamp": int(time.time())
            })
            
            logger.info(f"Temp OTP expired and cleaned up for account {account_id}")
            
    except Exception as e:
        logger.error(f"Error cleaning up temp OTP: {e}")