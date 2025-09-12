"""System health monitoring"""

import asyncio
import time
from pathlib import Path
from typing import Any, Dict


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

            # Check for essential environment variables
            required_vars = ["API_ID", "API_HASH", "BOT_TOKEN"]
            missing_vars = [var for var in required_vars if not os.getenv(var)]

            if missing_vars:
                return {
                    "healthy": False,
                    "error": f"Missing environment variables: {missing_vars}",
                }

            # Check if config files exist (optional for cloud deployments)
            config_dir = Path("config")
            env_file = config_dir / ".env"

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
