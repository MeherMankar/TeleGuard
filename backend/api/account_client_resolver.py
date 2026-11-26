from typing import Any, Mapping, Optional


def _normalize_account_alias(value: Any) -> str:
    return "".join(str(value).casefold().replace("+", "").split())


def resolve_account_client(
    clients: Mapping[str, Any], account_name: str
) -> Optional[Any]:
    """Resolve only a unique, exact normalized alias; never guess an account."""
    normalized_name = _normalize_account_alias(account_name)
    if not normalized_name:
        return None

    matches = {
        id(client): client
        for alias, client in clients.items()
        if _normalize_account_alias(alias) == normalized_name
    }
    if len(matches) > 1:
        raise ValueError("Account name matches more than one connected account")
    return next(iter(matches.values()), None)
