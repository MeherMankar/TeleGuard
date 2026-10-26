"""Parsing and mapping for user-selected account cleanup actions."""

CLEANUP_TYPE_SETTINGS = {
    "personal": "personal_chats",
    "bots": "bot_chats",
    "telegram": "telegram_chat",
    "spambot": "spambot_chat",
    "my_messages": "my_messages",
    "channels": "channels",
    "groups": "groups",
    "owned_groups": "owned_groups",
    "owned_channels": "owned_channels",
}


def parse_cleanup_types(cleanup_types: str) -> tuple[list[str], dict[str, bool]]:
    """Validate cleanup tokens and expand ``all`` into every supported action."""
    selected = [item.strip().lower() for item in cleanup_types.split(",")]
    if not cleanup_types.strip() or any(not item for item in selected):
        raise ValueError("Select at least one cleanup type.")

    invalid = [
        item
        for item in selected
        if item != "all" and item not in CLEANUP_TYPE_SETTINGS
    ]
    if invalid:
        raise ValueError(f"Invalid cleanup types: {', '.join(invalid)}")

    if "all" in selected:
        selected = list(CLEANUP_TYPE_SETTINGS)
    else:
        selected = list(dict.fromkeys(selected))

    settings = {
        setting: cleanup_type in selected
        for cleanup_type, setting in CLEANUP_TYPE_SETTINGS.items()
    }
    return selected, settings
