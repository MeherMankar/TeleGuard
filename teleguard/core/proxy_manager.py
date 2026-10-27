"""Proxy Management System for TeleGuard"""

import asyncio
import base64
import binascii
import html
import logging
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from telethon import TelegramClient, connection

from .mongo_database import mongodb
from ..utils.crypto_utils import DataEncryption

logger = logging.getLogger(__name__)


class ProxyManager:
    """Manages proxies for Telegram accounts"""

    def __init__(self):
        self.proxy_cache = {}  # {proxy_id: last_check_time}

    @staticmethod
    def _normalize_proxy_endpoint(server: str, port: str | int) -> tuple[str, int]:
        if not isinstance(server, str) or not server.strip():
            raise ValueError("Proxy server is required.")
        try:
            port_number = int(port)
        except (TypeError, ValueError) as e:
            raise ValueError("Proxy port must be a number.") from e
        if not 1 <= port_number <= 65535:
            raise ValueError("Proxy port must be between 1 and 65535.")
        return server.strip(), port_number

    @staticmethod
    def normalize_mtproto_secret(secret: str) -> str:
        """Normalize Telegram hex/base64url MTProxy secrets for Telethon."""
        if not isinstance(secret, str) or not secret:
            raise ValueError("MTProto proxy secret is required.")

        value = secret.strip()
        hex_value = value[2:] if value[:2].lower() in {"dd", "ee"} else value
        try:
            secret_bytes = bytes.fromhex(hex_value)
        except ValueError:
            encoded = value.encode("ascii")
            encoded += b"=" * (-len(encoded) % 4)
            try:
                secret_bytes = base64.b64decode(
                    encoded, altchars=b"-_", validate=True
                )
            except (binascii.Error, ValueError) as e:
                raise ValueError("Invalid MTProto proxy secret format.") from e

        if len(secret_bytes) < 16:
            raise ValueError("MTProto proxy secret must contain at least 16 bytes.")
        return secret_bytes[:16].hex()

    async def parse_telegram_proxy_link(self, link: str) -> Optional[Dict]:
        """Parse Telegram proxy link (t.me/proxy, t.me/socks, tg://proxy, tg://socks)"""
        try:
            link = html.unescape(link.strip())
            telegram_link = link.lower().startswith(
                (
                    "t.me/",
                    "https://t.me/",
                    "http://t.me/",
                    "https://www.t.me/",
                    "http://www.t.me/",
                )
            )
            if telegram_link:
                parsed = urlparse(
                    f"https://{link}" if link.lower().startswith("t.me/") else link
                )
                path = parsed.path.lower().rstrip("/")
                if path.rsplit("/", 1)[-1] not in {"proxy", "socks"}:
                    return None
                params = parse_qs(parsed.query)
                proxy_type = "mtproto" if path.endswith("/proxy") else "socks5"
                default_port = "443" if proxy_type == "mtproto" else "1080"
                server, port = self._normalize_proxy_endpoint(
                    params.get("server", [""])[0],
                    params.get("port", [default_port])[0],
                )
                if proxy_type == "mtproto":
                    return {
                        "type": proxy_type,
                        "server": server,
                        "port": port,
                        "secret": self.normalize_mtproto_secret(
                            params.get("secret", [""])[0]
                        ),
                    }
                return {
                    "type": proxy_type,
                    "server": server,
                    "port": port,
                    "username": params.get("user", [None])[0],
                    "password": params.get("pass", [None])[0],
                }

            if link.lower().startswith("mtproto://"):
                authority = urlparse(link).netloc
                parts = authority.rsplit(":", 2)
                if len(parts) == 3:
                    server, port_text, secret = parts
                elif len(parts) == 2:
                    server, port_text = parts
                    secret = parse_qs(urlparse(link).query).get("secret", [""])[0]
                else:
                    raise ValueError("Use mtproto://host:port:secret.")
                server, port = self._normalize_proxy_endpoint(server, port_text)
                return {
                    "type": "mtproto",
                    "server": server,
                    "port": port,
                    "secret": self.normalize_mtproto_secret(secret),
                }

            if link.startswith("tg://"):
                parsed = urlparse(link)
                params = parse_qs(parsed.query)

                proxy_type = "socks5" if "socks" in link else "mtproto"

                if proxy_type == "mtproto":
                    secret = params.get("secret", [""])[0]
                    secret = self.normalize_mtproto_secret(secret)
                    return {
                        "type": "mtproto",
                        "server": params.get("server", [""])[0],
                        "port": int(params.get("port", [443])[0]),
                        "secret": secret,
                    }
                else:
                    return {
                        "type": "socks5",
                        "server": params.get("server", [""])[0],
                        "port": int(params.get("port", [1080])[0]),
                        "username": params.get("user", [""])[0],
                        "password": params.get("pass", [""])[0],
                    }

            # Handle manual format: socks5://user:pass@host:port
            elif "://" in link:
                parsed = urlparse(link)
                return {
                    "type": "http" if parsed.scheme == "https" else parsed.scheme,
                    "server": parsed.hostname,
                    "port": parsed.port or 1080,
                    "username": parsed.username,
                    "password": parsed.password,
                }

            return None
        except Exception as e:
            logger.error(f"Failed to parse proxy link: {e}")
            return None

    async def add_proxy(
        self, user_id: int, proxy_data: Dict, name: str = None
    ) -> Tuple[bool, str]:
        """Add proxy to database"""
        try:
            proxy_type = proxy_data.get("type", "socks5")
            if proxy_type not in {"mtproto", "socks5", "http"}:
                return False, "Unsupported proxy type"
            server, port = self._normalize_proxy_endpoint(
                proxy_data.get("server"), proxy_data.get("port")
            )
            secret = None
            if proxy_type == "mtproto":
                secret = self.normalize_mtproto_secret(proxy_data.get("secret"))

            proxy_doc = {
                "user_id": user_id,
                "name": name or f"{server}:{port}",
                "type": proxy_type,
                "server": server,
                "port": port,
                "username": proxy_data.get("username"),
                "password": proxy_data.get("password"),
                "secret": secret,
                "status": "untested",
                "last_check": None,
                "response_time": None,
                "created_at": int(time.time()),
            }

            result = await mongodb.db.proxies.insert_one(proxy_doc)
            return True, str(result.inserted_id)
        except Exception as e:
            logger.error(f"Failed to add proxy: {e}")
            return False, str(e)

    async def import_webshare_proxies(
        self, user_id: int, api_key: str
    ) -> Dict[str, int]:
        """Import the user's direct Webshare proxies without storing their API key."""
        api_key = api_key.strip()
        if not api_key:
            raise ValueError("Webshare API key is required.")

        import aiohttp

        api_url = "https://proxy.webshare.io/api/v2/proxy/list/"
        page_size = 100
        proxies = []
        page = 1

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                while True:
                    params = {
                        "mode": "direct",
                        "page": page,
                        "page_size": page_size,
                    }
                    async with session.get(
                        api_url,
                        params=params,
                        headers={"Authorization": f"Token {api_key}"},
                    ) as response:
                        if response.status in (401, 403):
                            raise ValueError("Webshare rejected the API key.")
                        if response.status == 429:
                            raise ValueError(
                                "Webshare rate limit reached. Try again later."
                            )
                        if response.status >= 400:
                            raise ValueError(
                                f"Webshare API request failed (HTTP {response.status})."
                            )

                        payload = await response.json()

                    if not isinstance(payload, dict) or not isinstance(
                        payload.get("results"), list
                    ):
                        raise ValueError("Webshare returned an invalid proxy list.")

                    proxies.extend(payload["results"])
                    next_page = payload.get("next")
                    if not next_page:
                        break

                    page += 1
                    if page > 1000:
                        raise ValueError(
                            "Webshare proxy list exceeded the import limit."
                        )
        except ValueError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning(
                "Could not retrieve proxies from Webshare: %s", type(e).__name__
            )
            raise ValueError("Could not connect to the Webshare API.") from e

        existing_proxies = await mongodb.db.proxies.find(
            {"user_id": user_id}
        ).to_list(length=None)
        existing_keys = {
            (
                item.get("type"),
                item.get("server"),
                item.get("port"),
                item.get("username") or "",
            )
            for item in existing_proxies
        }

        imported = 0
        skipped = 0
        failed = 0
        for item in proxies:
            if not isinstance(item, dict):
                failed += 1
                continue

            server = item.get("proxy_address")
            port = item.get("port")
            username = item.get("username") or None
            password = item.get("password") or None
            if not isinstance(server, str) or not server.strip():
                failed += 1
                continue
            try:
                port = int(port)
            except (TypeError, ValueError):
                failed += 1
                continue
            if not 1 <= port <= 65535:
                failed += 1
                continue

            proxy_key = ("http", server, port, username or "")
            if proxy_key in existing_keys:
                skipped += 1
                continue

            success, _ = await self.add_proxy(
                user_id,
                {
                    "type": "http",
                    "server": server,
                    "port": port,
                    "username": username,
                    "password": password,
                },
                name=f"Webshare {server}:{port}",
            )
            if success:
                imported += 1
                existing_keys.add(proxy_key)
            else:
                failed += 1

        return {
            "total": len(proxies),
            "imported": imported,
            "skipped": skipped,
            "failed": failed,
        }

    async def test_proxy(
        self, proxy_id: str, bot_manager=None
    ) -> Tuple[bool, str, Optional[float]]:
        """Test proxy connection"""
        try:
            from bson import ObjectId

            proxy = await mongodb.db.proxies.find_one({"_id": ObjectId(proxy_id)})
            if not proxy:
                return False, "Proxy not found", None

            # Test MTProto proxies using Telethon's native MTProxy connection.
            if proxy["type"] == "mtproto":
                try:
                    secret = self.normalize_mtproto_secret(proxy.get("secret"))
                except ValueError:
                    await mongodb.db.proxies.update_one(
                        {"_id": ObjectId(proxy_id)},
                        {"$set": {"status": "failed", "last_check": int(time.time())}},
                    )
                    return False, "Invalid MTProto secret", None

                from telethon.sessions import StringSession

                from .config import config

                test_client = TelegramClient(
                    StringSession(),
                    config.telegram.api_id,
                    config.telegram.api_hash,
                    connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,
                    proxy=(proxy["server"], int(proxy["port"]), secret),
                )
                start_time = time.time()
                try:
                    await asyncio.wait_for(test_client.connect(), timeout=10)
                    response_time = time.time() - start_time
                except asyncio.TimeoutError:
                    await mongodb.db.proxies.update_one(
                        {"_id": ObjectId(proxy_id)},
                        {
                            "$set": {
                                "status": "timeout",
                                "last_check": int(time.time()),
                            }
                        },
                    )
                    return False, "Connection timeout", None
                except Exception as e:
                    await mongodb.db.proxies.update_one(
                        {"_id": ObjectId(proxy_id)},
                        {
                            "$set": {
                                "status": "failed",
                                "last_check": int(time.time()),
                            }
                        },
                    )
                    return False, str(e), None
                finally:
                    try:
                        await test_client.disconnect()
                    except Exception as e:
                        logger.debug("MTProto test client disconnect failed: %s", e)

                await mongodb.db.proxies.update_one(
                    {"_id": ObjectId(proxy_id)},
                    {
                        "$set": {
                            "status": "working",
                            "last_check": int(time.time()),
                            "response_time": round(response_time, 2),
                        }
                    },
                )
                return True, f"Working ({response_time:.2f}s)", response_time

            # Test SOCKS5/HTTP proxies
            proxy_dict = {
                "proxy_type": proxy["type"],
                "addr": proxy["server"],
                "port": proxy["port"],
            }

            if proxy.get("username"):
                proxy_dict["username"] = proxy["username"]
            if proxy.get("password"):
                proxy_dict["password"] = proxy["password"]

            # Test connection with timeout
            start_time = time.time()
            try:
                # Create temporary client to test proxy
                from ..core.config import config

                test_client = TelegramClient(
                    "test_proxy_session",
                    config.telegram.api_id,
                    config.telegram.api_hash,
                    proxy=proxy_dict,
                )

                await asyncio.wait_for(test_client.connect(), timeout=10)
                response_time = time.time() - start_time
                await test_client.disconnect()

                # Update proxy status
                await mongodb.db.proxies.update_one(
                    {"_id": ObjectId(proxy_id)},
                    {
                        "$set": {
                            "status": "working",
                            "last_check": int(time.time()),
                            "response_time": round(response_time, 2),
                        }
                    },
                )

                return True, f"Working ({response_time:.2f}s)", response_time
            except asyncio.TimeoutError:
                await mongodb.db.proxies.update_one(
                    {"_id": ObjectId(proxy_id)},
                    {"$set": {"status": "timeout", "last_check": int(time.time())}},
                )
                return False, "Connection timeout", None
            except Exception as e:
                await mongodb.db.proxies.update_one(
                    {"_id": ObjectId(proxy_id)},
                    {"$set": {"status": "failed", "last_check": int(time.time())}},
                )
                return False, str(e), None
        except Exception as e:
            logger.error(f"Proxy test error: {e}")
            return False, str(e), None

    async def assign_proxy_to_account(
        self, user_id: int, account_id: str, proxy_id: str, bot_manager=None
    ) -> Tuple[bool, str]:
        """Assign proxy to account and reconnect with new proxy"""
        try:
            from bson import ObjectId

            # Verify proxy exists
            proxy = await mongodb.db.proxies.find_one(
                {"_id": ObjectId(proxy_id), "user_id": user_id}
            )
            if not proxy:
                return False, "Proxy not found"

            # Get account info
            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                return False, "Account not found"

            account = DataEncryption.decrypt_account_data(account)

            # Update account with proxy in database
            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id), "user_id": user_id},
                {"$set": {"proxy_id": proxy_id, "proxy_assigned_at": int(time.time())}},
            )

            # Reconnect the client with new proxy (like official Telegram clients do)
            account_name = account.get("name")
            session_string = account.get("session_string")

            if not session_string:
                return (
                    True,
                    "Proxy assigned (account not active, will use proxy on next connection)",
                )

            # Reconnect client if bot_manager provided
            if bot_manager and hasattr(bot_manager, "user_clients"):
                # Disconnect old client
                if (
                    user_id in bot_manager.user_clients
                    and account_name in bot_manager.user_clients[user_id]
                ):
                    old_client = bot_manager.user_clients[user_id][account_name]
                    if old_client and old_client.is_connected():
                        await old_client.disconnect()
                        logger.info(f"Disconnected {account_name} to apply proxy")

                # Reconnect with new proxy
                try:
                    await bot_manager.start_user_client(
                        user_id, account_name, session_string
                    )
                    client = bot_manager.user_clients.get(user_id, {}).get(
                        account_name
                    )
                    if not client or not client.is_connected():
                        return (
                            True,
                            "Proxy assigned, but the account has not connected yet. "
                            "Check the proxy endpoint and network access.",
                        )
                    return (
                        True,
                        "✅ Proxy assigned and applied! Account reconnected with new proxy.",
                    )
                except Exception as e:
                    logger.error(f"Failed to reconnect with proxy: {e}")
                    return (
                        True,
                        f"⚠️ Proxy assigned but reconnection failed: {
                            str(e)}. Account will use proxy on next restart.",
                    )

            return True, "Proxy assigned successfully (will be used on next connection)"
        except Exception as e:
            logger.error(f"Failed to assign proxy: {e}")
            return False, str(e)

    async def remove_proxy_from_account(
        self, user_id: int, account_id: str
    ) -> Tuple[bool, str]:
        """Remove proxy from account"""
        try:
            from bson import ObjectId

            result = await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id), "user_id": user_id},
                {"$unset": {"proxy_id": "", "proxy_assigned_at": ""}},
            )

            if result.modified_count > 0:
                return True, "Proxy removed successfully"
            return False, "Account not found"
        except Exception as e:
            logger.error(f"Failed to remove proxy: {e}")
            return False, str(e)

    async def get_user_proxies(self, user_id: int) -> List[Dict]:
        """Get all proxies for user"""
        try:
            proxies = await mongodb.db.proxies.find({"user_id": user_id}).to_list(
                length=None
            )
            return proxies
        except Exception as e:
            logger.error(f"Failed to get proxies: {e}")
            return []

    async def delete_proxy(self, user_id: int, proxy_id: str) -> Tuple[bool, str]:
        """Delete proxy"""
        try:
            from bson import ObjectId

            # Remove proxy from all accounts first
            await mongodb.db.accounts.update_many(
                {"user_id": user_id, "proxy_id": proxy_id},
                {"$unset": {"proxy_id": "", "proxy_assigned_at": ""}},
            )

            # Remove from default if set
            await mongodb.db.user_settings.update_one(
                {"user_id": user_id, "default_proxy_id": proxy_id},
                {"$unset": {"default_proxy_id": ""}},
            )

            # Delete proxy
            result = await mongodb.db.proxies.delete_one(
                {"_id": ObjectId(proxy_id), "user_id": user_id}
            )

            if result.deleted_count > 0:
                return True, "Proxy deleted successfully"
            return False, "Proxy not found"
        except Exception as e:
            logger.error(f"Failed to delete proxy: {e}")
            return False, str(e)

    async def get_account_proxy(self, account_id: str) -> Optional[Dict]:
        """Get proxy assigned to account"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id)})
            if not account or not account.get("proxy_id"):
                return None

            proxy = await mongodb.db.proxies.find_one(
                {"_id": ObjectId(account["proxy_id"])}
            )
            return proxy
        except Exception as e:
            logger.error(f"Failed to get account proxy: {e}")
            return None

    async def set_default_proxy(self, user_id: int, proxy_id: str) -> Tuple[bool, str]:
        """Set default proxy for new accounts"""
        try:
            from bson import ObjectId

            # Verify proxy exists
            proxy = await mongodb.db.proxies.find_one(
                {"_id": ObjectId(proxy_id), "user_id": user_id}
            )
            if not proxy:
                return False, "Proxy not found"

            # Store in user settings collection
            await mongodb.db.user_settings.update_one(
                {"user_id": user_id},
                {"$set": {"default_proxy_id": proxy_id}},
                upsert=True,
            )

            return True, "Default proxy set successfully"
        except Exception as e:
            logger.error(f"Failed to set default proxy: {e}")
            return False, str(e)

    async def get_default_proxy(self, user_id: int) -> Optional[Dict]:
        """Get default proxy for new accounts"""
        try:
            from bson import ObjectId

            # Get user settings
            settings = await mongodb.db.user_settings.find_one({"user_id": user_id})
            if not settings or not settings.get("default_proxy_id"):
                return None

            # Get proxy
            proxy = await mongodb.db.proxies.find_one(
                {"_id": ObjectId(settings["default_proxy_id"])}
            )
            return proxy
        except Exception as e:
            logger.error(f"Failed to get default proxy: {e}")
            return None

    async def build_telethon_proxy(
        self, proxy: Dict, proxy_id: str = None
    ) -> Optional[Dict]:
        """Build Telethon settings for supported proxy types."""
        try:
            if not proxy:
                return None

            proxy_type = proxy.get("type")
            server, port = self._normalize_proxy_endpoint(
                proxy.get("server"), proxy.get("port")
            )
            if proxy_type == "mtproto":
                secret = self.normalize_mtproto_secret(proxy.get("secret"))
                return {
                    "type": "mtproto",
                    "server": server,
                    "port": port,
                    "secret": secret,
                }

            if proxy_type not in {"socks5", "http"}:
                raise ValueError(f"Unsupported proxy type: {proxy_type}")

            proxy_dict = {
                "proxy_type": proxy_type,
                "addr": server,
                "port": port,
            }

            if proxy.get("username"):
                proxy_dict["username"] = proxy["username"]
            if proxy.get("password"):
                proxy_dict["password"] = proxy["password"]

            return proxy_dict
        except Exception as e:
            logger.error("Failed to build proxy configuration: %s", e)
            return None


# Global instance
proxy_manager = ProxyManager()
