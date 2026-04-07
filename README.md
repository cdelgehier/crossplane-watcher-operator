# crossplane-watcher-operator

[![Python](https://img.shields.io/badge/Python_3.14-3776AB.svg?style=for-the-badge&logo=Python&logoColor=white)](https://python.org)
[![uv](https://img.shields.io/badge/uv-DE5FE9.svg?style=for-the-badge&logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/badge/Ruff-D7FF64.svg?style=for-the-badge&logo=Ruff&logoColor=black)](https://docs.astral.sh/ruff/)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF.svg?style=for-the-badge&logo=GitHub-Actions&logoColor=white)](https://github.com/features/actions)
[![Crossplane](https://img.shields.io/badge/Crossplane-EF7B4D.svg?style=for-the-badge&logo=Crossplane&logoColor=white)](https://crossplane.io)
[![Commitizen](https://img.shields.io/badge/Commitizen-Conventional_Commits-D3E97A.svg?style=for-the-badge&logo=Commitizen&logoColor=black)](https://commitizen-tools.github.io/commitizen/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-FAB040.svg?style=for-the-badge&logo=pre-commit&logoColor=black)](https://pre-commit.com/)

Kubernetes operator that watches Crossplane composites in the `homelab.crossplane.io` group and posts status updates as comments on the originating GitHub Pull Request.

## Why?

When a developer submits a claim through a GitOps PR, there is no feedback on what happens after the merge:

- Did the provisioning start?
- Is there a Crossplane error?
- Are my Cloud resources ready?

`crossplane-watcher-operator` closes this loop: **one single comment, edited in real time**, directly in the PR.

---

## Overview

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant GH as GitHub PR
    participant CI as GitHub Actions
    participant AR as ArgoCD
    participant XP as Crossplane
    participant CWO as crossplane-watcher-operator

    Dev->>GH: Opens a PR with claim YAML
    GH->>CI: Trigger PR pipeline
    CI->>GH: Validation comment ✅ / ❌
    CI->>GH: Render comment (planned Cloud resources)
    CI->>GH: Inject annotations (repo, pr-number, commit-sha)

    Dev->>GH: Merge
    GH->>AR: New commit on main
    AR->>XP: Sync claim YAML (with annotations)
    XP->>XP: Provisions Cloud resources

    loop Watch K8s — re-discovery every 60s
        CWO->>XP: Watch status.conditions via Discovery API
        XP-->>CWO: Condition changed (Ready / Synced)
        CWO->>GH: Edits the status comment on the PR
    end
```

---

## Internal architecture

```mermaid
flowchart TD
    MAIN["main.py asyncio.run() + SIGTERM handler"]
    MAIN --> OP

    OP["operator.py run() — loop every 60s"]
    OP -->|"K8s Discovery API search(group=homelab.crossplane.io)"| DISC

    DISC["Discovered resources XStackVM, XS3Bucket, ..."]
    DISC -->|"one asyncio.Task per kind"| W1 & W2 & WN

    W1["watch_resource(XStackVM)"]
    W2["watch_resource(XS3Bucket)"]
    WN["watch_resource(...)"]

    W1 & W2 & WN --> EVT

    EVT{K8s event received ADDED / MODIFIED}
    EVT -->|no GitHub annotations| SKIP[Skip]
    EVT -->|no conditions yet| SKIP
    EVT -->|hash unchanged| SKIP2[Skip — anti-spam]
    EVT -->|state changed| NOT

    NOT["notifier.py format_comment() + compute_hash()"]
    NOT --> NOTE{github-comment-id in annotations?}

    NOTE -->|No — first event| POST["github_client.py POST → create comment"]
    NOTE -->|Yes — next events| PATCH["github_client.py PATCH → edit comment"]

    POST & PATCH --> ANN["Patch annotations on the claim github-comment-id + last-notified-hash"]
```

---

## Notification strategy

Instead of creating a new comment on every state change (spam), the operator **always edits the same comment**:

```mermaid
sequenceDiagram
    participant CWO as crossplane-watcher-operator
    participant K8S as Kubernetes (claim)
    participant GH as GitHub PR

    CWO->>K8S: Watch stream — event received
    CWO->>CWO: compute_hash(conditions)
    CWO->>K8S: Read annotation last-notified-hash
    alt same hash
        CWO->>CWO: Skip — no change
    else different hash
        CWO->>K8S: Read annotation github-comment-id
        alt no comment-id (first event)
            CWO->>GH: POST /issues/{pr}/comments → create comment
            GH-->>CWO: comment_id = 12345
            CWO->>K8S: Patch annotation github-comment-id=12345
        else comment-id present
            CWO->>GH: PATCH /issues/comments/12345 → edit comment
        end
        CWO->>K8S: Patch annotation last-notified-hash
    end
```

### Comment format

```
## Crossplane Provisioning Status

**Resource:** `XStackVM/monapp-vm` (namespace: `dev-monapp`)
**Commit:** `abc123def`
**Updated at:** 2026-04-08T10:23:00Z

| Condition | Status | Reason | Message |
|---|---|---|---|
| ✅ Ready | True | Available | |
| ✅ Synced | True | ReconcileSuccess | |

<details><summary>Full status</summary> ... </details>
```

| Conditions | Emoji | Meaning |
|---|---|---|
| `Ready=True` | ✅ | Provisioning complete |
| `Ready=False` + `ReconcilePending` | ⏳ | Provisioning in progress |
| `Ready=False` + `ReconcileError` | ❌ | Error — see message |
| `Synced=False` | ⚠️ | Out of sync |

---

## CI/CD pipeline

```mermaid
flowchart LR
    PUSH["push on main"] --> CZ_CHECK["commitizen-check"]
    CZ_CHECK --> CZ_BUMP["bump-version → bump pyproject.toml → CHANGELOG.md → tag vX.Y.Z"]
    CZ_BUMP -->|"tag pipeline"| BUILD["docker-publish → buildx multi-arch → GHCR :vX.Y.Z + :latest"]
    CZ_BUMP -->|"tag pipeline"| RELEASE["create-release → GitHub Release (CHANGELOG)"]
```

---

## Configuration

Environment variables — prefix `CWO_` (Crossplane Watcher Operator).

| Variable | Required | Default | Description |
|---|---|---|---|
| `CWO_GITHUB_TOKEN` | ✅ | — | GitHub PAT with `public_repo` scope |
| `CWO_API_GROUP` | ❌ | `homelab.crossplane.io` | Kubernetes API group to watch |
| `CWO_LOG_LEVEL` | ❌ | `INFO` | Minimum log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `CWO_DISCOVERY_INTERVAL_SECONDS` | ❌ | `60` | Seconds between CRD re-discovery |
| `CWO_KUBE_CONTEXT` | ❌ | current-context | Kubernetes context (ignored in-cluster) |

---

## Local development

### Prerequisites

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- [Task](https://taskfile.dev)
- `kubectl` configured on a cluster with Crossplane

### Getting started

```bash
# Install dependencies
task install

# Install pre-commit hooks
task pre-commit:install

# Check the code
task lint
task fmt

# Run tests
task test:py
task test:helm

# Run the operator locally
export CWO_GITHUB_TOKEN=ghp_xxxx
task up
```

### Available tasks

| Command | Description |
|---|---|
| `task install` | Install dependencies with uv |
| `task lint` | Lint with ruff |
| `task fmt` | Format with ruff |
| `task fmt:check` | Check formatting without modifying |
| `task test:py` | Run pytest unit tests |
| `task test:helm` | Helm unit tests (helm-unittest) |
| `task test` | Run all tests |
| `task ci` | lint + fmt:check + tests (local pipeline) |
| `task docker:build` | Build Docker image locally |
| `task test:docker` | container-structure-test |
| `task up` | Run the operator locally |
| `task pre-commit:install` | Install git hooks |
| `task pre-commit:run` | Run all pre-commit hooks |

---

## Deployment

The operator is deployed via **ArgoCD** from `k3s-homelab` — same pattern as other platform components.

```mermaid
flowchart LR
    CW["crossplane-watcher Helm chart"] -->|"Git source"| APP
    APP["ArgoCD Application sync-wave: 7 (after Crossplane core)"] -->|"deploy"| NS
    NS["crossplane-system k3s homelab"]
```

The Helm chart deploys:
- `Deployment` — the watcher pod
- `ServiceAccount` — Kubernetes identity for the pod
- `ClusterRole` — `get/list/watch/patch` on `homelab.crossplane.io/*`
- `ClusterRoleBinding`
- `Secret` — `CWO_GITHUB_TOKEN` (or use `existingSecret`)

The image is published to GHCR:
```
ghcr.io/cdelgehier/crossplane-watcher-operator:latest
```

---

## Claim annotations

**Read** (injected by `homelab-ci-templates`):

```yaml
metadata:
  annotations:
    homelab.io/github-repo: "cdelgehier/homelab-endusers"
    homelab.io/github-pr: "42"
    homelab.io/github-sha: "abc123def"
```

**Written** by the operator (state persisted without external storage):

```yaml
metadata:
  annotations:
    homelab.io/github-comment-id: "12345"       # ID of the GitHub comment to edit
    homelab.io/last-notified-hash: "a3f2b1c9"   # Hash of the last notified state
```
