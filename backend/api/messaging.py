import logging
import time
from typing import Any, Dict, List, Literal, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel, Field, field_validator

from backend.auth.jwt import get_current_user_id
from teleguard.core.mongo_database import mongodb

router = APIRouter(prefix="/messaging", tags=["Messaging"])
logger = logging.getLogger(__name__)
MAX_UPLOAD_SIZE = 50 * 1024 * 1024
MAX_BULK_TARGETS = 50
_active_bulk_users: set[int] = set()


def _get_bot_manager():
    try:
        from teleguard.core.bot_manager import bot_manager
        return bot_manager
    except Exception:
        return None


class SendMessageRequest(BaseModel):
    account_name: str
    target: str
    message: str = Field(min_length=1, max_length=4096)
    reply_to_message_id: Optional[int] = None


class CreateJobRequest(BaseModel):
    account_id: str
    job_type: Literal["scheduled_post", "auto_join"]
    job_config: Dict[str, Any]
    interval_seconds: int = Field(ge=60)


class BulkMessageRequest(BaseModel):
    account_name: str
    targets: List[str] = Field(min_length=1, max_length=MAX_BULK_TARGETS)
    message: str = Field(min_length=1, max_length=4096)

    @field_validator("targets")
    @classmethod
    def validate_targets(cls, targets: List[str]) -> List[str]:
        cleaned = [target.strip() for target in targets]
        if any(not target or len(target) > 256 for target in cleaned):
            raise ValueError("Targets must contain 1 to 256 non-whitespace characters")
        return cleaned


@router.get("/stats")
async def get_stats(user_id: int = Depends(get_current_user_id)):
    bot_manager = _get_bot_manager()
    if not bot_manager or not bot_manager.messaging_manager:
        raise HTTPException(
            status_code=503, detail="Messaging manager not initialized"
        )
    try:
        stats = await bot_manager.messaging_manager.get_messaging_statistics(user_id)
        auto_replies = await mongodb.db.auto_replies_sent_count.find_one({"user_id": user_id})
        if auto_replies:
            stats["auto_replies_sent"] = auto_replies.get("count", 0)
        return stats
    except Exception as e:
        logger.error(f"Error fetching messaging stats: {e}")
        raise HTTPException(
            status_code=500, detail="Could not fetch messaging statistics"
        ) from e


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
            reply_to_message_id=payload.reply_to_message_id,
        )
        if success:
            await mongodb.db.users.update_one(
                {"telegram_id": user_id},
                {"$inc": {"messages_sent_count": 1}},
            )
            return {"status": "success"}
        raise HTTPException(status_code=400, detail="Failed to send message")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        try:
            account_id = ObjectId(payload.account_id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="Invalid account ID")
        account = await mongodb.db.accounts.find_one({
            "_id": account_id,
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
        try:
            mongo_job_id = ObjectId(job_id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="Invalid job ID")
        result = await mongodb.db.automation_jobs.delete_one({
            "_id": mongo_job_id,
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
    try:
        for target in targets:
            try:
                if bot_manager and bot_manager.messaging_manager:
                    await bot_manager.messaging_manager.send_message(
                        user_id=user_id, account_name=account_name, target=target, message=message
                    )
                await asyncio.sleep(3.0)
            except Exception as e:
                logger.error(f"Bulk send failed for {target}: {e}")
    finally:
        _active_bulk_users.discard(user_id)


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
    if user_id in _active_bulk_users:
        raise HTTPException(status_code=409, detail="A bulk send is already running")

    _active_bulk_users.add(user_id)
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
    caption: str = Form("", max_length=1024),
    reply_to_message_id: Optional[int] = Form(None),
    voice_note: bool = Form(False),
    user_id: int = Depends(get_current_user_id),
):
    """Send a file (image/document/video) to a target chat."""
    bot_manager = _get_bot_manager()
    if not bot_manager:
        raise HTTPException(status_code=503, detail="Bot not running")

    client = bot_manager.get_client(user_id, {"name": account_name})
    if not client:
        raise HTTPException(status_code=404, detail="Active client not found")

    tmp_path = None
    try:
        import os
        import tempfile

        if file.size is not None and file.size > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="Uploaded file exceeds 50 MiB limit")

        suffix = os.path.splitext(file.filename or "file")[1] or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = tmp.name
            total_size = 0
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=413, detail="Uploaded file exceeds 50 MiB limit"
                    )
                tmp.write(chunk)

        entity = await client.get_entity(target)
        await client.send_file(
            entity,
            tmp_path,
            caption=caption or None,
            reply_to=reply_to_message_id,
            voice_note=voice_note,
        )
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"send-file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path:
            import os

            try:
                os.unlink(tmp_path)
            except OSError:
                logger.warning("Unable to remove temporary upload file %s", tmp_path)
