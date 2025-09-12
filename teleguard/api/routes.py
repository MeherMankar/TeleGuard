"""API Routes for TeleGuard"""

import json
import logging
from typing import Any, Dict

from aiohttp import web, web_request

from ..core.database import get_session
from ..core.models import Account, User
from ..utils.api_security import validate_api_key

logger = logging.getLogger(__name__)


class APIRouter:
    """REST API router for TeleGuard"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        """Setup API routes"""
        self.app.router.add_get("/api/v1/accounts", self.list_accounts)
        self.app.router.add_post(
            "/api/v1/accounts/{account_id}/otp/toggle", self.toggle_otp
        )
        self.app.router.add_get(
            "/api/v1/accounts/{account_id}/sessions", self.list_sessions
        )
        self.app.router.add_post(
            "/api/v1/accounts/{account_id}/online/toggle", self.toggle_online
        )

    async def _authenticate(self, request: web_request.Request) -> int:
        """Authenticate API request and return user_id"""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise web.HTTPUnauthorized(text="Missing or invalid authorization header")

        api_key = auth_header[7:]  # Remove 'Bearer '
        user_id = await validate_api_key(api_key)
        if not user_id:
            raise web.HTTPUnauthorized(text="Invalid API key")

        return user_id

    async def list_accounts(self, request: web_request.Request) -> web.Response:
        """List user accounts"""
        try:
            user_id = await self._authenticate(request)

            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(Account).join(User).where(User.telegram_id == user_id)
                )
                accounts = result.scalars().all()

                account_list = []
                for account in accounts:
                    account_list.append(
                        {
                            "id": account.id,
                            "name": account.name,
                            "phone": account.phone,
                            "is_active": account.is_active,
                            "otp_destroyer_enabled": account.otp_destroyer_enabled,
                            "online_maker_enabled": account.online_maker_enabled,
                        }
                    )

                return web.json_response({"accounts": account_list})

        except web.HTTPException:
            raise
        except Exception as e:
            logger.error(f"API error in list_accounts: {e}")
            return web.json_response({"error": "Internal server error"}, status=500)

    async def toggle_otp(self, request: web_request.Request) -> web.Response:
        """Toggle OTP destroyer for account"""
        try:
            user_id = await self._authenticate(request)
            account_id = int(request.match_info["account_id"])

            data = await request.json()
            enabled = data.get("enabled", False)

            if hasattr(self.bot_manager, "otp_destroyer"):
                if enabled:
                    success = await self.bot_manager.otp_destroyer.enable_otp_destroyer(
                        user_id, account_id
                    )
                else:
                    (
                        success,
                        msg,
                    ) = await self.bot_manager.otp_destroyer.disable_otp_destroyer(
                        user_id, account_id
                    )

                if success:
                    return web.json_response({"success": True, "enabled": enabled})
                else:
                    return web.json_response(
                        {"error": "Failed to toggle OTP destroyer"}, status=400
                    )

            return web.json_response(
                {"error": "OTP destroyer not available"}, status=503
            )

        except web.HTTPException:
            raise
        except Exception as e:
            logger.error(f"API error in toggle_otp: {e}")
            return web.json_response({"error": "Internal server error"}, status=500)

    async def list_sessions(self, request: web_request.Request) -> web.Response:
        """List active sessions for account"""
        try:
            user_id = await self._authenticate(request)
            account_id = int(request.match_info["account_id"])

            if hasattr(self.bot_manager, "client_manager"):
                (
                    success,
                    sessions,
                ) = await self.bot_manager.client_manager.list_active_sessions(
                    user_id, account_id
                )
                if success:
                    return web.json_response({"sessions": sessions})
                else:
                    return web.json_response(
                        {"error": "Failed to list sessions"}, status=400
                    )

            return web.json_response(
                {"error": "Client manager not available"}, status=503
            )

        except web.HTTPException:
            raise
        except Exception as e:
            logger.error(f"API error in list_sessions: {e}")
            return web.json_response({"error": "Internal server error"}, status=500)

    async def toggle_online(self, request: web_request.Request) -> web.Response:
        """Toggle online maker for account"""
        try:
            user_id = await self._authenticate(request)
            account_id = int(request.match_info["account_id"])

            data = await request.json()
            enabled = data.get("enabled", False)
            interval = data.get("interval", 3600)

            if hasattr(self.bot_manager, "client_manager"):
                (
                    success,
                    msg,
                ) = await self.bot_manager.client_manager.toggle_online_maker(
                    user_id, account_id, enabled, interval
                )
                if success:
                    return web.json_response(
                        {"success": True, "enabled": enabled, "interval": interval}
                    )
                else:
                    return web.json_response({"error": msg}, status=400)

            return web.json_response(
                {"error": "Client manager not available"}, status=503
            )

        except web.HTTPException:
            raise
        except Exception as e:
            logger.error(f"API error in toggle_online: {e}")
            return web.json_response({"error": "Internal server error"}, status=500)
