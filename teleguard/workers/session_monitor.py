"""Session Monitor for TeleGuard
Monitors active sessions and handles invalidations automatically
"""

import asyncio
import logging
from typing import Dict

from ..core.mongo_database import mongodb
from ..utils.account_invalidation import handle_account_error
from ..utils.crypto_utils import DataEncryption

logger = logging.getLogger(__name__)


class SessionMonitor:
    """Monitors session health and handles invalidations"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.monitoring = False
        self.check_interval = 600  # 10 minutes (reduced frequency)
        self.monitored_clients: Dict[int, Dict[str, any]] = {}
        self._monitor_task = None

    async def start_monitoring(self):
        """Start session monitoring"""
        if self.monitoring:
            return

        self.monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Session monitoring started")

    async def stop_monitoring(self):
        """Stop session monitoring"""
        self.monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Session monitoring stopped")

    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring:
            try:
                await self._check_all_sessions()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session monitoring loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying

    async def _check_all_sessions(self):
        """Check all active sessions for validity"""
        try:
            for user_id, clients in self.bot_manager.user_clients.items():
                for account_name, client in list(clients.items()):
                    try:
                        await self._check_session_health(user_id, account_name, client)
                        await asyncio.sleep(1)  # Rate limit checks
                    except Exception as e:
                        logger.warning(f"Session check failed for {account_name}: {e}")
                        # Handle potential invalidation
                        await self._handle_potential_invalidation(
                            user_id, account_name, str(e)
                        )
        except Exception as e:
            logger.error(f"Error checking sessions: {e}")

    async def _check_session_health(self, user_id: int, account_name: str, client):
        """Check if a session is still valid"""
        try:
            if not client.is_connected():
                # Try to reconnect
                await client.connect()

            # Test session validity by getting user info
            from ..utils.network_helpers import get_user_info_safe

            await get_user_info_safe(client)

        except Exception as e:
            error_msg = str(e).lower()
            # Check for session invalidation errors
            if any(
                phrase in error_msg
                for phrase in [
                    "auth_key_unregistered",
                    "session_revoked",
                    "user_deactivated",
                    "authorization key",
                    "duplicated",
                ]
            ):
                raise e  # Re-raise for invalidation handling
            else:
                # Other errors might be temporary
                logger.debug(f"Temporary session issue for {account_name}: {e}")

    async def _handle_potential_invalidation(
        self, user_id: int, account_name: str, error_message: str
    ):
        """Handle potential session invalidation"""
        try:
            # Get phone number for the account
            phone = await self._get_phone_for_account(user_id, account_name)

            # Use the global invalidation handler
            await handle_account_error(user_id, account_name, phone, error_message)

            logger.info(f"Handled session invalidation for {account_name} ({phone})")

        except Exception as e:
            logger.error(f"Failed to handle session invalidation: {e}")

    async def _get_phone_for_account(self, user_id: int, account_name: str) -> str:
        """Get phone number for an account"""
        try:
            enc_name = DataEncryption.encrypt_field(account_name)
            account = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "name_enc": enc_name}
            )
            if not account:
                # fallback for unencrypted legacy docs
                account = await mongodb.db.accounts.find_one(
                    {"user_id": user_id, "name": account_name}
                )
            if account:
                account = DataEncryption.decrypt_account_data(account)
                return account.get("phone", "Unknown")
            return "Unknown"
        except Exception:
            return "Unknown"

    def add_client_to_monitor(self, user_id: int, account_name: str, client):
        """Add a client to monitoring"""
        if user_id not in self.monitored_clients:
            self.monitored_clients[user_id] = {}

        self.monitored_clients[user_id][account_name] = {
            "client": client,
            "last_check": None,
            "error_count": 0,
        }

        logger.debug(f"Added {account_name} to session monitoring")

    def remove_client_from_monitor(self, user_id: int, account_name: str):
        """Remove a client from monitoring"""
        if user_id in self.monitored_clients:
            self.monitored_clients[user_id].pop(account_name, None)
            if not self.monitored_clients[user_id]:
                del self.monitored_clients[user_id]

        logger.debug(f"Removed {account_name} from session monitoring")
