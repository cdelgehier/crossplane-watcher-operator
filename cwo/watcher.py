"""Event handler — watches one Crossplane resource type and notifies GitHub.

Core logic:
    1. Watch Kubernetes events for a resource type (e.g. XStackVM).
    2. For each event, check if the claim has homelab.io/github-* annotations.
    3. If the state (Ready/Synced) has changed, post or edit a PR comment.
    4. Save the comment ID and state hash on the claim (as annotations) — no DB needed.
"""

import asyncio

from kubernetes_asyncio.client import ApiClient
from kubernetes_asyncio.dynamic import DynamicClient

from cwo import github_client, notifier
from cwo.logger import get_logger
from cwo.settings import SETTINGS

log = get_logger(__name__)


async def _patch_annotations(
    dyn_client: DynamicClient,
    resource,
    name: str,
    namespace: str,
    annotations: dict[str, str],
) -> None:
    """Save annotations on the Kubernetes claim (stateless persistence)."""
    try:
        await resource.patch(
            body={"metadata": {"annotations": annotations}},
            name=name,
            namespace=namespace,
            content_type="application/merge-patch+json",
        )
    except Exception:
        log.warning("failed to patch annotations", name=name, namespace=namespace)


async def _handle_event(
    dyn_client: DynamicClient,
    resource,
    obj: dict,
) -> None:
    """Process one Kubernetes event.

    Decision flow:
        1. Does the claim have homelab.io/github-* annotations? (no → skip)
        2. Are there conditions yet? (no → skip, too early)
        3. Has the state changed since last notification? (no → skip, anti-spam)
        4. Format a comment and POST/PATCH it on the GitHub PR.
    """
    metadata = obj.get("metadata", {})
    name = metadata.get("name", "unknown")
    namespace = metadata.get("namespace", "unknown")
    kind = obj.get("kind", resource.kind)
    annotations = metadata.get("annotations") or {}

    bound_log = log.bind(kind=kind, name=name, namespace=namespace)

    # Skip claims not created via homelab CI
    repo = annotations.get(SETTINGS.annotation_github_repo)
    pr_number = annotations.get(SETTINGS.annotation_github_pr)
    commit_sha = annotations.get(SETTINGS.annotation_github_sha, "unknown")

    if not repo or not pr_number:
        bound_log.debug("no github annotations, skipping")
        return

    conditions: list[dict] = (obj.get("status") or {}).get("conditions") or []
    if not conditions:
        bound_log.debug("no conditions yet, skipping")
        return

    # Anti-spam: only notify if conditions actually changed
    current_hash = notifier.compute_hash(conditions)
    last_hash = annotations.get(SETTINGS.annotation_last_hash)

    if current_hash == last_hash:
        bound_log.debug("state unchanged, skipping", hash=current_hash)
        return

    bound_log.info("condition changed, notifying github", hash=current_hash)

    body = notifier.format_comment(
        kind=kind,
        name=name,
        namespace=namespace,
        commit_sha=commit_sha,
        conditions=conditions,
        full_status=obj.get("status", {}),
    )

    comment_id = annotations.get(SETTINGS.annotation_comment_id) or None
    try:
        if comment_id:
            await github_client.update_comment(repo, comment_id, body)
        else:
            comment_id = await github_client.create_comment(repo, pr_number, body)
    except Exception as exc:
        bound_log.error("github notification failed", error=str(exc))
        return

    # Persist new state onto the claim — no external DB needed
    await _patch_annotations(
        dyn_client,
        resource,
        name,
        namespace,
        {
            SETTINGS.annotation_comment_id: comment_id,
            SETTINGS.annotation_last_hash: current_hash,
        },
    )


async def watch_resource(api_client: ApiClient, resource) -> None:
    """Watch all events for one resource type (e.g. all XStackVM resources).

    Runs a loop:
        - Open a streaming connection to the Kubernetes API.
        - For each ADDED/MODIFIED event, call ``_handle_event()``.
        - If the connection breaks, wait with exponential backoff and retry.
        - If the task is cancelled (operator re-discovery), exit cleanly.
    """
    kind = resource.kind
    log.info("starting watch", kind=kind, group=SETTINGS.api_group)

    backoff = 5
    async with DynamicClient(api_client) as dyn_client:
        while True:
            try:
                async for event in resource.watch(timeout=SETTINGS.watch_timeout_seconds):
                    if event["type"] == "DELETED":
                        continue
                    await _handle_event(dyn_client, resource, event["object"].to_dict())

                backoff = 5  # reset after a successful cycle

            except asyncio.CancelledError:
                log.info("watch cancelled", kind=kind)
                return
            except Exception as exc:
                log.warning(
                    "watch stream error, restarting",
                    kind=kind,
                    error=str(exc),
                    backoff=backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
