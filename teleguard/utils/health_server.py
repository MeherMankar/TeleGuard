"""Simple HTTP health check server for cloud deployments"""

import asyncio
import logging
from aiohttp import web
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class HealthServer:
    """Simple health check server for cloud platforms"""
    
    def __init__(self, port=8000):
        self.port = port
        self.app = None
        self.runner = None
        self.site = None
        self.bot_status = "starting"
        
    async def health_handler(self, request):
        """Health check endpoint"""
        health_data = {
            "status": "healthy" if self.bot_status == "running" else "starting",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "teleguard-bot"
        }
        return web.json_response(health_data)
    
    async def status_handler(self, request):
        """Status endpoint"""
        return web.json_response({"bot_status": self.bot_status})
    
    async def start(self):
        """Start the health server"""
        try:
            self.app = web.Application()
            self.app.router.add_get('/health', self.health_handler)
            self.app.router.add_get('/status', self.status_handler)
            self.app.router.add_get('/', self.health_handler)  # Root endpoint
            
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
            await self.site.start()
            
            logger.info(f"Health server started on port {self.port}")
            
        except Exception as e:
            logger.error(f"Failed to start health server: {e}")
    
    async def stop(self):
        """Stop the health server"""
        try:
            if self.site:
                await self.site.stop()
            if self.runner:
                await self.runner.cleanup()
            logger.info("Health server stopped")
        except Exception as e:
            logger.error(f"Error stopping health server: {e}")
    
    def set_bot_status(self, status):
        """Update bot status"""
        self.bot_status = status
        logger.info(f"Bot status updated to: {status}")

# Global health server instance
health_server = HealthServer()