from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import teleguard.core.mongo_database as mongo_database


class FailedMongoClient:
    def __init__(self, _uri, **_kwargs):
        self.admin = SimpleNamespace(command=self._fail_ping)
        self.close = Mock()

    async def _fail_ping(self, _command):
        raise OSError("MongoDB unavailable")

    def __getitem__(self, _name):
        return SimpleNamespace()


@pytest.mark.asyncio
async def test_production_mongodb_failure_does_not_fall_back_to_local_or_mock(
    monkeypatch,
):
    created_clients = []

    def create_client(uri, **kwargs):
        client = FailedMongoClient(uri, **kwargs)
        created_clients.append(client)
        return client

    monkeypatch.setattr(mongo_database, "AsyncIOMotorClient", create_client)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("MONGO_URI", "mongodb://configured-host:27017/teleguard")
    database = mongo_database.MongoDB()

    with pytest.raises(RuntimeError, match="durable storage"):
        await database.connect()

    assert len(created_clients) == 1
    assert created_clients[0].close.called
    assert database.client is None
    assert database.db is None


@pytest.mark.asyncio
async def test_development_mongodb_failure_uses_explicit_mock_fallback(monkeypatch):
    monkeypatch.setattr(
        mongo_database,
        "AsyncIOMotorClient",
        lambda uri, **kwargs: FailedMongoClient(uri, **kwargs),
    )
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("MONGO_URI", "mongodb://configured-host:27017/teleguard")
    database = mongo_database.MongoDB()

    await database.connect()

    assert database.client is None
    assert database.db.__class__.__name__ == "MockDB"
