"""Operator loop — discovers Crossplane resource types and manages watchers.

How it works:
    1. Connect to the Kubernetes API (in-cluster or local kubeconfig).
    2. Use the Discovery API to find all resource types in the watched group
       (e.g. XStackVM, XS3Bucket, …).
    3. Start one watcher task per resource type.
    4. Every ``discovery_interval_seconds``, re-discover to detect:
       - New resource types → start a new watcher.
       - Removed resource types → cancel its watcher.
       - Dead watchers (stream error) → restart them.
"""

import asyncio
import pathlib
import ssl

from kubernetes_asyncio import config
from kubernetes_asyncio.client import ApiClient
from kubernetes_asyncio.dynamic import DynamicClient
from kubernetes_asyncio.dynamic.discovery import EagerDiscoverer

from cwo.logger import get_logger
from cwo.settings import SETTINGS
from cwo.watcher import watch_resource

log = get_logger(__name__)

_HEALTHY_FILE = pathlib.Path("/tmp/healthy")  # noqa: S108
_READY_FILE = pathlib.Path("/tmp/ready")  # noqa: S108


def _relax_kube_ssl() -> None:
    """Work around Python 3.13+ strict X509 validation on Kubernetes.

    Kubernetes cluster CAs are self-signed and lack the *Authority Key Identifier*
    extension.  Starting with Python 3.13 / OpenSSL 3.x the default SSL
    context sets ``VERIFY_X509_STRICT`` which rejects such certificates.

    We monkey-patch ``ssl.create_default_context`` so that every context
    returned has the strict flag cleared.  This is safe because:
      - The CA certificate is still fully verified against the trust store.
      - Only the "nice-to-have" AKI metadata check is skipped.
    """
    _original = ssl.create_default_context

    def _patched(*args: object, **kwargs: object) -> ssl.SSLContext:
        ctx = _original(*args, **kwargs)
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        return ctx

    ssl.create_default_context = _patched  # type: ignore[assignment]
    log.info(
        "relaxed X509_STRICT for kube self-signed CA",
        openssl=ssl.OPENSSL_VERSION,
    )


async def _discover_resources(api_client: ApiClient) -> list:
    """Find all Crossplane resource types in the watched API group."""
    async with DynamicClient(api_client, discoverer=EagerDiscoverer) as dyn_client:
        all_resources = await dyn_client.resources.search(group=SETTINGS.api_group)
        resources = [
            r for r in all_resources if not r.kind.endswith("List") and "/status" not in r.name
        ]
        kinds = [r.kind for r in resources]
        log.info("discovered resources", group=SETTINGS.api_group, kinds=kinds)
        return resources


async def run() -> None:
    """Main operator loop: discover CRDs and manage one watch task per resource kind."""
    if not SETTINGS.kube_ssl_strict:
        _relax_kube_ssl()

    try:
        config.load_incluster_config()
        log.info("using in-cluster kubeconfig")
    except config.ConfigException:
        ctx = SETTINGS.kube_context
        await config.load_kube_config(context=ctx)
        log.info("using local kubeconfig", context=ctx or "current-context")

    active_tasks: dict[str, asyncio.Task] = {}

    async with ApiClient() as api_client:
        while True:
            try:
                resources = await _discover_resources(api_client)
                current_kinds = {r.kind: r for r in resources}

                # Cancel tasks for removed CRDs
                for kind in list(active_tasks):
                    if kind not in current_kinds:
                        log.info("crd removed, cancelling watch", kind=kind)
                        active_tasks.pop(kind).cancel()

                # Start or restart tasks for new/dead CRDs
                for kind, resource in current_kinds.items():
                    task = active_tasks.get(kind)
                    if task is not None and task.done():
                        log.warning("watch task died, restarting", kind=kind)
                    if task is None or task.done():
                        active_tasks[kind] = asyncio.create_task(
                            watch_resource(api_client, resource),
                            name=f"watch-{kind}",
                        )

                _HEALTHY_FILE.touch()
                _READY_FILE.touch()

            except Exception as exc:
                log.error("discovery failed", error=str(exc))

            await asyncio.sleep(SETTINGS.discovery_interval_seconds)
