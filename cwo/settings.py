"""Application settings — loaded from environment variables.

All settings use the ``CWO_`` prefix (Crossplane Watcher Operator).
For example, ``CWO_GITHUB_TOKEN`` maps to the ``github_token`` field.

Pydantic validates the values at startup. If a required variable is
missing, the application will stop immediately with a clear error.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Operator configuration, read from environment variables.

    Required:
        CWO_GITHUB_TOKEN  — GitHub PAT (scope: public_repo or repo).

    Optional:
        CWO_API_GROUP                   — Crossplane API group to watch (default: homelab.crossplane.io).
        CWO_DISCOVERY_INTERVAL_SECONDS  — Seconds between discovery loops (default: 60).
        CWO_GITHUB_TIMEOUT_SECONDS      — HTTP timeout for GitHub API calls (default: 10.0).
        CWO_WATCH_TIMEOUT_SECONDS       — Kubernetes watch stream timeout (default: 300).
        CWO_LOG_LEVEL                   — Minimum log level (default: INFO).
        CWO_LEASE_DURATION              — Leader lease duration in seconds (default: 30).
        CWO_KUBE_CONTEXT                — K8s context to use (default: current-context).
    """

    model_config = SettingsConfigDict(
        env_prefix="CWO_",
        extra="ignore",  # ignore Kubernetes-injected env vars
    )

    # --- Required ---
    github_token: SecretStr

    # --- Optional: operator behaviour ---
    log_level: str = "INFO"
    api_group: str = "homelab.crossplane.io"
    discovery_interval_seconds: int = 60
    github_timeout_seconds: float = 10.0
    watch_timeout_seconds: int = 300
    lease_duration: int = 30
    kube_context: str | None = None
    kube_ssl_strict: bool = False

    # --- Annotation keys: read from claims (injected by CI) ---
    annotation_github_repo: str = "homelab.io/github-repo"  # e.g. "cdelgehier/homelab-endusers"
    annotation_github_pr: str = "homelab.io/github-pr"  # e.g. "42"
    annotation_github_sha: str = "homelab.io/github-sha"  # e.g. "abc123"

    # --- Annotation keys: written by the operator ---
    annotation_comment_id: str = "homelab.io/github-comment-id"  # ID of the GitHub comment
    annotation_last_hash: str = "homelab.io/last-notified-hash"  # Anti-spam hash


SETTINGS = Settings()
