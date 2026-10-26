import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from teleguard.handlers import help_commands
from teleguard.handlers.menu_callbacks import help_callbacks
from teleguard.handlers.menu_modules import callback_router
from teleguard.handlers.menu_modules import menu_handlers


def test_non_admin_cannot_use_developer_callbacks(monkeypatch):
    monkeypatch.setattr(help_callbacks, "ADMIN_IDS", {1})
    event = SimpleNamespace(answer=AsyncMock())
    callbacks = help_callbacks.HelpCallbacks(
        bot=SimpleNamespace(),
        account_manager=None,
        menu_system=None,
    )

    asyncio.run(callbacks.handle_developer_callback(event, 2, "dev:sysinfo"))

    event.answer.assert_awaited_once()
    assert "access" in event.answer.await_args.args[0].lower()


def test_developer_callback_router_denies_non_admins(monkeypatch):
    monkeypatch.setattr(callback_router, "ADMIN_IDS", {1})
    event = SimpleNamespace(answer=AsyncMock())
    router = object.__new__(callback_router.CallbackRouter)

    asyncio.run(router.handle_dev_callback(event, 2, "dev:sysinfo"))

    event.answer.assert_awaited_once()
    assert event.answer.await_args.kwargs["alert"] is True


def test_non_admin_cannot_toggle_developer_mode_from_help(monkeypatch):
    monkeypatch.setattr(help_callbacks, "ADMIN_IDS", {1})
    event = SimpleNamespace(answer=AsyncMock())
    callbacks = help_callbacks.HelpCallbacks(
        bot=SimpleNamespace(),
        account_manager=None,
        menu_system=None,
    )

    asyncio.run(callbacks.handle_callback(event, 2, "help:toggle_dev"))

    event.answer.assert_awaited_once()
    assert "access" in event.answer.await_args.args[0].lower()


def test_non_admin_cannot_open_developer_menu(monkeypatch):
    monkeypatch.setattr(menu_handlers, "ADMIN_IDS", {1})
    event = SimpleNamespace(sender_id=2, reply=AsyncMock())
    handlers = object.__new__(menu_handlers.MenuHandlers)

    asyncio.run(handlers.handle_developer(event))

    event.reply.assert_awaited_once()
    assert "access" in event.reply.await_args.args[0].lower()


def test_private_help_command_is_available_to_non_admins():
    event = SimpleNamespace(
        is_private=True,
        sender_id=2,
        reply=AsyncMock(),
    )
    commands = help_commands.HelpCommands(bot=None, bot_manager=None)

    asyncio.run(commands._help_command(event))

    event.reply.assert_awaited_once()
