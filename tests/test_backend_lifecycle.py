import asyncio
import signal
from types import SimpleNamespace

import pytest

import main as bot_main


@pytest.mark.asyncio
async def test_signal_handler_waits_for_async_shutdown_without_exiting(monkeypatch):
    handlers = {}
    shutdown_finished = asyncio.Event()

    async def graceful_shutdown():
        shutdown_finished.set()

    monkeypatch.setattr(
        bot_main.signal,
        "signal",
        lambda signum, handler: handlers.__setitem__(signum, handler),
    )
    monkeypatch.setattr(bot_main, "graceful_shutdown", graceful_shutdown)
    monkeypatch.setattr(bot_main, "shutdown_task", None)
    monkeypatch.setattr(bot_main, "shutdown_requested", False)
    bot_main.setup_signal_handlers()

    handlers[signal.SIGTERM](signal.SIGTERM, None)
    await asyncio.wait_for(shutdown_finished.wait(), timeout=1)
    await bot_main.shutdown_task
    assert bot_main.shutdown_requested
    assert await bot_main._finish_shutdown_if_requested()


@pytest.mark.asyncio
async def test_failed_startup_retry_wait_exits_when_shutdown_is_requested(monkeypatch):
    async def request_shutdown(_delay):
        bot_main.shutdown_requested = True

    monkeypatch.setattr(bot_main, "shutdown_requested", False)
    monkeypatch.setattr(bot_main, "shutdown_task", None)
    monkeypatch.setattr(
        bot_main, "asyncio", SimpleNamespace(sleep=request_shutdown)
    )

    await bot_main._wait_for_shutdown_request()

