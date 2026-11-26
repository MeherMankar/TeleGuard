from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import teleguard.workers.activity_simulator as activity_simulator
from teleguard.workers.activity_simulator import ActivitySimulator


@pytest.mark.asyncio
async def test_add_account_starts_simulation_for_active_enabled_account(monkeypatch):
    account = {
        "_id": "account-id",
        "name": "Primary",
        "is_active": True,
        "simulation_enabled": True,
    }

    class Accounts:
        async def find_one(self, query):
            assert query == {"user_id": 123, "name": "Primary"}
            return account

    monkeypatch.setattr(
        activity_simulator.mongodb, "db", SimpleNamespace(accounts=Accounts())
    )
    monkeypatch.setattr(
        activity_simulator.DataEncryption,
        "decrypt_account_data",
        lambda value: value,
    )
    simulator = ActivitySimulator(SimpleNamespace(user_clients={}))
    simulator.running = True
    simulator._start_account_simulation = AsyncMock()
    client = SimpleNamespace(is_connected=lambda: True)

    await simulator.add_account(123, "Primary", client)

    simulator._start_account_simulation.assert_awaited_once_with(
        123, "account-id", "Primary"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "account",
    [
        {"_id": "account-id", "is_active": False, "simulation_enabled": True},
        {"_id": "account-id", "is_active": True, "simulation_enabled": False},
    ],
)
async def test_add_account_skips_inactive_or_disabled_accounts(monkeypatch, account):
    class Accounts:
        async def find_one(self, _query):
            return account

    monkeypatch.setattr(
        activity_simulator.mongodb, "db", SimpleNamespace(accounts=Accounts())
    )
    monkeypatch.setattr(
        activity_simulator.DataEncryption,
        "decrypt_account_data",
        lambda value: value,
    )
    simulator = ActivitySimulator(SimpleNamespace(user_clients={}))
    simulator.running = True
    simulator._start_account_simulation = AsyncMock()

    await simulator.add_account(
        123, "Primary", SimpleNamespace(is_connected=lambda: True)
    )

    simulator._start_account_simulation.assert_not_awaited()
