"""
Session Guardian - Robust session protection and anti-abuse system for Telegram userbots
Prevents AUTH_KEY_UNREGISTERED and implements comprehensive safety measures.
"""

import asyncio
import json
import logging
import os
import platform
import random
import sys
import threading
import time
import traceback
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Optional

from telethon.tl.functions.contacts import GetContactsRequest

# Platform-specific imports
try:
    if platform.system() == "Windows":
        import msvcrt
    else:
        import fcntl
except ImportError:
    # Cloud platforms may not have fcntl
    fcntl = None
    msvcrt = None

logger = logging.getLogger(__name__)


@dataclass
class ActionLog:
    """Single action log entry"""

    timestamp: str
    action: str
    target: str
    success: bool
    error: Optional[str] = None
    stack_trace: Optional[str] = None


class TokenBucket:
    """Token bucket rate limiter with jitter"""

    def __init__(self, max_tokens: int, refill_rate: float):
        self.max_tokens = max_tokens
        self.tokens = max_tokens
        self.refill_rate = refill_rate
        self.last_refill = time.time()
        self.lock = threading.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """Acquire tokens with async support"""
        with self.lock:
            now = time.time()
            # Refill tokens
            elapsed = now - self.last_refill
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    async def wait_for_tokens(self, tokens: int = 1):
        """Wait until tokens are available"""
        while not await self.acquire(tokens):
            # Add jitter to prevent thundering herd
            await asyncio.sleep(random.uniform(0.1, 0.5))


class SessionLock:
    """Cross-platform session file locking"""

    def __init__(self, session_path: str):
        self.session_path = Path(session_path)
        self.lock_path = self.session_path.with_suffix(".lock")
        self.lock_file = None
        self.locked = False

    def acquire(self) -> bool:
        """Acquire exclusive lock on session file"""
        try:
            self.lock_file = open(self.lock_path, "w")

            if platform.system() == "Windows" and msvcrt:
                # Windows file locking
                try:
                    msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    self.locked = True
                except OSError:
                    return False
            elif fcntl:
                # Unix file locking
                try:
                    fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.locked = True
                except OSError:
                    return False
            else:
                # Fallback for cloud platforms without file locking
                self.locked = True

            # Write process info to lock file
            lock_info = {
                "pid": os.getpid(),
                "hostname": platform.node(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_path": str(self.session_path),
            }
            self.lock_file.write(json.dumps(lock_info, indent=2))
            self.lock_file.flush()

            logger.info(f"Acquired session lock: {self.lock_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to acquire session lock: {e}")
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
            return False

    def release(self):
        """Release session lock"""
        if self.locked and self.lock_file:
            try:
                if platform.system() == "Windows" and msvcrt:
                    msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                elif fcntl:
                    fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)

                self.lock_file.close()
                self.lock_file = None

                # Remove lock file
                if self.lock_path.exists():
                    self.lock_path.unlink()

                self.locked = False
                logger.info(f"Released session lock: {self.lock_path}")

            except Exception as e:
                logger.error(f"Error releasing session lock: {e}")

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(
                f"Cannot acquire session lock. Another process may be using {
                    self.session_path}"
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class SessionGuardian:
    """Main session protection and monitoring system"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.action_history: Deque[ActionLog] = deque(maxlen=100)
        self.session_lock: Optional[SessionLock] = None
        self.rate_limiters: Dict[str, TokenBucket] = {}
        self.is_shutdown = False
        self.last_summary_time = time.time()
        self.current_ip = None
        self.last_ip_check = 0
        self.ip_change_count = 0

        # Initialize rate limiters
        self._init_rate_limiters()

        # Setup logging
        self._setup_logging()

        # IP monitoring will be started via start_monitoring() from an async context

    async def start_monitoring(self):
        """Start background monitoring tasks (call from async context)"""
        asyncio.create_task(self._start_ip_monitoring())

    async def _start_ip_monitoring(self):
        """Start continuous IP monitoring"""
        logger.info("Starting IP monitoring service")

        while not self.is_shutdown:
            try:
                await self.check_ip_change()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"IP monitoring error: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    def _init_rate_limiters(self):
        """Initialize rate limiters for different operations"""
        limits = self.config.get("rate_limits", {})

        self.rate_limiters = {
            "message": TokenBucket(
                max_tokens=limits.get("messages_per_minute", 20),
                refill_rate=limits.get("messages_per_minute", 20) / 60.0,
            ),
            "join": TokenBucket(
                max_tokens=limits.get("joins_per_hour", 10),
                refill_rate=limits.get("joins_per_hour", 10) / 3600.0,
            ),
            "forward": TokenBucket(
                max_tokens=limits.get("forwards_per_minute", 10),
                refill_rate=limits.get("forwards_per_minute", 10) / 60.0,
            ),
            "bulk": TokenBucket(
                max_tokens=limits.get("bulk_per_minute", 5),
                refill_rate=limits.get("bulk_per_minute", 5) / 60.0,
            ),
            "warmup": TokenBucket(
                max_tokens=10,
                refill_rate=10 / 60.0,  # 10 per minute for warmup activities
            ),
        }

    def _setup_logging(self):
        """Setup rotating file logging"""
        from logging.handlers import RotatingFileHandler

        log_dir = Path(self.config.get("log_dir", "logs"))
        log_dir.mkdir(exist_ok=True)

        # Setup rotating file handler
        file_handler = RotatingFileHandler(
            log_dir / "session_guardian.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=7,
            encoding="utf-8",
        )

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)

        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        root_logger.setLevel(logging.INFO)

    async def acquire_session_lock(self, session_path: str) -> bool:
        """Acquire exclusive lock on session file"""
        try:
            self.session_lock = SessionLock(session_path)
            return self.session_lock.acquire()
        except Exception as e:
            await self._send_alert(
                f"🔒 **Session Lock Failed**\n\n"
                f"Cannot acquire lock for session: {session_path}\n"
                f"Error: {e}\n\n"
                f"Another process may be using this session.\n"
                f"Check for running instances and try again."
            )
            return False

    def release_session_lock(self):
        """Release session lock"""
        if self.session_lock:
            self.session_lock.release()
            self.session_lock = None

    async def rate_limit(self, operation: str, tokens: int = 1):
        """Apply rate limiting to operations"""
        if operation in self.rate_limiters:
            await self.rate_limiters[operation].wait_for_tokens(tokens)

            # Add randomized delay to prevent deterministic patterns
            jitter = random.uniform(0.1, 0.8)
            await asyncio.sleep(jitter)

    def log_action(
        self, action: str, target: str, success: bool = True, error: str = None
    ):
        """Log an action for monitoring"""
        log_entry = ActionLog(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action=action,
            target=target,
            success=success,
            error=error,
            stack_trace=traceback.format_exc() if error else None,
        )

        self.action_history.append(log_entry)

        # Log to file
        if success:
            logger.info(f"Action: {action} -> {target}")
        else:
            logger.error(f"Action failed: {action} -> {target}: {error}")

    def is_auth_key_error(self, exception: Exception) -> bool:
        """Detect AUTH_KEY_UNREGISTERED errors across different libraries"""
        error_str = str(exception).lower()
        error_code = getattr(exception, "code", None)

        # Check for specific error patterns
        auth_key_patterns = [
            "auth_key_unregistered",
            "auth_key_duplicated",
            "session_revoked",
            "user_deactivated",
        ]

        # Check error code
        if error_code in [401, 406]:
            return True

        # Check error message
        for pattern in auth_key_patterns:
            if pattern in error_str:
                return True

        # Library-specific checks
        exception_name = exception.__class__.__name__

        # Telethon specific
        if exception_name in ["AuthKeyUnregisteredError", "SessionRevokedError"]:
            return True

        # Pyrogram specific
        if exception_name in ["AuthKeyUnregistered", "SessionRevoked"]:
            return True

        return False

    async def handle_auth_key_error(
        self, exception: Exception, context: Dict[str, Any] = None
    ):
        """Handle AUTH_KEY_UNREGISTERED with safe shutdown and alerts"""
        logger.critical(f"AUTH_KEY_UNREGISTERED detected: {exception}")

        # Mark for shutdown
        self.is_shutdown = True

        # Prepare detailed error report
        error_report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hostname": platform.node(),
            "pid": os.getpid(),
            "exception": str(exception),
            "exception_type": exception.__class__.__name__,
            "context": context or {},
            "last_actions": [
                asdict(action) for action in list(self.action_history)[-10:]
            ],
        }

        # Log detailed error
        logger.critical(
            f"Session revocation details: {json.dumps(error_report, indent=2)}"
        )

        # Send alert to admin
        await self._send_critical_alert(error_report)

        # Stop all operations
        await self._emergency_shutdown()

    async def _send_critical_alert(self, error_report: Dict[str, Any]):
        """Send critical alert to admin via Telegram"""
        try:
            # Get phone number from database or session
            phone = await self._get_phone_number()

            message = (
                f"🚨 **CRITICAL: Session Revoked**\n\n"
                f"📱 **Phone:** {phone}\n"
                f"🕐 **Time:** {error_report['timestamp']}\n"
                f"🖥️ **Host:** {error_report['hostname']}\n"
                f"🆔 **PID:** {error_report['pid']}\n"
                f"❌ **Error:** {error_report['exception']}\n\n"
                f"**🔧 Manual Recovery Required:**\n"
                f"1. Stop all bot processes\n"
                f"2. Delete session file: `rm *.session`\n"
                f"3. Run: `python main.py` to re-authenticate\n"
                f"4. Check for conflicting processes\n\n"
                f"**📊 Last Actions:**\n"
            )

            # Add last actions
            for action in error_report["last_actions"][-5:]:
                status = "✅" if action["success"] else "❌"
                message += f"{status} {action['action']} -> {action['target']}\n"

            message += (
                "\n**⚠️ DO NOT auto-restart until manual recovery is complete.**\n"
                "Check logs for more details: `tail -f logs/session_guardian.log`"
            )

            await self._send_alert(message)

        except Exception as e:
            logger.error(f"Failed to send critical alert: {e}")

    async def _send_alert(self, message: str):
        """Send alert message to configured Telegram channel"""
        try:
            log_config = self.config.get("telegram_logging", {})
            bot_token = log_config.get("bot_token")
            chat_id = log_config.get("chat_id")

            if not bot_token or not chat_id:
                logger.warning("Telegram logging not configured, cannot send alert")
                return

            # Use simple HTTP request to avoid session conflicts
            import aiohttp

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        logger.info("Alert sent successfully")
                    else:
                        logger.error(f"Failed to send alert: {response.status}")

        except Exception as e:
            logger.error(f"Error sending alert: {e}")

    async def _emergency_shutdown(self):
        """Emergency shutdown procedure"""
        logger.critical("Initiating emergency shutdown...")

        # Release session lock
        self.release_session_lock()

        # Cancel all running tasks
        tasks = [task for task in asyncio.all_tasks() if not task.done()]
        for task in tasks:
            task.cancel()

        # Wait for tasks to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.critical("Emergency shutdown complete")

        # Exit process
        sys.exit(1)

    async def exponential_backoff(
        self,
        func: Callable,
        *args,
        max_attempts: int = 5,
        base_delay: float = 0.5,
        **kwargs,
    ):
        """Execute function with exponential backoff and jitter"""
        for attempt in range(max_attempts):
            try:
                result = await func(*args, **kwargs)
                return result

            except Exception as e:
                # Check if this is an auth key error
                if self.is_auth_key_error(e):
                    await self.handle_auth_key_error(
                        e,
                        {
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "args": str(args)[:200],
                        },
                    )
                    return None

                # For other errors, retry with backoff
                if attempt == max_attempts - 1:
                    self.log_action(
                        f"retry_failed_{func.__name__}", str(args)[:50], False, str(e)
                    )
                    raise e

                # Calculate delay with jitter
                delay = base_delay * (2**attempt)
                jitter = random.uniform(0, delay * 0.1)
                total_delay = delay + jitter

                logger.warning(
                    f"Attempt {
                        attempt +
                        1} failed for {
                        func.__name__}: {e}. Retrying in {
                        total_delay:.2f}s"
                )
                await asyncio.sleep(total_delay)

    async def _get_phone_number(self) -> str:
        """Get phone number from database or active session"""
        try:
            # Try to get from database first
            from ..core.mongo_database import mongodb

            account = await mongodb.db.accounts.find_one({"is_active": True})
            if account and account.get("phone"):
                return account["phone"]

            # Fallback to unknown if no active accounts
            return "Unknown"

        except Exception as e:
            logger.warning(f"Could not retrieve phone number: {e}")
            return "Unknown"

    async def check_ip_change(self):
        """Advanced IP monitoring with multiple providers and geolocation"""
        ip_config = self.config.get("ip_monitoring", {})
        if not ip_config.get("enabled", True):
            return

        current_time = time.time()
        check_interval = ip_config.get("check_interval", 300)
        if current_time - self.last_ip_check < check_interval:
            return

        self.last_ip_check = current_time
        new_ip = await self._get_ip_with_fallback()

        if new_ip and self.current_ip and self.current_ip != new_ip:
            self.ip_change_count += 1
            await self._handle_ip_change(self.current_ip, new_ip)

        if new_ip:
            self.current_ip = new_ip

    async def _get_ip_with_fallback(self) -> Optional[str]:
        """Get IP with multiple providers and geolocation data"""
        providers = [
            ("https://api.ipify.org?format=json", "ip"),
            ("https://httpbin.org/ip", "origin"),
            ("https://api.myip.com", "ip"),
            ("https://ipapi.co/json/", "ip"),
        ]

        import aiohttp

        for url, key in providers:
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            ip = data.get(key)
                            if ip and "," in ip:
                                # httpbin can return multiple IPs (e.g., if behind proxy)
                                ip = ip.split(",")[0].strip()
                            return ip
            except BaseException:
                continue
        return None

    async def _handle_ip_change(self, old_ip: str, new_ip: str):
        """Advanced IP change handling with geolocation and smart warmup"""
        logger.warning(f"IP changed: {old_ip} -> {new_ip} (#{self.ip_change_count})")

        # Get geolocation data
        geo_data = await self._get_geolocation(new_ip)

        # Smart notification
        if self.config.get("ip_monitoring", {}).get("notify_on_change", True):
            location = (
                f"{geo_data.get('city',
                                'Unknown')}, {geo_data.get('country',
                                                           'Unknown')}"
                if geo_data
                else "Unknown"
            )
            message = (
                f"🌐 **IP Changed** (#{self.ip_change_count})\n\n"
                f"📍 **Location:** {location}\n"
                f"🔄 **Old:** {old_ip}\n"
                f"🆕 **New:** {new_ip}\n"
                f"⏰ **Time:** {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}\n\n"
                f"🔧 **Auto-Recovery Active**"
            )
            await self._send_alert(message)

        # Intelligent warmup based on change frequency
        await self._smart_session_warmup()

    async def _get_geolocation(self, ip: str) -> Dict[str, Any]:
        """Get geolocation data for IP"""
        try:
            import aiohttp

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=3)
            ) as session:
                async with session.get(f"https://ipapi.co/{ip}/json/") as response:
                    if response.status == 200:
                        return await response.json()
        except BaseException:
            pass
        return {}

    async def _smart_session_warmup(self):
        """Intelligent session warmup based on change frequency"""
        try:
            # Adaptive delay based on change frequency
            if self.ip_change_count > 5:
                delay = 60  # More aggressive for frequent changes
            elif self.ip_change_count > 2:
                delay = 30
            else:
                delay = 15

            await asyncio.sleep(delay)
            self.log_action("smart_warmup", f"change_{self.ip_change_count}", True)

            # Progressive warmup activities
            await self._progressive_activity()

            logger.info(f"Smart warmup completed (change #{self.ip_change_count})")

        except Exception as e:
            logger.error(f"Smart warmup failed: {e}")
            self.log_action("smart_warmup", "failed", False, str(e))

    async def _progressive_activity(self):
        """Progressive warmup with human-like patterns"""
        try:
            from ..core.bot_manager import bot_manager

            if not bot_manager or not bot_manager.user_clients:
                return

            # Flatten the nested {user_id: {name: client}} dict to get first client
            client = next(
                (c for clients in bot_manager.user_clients.values() for c in clients.values()),
                None,
            )
            if not client:
                return

            # Progressive operations with realistic delays
            activities = [
                ("ping", lambda: client.get_me(), 3),
                ("check_dialogs", lambda: client.get_dialogs(limit=2), 5),
                ("get_contacts", lambda: client(GetContactsRequest(hash=0)), 8),
            ]

            for name, func, base_delay in activities:
                try:
                    # Human-like delay with variance
                    delay = random.uniform(base_delay * 0.7, base_delay * 1.3)
                    await asyncio.sleep(delay)

                    await func()
                    logger.debug(f"Progressive activity: {name} ✓")

                    # Rate limiting protection
                    await self.rate_limit("warmup")

                except Exception as e:
                    logger.warning(f"Activity {name} failed: {e}")
                    # Continue with other activities

        except Exception as e:
            logger.error(f"Progressive activity failed: {e}")

    async def send_periodic_summary(self):
        """Send periodic summary of activities"""
        try:
            current_time = time.time()
            if current_time - self.last_summary_time < self.config.get(
                "summary_interval", 36000
            ):  # 10 hours
                return

            self.last_summary_time = current_time

            # Prepare summary
            total_actions = len(self.action_history)
            successful_actions = sum(
                1 for action in self.action_history if action.success
            )
            failed_actions = total_actions - successful_actions

            # Action breakdown
            action_counts = {}
            for action in self.action_history:
                action_counts[action.action] = action_counts.get(action.action, 0) + 1

            summary = (
                f"📊 **10-Hour Activity Summary**\n\n"
                f"📈 **Total Actions:** {total_actions}\n"
                f"✅ **Successful:** {successful_actions}\n"
                f"❌ **Failed:** {failed_actions}\n\n"
                f"**📋 Action Breakdown:**\n"
            )

            for action, count in sorted(action_counts.items()):
                summary += f"• {action}: {count}\n"

            # Rate limiter status
            summary += "\n**🚦 Rate Limiter Status:**\n"
            for name, limiter in self.rate_limiters.items():
                summary += (
                    f"• {name}: {limiter.tokens:.1f}/{limiter.max_tokens} tokens\n"
                )

            # Enhanced IP monitoring status
            if self.config.get("ip_monitoring", {}).get("enabled", True):
                summary += "\n**🌐 Network Status:**\n"
                summary += f"• Current IP: {self.current_ip or 'Detecting...'}\n"
                summary += f"• IP Changes: {self.ip_change_count}\n"
                summary += f"• Stability: {
                    'High' if self.ip_change_count < 3 else 'Medium' if self.ip_change_count < 10 else 'Low'}\n"

            summary += f"\n🕐 **Report Time:** {
                datetime.now(
                    timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"

            await self._send_alert(summary)

        except Exception as e:
            logger.error(f"Failed to send periodic summary: {e}")


# Global guardian instance
guardian: Optional[SessionGuardian] = None


def init_guardian(config: Dict[str, Any]) -> SessionGuardian:
    """Initialize global session guardian"""
    global guardian
    guardian = SessionGuardian(config)
    return guardian


def get_guardian() -> Optional[SessionGuardian]:
    """Get global session guardian instance"""
    return guardian
