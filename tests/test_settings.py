import pytest
from pydantic import ValidationError

from cwo.settings import Settings


def test_settings_raises_when_github_token_missing(monkeypatch):
    monkeypatch.delenv("CWO_GITHUB_TOKEN", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_reads_token_from_env(monkeypatch):
    monkeypatch.setenv("CWO_GITHUB_TOKEN", "ghp-secret")

    s = Settings()
    assert s.github_token.get_secret_value() == "ghp-secret"


def test_settings_token_is_masked_in_repr(monkeypatch):
    monkeypatch.setenv("CWO_GITHUB_TOKEN", "ghp-secret")

    s = Settings()
    assert "ghp-secret" not in repr(s)


def test_settings_default_api_group(monkeypatch):
    monkeypatch.setenv("CWO_GITHUB_TOKEN", "ghp-test")

    s = Settings()
    assert s.api_group == "homelab.crossplane.io"


def test_settings_default_discovery_interval(monkeypatch):
    monkeypatch.setenv("CWO_GITHUB_TOKEN", "ghp-test")

    s = Settings()
    assert s.discovery_interval_seconds == 60


@pytest.mark.parametrize("interval", [30, 120, 300])
def test_settings_custom_discovery_interval(monkeypatch, interval):
    monkeypatch.setenv("CWO_GITHUB_TOKEN", "ghp-test")
    monkeypatch.setenv("CWO_DISCOVERY_INTERVAL_SECONDS", str(interval))

    s = Settings()
    assert s.discovery_interval_seconds == interval


def test_settings_ignores_unknown_env_vars(monkeypatch):
    monkeypatch.setenv("CWO_GITHUB_TOKEN", "ghp-test")
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")  # injected by K8s

    s = Settings()  # must not raise
    assert s.github_token.get_secret_value() == "ghp-test"


@pytest.mark.parametrize(
    "annotation_field, expected_value",
    [
        ("annotation_github_repo", "homelab.io/github-repo"),
        ("annotation_github_pr", "homelab.io/github-pr"),
        ("annotation_github_sha", "homelab.io/github-sha"),
        ("annotation_comment_id", "homelab.io/github-comment-id"),
        ("annotation_last_hash", "homelab.io/last-notified-hash"),
    ],
)
def test_settings_annotation_keys_defaults(monkeypatch, annotation_field, expected_value):
    monkeypatch.setenv("CWO_GITHUB_TOKEN", "ghp-test")

    s = Settings()
    assert getattr(s, annotation_field) == expected_value
