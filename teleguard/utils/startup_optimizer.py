"""Startup optimization for cloud deployments"""

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

class StartupOptimizer:
    """Optimizes startup for cloud platforms like Koyeb"""
    
    def __init__(self):
        self.is_cloud_deployment = self._detect_cloud_deployment()
        self.startup_timeout = 45  # seconds
        
    def _detect_cloud_deployment(self) -> bool:
        """Detect if running on cloud platform"""
        cloud_indicators = [
            "KOYEB_DEPLOYMENT",
            "HEROKU_APP_NAME", 
            "RAILWAY_ENVIRONMENT",
            "RENDER_SERVICE_NAME"
        ]
        return any(os.getenv(indicator) for indicator in cloud_indicators)
    
    async def optimize_startup(self, startup_func, *args, **kwargs):
        """Run startup function with timeout for cloud deployments"""
        try:
            if self.is_cloud_deployment:
                logger.info(f"Cloud deployment detected, using {self.startup_timeout}s timeout")
                return await asyncio.wait_for(
                    startup_func(*args, **kwargs),
                    timeout=self.startup_timeout
                )
            else:
                return await startup_func(*args, **kwargs)
        except asyncio.TimeoutError:
            logger.warning(f"Startup timeout after {self.startup_timeout}s")
            if self.is_cloud_deployment:
                return None
            raise
        except Exception as e:
            logger.error(f"Startup error: {e}")
            if self.is_cloud_deployment:
                logger.info("Continuing with minimal startup for cloud deployment")
                return None
            raise

startup_optimizer = StartupOptimizer()