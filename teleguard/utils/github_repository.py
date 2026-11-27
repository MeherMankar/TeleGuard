"""Helpers for creating configured GitHub repositories when they are missing."""

from typing import Any, Callable, Dict, Tuple
from urllib.parse import quote


GitHubRequest = Callable[..., Tuple[int, Dict[str, Any]]]


def create_repository(
    request: GitHubRequest, owner: str, name: str, *, private: bool
) -> Dict[str, Any]:
    """Create a repository under the token owner or an accessible organization."""
    _, authenticated_user = request("GET", "/user")
    login = authenticated_user.get("login")
    if not login:
        raise RuntimeError("GitHub did not identify the authenticated token owner")

    if login.casefold() == owner.casefold():
        endpoint = "/user/repos"
    else:
        status, _ = request(
            "GET",
            f"/orgs/{quote(owner, safe='')}",
            allow_status=(404,),
        )
        if status == 404:
            raise RuntimeError(
                f"Cannot create {owner}/{name}: the token belongs to '{login}', "
                "which is neither the repository owner nor an accessible organization"
            )
        endpoint = f"/orgs/{quote(owner, safe='')}/repos"

    status, repository = request(
        "POST",
        endpoint,
        json_body={"name": name, "private": private, "auto_init": False},
        allow_status=(422,),
    )
    if status == 422:
        status, existing_repository = request("GET", "", allow_status=(404,))
        if status == 404:
            raise RuntimeError(
                f"GitHub could not create {owner}/{name}: "
                f"{repository.get('message', 'repository creation was rejected')}"
            )
        repository = existing_repository

    actual_name = repository.get("full_name", "")
    if actual_name.casefold() != f"{owner}/{name}".casefold():
        raise RuntimeError(
            f"GitHub created or returned unexpected repository '{actual_name}' "
            f"instead of '{owner}/{name}'"
        )
    if repository.get("private") is not private:
        visibility = "private" if private else "public"
        raise RuntimeError(
            f"GitHub repository '{owner}/{name}' must be {visibility}"
        )
    return repository
