from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from cwo import github_client

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    settings = MagicMock()
    settings.github_token.get_secret_value.return_value = "ghp-test-token"
    settings.github_timeout_seconds = 10.0
    monkeypatch.setattr(github_client, "SETTINGS", settings)
    return settings


@pytest.fixture(autouse=True)
def _reset_client(monkeypatch):
    """Reset the shared httpx client before each test."""
    monkeypatch.setattr(github_client, "_client", None)


@pytest.fixture
def mock_http_client():
    client = AsyncMock()
    client.is_closed = False
    return client


def _make_response(comment_id: int = 12345):
    response = MagicMock(spec=httpx.Response)
    response.json.return_value = {"id": comment_id, "body": "some comment"}
    response.raise_for_status = MagicMock()
    return response


def _make_error_response(status_code: str = "404"):
    response = MagicMock(spec=httpx.Response)
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        status_code, request=MagicMock(), response=MagicMock()
    )
    return response


# ---------------------------------------------------------------------------
# _get_client
# ---------------------------------------------------------------------------


async def test_get_client_creates_client_on_first_call():
    github_client._client = None
    client = await github_client._get_client()
    assert client is not None
    assert isinstance(client, httpx.AsyncClient)
    await client.aclose()


async def test_get_client_reuses_existing_client():
    github_client._client = None
    client1 = await github_client._get_client()
    client2 = await github_client._get_client()
    assert client1 is client2
    await client1.aclose()


# ---------------------------------------------------------------------------
# create_comment
# ---------------------------------------------------------------------------


@patch("cwo.github_client._get_client")
async def test_create_comment_returns_comment_id(mock_get_client, mock_http_client):
    mock_http_client.post.return_value = _make_response(comment_id=12345)
    mock_get_client.return_value = mock_http_client

    comment_id = await github_client.create_comment(
        "cdelgehier/homelab-endusers", "42", "## Status"
    )

    assert comment_id == "12345"


@patch("cwo.github_client._get_client")
async def test_create_comment_posts_to_correct_url(mock_get_client, mock_http_client):
    mock_http_client.post.return_value = _make_response()
    mock_get_client.return_value = mock_http_client

    await github_client.create_comment("cdelgehier/homelab-endusers", "42", "## Status")

    url = mock_http_client.post.call_args[0][0]
    assert "cdelgehier/homelab-endusers" in url
    assert "issues/42" in url
    assert "comments" in url


@patch("cwo.github_client._get_client")
async def test_create_comment_sends_bearer_token_header(mock_get_client, mock_http_client):
    mock_http_client.post.return_value = _make_response()
    mock_get_client.return_value = mock_http_client

    await github_client.create_comment("cdelgehier/homelab-endusers", "42", "## Status")

    headers = mock_http_client.post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer ghp-test-token"


@patch("cwo.github_client._get_client")
async def test_create_comment_sends_body_as_json(mock_get_client, mock_http_client):
    mock_http_client.post.return_value = _make_response()
    mock_get_client.return_value = mock_http_client

    await github_client.create_comment("cdelgehier/homelab-endusers", "42", "## My Status")

    assert mock_http_client.post.call_args[1]["json"] == {"body": "## My Status"}


@patch("cwo.github_client._get_client")
async def test_create_comment_raises_on_http_error(mock_get_client, mock_http_client):
    mock_http_client.post.return_value = _make_error_response("404")
    mock_get_client.return_value = mock_http_client

    with pytest.raises(httpx.HTTPStatusError):
        await github_client.create_comment("cdelgehier/homelab-endusers", "42", "## Status")


# ---------------------------------------------------------------------------
# update_comment
# ---------------------------------------------------------------------------


@patch("cwo.github_client._get_client")
async def test_update_comment_patches_to_correct_url(mock_get_client, mock_http_client):
    mock_http_client.patch.return_value = _make_response()
    mock_get_client.return_value = mock_http_client

    await github_client.update_comment("cdelgehier/homelab-endusers", "12345", "## Updated")

    url = mock_http_client.patch.call_args[0][0]
    assert "cdelgehier/homelab-endusers" in url
    assert "issues/comments/12345" in url


@patch("cwo.github_client._get_client")
async def test_update_comment_sends_bearer_token_header(mock_get_client, mock_http_client):
    mock_http_client.patch.return_value = _make_response()
    mock_get_client.return_value = mock_http_client

    await github_client.update_comment("cdelgehier/homelab-endusers", "12345", "## Updated")

    headers = mock_http_client.patch.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer ghp-test-token"


@patch("cwo.github_client._get_client")
async def test_update_comment_raises_on_http_error(mock_get_client, mock_http_client):
    mock_http_client.patch.return_value = _make_error_response("403")
    mock_get_client.return_value = mock_http_client

    with pytest.raises(httpx.HTTPStatusError):
        await github_client.update_comment("cdelgehier/homelab-endusers", "12345", "## Updated")


@pytest.mark.parametrize(
    "repo, comment_id",
    [
        ("cdelgehier/homelab-endusers", "12345"),
        ("myorg/myrepo", "1"),
        ("user/project", "99999"),
    ],
)
@patch("cwo.github_client._get_client")
async def test_update_comment_url_contains_correct_ids(
    mock_get_client, mock_http_client, repo, comment_id
):
    mock_http_client.patch.return_value = _make_response()
    mock_get_client.return_value = mock_http_client

    await github_client.update_comment(repo, comment_id, "body")

    url = mock_http_client.patch.call_args[0][0]
    assert repo in url
    assert comment_id in url
