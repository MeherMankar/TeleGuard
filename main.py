#!/usr/bin/env python3
"""TeleGuard - Professional Telegram Account Manager

A secure, professional-grade Telegram bot for managing multiple user accounts
with advanced OTP destroyer protection against unauthorized access attempts.

Developed by:
- @Meher_Mankar (https://t.me/Meher_Mankar)
- @Gutkesh (https://t.me/Gutkesh)

Repository: https://github.com/MeherMankar/TeleGuard
Support: https://t.me/ContactXYZrobot
Documentation: https://github.com/MeherMankar/TeleGuard/wiki

License: MIT
Version: 2.0.0
"""

import asyncio
import logging
import os
import signal
import sys
import time
import traceback
from pathlib import Path
from typing import NoReturn

try:
    from teleguard import AccountManager
    from teleguard.core.async_client_manager import client_manager
    from teleguard.core.task_queue import task_queue
    from teleguard.github_db import GitHubJSONDB
    from teleguard.local_db import LocalJSONDB
    from teleguard.utils.health_check import health_checker
    from teleguard.utils.logger import get_logger
except ImportError as e:
    print(f"❌ Failed to import TeleGuard modules: {e}")
    print(
        "💡 Please ensure all dependencies are installed: pip install -r config/requirements.txt"
    )
    sys.exit(1)

# Configure professional logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / "teleguard.log", encoding="utf-8"),
    ],
)

# Suppress noisy third-party logs
logging.getLogger("telethon").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)

logger = get_logger(__name__)

# Global database instance
db = None


def initialize_database():
    """Initialize database backend (GitHub or local)"""
    global db

    if os.getenv("USE_GITHUB_DB", "false").lower() == "true":
        logger.info("Initializing GitHub database...")

        # Validate required environment variables
        required_vars = ["DB_GITHUB_OWNER", "DB_GITHUB_REPO", "GITHUB_TOKEN"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            logger.error("Missing GitHub DB variables", missing=missing_vars)
            logger.info("Set USE_GITHUB_DB=false to use local database")
            sys.exit(1)

        db = GitHubJSONDB(
            owner=os.getenv("DB_GITHUB_OWNER"),
            repo=os.getenv("DB_GITHUB_REPO"),
            token=os.getenv("GITHUB_TOKEN"),
            branch=os.getenv("DB_GITHUB_BRANCH", "db-live"),
            write_allowed=os.getenv("DB_WRITE_ALLOWED", "false").lower() == "true",
        )

        # Test connection only
        try:
            rate_limit = db._get_rate_limit()
            logger.info(
                "GitHub API connected",
                remaining=rate_limit.remaining,
                limit=rate_limit.limit,
            )
            logger.info(
                "GitHub database ready", branch=db.branch, repo=f"{db.owner}/{db.repo}"
            )

        except Exception as e:
            logger.error("GitHub API connection failed", error=str(e))
            logger.info("Falling back to local database")
            db = LocalJSONDB(base_path=".", write_allowed=True)
    else:
        logger.info("Using local database...")
        db = LocalJSONDB(base_path=os.getenv("LOCAL_DB_PATH", "."), write_allowed=True)

    return db


async def perform_startup_checks() -> bool:
    """Perform comprehensive startup health checks.

    Returns:
        bool: True if all checks pass, False otherwise
    """
    logger.info("Performing startup health checks...")

    try:
        health_status = await health_checker.get_health_status()

        if health_status.get("status") == "healthy":
            logger.info("All health checks passed")
            return True
        else:
            logger.error("Health checks failed", issues=health_status.get("issues", []))
            return False

    except Exception as e:
        logger.error("Health check error", error=str(e))
        return False


async def graceful_shutdown() -> None:
    """Perform graceful shutdown of all services."""
    logger.info("Initiating graceful shutdown...")

    shutdown_tasks = []

    try:
        # Stop task queue
        logger.info("Stopping task queue...")
        shutdown_tasks.append(task_queue.stop())

        # Shutdown client manager
        logger.info("Shutting down client manager...")
        shutdown_tasks.append(client_manager.shutdown())

        # Wait for all shutdown tasks with timeout
        await asyncio.wait_for(
            asyncio.gather(*shutdown_tasks, return_exceptions=True), timeout=30.0
        )

        logger.info("Graceful shutdown completed")

    except asyncio.TimeoutError:
        logger.warning("Shutdown timeout reached, forcing exit")
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))

    finally:
        # Ensure logging is flushed
        for handler in logging.getLogger().handlers:
            handler.flush()


def setup_signal_handlers() -> None:
    """Setup signal handlers for graceful shutdown."""

    def signal_handler(signum: int, frame) -> NoReturn:
        signal_name = signal.Signals(signum).name
        logger.info("Received signal, initiating shutdown", signal=signal_name)

        # Create shutdown task
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(graceful_shutdown())

        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

    if hasattr(signal, "SIGHUP"):  # Unix only
        signal.signal(signal.SIGHUP, signal_handler)


def print_startup_banner() -> None:
    """Print professional startup banner."""
    try:
        banner = """
╔══════════════════════════════════════════════════════════════╗
║                      TeleGuard v1.0.0                        ║
║              Professional Telegram Account Manager           ║
╠══════════════════════════════════════════════════════════════╣
║  OTP Destroyer Protection      Multi-Account Support         ║
║  Military-Grade Encryption     Advanced Automation           ║
║  Health Monitoring             Activity Simulation           ║
╠══════════════════════════════════════════════════════════════╣
║  Developers: @Meher_Mankar & @Gutkesh                        ║
║  GitHub: github.com/MeherMankar/TeleGuard                    ║
║  Support: t.me/ContactXYZrobot                               ║
║  Docs: github.com/MeherMankar/TeleGuard/wiki                 ║
╚══════════════════════════════════════════════════════════════╝
"""
        print(banner)
    except UnicodeEncodeError:
        # Fallback for systems with encoding issues
        print("=" * 60)
        print("           TeleGuard v2.0.0")
        print("    Professional Telegram Account Manager")
        print("=" * 60)
        print("Features:")
        print("- OTP Destroyer Protection")
        print("- Multi-Account Support")
        print("- Military-Grade Encryption")
        print("- Advanced Automation")
        print("=" * 60)
        print("Developers: @Meher_Mankar & @Gutkesh")
        print("GitHub: github.com/MeherMankar/TeleGuard")
        print("Support: t.me/ContactXYZrobot")
        print("=" * 60)


async def main() -> None:
    """Main application entry point with comprehensive error handling."""
    try:
        # Print startup banner
        print_startup_banner()

        # Setup signal handlers
        setup_signal_handlers()

        # Initialize database
        db_instance = initialize_database()

        # Set database reference for helpers
        from teleguard import db_helpers

        db_helpers.db = db_instance

        # Perform startup health checks
        if not await perform_startup_checks():
            logger.error("Startup checks failed, exiting...")
            sys.exit(1)

        # Initialize and start the bot
        logger.info("Health checks passed - Starting TeleGuard Bot...")

        async with AccountManager() as bot:
            logger.info("TeleGuard Bot successfully started")
            print("\nBot is running! Press Ctrl+C to stop.\n")

            # Run until disconnected
            await bot.bot.run_until_disconnected()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        await graceful_shutdown()

    except ImportError as e:
        logger.error("Import error", error=str(e))
        print(f"\nMissing dependencies: {e}")
        print("Run: pip install -r config/requirements.txt")
        sys.exit(1)

    except FileNotFoundError as e:
        logger.error("Configuration file not found", error=str(e))
        print(f"\nConfiguration error: {e}")
        print("Ensure config/.env file exists with required variables")
        sys.exit(1)

    except Exception as e:
        logger.error("Fatal error", error=str(e))
        logger.error("Traceback", traceback=traceback.format_exc())

        print(f"\nFatal error occurred: {e}")
        print("Check logs/teleguard.log for detailed error information")
        print("Need help? Contact: https://t.me/ContactXYZrobot")

        await graceful_shutdown()
        sys.exit(1)

    finally:
        logger.info("TeleGuard shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\nCritical error: {e}")
        sys.exit(1)
