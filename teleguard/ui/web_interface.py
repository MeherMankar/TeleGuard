"""Basic Web Interface for TeleGuard"""

import logging
from pathlib import Path

from aiohttp import web, web_request

logger = logging.getLogger(__name__)


class WebInterface:
    """Basic web interface for TeleGuard management"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        """Setup web routes"""
        self.app.router.add_get("/", self.dashboard)
        self.app.router.add_get("/accounts", self.accounts_page)
        self.app.router.add_get("/health", self.health_check)

    async def dashboard(self, request: web_request.Request) -> web.Response:
        """Main dashboard"""
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>TeleGuard Dashboard</title></head>
        <body>
            <h1>TeleGuard Dashboard</h1>
            <nav>
                <a href="/accounts">Accounts</a> |
                <a href="/health">Health</a>
            </nav>
            <p>Telegram Account Manager with OTP Destroyer Protection</p>
        </body>
        </html>
        """
        return web.Response(text=html, content_type="text/html")

    async def accounts_page(self, request: web_request.Request) -> web.Response:
        """Accounts management page"""
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>TeleGuard - Accounts</title></head>
        <body>
            <h1>Account Management</h1>
            <p>Use the Telegram bot interface for account management.</p>
            <a href="/">← Back to Dashboard</a>
        </body>
        </html>
        """
        return web.Response(text=html, content_type="text/html")

    async def health_check(self, request: web_request.Request) -> web.Response:
        """Health check endpoint"""
        status = {
            "status": "healthy",
            "bot_running": hasattr(self.bot_manager, "bot")
            and self.bot_manager.bot is not None,
            "workers_active": len(getattr(self.bot_manager, "workers", {})),
        }
        return web.json_response(status)
