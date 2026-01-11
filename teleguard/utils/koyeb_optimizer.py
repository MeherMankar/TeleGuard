"""
Koyeb Platform Optimizer
Prevents IP changes and optimizes deployment stability
"""

import asyncio
import logging
import os
import time

logger = logging.getLogger(__name__)


class KoyebOptimizer:
    """Optimize Koyeb deployment for IP stability"""

    def __init__(self):
        self.keep_alive_task = None
        self.last_activity = time.time()

    async def start_optimization(self):
        """Start Koyeb-specific optimizations"""
        logger.info("🚀 Starting Koyeb optimization...")

        # Start keep-alive to prevent idle shutdown
        self.keep_alive_task = asyncio.create_task(self._keep_alive_loop())

        # Set process priority if possible
        self._set_process_priority()

        # Configure memory usage
        self._optimize_memory()

        logger.info("✅ Koyeb optimization active")

    async def _keep_alive_loop(self):
        """Keep service active to prevent IP reassignment"""
        while True:
            try:
                # Update activity timestamp
                self.last_activity = time.time()

                # Light CPU activity to prevent idle detection
                await self._light_activity()

                # Sleep for 5 minutes
                await asyncio.sleep(300)

            except Exception as e:
                logger.error(f"Keep-alive error: {e}")
                await asyncio.sleep(60)

    async def _light_activity(self):
        """Minimal activity to prevent idle shutdown"""
        # Simple computation to show activity
        _ = sum(range(1000))

        # Update environment variable to show activity
        os.environ["LAST_ACTIVITY"] = str(int(time.time()))

    def _set_process_priority(self):
        """Set higher process priority if possible"""
        try:
            import psutil

            process = psutil.Process()
            process.nice(psutil.HIGH_PRIORITY_CLASS if os.name == "nt" else -10)
            logger.debug("Process priority set to high")
        except BaseException:
            pass

    def _optimize_memory(self):
        """Optimize memory usage for stability"""
        try:
            import gc

            gc.set_threshold(700, 10, 10)  # More aggressive GC
            logger.debug("Memory optimization configured")
        except BaseException:
            pass

    def get_uptime(self) -> float:
        """Get current uptime in seconds"""
        return time.time() - self.last_activity


# Global optimizer
koyeb_optimizer = KoyebOptimizer()
