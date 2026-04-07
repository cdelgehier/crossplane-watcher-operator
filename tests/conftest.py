import os

import pytest


def pytest_configure(config):
    """Set required env vars before collection so that the module-level
    ``SETTINGS = Settings()`` in *settings.py* can be instantiated."""
    os.environ.setdefault("CWO_GITHUB_TOKEN", "ghp_test-placeholder")


@pytest.fixture
def sample_conditions():
    return [
        {"type": "Ready", "status": "True", "reason": "Available", "message": ""},
        {"type": "Synced", "status": "True", "reason": "ReconcileSuccess", "message": ""},
    ]


@pytest.fixture
def pending_conditions():
    return [
        {
            "type": "Ready",
            "status": "False",
            "reason": "ReconcilePending",
            "message": "Waiting for resources",
        },
        {"type": "Synced", "status": "True", "reason": "ReconcileSuccess", "message": ""},
    ]


@pytest.fixture
def error_conditions():
    return [
        {
            "type": "Ready",
            "status": "False",
            "reason": "ReconcileError",
            "message": "terraform apply failed",
        },
        {
            "type": "Synced",
            "status": "False",
            "reason": "ReconcileError",
            "message": "terraform apply failed",
        },
    ]


@pytest.fixture
def sample_claim():
    return {
        "apiVersion": "homelab.crossplane.io/v1alpha1",
        "kind": "XStackVM",
        "metadata": {
            "name": "monapp-vm",
            "namespace": "eu1-dev-monapp",
            "annotations": {
                "homelab.io/github-repo": "cdelgehier/homelab-endusers",
                "homelab.io/github-pr": "42",
                "homelab.io/github-sha": "abc123def",
            },
        },
        "status": {
            "conditions": [
                {"type": "Ready", "status": "True", "reason": "Available", "message": ""},
                {
                    "type": "Synced",
                    "status": "True",
                    "reason": "ReconcileSuccess",
                    "message": "",
                },
            ]
        },
    }
