import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cwo import operator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    settings = MagicMock()
    settings.api_group = "homelab.crossplane.io"
    settings.discovery_interval_seconds = 60
    monkeypatch.setattr(operator, "SETTINGS", settings)
    return settings


def _make_resource(kind: str):
    r = MagicMock()
    r.kind = kind
    return r


def _make_api_client():
    api_client = AsyncMock()
    api_client.__aenter__.return_value = api_client
    api_client.__aexit__.return_value = None
    return api_client


# ---------------------------------------------------------------------------
# _discover_resources
# ---------------------------------------------------------------------------


@patch("cwo.operator.DynamicClient")
async def test_discover_resources_returns_resources(mock_dyn_cls):
    resources = [_make_resource("XStackVM"), _make_resource("XS3Bucket")]

    dyn_client = AsyncMock()
    dyn_client.resources.search = AsyncMock(return_value=resources)
    dyn_client.__aenter__.return_value = dyn_client
    dyn_client.__aexit__.return_value = None
    mock_dyn_cls.return_value = dyn_client

    result = await operator._discover_resources(MagicMock())

    assert result == resources


@patch("cwo.operator.DynamicClient")
async def test_discover_resources_searches_api_group(mock_dyn_cls, mock_settings):
    dyn_client = AsyncMock()
    dyn_client.resources.search = AsyncMock(return_value=[])
    dyn_client.__aenter__.return_value = dyn_client
    dyn_client.__aexit__.return_value = None
    mock_dyn_cls.return_value = dyn_client

    await operator._discover_resources(MagicMock())

    dyn_client.resources.search.assert_called_once_with(group="homelab.crossplane.io")


# ---------------------------------------------------------------------------
# run — config loading
# ---------------------------------------------------------------------------


@patch("cwo.operator.asyncio.sleep", new_callable=AsyncMock)
@patch("cwo.operator._discover_resources", new_callable=AsyncMock)
@patch("cwo.operator.ApiClient")
@patch("cwo.operator.config")
async def test_run_uses_incluster_config_when_available(
    mock_config, mock_api_cls, mock_discover, mock_sleep
):
    mock_config.ConfigException = type("ConfigException", (Exception,), {})
    mock_api_cls.return_value = _make_api_client()
    mock_discover.return_value = []
    mock_sleep.side_effect = asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await operator.run()

    mock_config.load_incluster_config.assert_called_once()


@patch("cwo.operator.asyncio.sleep", new_callable=AsyncMock)
@patch("cwo.operator._discover_resources", new_callable=AsyncMock)
@patch("cwo.operator.ApiClient")
@patch("cwo.operator.config")
async def test_run_falls_back_to_kube_config(mock_config, mock_api_cls, mock_discover, mock_sleep):
    mock_config.ConfigException = type("ConfigException", (Exception,), {})
    mock_config.load_incluster_config.side_effect = mock_config.ConfigException()
    mock_config.load_kube_config = AsyncMock()
    mock_api_cls.return_value = _make_api_client()
    mock_discover.return_value = []
    mock_sleep.side_effect = asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await operator.run()

    mock_config.load_kube_config.assert_called_once()


# ---------------------------------------------------------------------------
# run — task lifecycle
# ---------------------------------------------------------------------------


@patch("cwo.operator.asyncio.sleep", new_callable=AsyncMock)
@patch("cwo.operator.asyncio.create_task")
@patch("cwo.operator._discover_resources", new_callable=AsyncMock)
@patch("cwo.operator.ApiClient")
@patch("cwo.operator.config")
async def test_run_starts_watch_for_each_discovered_resource(
    mock_config, mock_api_cls, mock_discover, mock_create_task, mock_sleep
):
    mock_config.ConfigException = type("ConfigException", (Exception,), {})
    mock_api_cls.return_value = _make_api_client()

    resource_vm = _make_resource("XStackVM")
    resource_s3 = _make_resource("XS3Bucket")
    mock_discover.return_value = [resource_vm, resource_s3]

    task_vm = MagicMock()
    task_vm.done.return_value = False
    task_s3 = MagicMock()
    task_s3.done.return_value = False
    mock_create_task.side_effect = [task_vm, task_s3]

    mock_sleep.side_effect = asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await operator.run()

    assert mock_create_task.call_count == 2


@patch("cwo.operator.asyncio.sleep", new_callable=AsyncMock)
@patch("cwo.operator.asyncio.create_task")
@patch("cwo.operator._discover_resources", new_callable=AsyncMock)
@patch("cwo.operator.ApiClient")
@patch("cwo.operator.config")
async def test_run_cancels_tasks_for_removed_crds(
    mock_config, mock_api_cls, mock_discover, mock_create_task, mock_sleep
):
    mock_config.ConfigException = type("ConfigException", (Exception,), {})
    mock_api_cls.return_value = _make_api_client()

    resource_vm = _make_resource("XStackVM")
    resource_s3 = _make_resource("XS3Bucket")

    # First iteration: both; second: only XStackVM
    mock_discover.side_effect = [[resource_vm, resource_s3], [resource_vm]]

    task_vm = MagicMock()
    task_vm.done.return_value = False
    task_s3 = MagicMock()
    task_s3.done.return_value = False
    mock_create_task.side_effect = [task_vm, task_s3]

    mock_sleep.side_effect = [None, asyncio.CancelledError()]

    with pytest.raises(asyncio.CancelledError):
        await operator.run()

    task_s3.cancel.assert_called_once()
    task_vm.cancel.assert_not_called()


@patch("cwo.operator.asyncio.sleep", new_callable=AsyncMock)
@patch("cwo.operator.asyncio.create_task")
@patch("cwo.operator._discover_resources", new_callable=AsyncMock)
@patch("cwo.operator.ApiClient")
@patch("cwo.operator.config")
async def test_run_restarts_dead_watch_tasks(
    mock_config, mock_api_cls, mock_discover, mock_create_task, mock_sleep
):
    mock_config.ConfigException = type("ConfigException", (Exception,), {})
    mock_api_cls.return_value = _make_api_client()

    resource_vm = _make_resource("XStackVM")
    mock_discover.return_value = [resource_vm]

    task_dead = MagicMock()
    task_dead.done.return_value = True
    task_new = MagicMock()
    task_new.done.return_value = False
    mock_create_task.side_effect = [task_dead, task_new]

    mock_sleep.side_effect = [None, asyncio.CancelledError()]

    with pytest.raises(asyncio.CancelledError):
        await operator.run()

    assert mock_create_task.call_count == 2


@patch("cwo.operator.asyncio.sleep", new_callable=AsyncMock)
@patch("cwo.operator._discover_resources", new_callable=AsyncMock)
@patch("cwo.operator.ApiClient")
@patch("cwo.operator.config")
async def test_run_handles_discovery_error(mock_config, mock_api_cls, mock_discover, mock_sleep):
    mock_config.ConfigException = type("ConfigException", (Exception,), {})
    mock_api_cls.return_value = _make_api_client()
    mock_discover.side_effect = Exception("k8s API unavailable")
    mock_sleep.side_effect = asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await operator.run()  # should not crash despite discovery error
