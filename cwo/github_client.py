"""GitHub API client — creates and updates comments on Pull Requests.

This module calls the GitHub REST API:
    - POST   /repos/{owner}/{repo}/issues/{pr_number}/comments  → create comment
    - PATCH  /repos/{owner}/{repo}/issues/comments/{comment_id} → update comment

The token is read from SETTINGS (env var CWO_GITHUB_TOKEN).
A single httpx.AsyncClient is reused for all calls.
"""

import httpx

from cwo.logger import get_logger
from cwo.settings import SETTINGS

log = get_logger(__name__)

_GITHUB_API = "https://api.github.com"

_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    """Return the shared httpx client, creating it on first use."""
    global _client  # noqa: PLW0603
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=SETTINGS.github_timeout_seconds,
        )
    return _client


def _headers() -> dict[str, str]:
    """Build the HTTP headers for GitHub API calls."""
    return {
        "Authorization": f"Bearer {SETTINGS.github_token.get_secret_value()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def create_comment(repo: str, pr_number: str, body: str) -> str:
    """Create a new comment on a Pull Request.

    Args:
        repo:      "owner/repo" (e.g. "cdelgehier/homelab-endusers")
        pr_number: The PR number as a string (e.g. "42")
        body:      The comment text (markdown)

    Returns:
        The ID of the created comment (as a string).
    """
    url = f"{_GITHUB_API}/repos/{repo}/issues/{pr_number}/comments"
    client = await _get_client()
    response = await client.post(url, headers=_headers(), json={"body": body})
    response.raise_for_status()
    comment_id = str(response.json()["id"])
    log.info("github comment created", repo=repo, pr_number=pr_number, comment_id=comment_id)
    return comment_id


async def update_comment(repo: str, comment_id: str, body: str) -> None:
    """Edit an existing comment on a Pull Request.

    Args:
        repo:       "owner/repo"
        comment_id: The ID of the comment to edit
        body:       The new comment text (markdown)
    """
    url = f"{_GITHUB_API}/repos/{repo}/issues/comments/{comment_id}"
    client = await _get_client()
    response = await client.patch(url, headers=_headers(), json={"body": body})
    response.raise_for_status()
    log.info("github comment updated", repo=repo, comment_id=comment_id)
