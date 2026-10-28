import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from teleguard.core.contact_models import ContactGroup
from teleguard.handlers.contact_handler import ContactHandler
from teleguard.handlers.menu_system import _is_owned_callback
from teleguard.handlers.menu_modules.callback_router import CallbackRouter


def test_contact_menu_callbacks_reach_router_except_dedicated_export():
    assert not _is_owned_callback("contacts:list")
    assert not _is_owned_callback("contacts:add")
    assert not _is_owned_callback("contacts:search")
    assert _is_owned_callback("contacts:export")
    assert _is_owned_callback("export_contacts:0")


def test_get_user_account_skips_disconnected_clients():
    handler = object.__new__(ContactHandler)
    handler.bot_manager = SimpleNamespace(
        user_clients={
            123: {
                "offline": SimpleNamespace(is_connected=lambda: False),
                "online": SimpleNamespace(is_connected=lambda: True),
            }
        }
    )

    assert asyncio.run(handler._get_user_account(123)) == "online"


def test_export_uses_the_selected_account_client_only():
    handler = object.__new__(ContactHandler)
    handler.pending_actions = {
        123: {
            "type": "export_select",
            "accounts": [{"name": "selected"}],
        }
    }
    selected_client = AsyncMock()
    selected_client.is_connected.return_value = True
    selected_client.return_value = SimpleNamespace(users=[])
    other_client = AsyncMock()
    other_client.is_connected.return_value = True
    handler.bot_manager = SimpleNamespace(
        user_clients={123: {"other": other_client, "selected": selected_client}}
    )
    event = SimpleNamespace(edit=AsyncMock(), answer=AsyncMock())

    asyncio.run(handler._process_export(event, 123, 0))

    selected_client.assert_awaited_once()
    other_client.assert_not_awaited()
    assert 123 not in handler.pending_actions


def test_group_creation_persists_group_and_clears_pending_state(monkeypatch):
    handler = object.__new__(ContactHandler)
    handler.pending_actions = {123: {"type": "create_group"}}
    handler._get_user_account = AsyncMock(return_value="account")
    event = SimpleNamespace(reply=AsyncMock())
    add_group = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "teleguard.handlers.contact_handler.ContactDB.add_group", add_group
    )

    asyncio.run(handler._process_create_group(event, 123, "  Friends  "))

    group = add_group.await_args.args[0]
    assert isinstance(group, ContactGroup)
    assert group.name == "Friends"
    assert group.managed_by_account == "account"
    assert 123 not in handler.pending_actions


def test_contact_name_edit_callback_routes_to_input_flow():
    contact_handler = SimpleNamespace(_start_edit_name=AsyncMock())
    router = object.__new__(CallbackRouter)
    router.menu = SimpleNamespace(
        account_manager=SimpleNamespace(contact_handler=contact_handler)
    )
    event = SimpleNamespace(answer=AsyncMock())

    asyncio.run(router.handle_contacts_callback(event, 123, "contact:edit_name:456"))

    contact_handler._start_edit_name.assert_awaited_once_with(event, 123, 456)


def test_group_add_contact_callback_routes_to_input_flow():
    contact_handler = SimpleNamespace(_start_group_add_contact=AsyncMock())
    router = object.__new__(CallbackRouter)
    router.menu = SimpleNamespace(
        account_manager=SimpleNamespace(contact_handler=contact_handler)
    )
    event = SimpleNamespace(answer=AsyncMock())

    asyncio.run(
        router.handle_contacts_callback(event, 123, "group:add_contact:Friends")
    )

    contact_handler._start_group_add_contact.assert_awaited_once_with(
        event, 123, "Friends"
    )


def test_group_delete_callback_routes_to_account_scoped_delete():
    contact_handler = SimpleNamespace(_delete_group=AsyncMock())
    router = object.__new__(CallbackRouter)
    router.menu = SimpleNamespace(
        account_manager=SimpleNamespace(contact_handler=contact_handler)
    )
    event = SimpleNamespace(answer=AsyncMock())

    asyncio.run(router.handle_contacts_callback(event, 123, "group:delete:Friends"))

    contact_handler._delete_group.assert_awaited_once_with(event, 123, "Friends")


def test_contact_list_page_callback_routes_page_number():
    contact_handler = SimpleNamespace(_show_contacts_list=AsyncMock())
    router = object.__new__(CallbackRouter)
    router.menu = SimpleNamespace(
        account_manager=SimpleNamespace(contact_handler=contact_handler)
    )
    event = SimpleNamespace(answer=AsyncMock())

    asyncio.run(router.handle_contacts_callback(event, 123, "contacts:list:2"))

    contact_handler._show_contacts_list.assert_awaited_once_with(event, 123, 2)


def test_contact_list_paginates_eight_results():
    handler = object.__new__(ContactHandler)
    event = SimpleNamespace(edit=AsyncMock())
    contacts = [
        {
            "name": f"Contact {index}",
            "username": "No username",
            "phone": "No phone",
            "account": "account",
        }
        for index in range(1, 10)
    ]

    asyncio.run(handler._display_contacts(event, contacts, 9, page=1))

    text = event.edit.await_args.args[0]
    assert "Showing 9-9 of 9" in text
    assert "Contact 9" in text
    assert "Contact 8" not in text
