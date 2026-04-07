import asyncio
import signal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cwo import main

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    settings = MagicMock()
    settings.api_group = "homelab.crossplane.io"
    settings.discovery_interval_seconds = 60
    settings.log_level = "INFO"
    monkeypatch.setattr(main, "SETTINGS", settings)
    return settings


# ---------------------------------------------------------------------------
# _handle_signal
# ---------------------------------------------------------------------------


@patch("cwo.main.asyncio.all_tasks")
def test_handle_signal_cancels_all_tasks(mock_all_tasks):
    task1, task2 = MagicMock(), MagicMock()
    mock_all_tasks.return_value = {task1, task2}
    loop = MagicMock()

    main._handle_signal(signal.SIGTERM, loop)

    task1.cancel.assert_called_once()
    task2.cancel.assert_called_once()


@patch("cwo.main.asyncio.all_tasks")
def test_handle_signal_with_no_tasks_does_not_raise(mock_all_tasks):
    mock_all_tasks.return_value = set()
    loop = MagicMock()

    main._handle_signal(signal.SIGINT, loop)  # should not raise


# ---------------------------------------------------------------------------
# _handle_sigusr1
# ---------------------------------------------------------------------------


@patch("cwo.main.asyncio.print_call_graph")
@patch("cwo.main.asyncio.all_tasks")
def test_handle_sigusr1_prints_call_graph(mock_all_tasks, mock_print_call_graph):
    task1, task2 = MagicMock(), MagicMock()
    mock_all_tasks.return_value = {task1, task2}

    main._handle_sigusr1()

    assert mock_print_call_graph.call_count == 2
    mock_print_call_graph.assert_any_call(task1)
    mock_print_call_graph.assert_any_call(task2)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


@patch("cwo.main.run", new_callable=AsyncMock)
@patch("cwo.main.setup_logging")
async def test_main_calls_setup_logging(mock_setup, mock_run):
    await main.main()
    mock_setup.assert_called_once()


@patch("cwo.main.run", new_callable=AsyncMock)
@patch("cwo.main.setup_logging")
async def test_main_runs_operator(mock_setup, mock_run):
    await main.main()
    mock_run.assert_called_once()


@patch("cwo.main.run", new_callable=AsyncMock)
@patch("cwo.main.setup_logging")
async def test_main_handles_cancelled_error_gracefully(mock_setup, mock_run):
    mock_run.side_effect = asyncio.CancelledError()
    await main.main()  # should not raise
