import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from teleguard.core.mongo_database import mongodb
from teleguard.handlers.menu_modules.callback_router import CallbackRouter
from teleguard.handlers.menu_modules.menu_handlers import MenuHandlers
from teleguard.handlers.menu_system import MenuSystem


def test_otp_coverage_excludes_accounts_with_active_temporary_bypass():
    accounts = [
        {"_id": "protected", "otp_destroyer_enabled": True},
        {"_id": "bypassed", "otp_destroyer_enabled": True},
        {"_id": "unprotected", "otp_destroyer_enabled": False},
    ]

    assert MenuHandlers._otp_coverage(accounts, {"bypassed"}) == 33


def test_temporary_bypass_requires_valid_unexpired_flag():
    now = 1000

    assert MenuHandlers._is_temp_bypass_active(
        {"otp_temp_passthrough": True, "temp_passthrough_expiry": "1001"}, now
    )
    assert not MenuHandlers._is_temp_bypass_active(
        {"otp_temp_passthrough": True, "temp_passthrough_expiry": "1000"}, now
    )
    assert not MenuHandlers._is_temp_bypass_active(
        {"otp_temp_passthrough": True, "temp_passthrough_expiry": "invalid"}, now
    )
    assert not MenuHandlers._is_temp_bypass_active(
        {"otp_temp_passthrough": False, "temp_passthrough_expiry": "1001"}, now
    )


def test_cleanup_account_must_be_active_and_connected():
    connected_client = SimpleNamespace(is_connected=lambda: True)
    disconnected_client = SimpleNamespace(is_connected=lambda: False)
    manager = SimpleNamespace(
        bot=SimpleNamespace(),
        account_manager=SimpleNamespace(
            user_clients={
                7: {
                    "connected": connected_client,
                    "disconnected": disconnected_client,
                }
            }
        )
    )
    handlers = MenuHandlers(manager)

    assert handlers._is_cleanup_account_available(
        7, {"name": "connected", "is_active": True}
    )
    assert not handlers._is_cleanup_account_available(
        7, {"name": "disconnected", "is_active": True}
    )
    assert not handlers._is_cleanup_account_available(
        7, {"name": "connected", "is_active": False}
    )


def test_2fa_back_navigation_opens_the_2fa_menu():
    send_2fa_menu = AsyncMock()
    router = object.__new__(CallbackRouter)
    router.menu = SimpleNamespace(_send_2fa_menu=send_2fa_menu)
    event = SimpleNamespace(message_id=55, answer=AsyncMock())

    asyncio.run(router.handle_menu_callback(event, 123, "menu:2fa"))

    send_2fa_menu.assert_awaited_once_with(123, 55)


def test_unknown_callback_reports_unavailable_instead_of_success():
    router = object.__new__(CallbackRouter)
    router.routes = {}
    event = SimpleNamespace(answer=AsyncMock())

    routed = asyncio.run(router.route_callback(event, 123, "missing:action"))

    assert not routed
    event.answer.assert_awaited_once_with(
        "This button is unavailable. Please reopen the menu.",
        alert=True,
    )


def test_main_menu_callback_edits_current_message_instead_of_deleting_it():
    send_main_menu = AsyncMock()
    router = object.__new__(CallbackRouter)
    router.menu = SimpleNamespace(
        account_manager=SimpleNamespace(pending_actions={}),
        send_main_menu=send_main_menu,
    )
    event = SimpleNamespace(
        message_id=55,
        answer=AsyncMock(),
        delete=AsyncMock(),
    )

    asyncio.run(router.handle_menu_callback(event, 123, "menu:main"))

    send_main_menu.assert_awaited_once_with(123, 55)
    event.delete.assert_not_awaited()


def test_text_menu_action_reuses_saved_bot_menu_message(monkeypatch):
    users = SimpleNamespace(
        find_one=AsyncMock(return_value={"main_menu_message_id": 99}),
        update_one=AsyncMock(),
    )
    monkeypatch.setattr(mongodb, "db", SimpleNamespace(users=users))
    bot = SimpleNamespace(edit_message=AsyncMock(), send_message=AsyncMock())
    handlers = MenuHandlers(SimpleNamespace(bot=bot, account_manager=None))

    asyncio.run(handlers._render_menu(123, None, "Account menu", []))

    bot.edit_message.assert_awaited_once_with(123, 99, "Account menu", buttons=[])
    bot.send_message.assert_not_awaited()
    users.update_one.assert_awaited_once_with(
        {"telegram_id": 123},
        {"$set": {"main_menu_message_id": 99}},
        upsert=True,
    )


def test_send_main_menu_edits_the_saved_message_instead_of_sending_another(
    monkeypatch,
):
    users = SimpleNamespace(
        find_one=AsyncMock(return_value={"main_menu_message_id": 99}),
        update_one=AsyncMock(),
    )
    monkeypatch.setattr(mongodb, "db", SimpleNamespace(users=users))
    bot = SimpleNamespace(edit_message=AsyncMock(), send_message=AsyncMock())
    menu = object.__new__(MenuSystem)
    menu.bot = bot
    menu.get_main_menu_keyboard = Mock(return_value=[])

    message_id = asyncio.run(MenuSystem.send_main_menu(menu, 123))

    assert message_id == 99
    bot.edit_message.assert_awaited_once_with(
        123,
        99,
        "🛡️ **TeleGuard Account Manager**\n\n"
        "⚡ Professional Telegram security & automation\n\n"
        "Use the menu buttons below to get started:",
        buttons=[],
    )
    bot.send_message.assert_not_awaited()
