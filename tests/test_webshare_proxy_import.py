import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from teleguard.core.proxy_manager import ProxyManager


class FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def json(self):
        return self.payload


class FakeSession:
    responses = []
    requests = []

    def __init__(self, **_kwargs):
        self.response_index = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        response = self.responses[self.response_index]
        self.response_index += 1
        return response


def test_import_webshare_proxies_paginates_and_skips_existing():
    FakeSession.responses = [
        FakeResponse(
            200,
            {
                "next": "https://proxy.webshare.io/api/v2/proxy/list/?page=2",
                "results": [
                    {
                        "proxy_address": "203.0.113.10",
                        "port": 80,
                        "username": "user",
                        "password": "password",
                    }
                ],
            },
        ),
        FakeResponse(
            200,
            {
                "next": None,
                "results": [
                    {
                        "proxy_address": "203.0.113.11",
                        "port": 8080,
                        "username": "existing",
                        "password": "password",
                    }
                ],
            },
        ),
    ]
    FakeSession.requests = []
    manager = ProxyManager()
    manager.add_proxy = AsyncMock(return_value=(True, "proxy-id"))

    proxy_collection = MagicMock()
    proxy_collection.find.return_value.to_list = AsyncMock(
        return_value=[
            {
                "type": "http",
                "server": "203.0.113.11",
                "port": 8080,
                "username": "existing",
            }
        ]
    )

    with (
        patch("aiohttp.ClientSession", FakeSession),
        patch(
            "teleguard.core.proxy_manager.mongodb.db",
            SimpleNamespace(proxies=proxy_collection),
        ),
    ):
        result = asyncio.run(manager.import_webshare_proxies(123, "secret-api-key"))

    assert result == {"total": 2, "imported": 1, "skipped": 1, "failed": 0}
    assert len(FakeSession.requests) == 2
    assert FakeSession.requests[0][1]["headers"] == {
        "Authorization": "Token secret-api-key"
    }
    manager.add_proxy.assert_awaited_once_with(
        123,
        {
            "type": "http",
            "server": "203.0.113.10",
            "port": 80,
            "username": "user",
            "password": "password",
        },
        name="Webshare 203.0.113.10:80",
    )


def test_import_webshare_proxies_rejects_invalid_api_key():
    FakeSession.responses = [FakeResponse(401, {})]
    manager = ProxyManager()

    with patch("aiohttp.ClientSession", FakeSession):
        with pytest.raises(ValueError, match="rejected the API key"):
            asyncio.run(manager.import_webshare_proxies(123, "invalid-key"))
