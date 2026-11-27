"""Check GitHub token authentication and optional repository visibility."""

import argparse
import getpass
import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


API_BASE = "https://api.github.com"
REPOSITORY_PART = re.compile(r"^[A-Za-z0-9_.-]+$")


def request_github(token: str, endpoint: str) -> tuple[int, dict]:
    request = Request(
        f"{API_BASE}{endpoint}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "TeleGuard-GitHub-token-check",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read()
            return response.status, json.loads(body) if body else {}
    except HTTPError as error:
        body = error.read()
        try:
            details = json.loads(body) if body else {}
        except json.JSONDecodeError:
            details = {}
        return error.code, details


def parse_repository(value: str) -> tuple[str, str]:
    parts = value.strip().split("/")
    if len(parts) != 2 or not all(REPOSITORY_PART.fullmatch(part) for part in parts):
        raise ValueError("Repository must be written as owner/name")
    return parts[0], parts[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check GitHub token authentication and optionally verify access "
            "to a repository. This script makes GET requests only."
        )
    )
    parser.add_argument(
        "--repo",
        help="Optional repository to check, formatted as owner/name",
    )
    args = parser.parse_args()

    token = getpass.getpass("GitHub PAT (input hidden): ").strip()
    if not token:
        print("No token entered.", file=sys.stderr)
        return 2
    if token.lower().startswith("bearer "):
        print("Enter the raw token only; do not include the 'Bearer ' prefix.")
        return 2

    try:
        status, user = request_github(token, "/user")
    except URLError as error:
        print(f"Could not reach api.github.com: {error.reason}", file=sys.stderr)
        return 2

    if status != 200:
        message = user.get("message", "GitHub did not accept the token")
        print(f"Authentication failed (HTTP {status}): {message}")
        if status == 401:
            print("Check that the token is active, unexpired, and pasted correctly.")
        return 1

    print(f"Authentication succeeded as @{user.get('login', 'unknown')}.")
    if not args.repo:
        print("This confirms authentication only; no repository was checked.")
        return 0

    try:
        owner, name = parse_repository(args.repo)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    endpoint = f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
    try:
        status, repository = request_github(token, endpoint)
    except URLError as error:
        print(f"Could not reach api.github.com: {error.reason}", file=sys.stderr)
        return 2

    if status != 200:
        message = repository.get("message", "Repository was not found or accessible")
        print(f"Repository check failed (HTTP {status}): {message}")
        if status == 404:
            print("GitHub may return 404 when the token cannot access an existing repo.")
        return 1

    visibility = "private" if repository.get("private") else "public"
    print(f"Repository access succeeded: {repository.get('full_name')} ({visibility}).")
    permissions = repository.get("permissions", {})
    if "push" in permissions:
        print(f"GitHub reports Contents push permission: {permissions['push']}.")
    else:
        print("GitHub did not report push access; this check does not prove write permissions.")
    print("This check does not test repository-creation permission.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
