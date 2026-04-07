import asyncio
import unittest.mock
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cwo import watcher

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    settings = MagicMock()
    settings.annotation_github_repo = "homelab.io/github-repo"
    settings.annotation_github_pr = "homelab.io/github-pr"
    settings.annotation_github_sha = "homelab.io/github-sha"
    settings.annotation_comment_id = "homelab.io/github-comment-id"
    settings.annotation_last_hash = "homelab.io/last-notified-hash"
    settings.api_group = "homelab.crossplane.io"
    monkeypatch.setattr(watcher, "SETTINGS", settings)
    return settings


@pytest.fixture
def dyn_client():
    client = AsyncMock()
    client.patch = AsyncMock()
    return client


@pytest.fixture
def resource():
    r = MagicMock()
    r.kind = "XStackVM"
    r.patch = AsyncMock()
    return r


# ---------------------------------------------------------------------------
# _handle_event — skip cases
# ---------------------------------------------------------------------------


@patch("cwo.watcher.github_client")
async def test_handle_event_skips_when_no_github_annotations(mock_gh, dyn_client, resource):
    obj = {
        "kind": "XStackVM",
        "metadata": {"name": "monapp-vm", "namespace": "eu1-dev-monapp", "annotations": {}},
        "status": {
            "conditions": [
                {"type": "Ready", "status": "True", "reason": "Available", "message": ""}
            ]
        },
    }
    await watcher._handle_event(dyn_client, resource, obj)
    mock_gh.create_comment.assert_not_called()
    mock_gh.update_comment.assert_not_called()


@patch("cwo.watcher.github_client")
async def test_handle_event_skips_when_no_conditions(mock_gh, dyn_client, resource):
    obj = {
        "kind": "XStackVM",
        "metadata": {
            "name": "monapp-vm",
            "namespace": "eu1-dev-monapp",
            "annotations": {
                "homelab.io/github-repo": "cdelgehier/homelab-endusers",
                "homelab.io/github-pr": "42",
                "homelab.io/github-sha": "abc123",
            },
        },
        "status": {},
    }
    await watcher._handle_event(dyn_client, resource, obj)
    mock_gh.create_comment.assert_not_called()


@patch("cwo.watcher.github_client")
async def test_handle_event_skips_when_hash_unchanged(
    mock_gh, dyn_client, resource, sample_conditions
):
    from cwo.notifier import compute_hash

    current_hash = compute_hash(sample_conditions)

    obj = {
        "kind": "XStackVM",
        "metadata": {
            "name": "monapp-vm",
            "namespace": "eu1-dev-monapp",
            "annotations": {
                "homelab.io/github-repo": "cdelgehier/homelab-endusers",
                "homelab.io/github-pr": "42",
                "homelab.io/github-sha": "abc123",
                "homelab.io/last-notified-hash": current_hash,
            },
        },
        "status": {"conditions": sample_conditions},
    }
    await watcher._handle_event(dyn_client, resource, obj)
    mock_gh.create_comment.assert_not_called()
    mock_gh.update_comment.assert_not_called()


# ---------------------------------------------------------------------------
# _handle_event — notification cases
# ---------------------------------------------------------------------------


@patch("cwo.watcher._patch_annotations", new_callable=AsyncMock)
@patch("cwo.watcher.github_client")
async def test_handle_event_creates_comment_when_no_comment_id(
    mock_gh, mock_patch, dyn_client, resource, sample_conditions
):
    mock_gh.create_comment = AsyncMock(return_value="99999")

    obj = {
        "kind": "XStackVM",
        "metadata": {
            "name": "monapp-vm",
            "namespace": "eu1-dev-monapp",
            "annotations": {
                "homelab.io/github-repo": "cdelgehier/homelab-endusers",
                "homelab.io/github-pr": "42",
                "homelab.io/github-sha": "abc123",
            },
        },
        "status": {"conditions": sample_conditions},
    }
    await watcher._handle_event(dyn_client, resource, obj)
    mock_gh.create_comment.assert_called_once()
    mock_gh.update_comment.assert_not_called()


@patch("cwo.watcher._patch_annotations", new_callable=AsyncMock)
@patch("cwo.watcher.github_client")
async def test_handle_event_updates_comment_when_comment_id_present(
    mock_gh, mock_patch, dyn_client, resource, sample_conditions
):
    mock_gh.update_comment = AsyncMock()

    obj = {
        "kind": "XStackVM",
        "metadata": {
            "name": "monapp-vm",
            "namespace": "eu1-dev-monapp",
            "annotations": {
                "homelab.io/github-repo": "cdelgehier/homelab-endusers",
                "homelab.io/github-pr": "42",
                "homelab.io/github-sha": "abc123",
                "homelab.io/github-comment-id": "12345",
            },
        },
        "status": {"conditions": sample_conditions},
    }
    await watcher._handle_event(dyn_client, resource, obj)
    mock_gh.update_comment.assert_called_once()
    mock_gh.create_comment.assert_not_called()


@patch("cwo.watcher._patch_annotations", new_callable=AsyncMock)
@patch("cwo.watcher.github_client")
async def test_handle_event_patches_annotations_after_notify(
    mock_gh, mock_patch, dyn_client, resource, sample_conditions
):
    mock_gh.create_comment = AsyncMock(return_value="99999")

    obj = {
        "kind": "XStackVM",
        "metadata": {
            "name": "monapp-vm",
            "namespace": "eu1-dev-monapp",
            "annotations": {
                "homelab.io/github-repo": "cdelgehier/homelab-endusers",
                "homelab.io/github-pr": "42",
                "homelab.io/github-sha": "abc123",
            },
        },
        "status": {"conditions": sample_conditions},
    }
    await watcher._handle_event(dyn_client, resource, obj)
    mock_patch.assert_called_once()
    patched = mock_patch.call_args[0][-1]
    assert "homelab.io/github-comment-id" in patched
    assert "homelab.io/last-notified-hash" in patched


@patch("cwo.watcher._patch_annotations", new_callable=AsyncMock)
@patch("cwo.watcher.github_client")
async def test_handle_event_does_not_patch_on_github_failure(
    mock_gh, mock_patch, dyn_client, resource, sample_conditions
):
    mock_gh.create_comment = AsyncMock(side_effect=Exception("github down"))

    obj = {
        "kind": "XStackVM",
        "metadata": {
            "name": "monapp-vm",
            "namespace": "eu1-dev-monapp",
            "annotations": {
                "homelab.io/github-repo": "cdelgehier/homelab-endusers",
                "homelab.io/github-pr": "42",
                "homelab.io/github-sha": "abc123",
            },
        },
        "status": {"conditions": sample_conditions},
    }
    await watcher._handle_event(dyn_client, resource, obj)
    mock_patch.assert_not_called()


@pytest.mark.parametrize(
    "missing_annotation",
    [
        "homelab.io/github-repo",
        "homelab.io/github-pr",
    ],
)
@patch("cwo.watcher.github_client")
async def test_handle_event_skips_when_annotation_missing(
    mock_gh, missing_annotation, dyn_client, resource, sample_conditions
):
    annotations = {
        "homelab.io/github-repo": "cdelgehier/homelab-endusers",
        "homelab.io/github-pr": "42",
        "homelab.io/github-sha": "abc123",
    }
    del annotations[missing_annotation]

    obj = {
        "kind": "XStackVM",
        "metadata": {
            "name": "monapp-vm",
            "namespace": "eu1-dev-monapp",
            "annotations": annotations,
        },
        "status": {"conditions": sample_conditions},
    }
    await watcher._handle_event(dyn_client, resource, obj)
    mock_gh.create_comment.assert_not_called()


# ---------------------------------------------------------------------------
# _patch_annotations
# ---------------------------------------------------------------------------


async def test_patch_annotations_calls_resource_patch(dyn_client, resource):
    await watcher._patch_annotations(
        dyn_client, resource, "monapp-vm", "eu1-dev-monapp", {"key": "value"}
    )
    resource.patch.assert_called_once_with(
        body={"metadata": {"annotations": {"key": "value"}}},
        name="monapp-vm",
        namespace="eu1-dev-monapp",
        content_type="application/merge-patch+json",
    )


async def test_patch_annotations_swallows_exception(dyn_client, resource):
    resource.patch.side_effect = Exception("k8s API error")
    await watcher._patch_annotations(
        dyn_client, resource, "monapp-vm", "eu1-dev-monapp", {"key": "value"}
    )  # should not raise


# ---------------------------------------------------------------------------
# watch_resource
# ---------------------------------------------------------------------------


@patch("cwo.watcher._handle_event", new_callable=AsyncMock)
@patch("cwo.watcher.DynamicClient")
async def test_watch_resource_processes_added_events(
    mock_dyn_cls, mock_handle, resource, mock_settings
):
    mock_obj = MagicMock()
    mock_obj.to_dict.return_value = {"kind": "XStackVM", "metadata": {"name": "monapp-vm"}}

    async def _events():
        yield {"type": "ADDED", "object": mock_obj}

    resource.watch = MagicMock(side_effect=[_events(), asyncio.CancelledError()])

    dyn_client = AsyncMock()
    dyn_client.__aenter__.return_value = dyn_client
    dyn_client.__aexit__.return_value = None
    mock_dyn_cls.return_value = dyn_client

    await watcher.watch_resource(MagicMock(), resource)

    mock_handle.assert_called_once()


@patch("cwo.watcher._handle_event", new_callable=AsyncMock)
@patch("cwo.watcher.DynamicClient")
async def test_watch_resource_skips_deleted_events(
    mock_dyn_cls, mock_handle, resource, mock_settings
):
    mock_obj = MagicMock()
    mock_obj.to_dict.return_value = {"kind": "XStackVM", "metadata": {"name": "monapp-vm"}}

    async def _events():
        yield {"type": "DELETED", "object": mock_obj}

    resource.watch = MagicMock(side_effect=[_events(), asyncio.CancelledError()])

    dyn_client = AsyncMock()
    dyn_client.__aenter__.return_value = dyn_client
    dyn_client.__aexit__.return_value = None
    mock_dyn_cls.return_value = dyn_client

    await watcher.watch_resource(MagicMock(), resource)

    mock_handle.assert_not_called()


@patch("cwo.watcher._handle_event", new_callable=AsyncMock)
@patch("cwo.watcher.DynamicClient")
async def test_watch_resource_exits_on_cancelled_error(
    mock_dyn_cls, mock_handle, resource, mock_settings
):
    resource.watch = MagicMock(side_effect=asyncio.CancelledError())

    dyn_client = AsyncMock()
    dyn_client.__aenter__.return_value = dyn_client
    dyn_client.__aexit__.return_value = None
    mock_dyn_cls.return_value = dyn_client

    await watcher.watch_resource(MagicMock(), resource)  # should return cleanly


@patch("cwo.watcher.asyncio.sleep", new_callable=AsyncMock)
@patch("cwo.watcher._handle_event", new_callable=AsyncMock)
@patch("cwo.watcher.DynamicClient")
async def test_watch_resource_retries_on_stream_error(
    mock_dyn_cls, mock_handle, mock_sleep, resource, mock_settings
):
    resource.watch = MagicMock(side_effect=[Exception("stream reset"), asyncio.CancelledError()])

    dyn_client = AsyncMock()
    dyn_client.__aenter__.return_value = dyn_client
    dyn_client.__aexit__.return_value = None
    mock_dyn_cls.return_value = dyn_client

    await watcher.watch_resource(MagicMock(), resource)

    mock_sleep.assert_called_once_with(5)


@pytest.mark.parametrize(
    "errors, expected_sleeps",
    [
        (1, [5]),
        (2, [5, 10]),
        (3, [5, 10, 20]),
        (4, [5, 10, 20, 40]),
        (5, [5, 10, 20, 40, 60]),
        (6, [5, 10, 20, 40, 60, 60]),  # capped at 60
    ],
)
@patch("cwo.watcher.asyncio.sleep", new_callable=AsyncMock)
@patch("cwo.watcher._handle_event", new_callable=AsyncMock)
@patch("cwo.watcher.DynamicClient")
async def test_watch_resource_backoff_doubles_up_to_60s(
    mock_dyn_cls, mock_handle, mock_sleep, errors, expected_sleeps, resource, mock_settings
):
    resource.watch = MagicMock(
        side_effect=[Exception("stream error")] * errors + [asyncio.CancelledError()]
    )

    dyn_client = AsyncMock()
    dyn_client.__aenter__.return_value = dyn_client
    dyn_client.__aexit__.return_value = None
    mock_dyn_cls.return_value = dyn_client

    await watcher.watch_resource(MagicMock(), resource)

    assert mock_sleep.call_args_list == [unittest.mock.call(s) for s in expected_sleeps]
