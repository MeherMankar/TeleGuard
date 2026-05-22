import logging
from typing import List, Dict, Any, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.jwt import get_current_user_id
from teleguard.core.mongo_database import mongodb
from teleguard.core.proxy_manager import proxy_manager

router = APIRouter(prefix="/proxies", tags=["Proxies"])
logger = logging.getLogger(__name__)


def _get_bot_manager():
    try:
        from teleguard.core.bot_manager import bot_manager
        return bot_manager
    except Exception:
        return None


class AddProxyRequest(BaseModel):
    name: Optional[str] = None
    type: str
    server: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    secret: Optional[str] = None


class AssignProxyRequest(BaseModel):
    account_id: str
    proxy_id: str


class RemoveProxyRequest(BaseModel):
    account_id: str


class TestProxyRequest(BaseModel):
    proxy_id: str


class SetDefaultProxyRequest(BaseModel):
    proxy_id: str


@router.get("/list", response_model=List[Dict[str, Any]])
async def list_proxies(user_id: int = Depends(get_current_user_id)):
    try:
        raw = await proxy_manager.get_user_proxies(user_id)
        result = []
        for p in raw:
            p["id"] = str(p["_id"])
            p.pop("_id", None)
            result.append(p)
        return result
    except Exception as e:
        logger.error(f"Error listing proxies: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/add")
async def add_proxy(payload: AddProxyRequest, user_id: int = Depends(get_current_user_id)):
    try:
        proxy_data = {
            "type": payload.type,
            "server": payload.server,
            "port": payload.port,
            "username": payload.username,
            "password": payload.password,
            "secret": payload.secret,
        }
        success, result = await proxy_manager.add_proxy(user_id, proxy_data, payload.name)
        if success:
            return {"status": "success", "proxy_id": result}
        raise HTTPException(status_code=400, detail=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding proxy: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/delete/{proxy_id}")
async def delete_proxy(proxy_id: str, user_id: int = Depends(get_current_user_id)):
    try:
        success, message = await proxy_manager.delete_proxy(user_id, proxy_id)
        if success:
            return {"status": "success", "message": message}
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting proxy: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/assign")
async def assign_proxy(payload: AssignProxyRequest, user_id: int = Depends(get_current_user_id)):
    try:
        bot_manager = _get_bot_manager()
        success, message = await proxy_manager.assign_proxy_to_account(
            user_id=user_id,
            account_id=payload.account_id,
            proxy_id=payload.proxy_id,
            bot_manager=bot_manager,
        )
        if success:
            return {"status": "success", "message": message}
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning proxy: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/remove")
async def remove_proxy(payload: RemoveProxyRequest, user_id: int = Depends(get_current_user_id)):
    try:
        success, message = await proxy_manager.remove_proxy_from_account(
            user_id=user_id, account_id=payload.account_id
        )
        if success:
            return {"status": "success", "message": message}
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing proxy: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/test")
async def test_proxy(payload: TestProxyRequest, user_id: int = Depends(get_current_user_id)):
    try:
        p = await mongodb.db.proxies.find_one({"_id": ObjectId(payload.proxy_id), "user_id": user_id})
        if not p:
            raise HTTPException(status_code=404, detail="Proxy not found")

        bot_manager = _get_bot_manager()
        success, status_str, response_time = await proxy_manager.test_proxy(
            proxy_id=payload.proxy_id, bot_manager=bot_manager
        )
        return {
            "status": "working" if success else "failed",
            "message": status_str,
            "latency": response_time,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing proxy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/default")
async def set_default_proxy(payload: SetDefaultProxyRequest, user_id: int = Depends(get_current_user_id)):
    try:
        success, message = await proxy_manager.set_default_proxy(user_id, payload.proxy_id)
        if success:
            return {"status": "success", "message": message}
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting default proxy: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/default")
async def get_default_proxy(user_id: int = Depends(get_current_user_id)):
    try:
        p = await proxy_manager.get_default_proxy(user_id)
        if p:
            p["id"] = str(p["_id"])
            p.pop("_id", None)
            return p
        return {"status": "no_default"}
    except Exception as e:
        logger.error(f"Error getting default proxy: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
