import asyncio
import signal

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

