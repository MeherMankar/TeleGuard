"""Async client manager with proper lifecycle management"""

import asyncio
import logging
import time
from typing import Dict, Optional

from telethon import TelegramClient

from ..core.exceptions import AccountError, SessionError
from ..utils.session_manager import SessionManager


class AsyncClientManager:
    def __init__(self):
        self.clients: Dict[str, TelegramClient] = {}
        self.last_activity: Dict[str, float] = {}
        self.session_manager = SessionManager()
        self.cleanup_task = None
        self.max_idle_time = 3600  # 1 hour
        self._lock = asyncio.Lock()

    async def get_client(
        self, user_id: int, account_name: str, api_id: int, api_hash: str
    ) -> Optional[TelegramClient]:
        """Get or create client with lifecycle management"""
        client_key = f"{user_id}_{account_name}"

        async with self._lock:
            # Return existing client if available
            if client_key in self.clients:
                self.last_activity[client_key] = time.time()
                return self.clients[client_key]

            # Create new client
            try:
                session_path = self.session_manager.get_session_path(
                    user_id, account_name
                )
                client = TelegramClient(str(session_path), api_id, api_hash)

                await client.connect()
                if not await client.is_user_authorized():
                    raise SessionError("Client not authorized")

                self.clients[client_key] = client
                self.last_activity[client_key] = time.time()

                # Start cleanup task if not running
                if not self.cleanup_task:
                    self.cleanup_task = asyncio.create_task(
                        self._cleanup_idle_clients()
                    )

                return client

            except Exception as e:
                raise SessionError(f"Failed to create client: {e}")

    async def remove_client(self, user_id: int, account_name: str):
        """Remove and disconnect client"""
        client_key = f"{user_id}_{account_name}"

        async with self._lock:
            if client_key in self.clients:
                client = self.clients.pop(client_key)
                self.last_activity.pop(client_key, None)
                await client.disconnect()

    async def _cleanup_idle_clients(self):
        """Background task to cleanup idle clients"""
        while True:
            try:
                current_time = time.time()
                idle_clients_to_disconnect = {}

                async with self._lock:
                    client_keys_to_remove = []
                    for client_key, last_active in self.last_activity.items():
                        if current_time - last_active > self.max_idle_time:
                            client_keys_to_remove.append(client_key)

                    for client_key in client_keys_to_remove:
                        if client_key in self.clients:
                            idle_clients_to_disconnect[client_key] = self.clients[
                                client_key
                            ]
                            del self.clients[client_key]
                            del self.last_activity[client_key]

                for client in idle_clients_to_disconnect.values():
                    try:
                        await client.disconnect()
                    except Exception as e:
                        logging.getLogger(__name__).error(
                            f"Error disconnecting idle client: {e}"
                        )

                await asyncio.sleep(300)  # Check every 5 minutes

            except Exception as e:
                logging.getLogger(__name__).error(
                    f"Error in _cleanup_idle_clients: {e}"
                )
                await asyncio.sleep(300)

    async def shutdown(self):
        """Shutdown all clients"""
        if self.cleanup_task:
            self.cleanup_task.cancel()

        async with self._lock:
            clients_to_disconnect = list(self.clients.values())
            self.clients.clear()
            self.last_activity.clear()

        for client in clients_to_disconnect:
            try:
                await client.disconnect()
            except Exception as e:
                logging.getLogger(__name__).error(
                    f"Error disconnecting client during shutdown: {e}"
                )


# Global client manager
client_manager = AsyncClientManager()
