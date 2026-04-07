"""Entry point — starts the operator and handles shutdown.

    python -m cwo.main

Steps:
    1. Set up structured logging.
    2. Start the operator loop (discover → watch → notify).
    3. Listen for SIGTERM/SIGINT for graceful pod shutdown.
"""

import asyncio
import signal

from cwo.logger import get_logger, setup_logging
from cwo.operator import run
from cwo.settings import SETTINGS

log = get_logger(__name__)


def _handle_signal(sig: signal.Signals, loop: asyncio.AbstractEventLoop) -> None:
    """Cancel all tasks on SIGTERM/SIGINT (graceful pod shutdown)."""
    log.info("signal received, shutting down", signal=sig.name)
    for task in asyncio.all_tasks(loop):
        task.cancel()


def _handle_sigusr1() -> None:
    """Dump asyncio call graph on SIGUSR1 (debug: kill -USR1 <pid>)."""
    for task in asyncio.all_tasks():
        asyncio.print_call_graph(task)


async def main() -> None:
    """Start the operator."""
    setup_logging(SETTINGS.log_level)
    log.info(
        "crossplane-watcher-operator starting",
        log_level=SETTINGS.log_level,
        api_group=SETTINGS.api_group,
        discovery_interval_seconds=SETTINGS.discovery_interval_seconds,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal, sig, loop)
    loop.add_signal_handler(signal.SIGUSR1, _handle_sigusr1)

    try:
        await run()
    except asyncio.CancelledError:
        log.info("shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
