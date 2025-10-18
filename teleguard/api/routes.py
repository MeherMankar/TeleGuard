"""
REST API Routes for TeleGuard
Professional REST API implementation with comprehensive error handling,
authentication, and standardized response formats.
Authors: @Meher_Mankar, @Gutkesh
Repository: https://github.com/mehermankar/teleguard
"""
import json
import logging
from typing import Any, Dict, List, Optional
from http import HTTPStatus
from aiohttp import web, web_request
from aiohttp.web_response import Response
from ..core.mongo_database import mongodb
from ..utils.api_security import validate_api_key
logger = logging.getLogger(__name__)
class APIError(Exception):
    """Custom exception for API operations"""
    def __init__(self, message: str, status_code: int = HTTPStatus.BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(message)
class APIRouter:
    """
    Professional REST API router for TeleGuard.
    Provides secure, well-documented API endpoints for account management,
    OTP control, session management, and online status control.
    """
    # API version and base path
    API_VERSION = "v1"
    BASE_PATH = f"/api/{API_VERSION}"
    # Standard response messages
    RESPONSES = {
        'unauthorized': 'Missing or invalid authorization header',
        'invalid_api_key': 'Invalid API key',
        'internal_error': 'Internal server error',
        'account_not_found': 'Account not found',
        'service_unavailable': 'Service temporarily unavailable'
    }
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.app = web.Application()
        self._setup_routes()
        self._setup_middleware()
    def _setup_middleware(self) -> None:
        """Setup API middleware for logging and error handling"""
        @web.middleware
        async def error_middleware(request, handler):
            try:
                return await handler(request)
            except APIError as e:
                return self._error_response(e.message, e.status_code)
            except Exception as e:
                logger.error(f"Unhandled API error: {e}")
                return self._error_response(
                    self.RESPONSES['internal_error'], 
                    HTTPStatus.INTERNAL_SERVER_ERROR
                )
        self.app.middlewares.append(error_middleware)
    def _setup_routes(self) -> None:
        """Setup all API routes with proper HTTP methods"""
        routes = [
            ('GET', '/accounts', self.list_accounts),
            ('POST', '/accounts/{account_id}/otp/toggle', self.toggle_otp),
            ('GET', '/accounts/{account_id}/sessions', self.list_sessions),
            ('POST', '/accounts/{account_id}/online/toggle', self.toggle_online),
            ('GET', '/health', self.health_check),
        ]
        for method, path, handler in routes:
            full_path = f"{self.BASE_PATH}{path}"
            self.app.router.add_route(method, full_path, handler)
        logger.info(f"API routes registered: {len(routes)} endpoints")
    def _success_response(self, data: Any, status_code: int = HTTPStatus.OK) -> Response:
        """Create standardized success response"""
        return web.json_response({
            'success': True,
            'data': data
        }, status=status_code)
    def _error_response(self, message: str, status_code: int = HTTPStatus.BAD_REQUEST) -> Response:
        """Create standardized error response"""
        return web.json_response({
            'success': False,
            'error': message
        }, status=status_code)
    async def _authenticate(self, request: web_request.Request) -> int:
        """
        Authenticate API request and return user_id.
        Args:
            request: HTTP request object
        Returns:
            User ID if authentication successful
        Raises:
            APIError: If authentication fails
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise APIError(self.RESPONSES['unauthorized'], HTTPStatus.UNAUTHORIZED)
        api_key = auth_header[7:]
        user_id = await validate_api_key(api_key)
        if not user_id:
            raise APIError(self.RESPONSES['invalid_api_key'], HTTPStatus.UNAUTHORIZED)
        return user_id
    async def _get_user_accounts(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all active accounts for a user"""
        try:
            accounts = await mongodb.db.accounts.find({
                "user_id": user_id, 
                "is_active": True
            }).to_list(length=None)
            return [self._format_account_data(account) for account in accounts]
        except Exception as e:
            logger.error(f"Database error getting accounts for user {user_id}: {e}")
            raise APIError("Failed to retrieve accounts", HTTPStatus.INTERNAL_SERVER_ERROR)
    def _format_account_data(self, account: Dict[str, Any]) -> Dict[str, Any]:
        """Format account data for API response"""
        return {
            "id": str(account["_id"]),
            "name": account.get("name"),
            "phone": account.get("phone"),
            "is_active": account.get("is_active", True),
            "otp_destroyer_enabled": account.get("otp_destroyer_enabled", False),
            "online_maker_enabled": account.get("online_maker_enabled", False),
            "created_at": account.get("created_at"),
            "updated_at": account.get("updated_at")
        }
    async def health_check(self, request: web_request.Request) -> Response:
        """Health check endpoint"""
        return self._success_response({
            'status': 'healthy',
            'service': 'teleguard-api',
            'version': self.API_VERSION
        })
    async def list_accounts(self, request: web_request.Request) -> Response:
        """
        List all user accounts.
        GET /api/v1/accounts
        Authorization: Bearer <api_key>
        Returns:
            JSON response with user accounts
        """
        try:
            user_id = await self._authenticate(request)
            accounts = await self._get_user_accounts(user_id)
            return self._success_response({
                'accounts': accounts,
                'total': len(accounts)
            })
        except APIError:
            raise
        except Exception as e:
            logger.error(f"List accounts error for user {request.get('user_id', 'unknown')}: {e}")
            raise APIError(self.RESPONSES['internal_error'], HTTPStatus.INTERNAL_SERVER_ERROR)
    async def toggle_otp(self, request: web_request.Request) -> Response:
        """
        Toggle OTP destroyer for account.
        POST /api/v1/accounts/{account_id}/otp/toggle
        Authorization: Bearer <api_key>
        Body: {"enabled": true/false}
        Returns:
            JSON response with operation result
        """
        try:
            user_id = await self._authenticate(request)
            account_id = request.match_info["account_id"]
            try:
                data = await request.json()
            except json.JSONDecodeError:
                raise APIError("Invalid JSON in request body")
            enabled = data.get("enabled", False)
            if not self._is_otp_manager_available():
                raise APIError(self.RESPONSES['service_unavailable'], HTTPStatus.SERVICE_UNAVAILABLE)
            if enabled:
                success = await self.bot_manager.otp_destroyer.enable_otp_destroyer(user_id, account_id)
            else:
                success, _ = await self.bot_manager.otp_destroyer.disable_otp_destroyer(user_id, account_id)
            if success:
                return self._success_response({
                    'enabled': enabled,
                    'account_id': account_id,
                    'message': f"OTP destroyer {'enabled' if enabled else 'disabled'}"
                })
            else:
                raise APIError("Failed to toggle OTP destroyer")
        except APIError:
            raise
        except Exception as e:
            logger.error(f"Toggle OTP error: {e}")
            raise APIError(self.RESPONSES['internal_error'], HTTPStatus.INTERNAL_SERVER_ERROR)
    async def list_sessions(self, request: web_request.Request) -> Response:
        """
        List active sessions for account.
        GET /api/v1/accounts/{account_id}/sessions
        Authorization: Bearer <api_key>
        Returns:
            JSON response with active sessions
        """
        try:
            user_id = await self._authenticate(request)
            account_id = request.match_info["account_id"]
            if not self._is_client_manager_available():
                raise APIError(self.RESPONSES['service_unavailable'], HTTPStatus.SERVICE_UNAVAILABLE)
            success, sessions = await self.bot_manager.client_manager.list_active_sessions(user_id, account_id)
            if success:
                return self._success_response({
                    'sessions': sessions,
                    'account_id': account_id,
                    'total': len(sessions) if sessions else 0
                })
            else:
                raise APIError("Failed to list sessions")
        except APIError:
            raise
        except Exception as e:
            logger.error(f"List sessions error: {e}")
            raise APIError(self.RESPONSES['internal_error'], HTTPStatus.INTERNAL_SERVER_ERROR)
    async def toggle_online(self, request: web_request.Request) -> Response:
        """
        Toggle online maker for account.
        POST /api/v1/accounts/{account_id}/online/toggle
        Authorization: Bearer <api_key>
        Body: {"enabled": true/false, "interval": 3600}
        Returns:
            JSON response with operation result
        """
        try:
            user_id = await self._authenticate(request)
            account_id = request.match_info["account_id"]
            try:
                data = await request.json()
            except json.JSONDecodeError:
                raise APIError("Invalid JSON in request body")
            enabled = data.get("enabled", False)
            interval = data.get("interval", 3600)
            if not isinstance(interval, int) or interval < 60 or interval > 86400:
                raise APIError("Interval must be between 60 and 86400 seconds")
            if not self._is_client_manager_available():
                raise APIError(self.RESPONSES['service_unavailable'], HTTPStatus.SERVICE_UNAVAILABLE)
            success, message = await self.bot_manager.client_manager.toggle_online_maker(
                user_id, account_id, enabled, interval
            )
            if success:
                return self._success_response({
                    'enabled': enabled,
                    'interval': interval,
                    'account_id': account_id,
                    'message': message
                })
            else:
                raise APIError(message or "Failed to toggle online maker")
        except APIError:
            raise
        except Exception as e:
            logger.error(f"Toggle online error: {e}")
            raise APIError(self.RESPONSES['internal_error'], HTTPStatus.INTERNAL_SERVER_ERROR)
    def _is_otp_manager_available(self) -> bool:
        """Check if OTP manager is available"""
        return (
            hasattr(self.bot_manager, "otp_destroyer") and 
            self.bot_manager.otp_destroyer is not None
        )
    def _is_client_manager_available(self) -> bool:
        """Check if client manager is available"""
        return (
            hasattr(self.bot_manager, "client_manager") and 
            self.bot_manager.client_manager is not None
        )
