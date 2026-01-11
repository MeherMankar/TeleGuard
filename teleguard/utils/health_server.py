"""Unified health check system for cloud deployments"""

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from aiohttp import web

logger = logging.getLogger(__name__)


class HealthChecker:
    def __init__(self):
        self.checks = {
            "config": self._check_config,
            "memory": self._check_memory,
            "disk": self._check_disk,
        }

    async def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        status = {"timestamp": time.time(), "status": "healthy", "checks": {}}
        for check_name, check_func in self.checks.items():
            try:
                check_result = await check_func()
                status["checks"][check_name] = check_result
                if not check_result.get("healthy", True):
                    status["status"] = "unhealthy"
            except Exception as e:
                status["checks"][check_name] = {"healthy": False, "error": str(e)}
                status["status"] = "unhealthy"
        return status

    async def _check_config(self) -> Dict[str, Any]:
        """Check configuration files"""
        try:
            import os

            from dotenv import load_dotenv

            config_dir = Path("config")
            env_file = config_dir / ".env"
            if env_file.exists():
                load_dotenv(env_file)
            required_vars = ["API_ID", "API_HASH", "BOT_TOKEN"]
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            if missing_vars:
                return {
                    "healthy": False,
                    "error": f"Missing environment variables: {missing_vars}",
                }
            config_status = {
                "config_dir_exists": config_dir.exists(),
                "env_file_exists": env_file.exists(),
            }
            return {"healthy": True, "config_found": True, **config_status}
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def _check_memory(self) -> Dict[str, Any]:
        """Check memory usage"""
        try:
            import psutil

            memory = psutil.virtual_memory()
            return {
                "healthy": memory.percent < 90,
                "usage_percent": memory.percent,
                "available_mb": memory.available // 1024 // 1024,
            }
        except ImportError:
            return {"healthy": True, "note": "psutil not available"}
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def _check_disk(self) -> Dict[str, Any]:
        """Check disk usage"""
        try:
            import psutil

            disk = psutil.disk_usage(".")
            return {
                "healthy": disk.percent < 90,
                "usage_percent": disk.percent,
                "free_gb": disk.free // 1024 // 1024 // 1024,
            }
        except ImportError:
            return {"healthy": True, "note": "psutil not available"}
        except Exception as e:
            return {"healthy": False, "error": str(e)}


# Global health checker
health_checker = HealthChecker()


class HealthServer:
    """Simple health check server for cloud platforms"""

    def __init__(self, port=None):
        self.port = port or int(os.getenv("HEALTH_SERVER_PORT", "8000"))
        self.app = None
        self.runner = None
        self.site = None
        self.bot_status = "starting"

    async def health_handler(self, request):
        """Health check endpoint"""
        try:
            system_health = await health_checker.get_health_status()
            health_data = {
                "status": (
                    "healthy"
                    if self.bot_status == "running"
                    and system_health["status"] == "healthy"
                    else "unhealthy"
                ),
                "timestamp": datetime.utcnow().isoformat(),
                "service": "teleguard-bot",
                "bot_status": self.bot_status,
                "system_checks": system_health["checks"],
            }
        except Exception as e:
            health_data = {
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "teleguard-bot",
                "error": str(e),
            }
        return web.json_response(health_data)

    async def status_handler(self, request):
        """Status endpoint"""
        return web.json_response({"bot_status": self.bot_status})

    async def start(self):
        """Start the health server"""
        try:
            self.app = web.Application()
            self.app.router.add_get("/health", self.health_handler)
            self.app.router.add_get("/status", self.status_handler)
            self.app.router.add_get("/", self.health_handler)  # Root endpoint
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, "0.0.0.0", self.port)
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
