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

# Set UTF-8 encoding for Windows compatibility
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'

import asyncio
import logging
import warnings
import signal

# Suppress experimental async session warning from Telethon
warnings.filterwarnings("ignore", category=UserWarning, module="telethon")
import sys
import time
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import NoReturn
from aiohttp import web

# Ensure stdout/stderr use UTF-8 on Windows so logging can emit emojis
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    # Fall back silently if reconfigure not available or fails
    pass

# Monkey-patch StreamHandler.emit to guard against encoding errors (Windows consoles)
_orig_streamhandler_emit = logging.StreamHandler.emit

def _safe_streamhandler_emit(self, record):
    try:
        _orig_streamhandler_emit(self, record)
    except UnicodeEncodeError:
        try:
            msg = self.format(record)
            # Replace any non-encodable characters so write doesn't fail
            safe_msg = msg.encode(getattr(self.stream, 'encoding', 'utf-8'), errors='replace').decode(getattr(self.stream, 'encoding', 'utf-8'), errors='replace')
            stream = self.stream
            stream.write(safe_msg + self.terminator)
            self.flush()
        except Exception:
            try:
                self.handleError(record)
            except Exception:
                pass

logging.StreamHandler.emit = _safe_streamhandler_emit

try:
    from teleguard import AccountManager, __version__
    from teleguard.core.client_manager import get_client_manager
    from teleguard.core.task_queue import task_queue
    from teleguard.core.database_manager import init_database_manager, db_manager
    from teleguard.utils.health_server import health_checker
    from teleguard.utils.logger import get_logger, BotLogger
except ImportError as e:
    print(f"Failed to import TeleGuard modules: {e}")
    print(
        "💡 Please ensure all dependencies are installed: pip install -r requirements.txt"
    )
    sys.exit(1)

# Configure professional logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Enhanced logging setup with rotation and structured format

# Create formatters
detailed_formatter = logging.Formatter(
    '%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
simple_formatter = logging.Formatter(
    '%(levelname)s: %(message)s'
)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# File handler with rotation (10MB max, keep 5 files)
file_handler = RotatingFileHandler(
    log_dir / "teleguard.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding="utf-8"
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(detailed_formatter)

# Safe console handler that handles Unicode on Windows cp1252 consoles
class SafeConsoleHandler(logging.StreamHandler):
    """Console handler that safely handles Unicode characters on Windows"""
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            encoding = getattr(stream, 'encoding', 'utf-8') or 'utf-8'
            # Encode with 'replace' so unmappable chars become '?' instead of crashing
            safe_msg = msg.encode(encoding, errors='replace').decode(encoding, errors='replace')
            stream.write(safe_msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

console_handler = SafeConsoleHandler()

# Console shows only WARNING+ to keep output clean.
# All INFO detail goes to the rotating log file.
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(simple_formatter)

# Remove all existing handlers from root logger
root_logger.handlers.clear()

# Add handlers to root logger
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Configure teleguard loggers - remove their handlers and let them propagate to root
for logger_name in ["teleguard", "teleguard.core", "teleguard.handlers", "teleguard.utils"]:
    mod_logger = logging.getLogger(logger_name)
    mod_logger.handlers.clear()  # Remove any existing handlers
    mod_logger.setLevel(logging.INFO)
    mod_logger.propagate = True  # Use root logger's handlers

# Silence noisy external modules
for mod in ["telethon", "aiosqlite", "pymongo", "redis", "asyncio", "motor", "urllib3", "aiohttp"]:
    mod_logger = logging.getLogger(mod)
    mod_logger.handlers.clear()  # Remove any existing handlers
    mod_logger.setLevel(logging.ERROR)
    mod_logger.propagate = True  # Use root logger's handlers

# Get logger after configuration
logger = get_logger(__name__)
logger.debug("Logging system configured with UTF-8 support")




async def perform_startup_checks() -> bool:
    """Perform comprehensive startup health checks.

    Returns:
        bool: True if all checks pass, False otherwise
    """
    logger.info("🔍 Performing startup health checks...")

    try:
        health_status = await health_checker.get_health_status()

        if health_status.get("status") == "healthy":
            logger.info("✅ All health checks passed")
            return True
        else:
            logger.error("❌ Health checks failed: %s", health_status.get("issues", []))
            return False

    except Exception as e:
        logger.error("💥 Health check error: %s", str(e))
        return False


async def graceful_shutdown() -> None:
    """Perform graceful shutdown of all services."""
    logger.info("🔄 Initiating graceful shutdown...")

    shutdown_tasks = []
    start_time = time.time()

    try:
        # Cancel all pending tasks
        logger.info("🛑 Cancelling pending tasks...")
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        
        # Wait for tasks to cancel
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Stop task queue
        logger.info("⏹️ Stopping task queue...")
        shutdown_tasks.append(task_queue.stop())

        # Shutdown client manager
        logger.info("🔌 Shutting down client manager...")
        client_manager = get_client_manager()
        if client_manager:
            shutdown_tasks.append(client_manager.shutdown_all_managed_clients())
        else:
            logger.debug("No client manager to shutdown")

        # Wait for all shutdown tasks with timeout
        logger.info("⏳ Waiting for shutdown tasks to complete (10s timeout)...")
        await asyncio.wait_for(
            asyncio.gather(*shutdown_tasks, return_exceptions=True), timeout=10.0
        )

        elapsed = time.time() - start_time
        logger.info("✅ Graceful shutdown completed in %.2f seconds", elapsed)

    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        logger.warning("⚠️ Shutdown timeout reached after %.2f seconds, forcing exit", elapsed)
    except Exception as e:
        logger.error("💥 Error during shutdown: %s", str(e))
        logger.debug("Shutdown error details:", exc_info=True)

    finally:
        # Ensure logging is flushed
        logger.debug("💾 Flushing log handlers...")
        for handler in logging.getLogger().handlers:
            handler.flush()


def setup_signal_handlers() -> None:
    """Setup signal handlers for graceful shutdown."""

    def signal_handler(signum: int, _) -> NoReturn:
        signal_name = signal.Signals(signum).name
        logger.info("📶 Received %s signal, initiating shutdown", signal_name)
        print(f"\n📶 Received {signal_name} signal, shutting down gracefully...")

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


async def health_check(request):
    """Health check endpoint for cloud platforms"""
    client_ip = request.remote
    user_agent = request.headers.get('User-Agent', 'Unknown')
    
    logger.debug("🌡️ Health check from %s (UA: %s)", client_ip, user_agent)
    
    response_data = {
        "status": "healthy", 
        "service": "teleguard",
        "timestamp": time.time()
    }
    
    return web.json_response(response_data)


async def ip_status(request):
    """IP status endpoint for monitoring"""
    from teleguard.core.session_guardian import get_guardian
    guardian = get_guardian()
    
    if guardian:
        return web.json_response({
            "current_ip": guardian.current_ip,
            "ip_changes": guardian.ip_change_count,
            "stability": "high" if guardian.ip_change_count < 3 else "medium" if guardian.ip_change_count < 10 else "low",
            "last_check": guardian.last_ip_check
        })
    
    return web.json_response({"status": "guardian_not_initialized"})

async def start_web_server():
    """Start enhanced web server with IP monitoring"""
    logger.info("🌐 Setting up enhanced health check server...")
    
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_get("/ip", ip_status)
    app.router.add_get("/", health_check)
    logger.debug("🔗 Enhanced routes configured")
    
    port = int(os.getenv("PORT", 8000))
    logger.info("🔌 Attempting to start web server on port %d", port)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Try multiple ports if the default is in use
    ports_tried = []
    for attempt_port in [port, port + 1, port + 2, 8001, 8080, 3000]:
        try:
            site = web.TCPSite(runner, "0.0.0.0", attempt_port)
            await site.start()
            print(f"Health server running on port {attempt_port}")
            logger.info("✅ Health check server started successfully on port %d", attempt_port)
            return runner
        except OSError as e:
            ports_tried.append(attempt_port)
            if "10048" in str(e) or "Address already in use" in str(e):
                logger.debug("🚫 Port %d in use, trying next...", attempt_port)
                continue
            logger.error("💥 Unexpected error on port %d: %s", attempt_port, str(e))
            raise
    
    logger.warning("⚠️ Could not start health server - all ports in use: %s", ports_tried)
    return runner


def print_startup_banner() -> None:
    """Print professional startup banner."""
    try:
        # Dynamically center version in the banner slot (12 characters wide)
        banner = f"""
╔══════════════════════════════════════════════════════════════╗
║                      TeleGuard v{__version__:<12}                ║
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
        print(f"           TeleGuard v{__version__}")
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
    # Force rebuild - fixed indentation issue
    startup_time = time.time()
    logger.debug("TeleGuard application starting up")
    
    try:
        # Print startup banner
        print_startup_banner()
        logger.debug("Startup banner displayed")

        # Setup signal handlers
        setup_signal_handlers()
        logger.debug("Signal handlers configured")
        
        # Setup global error handler
        BotLogger.setup_global_error_handler()
        logger.debug("Global error handler configured")

        # Database initialization
        logger.debug("Initializing database connections")
        print("Connecting to database...")
        await init_database_manager()
        
        health = await db_manager.health_check()
        if health.get('mongodb') and health.get('redis'):
            print("Database connected successfully")
            logger.info("✅ Database health check passed - MongoDB: %s, Redis: %s", 
                       health.get('mongodb'), health.get('redis'))
        else:
            logger.warning("⚠️ Database health check issues: %s", health)
        
        # Start web server
        logger.debug("Starting health check web server")
        await start_web_server()
        logger.debug("Web server started")
        
        # Initialize Koyeb optimization
        if os.getenv('KOYEB_OPTIMIZATION_ENABLED', 'true').lower() == 'true':
            logger.debug("Starting Koyeb optimization")
            from teleguard.utils.koyeb_optimizer import koyeb_optimizer
            await koyeb_optimizer.start_optimization()
        
        # Initialize session guardian with IP monitoring
        logger.debug("Initializing session guardian")
        from teleguard.core.session_guardian import init_guardian
        from teleguard.utils.guardian_config import load_guardian_config
        guardian_config = load_guardian_config()
        g = init_guardian(guardian_config)
        # Start IP monitoring background task (requires running event loop)
        await g.start_monitoring()
        logger.debug("Session guardian active")

        print("\n" + "="*50)
        logger.debug("Initializing TeleGuard bot")

        # Start bot without timeout on cloud platforms
        try:
            async with AccountManager() as bot:
                startup_elapsed = time.time() - startup_time
                koyeb_status = " + Koyeb optimized" if os.getenv('KOYEB_OPTIMIZATION_ENABLED', 'true').lower() == 'true' else ""
                print(f"\nTeleGuard is ready! 🌐 Smart IP monitoring active{koyeb_status}")
                logger.info("✨ TeleGuard bot ready! Startup completed in %.2f seconds", startup_elapsed)
                
                logger.debug("Starting bot main loop")
                await bot.run()
        except Exception as e:
            # Handle rate limits and other startup errors
            logger.error("🚨 Bot startup error: %s", str(e))
            if "FloodWaitError" in str(e) or "wait of" in str(e):
                import re
                wait_match = re.search(r'wait of (\d+) seconds', str(e))
                if wait_match:
                    wait_time = int(wait_match.group(1))
                    logger.info("⏳ Waiting %d seconds due to rate limit...", wait_time)
                    print(f"\nTelegram rate limit - waiting {wait_time} seconds...")
                    print("📝 This is normal, the bot will start automatically")
                    
                    # Keep health server running during wait
                    await asyncio.sleep(min(wait_time, 300))  # Cap at 5 minutes
                    logger.info("✅ Rate limit wait completed, retrying...")
                    
                    print("Retrying startup...")
                    try:
                        async with AccountManager() as bot:
                            logger.info("✅ Bot started successfully after rate limit")
                            print("Bot started successfully after rate limit")
                            await bot.run()
                    except Exception as retry_error:
                        logger.error("💥 Retry failed: %s", str(retry_error))
                        print(f"Retry failed: {retry_error}")
                        # Keep health server running
                        while True:
                            await asyncio.sleep(60)
                else:
                    logger.error("🚨 Could not parse wait time from rate limit error")
                    raise e
            else:
                logger.error("💥 Unhandled startup error: %s", str(e))
                logger.debug("Startup error details:", exc_info=True)
                raise e

    except KeyboardInterrupt:
        logger.debug("Keyboard interrupt received")
        print("\nShutting down TeleGuard...")
        await graceful_shutdown()
        sys.exit(0)

    except ImportError as e:
        logger.error("📦 Missing dependencies: %s", str(e))
        print(f"\nMissing dependencies: {e}")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)

    except FileNotFoundError as e:
        logger.error("📁 Configuration file not found: %s", str(e))
        print(f"\nConfiguration error: {e}")
        print("Ensure .env file exists with required variables")
        sys.exit(1)

    except Exception as e:
        total_runtime = time.time() - startup_time
        logger.error("💥 Fatal application error after %.2f seconds: %s", total_runtime, str(e))
        logger.error("📋 Full traceback: %s", traceback.format_exc())
        print(f"\n🚨 Fatal error occurred: {e}")
        print("📝 Check logs/teleguard.log for detailed error information")
        print("🆘 Need help? Contact: https://t.me/ContactXYZrobot")
        
        try:
            await BotLogger.log_error("Fatal Error", str(e), context=f"main.py after {total_runtime:.2f}s")
        except Exception:
            pass

        try:
            await graceful_shutdown()
        except Exception as shutdown_error:
            logger.error("💥 Shutdown error: %s", str(shutdown_error))
        
        # Exit immediately on fatal startup errors
        print("\n⚠️ Bot process will exit due to fatal error")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\nCritical error: {e}")
        sys.exit(1)

