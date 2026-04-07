"""Message builder — formats the markdown comment posted to GitHub PRs.

Two responsibilities:
    1. ``format_comment()`` → Build markdown text with emojis and a conditions table.
    2. ``compute_hash()``   → Create a short fingerprint for anti-spam deduplication.
"""

import hashlib
from datetime import UTC, datetime

import yaml

_EMOJI = {
    ("Ready", "True"): "✅",
    ("Ready", "False", "ReconcilePending"): "⏳",
    ("Ready", "False", "ReconcileError"): "❌",
    ("Synced", "True"): "✅",
    ("Synced", "False"): "⚠️",
}


def _emoji_for(condition: dict) -> str:
    """Pick the right emoji for a Crossplane condition."""
    ctype = condition.get("type", "")
    status = condition.get("status", "")
    reason = condition.get("reason", "")
    return _EMOJI.get((ctype, status, reason)) or _EMOJI.get((ctype, status)) or "🔵"


def format_comment(
    kind: str,
    name: str,
    namespace: str,
    commit_sha: str,
    conditions: list[dict],
    full_status: dict,
) -> str:
    """Build the markdown comment posted to the GitHub PR.

    Args:
        kind:        Resource type (e.g. "XStackVM")
        name:        Resource name (e.g. "monapp-vm")
        namespace:   Kubernetes namespace (e.g. "eu1-dev-monapp")
        commit_sha:  Git SHA that created the claim
        conditions:  List of Crossplane conditions (Ready, Synced, …)
        full_status: Complete status object, shown in a collapsible block

    Returns:
        Markdown string ready to be posted as a GitHub PR comment.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = []
    for c in conditions:
        emoji = _emoji_for(c)
        ctype = c.get("type", "—")
        status = c.get("status", "—")
        reason = c.get("reason", "—")
        message = c.get("message", "")
        rows.append(f"| {emoji} {ctype} | {status} | {reason} | {message} |")

    table = "\n".join(rows) if rows else "| — | — | — | — |"

    full_status_yaml = yaml.dump(full_status, default_flow_style=False, allow_unicode=True).strip()

    return f"""\
## Crossplane Provisioning Status

**Resource:** `{kind}/{name}` (namespace: `{namespace}`)
**Commit:** `{commit_sha}`
**Updated at:** {now}

| Condition | Status | Reason | Message |
|---|---|---|---|
{table}

<details>
<summary>Full status</summary>

```yaml
{full_status_yaml}
```

</details>
"""


def compute_hash(conditions: list[dict]) -> str:
    """Create a short fingerprint of the current state for anti-spam.

    Only ``Ready`` and ``Synced`` conditions are included.
    The ``message`` field is intentionally excluded — it often contains
    timestamps that change every reconciliation while the state hasn't.

    Returns:
        A 12-character hex string (e.g. "a1b2c3d4e5f6").
    """
    relevant = sorted(
        [
            f"{c.get('type')}={c.get('status')}/{c.get('reason', '')}"
            for c in conditions
            if c.get("type") in ("Ready", "Synced")
        ]
    )
    return hashlib.sha1(",".join(relevant).encode()).hexdigest()[:12]  # noqa: S324
