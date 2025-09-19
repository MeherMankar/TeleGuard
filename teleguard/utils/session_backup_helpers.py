"""Session backup utilities with robust account handling"""
import logging
import datetime
from bson import ObjectId
from typing import Optional, Tuple, Any

logger = logging.getLogger(__name__)

async def find_account_doc(db, account_id_or_phone) -> Tuple[Optional[dict], Optional[Any]]:
    """Find account by ID, phone, or other identifier"""
    # Try ObjectId
    try:
        oid = ObjectId(account_id_or_phone)
        doc = await db.accounts.find_one({"_id": oid})
        if doc:
            return doc, oid
    except Exception:
        pass
    
    # Try by phone
    doc = await db.accounts.find_one({"phone": account_id_or_phone})
    if doc:
        return doc, doc.get("_id")
    
    # Try by display_name
    doc = await db.accounts.find_one({"display_name": account_id_or_phone})
    if doc:
        return doc, doc.get("_id")
    
    return None, None

async def backup_session(db, account_id_or_phone: str, session_str: str) -> bool:
    """Backup session with robust account finding"""
    doc, acct_oid = await find_account_doc(db, account_id_or_phone)
    if not doc:
        logger.error("backup_session: account not found for %r", account_id_or_phone)
        return False
    
    backup_doc = {
        "old_session": doc.get("session_string"),
        "old_session_backup_ts": datetime.datetime.utcnow()
    }
    
    await db.accounts.update_one(
        {"_id": acct_oid}, 
        {"$set": backup_doc}
    )
    
    # Save new session
    await db.accounts.update_one(
        {"_id": acct_oid}, 
        {"$set": {"session_string": session_str}}
    )
    
    logger.info("Backed up and replaced session for account %s", acct_oid)
    return True