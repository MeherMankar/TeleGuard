import re

import pytest

from teleguard.handlers.start_handler import START_COMMAND_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        "/start",
        "/start payload",
        "/start@TeleGuardBot",
        "/start@TeleGuardBot payload",
    ],
)
def test_start_command_pattern_accepts_telegram_start_commands(command):
    assert re.match(START_COMMAND_PATTERN, command)


@pytest.mark.parametrize("command", ["/starter", "/start-extra", "hello /start"])
def test_start_command_pattern_rejects_non_commands(command):
    assert re.match(START_COMMAND_PATTERN, command) is None
