from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from teleguard.core.contact_models import ContactGroup
from teleguard.handlers.contact_handler import ContactHandler
from teleguard.handlers.menu_system import _is_owned_callback
from teleguard.handlers.menu_modules.callback_router import CallbackRouter
from teleguard.handlers.template_handler import TemplateHandler


def _run_immediately(coroutine):
    try:
        return coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError("Coroutine unexpectedly suspended")


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

    assert _run_immediately(handler._get_user_account(123)) == "online"


def test_export_uses_the_selected_account_client_only():
    handler = object.__new__(ContactHandler)
    handler.pending_actions = {
        123: {
            "type": "export_select",
            "accounts": [{"name": "selected"}],
        }
    }
    selected_client = AsyncMock()
    selected_client.is_connected = Mock(return_value=True)
    selected_client.return_value = SimpleNamespace(users=[])
    other_client = AsyncMock()
    other_client.is_connected = Mock(return_value=True)
    handler.bot_manager = SimpleNamespace(
        user_clients={123: {"other": other_client, "selected": selected_client}}
    )
    event = SimpleNamespace(edit=AsyncMock(), answer=AsyncMock())

    _run_immediately(handler._process_export(event, 123, 0))

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

    _run_immediately(handler._process_create_group(event, 123, "  Friends  "))

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

    _run_immediately(router.handle_contacts_callback(event, 123, "contact:edit_name:456"))

    contact_handler._start_edit_name.assert_awaited_once_with(event, 123, 456)


def test_group_add_contact_callback_routes_to_input_flow():
    contact_handler = SimpleNamespace(_start_group_add_contact=AsyncMock())
    router = object.__new__(CallbackRouter)
    router.menu = SimpleNamespace(
        account_manager=SimpleNamespace(contact_handler=contact_handler)
    )
    event = SimpleNamespace(answer=AsyncMock())

    _run_immediately(
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

    _run_immediately(router.handle_contacts_callback(event, 123, "group:delete:Friends"))

    contact_handler._delete_group.assert_awaited_once_with(event, 123, "Friends")


def test_contact_list_page_callback_routes_page_number():
    contact_handler = SimpleNamespace(_show_contacts_list=AsyncMock())
    router = object.__new__(CallbackRouter)
    router.menu = SimpleNamespace(
        account_manager=SimpleNamespace(contact_handler=contact_handler)
    )
    event = SimpleNamespace(answer=AsyncMock())

    _run_immediately(router.handle_contacts_callback(event, 123, "contacts:list:2"))

    contact_handler._show_contacts_list.assert_awaited_once_with(event, 123, 2)


def test_contact_main_menu_handles_missing_account_from_any_entry_point():
    handler = object.__new__(ContactHandler)
    handler.pending_actions = {123: {"type": "search"}}
    handler._get_user_account = AsyncMock(return_value=None)
    event = SimpleNamespace(edit=AsyncMock(), reply=AsyncMock())

    _run_immediately(handler._show_main_menu(event, 123))

    text = event.edit.await_args.args[0]
    assert "No active account found" in text
    assert len(event.edit.await_args.kwargs["buttons"]) == 2
    assert 123 not in handler.pending_actions


def test_messaging_templates_action_opens_registered_template_menu():
    template_callback = AsyncMock()
    router = object.__new__(CallbackRouter)
    router.menu = SimpleNamespace(_handle_template_callback=template_callback)
    event = SimpleNamespace(message_id=7)

    _run_immediately(router.handle_messaging_callback(event, 123, "msg:templates"))

    template_callback.assert_awaited_once_with(event, 123, "template:main")


def test_legacy_template_callbacks_route_to_current_template_views():
    handler = object.__new__(TemplateHandler)
    handler.show_view_menu = AsyncMock()
    handler.show_template_details = AsyncMock()
    event = SimpleNamespace()

    _run_immediately(handler._route_template_action(event, "template:list"))
    _run_immediately(handler._route_template_action(event, "template:view:456"))

    handler.show_view_menu.assert_awaited_once_with(event)
    handler.show_template_details.assert_awaited_once_with(event, "456")


def test_contact_list_paginates_eight_results():
    handler = object.__new__(ContactHandler)
    event = SimpleNamespace(edit=AsyncMock())
    contacts = [
        {
            "name": f"Contact {index}",
            "user_id": index,
            "username": "No username",
            "phone": "No phone",
            "account": "account",
        }
        for index in range(1, 10)
    ]

    _run_immediately(handler._display_contacts(event, contacts, 9, page=1))

    text = event.edit.await_args.args[0]
    assert "Showing 9-9 of 9" in text
    assert "Contact 9" in text
    assert "Contact 8" not in text
