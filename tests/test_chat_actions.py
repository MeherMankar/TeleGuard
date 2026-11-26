from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, UploadFile
from telethon import functions, types

from backend.api import chats, messaging


def test_extract_reactions_keeps_standard_emojis_and_chosen_state():
    message = SimpleNamespace(
        reactions=SimpleNamespace(
            results=[
                SimpleNamespace(
                    reaction=types.ReactionEmoji(emoticon="👍"),
                    count=4,
                    chosen_order=0,
                ),
                SimpleNamespace(
                    reaction=types.ReactionCustomEmoji(document_id=123),
                    count=2,
                    chosen_order=None,
                ),
            ]
        )
    )

    assert chats._extract_reactions(message) == [
        {"emoji": "👍", "count": 4, "chosen": True},
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("muted", "expected_timestamp"),
    [(True, 2_147_483_647), (False, 0)],
)
async def test_chat_notification_action_updates_telegram_settings(
    monkeypatch, muted, expected_timestamp
):
    client = AsyncMock()
    client.get_input_entity.return_value = types.InputPeerUser(user_id=42, access_hash=1)
    monkeypatch.setattr(chats, "_resolve_client", AsyncMock(return_value=client))

    result = await chats.update_chat_notifications(
        "primary",
        42,
        chats.UpdateMuteRequest(muted=muted),
        user_id=123,
    )

    request = client.await_args.args[0]
    assert result == {"status": "success", "muted": muted}
    assert isinstance(request, functions.account.UpdateNotifySettingsRequest)
    assert request.peer.peer.user_id == 42
    assert request.settings.mute_until == datetime.fromtimestamp(
        expected_timestamp,
        tz=timezone.utc,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("emoji", "expected"), [("❤️", ["❤️"]), (None, [])])
async def test_message_reaction_sets_or_clears_telegram_reaction(monkeypatch, emoji, expected):
    client = AsyncMock()
    client.get_messages.return_value = SimpleNamespace(id=5)
    client.get_input_entity.return_value = types.InputPeerUser(user_id=42, access_hash=1)
    monkeypatch.setattr(chats, "_resolve_client", AsyncMock(return_value=client))

    result = await chats.set_message_reaction(
        "primary",
        42,
        5,
        chats.MessageReactionRequest(emoji=emoji),
        user_id=123,
    )

    request = client.await_args.args[0]
    assert result == {"status": "success"}
    assert isinstance(request, functions.messages.SendReactionRequest)
    assert [reaction.emoticon for reaction in request.reaction] == expected


@pytest.mark.asyncio
async def test_message_edit_is_limited_to_outgoing_messages(monkeypatch):
    client = AsyncMock()
    client.get_messages.return_value = SimpleNamespace(out=False)
    monkeypatch.setattr(chats, "_resolve_client", AsyncMock(return_value=client))

    with pytest.raises(HTTPException) as error:
        await chats.edit_chat_message(
            "primary",
            42,
            5,
            chats.EditMessageRequest(text="updated"),
            user_id=123,
        )

    assert error.value.status_code == 403
    client.get_input_entity.assert_not_awaited()


@pytest.mark.asyncio
async def test_forward_pin_and_delete_delegate_to_telethon(monkeypatch):
    client = AsyncMock()
    client.get_messages.return_value = SimpleNamespace(id=5, out=True)
    monkeypatch.setattr(chats, "_resolve_client", AsyncMock(return_value=client))

    assert await chats.forward_chat_message(
        "primary",
        42,
        5,
        chats.ForwardMessageRequest(target_chat_id=84),
        user_id=123,
    ) == {"status": "success"}
    client.forward_messages.assert_awaited_once_with(
        84,
        client.get_messages.return_value,
        from_peer=42,
    )

    assert await chats.set_message_pinned(
        "primary",
        42,
        5,
        chats.PinMessageRequest(pinned=True),
        user_id=123,
    ) == {"status": "success", "pinned": True}
    client.pin_message.assert_awaited_once_with(42, 5, notify=False)

    assert await chats.delete_chat_message("primary", 42, 5, user_id=123) == {
        "status": "success"
    }
    client.delete_messages.assert_awaited_once_with(42, 5, revoke=True)


@pytest.mark.asyncio
async def test_send_file_can_send_a_telegram_voice_note(monkeypatch):
    client = AsyncMock()
    client.get_entity.return_value = object()
    bot_manager = SimpleNamespace(get_client=Mock(return_value=client))
    monkeypatch.setattr(messaging, "_get_bot_manager", lambda: bot_manager)
    upload = UploadFile(filename="voice-message.webm", file=BytesIO(b"voice data"))

    result = await messaging.send_file_message(
        account_name="primary",
        target="42",
        file=upload,
        voice_note=True,
        user_id=123,
    )

    uploaded_path = client.send_file.await_args.args[1]
    assert result == {"status": "success"}
    assert client.send_file.await_args.kwargs["voice_note"] is True
    assert uploaded_path.endswith(".webm")
    assert not Path(uploaded_path).exists()


@pytest.mark.asyncio
async def test_admin_folder_preset_includes_admin_chats(monkeypatch):
    peer = types.InputPeerUser(user_id=99, access_hash=1)
    async def iter_dialogs(limit):
        assert limit == 300
        yield SimpleNamespace(
            id=99,
            entity=SimpleNamespace(creator=True, admin_rights=None),
        )

    client = AsyncMock()
    client.iter_dialogs = Mock(return_value=iter_dialogs(300))
    monkeypatch.setattr(chats, "_resolve_client", AsyncMock(return_value=client))
    monkeypatch.setattr("telethon.utils.get_input_peer", lambda _entity: peer)

    result = await chats.create_folder(
        "primary",
        {"is_admin": True},
        user_id=123,
    )

    request = client.await_args.args[0]
    assert result == {"status": "success", "id": 7, "title": "Admin"}
    assert request.filter.include_peers == [peer]


@pytest.mark.asyncio
async def test_admin_folder_preset_fails_if_account_has_no_admin_chats(monkeypatch):
    async def iter_dialogs(limit):
        assert limit == 300
        if False:
            yield None

    client = AsyncMock()
    client.iter_dialogs = Mock(return_value=iter_dialogs(300))
    monkeypatch.setattr(chats, "_resolve_client", AsyncMock(return_value=client))

    with pytest.raises(HTTPException, match="No admin chats found"):
        await chats.create_folder(
            "primary",
            {"is_admin": True},
            user_id=123,
        )

    client.assert_not_awaited()
