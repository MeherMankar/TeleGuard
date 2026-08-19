import logging
import time
from typing import Dict, Any, List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, Form, UploadFile
from pydantic import BaseModel

from backend.auth.jwt import get_current_user_id
from teleguard.core.mongo_database import mongodb

router = APIRouter(prefix="/messaging", tags=["Messaging"])
logger = logging.getLogger(__name__)


def _get_bot_manager():
    try:
        from teleguard.core.bot_manager import bot_manager
        return bot_manager
    except Exception:
        return None


class SendMessageRequest(BaseModel):
    account_name: str
    target: str
    message: str


class CreateJobRequest(BaseModel):
    account_id: str
    job_type: str
    job_config: Dict[str, Any]
    interval_seconds: int


class BulkMessageRequest(BaseModel):
    account_name: str
    targets: List[str]
    message: str


@router.get("/stats")
async def get_stats(user_id: int = Depends(get_current_user_id)):
    bot_manager = _get_bot_manager()
    if not bot_manager or not bot_manager.messaging_manager:
        return {"total_messages_sent": 0, "auto_replies_sent": 0, "active_accounts": 0, "dm_topics_created": 0}
    try:
        stats = await bot_manager.messaging_manager.get_messaging_statistics(user_id)
        auto_replies = await mongodb.db.auto_replies_sent_count.find_one({"user_id": user_id})
        if auto_replies:
            stats["auto_replies_sent"] = auto_replies.get("count", 0)
        return stats
    except Exception as e:
        logger.error(f"Error fetching messaging stats: {e}")
        return {"total_messages_sent": 0, "auto_replies_sent": 0, "active_accounts": 0, "dm_topics_created": 0}


@router.post("/send")
async def send_message(payload: SendMessageRequest, user_id: int = Depends(get_current_user_id)):
    """Send a message using the live bot client."""
    bot_manager = _get_bot_manager()
    if not bot_manager or not bot_manager.messaging_manager:
        raise HTTPException(status_code=503, detail="Messaging manager not initialized")

    try:
        success = await bot_manager.messaging_manager.send_message(
            user_id=user_id,
            account_name=payload.account_name,
            target=payload.target,
            message=payload.message,
        )
        if success:
            await mongodb.db.users.update_one(
                {"telegram_id": user_id},
                {"$inc": {"messages_sent_count": 1}},
            )
            return {"status": "success"}
        raise HTTPException(status_code=400, detail="Failed to send message")
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs", response_model=List[Dict[str, Any]])
async def list_jobs(user_id: int = Depends(get_current_user_id)):
    try:
        cursor = mongodb.db.automation_jobs.find({"user_id": user_id})
        jobs = await cursor.to_list(length=100)
        for job in jobs:
            job["id"] = str(job["_id"])
            job.pop("_id", None)
        return jobs
    except Exception as e:
        logger.error(f"Error fetching jobs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/jobs")
async def create_job(payload: CreateJobRequest, user_id: int = Depends(get_current_user_id)):
    try:
        account = await mongodb.db.accounts.find_one({
            "_id": ObjectId(payload.account_id),
            "user_id": user_id,
        })
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        import json
        job_doc = {
            "user_id": user_id,
            "account_id": payload.account_id,
            "job_type": payload.job_type,
            "job_config": json.dumps(payload.job_config),
            "enabled": True,
            "interval_seconds": payload.interval_seconds,
            "last_run": 0,
            "next_run": time.time() + payload.interval_seconds,
            "created_at": time.time(),
        }
        result = await mongodb.db.automation_jobs.insert_one(job_doc)
        return {"status": "success", "job_id": str(result.inserted_id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, user_id: int = Depends(get_current_user_id)):
    try:
        result = await mongodb.db.automation_jobs.delete_one({
            "_id": ObjectId(job_id),
            "user_id": user_id,
        })
        if result.deleted_count > 0:
            return {"status": "success"}
        raise HTTPException(status_code=404, detail="Job not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def _run_bulk_send(user_id: int, account_name: str, targets: List[str], message: str):
    import asyncio
    bot_manager = _get_bot_manager()
    for target in targets:
        try:
            if bot_manager and bot_manager.messaging_manager:
                await bot_manager.messaging_manager.send_message(
                    user_id=user_id, account_name=account_name, target=target, message=message
                )
            await asyncio.sleep(3.0)
        except Exception as e:
            logger.error(f"Bulk send failed for {target}: {e}")


@router.post("/bulk")
async def send_bulk(
    payload: BulkMessageRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
):
    bot_manager = _get_bot_manager()
    if not bot_manager:
        raise HTTPException(status_code=503, detail="Bot manager not initialized")
    client = bot_manager.get_client(user_id, {"name": payload.account_name})
    if not client:
        raise HTTPException(status_code=404, detail="Active account client not found")

    background_tasks.add_task(
        _run_bulk_send,
        user_id=user_id,
        account_name=payload.account_name,
        targets=[t.strip() for t in payload.targets if t.strip()],
        message=payload.message,
    )
    return {"status": "enqueued", "message": f"Bulk message queued for {len(payload.targets)} targets"}


# ── Send file ─────────────────────────────────────────────────────────────────

@router.post("/send-file")
async def send_file_message(
    account_name: str = Form(...),
    target: str = Form(...),
    file: UploadFile = File(...),
    caption: str = Form(""),
    user_id: int = Depends(get_current_user_id),
):
    """Send a file (image/document/video) to a target chat."""
    bot_manager = _get_bot_manager()
    if not bot_manager:
        raise HTTPException(status_code=503, detail="Bot not running")

    client = bot_manager.get_client(user_id, {"name": account_name})
    if not client:
        raise HTTPException(status_code=404, detail="Active client not found")

    try:
        import tempfile, os
        suffix = os.path.splitext(file.filename or "file")[1] or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        entity = await client.get_entity(target)
        await client.send_file(entity, tmp_path, caption=caption or None)
        os.unlink(tmp_path)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"send-file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
