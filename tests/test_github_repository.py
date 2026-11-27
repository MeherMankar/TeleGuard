import pytest

from teleguard.utils.github_repository import create_repository


@pytest.mark.parametrize("private", [False, True])
def test_create_repository_uses_visibility_and_authenticated_owner(private):
    calls = []

    def request(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        if endpoint == "/user":
            return 200, {"login": "owner"}
        if endpoint == "/user/repos":
            return 201, {"full_name": "owner/archive", "private": private}
        raise AssertionError(f"Unexpected request: {method} {endpoint}")

    created = create_repository(request, "owner", "archive", private=private)

    assert created == {"full_name": "owner/archive", "private": private}
    assert calls[-1] == (
        "POST",
        "/user/repos",
        {
            "json_body": {
                "name": "archive",
                "private": private,
                "auto_init": False,
            },
            "allow_status": (422,),
        },
    )


def test_create_repository_refuses_unowned_user_namespace():
    calls = []

    def request(method, endpoint, **_kwargs):
        calls.append((method, endpoint))
        if endpoint == "/user":
            return 200, {"login": "token-owner"}
        if endpoint == "/orgs/repo-owner":
            return 404, {}
        raise AssertionError(f"Unexpected request: {method} {endpoint}")

    with pytest.raises(RuntimeError, match="neither the repository owner"):
        create_repository(request, "repo-owner", "archive", private=True)

    assert calls == [("GET", "/user"), ("GET", "/orgs/repo-owner")]


def test_create_repository_can_target_an_accessible_organization():
    calls = []

    def request(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        if endpoint == "/user":
            return 200, {"login": "member"}
        if endpoint == "/orgs/team":
            return 200, {"login": "team"}
        if endpoint == "/orgs/team/repos":
            return 201, {"full_name": "team/archive", "private": True}
        raise AssertionError(f"Unexpected request: {method} {endpoint}")

    repository = create_repository(request, "team", "archive", private=True)

    assert repository["full_name"] == "team/archive"
    assert [call[:2] for call in calls] == [
        ("GET", "/user"),
        ("GET", "/orgs/team"),
        ("POST", "/orgs/team/repos"),
    ]


def test_repository_creation_error_explains_404_then_422():
    def request(method, endpoint, **_kwargs):
        if endpoint == "/user":
            return 200, {"login": "owner"}
        if endpoint == "/user/repos":
            return 422, {
                "message": "Repository creation failed.",
                "errors": [
                    {
                        "resource": "Repository",
                        "field": "name",
                        "code": "already_exists",
                    }
                ],
            }
        if endpoint == "":
            return 404, {}
        raise AssertionError(f"Unexpected request: {method} {endpoint}")

    with pytest.raises(RuntimeError, match="token cannot access it") as error:
        create_repository(request, "owner", "archive", private=False)

    assert "HTTP 422" in str(error.value)
    assert "already_exists" in str(error.value)
    assert "Verify the configured owner/name" in str(error.value)
