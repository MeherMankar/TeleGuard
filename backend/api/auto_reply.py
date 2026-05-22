import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.jwt import get_current_user_id
from teleguard.core.mongo_database import mongodb

router = APIRouter(prefix="/auto-reply", tags=["Auto Reply"])
logger = logging.getLogger(__name__)


def _get_bot_manager():
    try:
        from teleguard.core.bot_manager import bot_manager
        return bot_manager
    except Exception:
        return None


class SaveKeywordRequest(BaseModel):
    keyword: str
    reply: str


@router.get("/settings")
async def get_settings(user_id: int = Depends(get_current_user_id)):
    try:
        settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id})
        if not settings:
            settings = {"user_id": user_id, "keywords": {}}
            await mongodb.db.auto_reply_settings.insert_one(settings)
        return {"keywords": settings.get("keywords", {})}
    except Exception as e:
        logger.error(f"Error fetching auto reply settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/keywords")
async def add_keyword(payload: SaveKeywordRequest, user_id: int = Depends(get_current_user_id)):
    keyword = payload.keyword.strip()
    reply = payload.reply.strip()
    if not keyword or not reply:
        raise HTTPException(status_code=400, detail="Keyword and reply cannot be empty")

    try:
        await mongodb.db.auto_reply_settings.update_one(
            {"user_id": user_id},
            {"$set": {f"keywords.{keyword}": reply}},
            upsert=True,
        )
        # Reload in running bot
        bot_manager = _get_bot_manager()
        if bot_manager and hasattr(bot_manager, "auto_reply_handler"):
            try:
                await bot_manager.auto_reply_handler.load_user_keywords(user_id)
            except Exception:
                pass
        return {"status": "success", "keyword": keyword, "reply": reply}
    except Exception as e:
        logger.error(f"Error adding keyword: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/keywords/{keyword}")
async def delete_keyword(keyword: str, user_id: int = Depends(get_current_user_id)):
    try:
        result = await mongodb.db.auto_reply_settings.update_one(
            {"user_id": user_id},
            {"$unset": {f"keywords.{keyword}": ""}},
        )
        if result.modified_count > 0:
            bot_manager = _get_bot_manager()
            if bot_manager and hasattr(bot_manager, "auto_reply_handler"):
                try:
                    await bot_manager.auto_reply_handler.load_user_keywords(user_id)
                except Exception:
                    pass
            return {"status": "success"}
        raise HTTPException(status_code=404, detail="Keyword not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting keyword: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
