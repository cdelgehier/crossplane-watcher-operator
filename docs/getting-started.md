# Getting Started

This guide helps you set up the operator on your machine, run the
tests and try it against a local Kubernetes cluster.

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.14+ | [python.org](https://www.python.org/) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Task | 3+ | `brew install go-task` |
| kubectl | 1.28+ | `brew install kubectl` |
| Helm | 3+ | `brew install helm` |
| helm-unittest | latest | `helm plugin install https://github.com/helm-unittest/helm-unittest` |
| container-structure-test | latest | `brew install container-structure-test` |
| Docker | any | Rancher Desktop, Docker Desktop or Colima |

---

## 1 — Clone and install

```bash
git clone https://github.com/cdelgehier/crossplane-watcher-operator.git
cd crossplane-watcher-operator
task install            # uv sync --all-groups
task pre-commit:install # set up git hooks (commitizen + ruff + helm)
```

---

## 2 — Run the tests

```bash
task test:py
task test:helm
task test       # both at once
task ci         # lint + fmt:check + tests (same as the CI pipeline)
```

---

## 3 — Build the Docker image

```bash
task docker:build   # build → crossplane-watcher-operator:dev
task test:docker    # container-structure-test
```

---

## 4 — Run the operator locally

The operator needs a GitHub token and a valid kubeconfig.

```bash
# Create a local cluster (if you don't have one yet)
kind create cluster

# Start the operator
export CWO_GITHUB_TOKEN=ghp_xxxx
task up
```

If you already have a cluster with the right permissions, use your own context:

```bash
CWO_KUBE_CONTEXT=rancher-desktop CWO_GITHUB_TOKEN=ghp_xxxx task up
```

Without `CWO_KUBE_CONTEXT`, the operator uses the current context
from your kubeconfig. In-cluster (pod), this setting is ignored.

Expected output on startup:

```
[info ] crossplane-watcher-operator starting  discovery_interval_seconds=60 api_group=homelab.crossplane.io
[info ] using local kubeconfig               context=kind-kind
[info ] discovered resources                 group=homelab.crossplane.io kinds=[]
```

`kinds=[]` is normal — there are no CRDs in the watched group yet.

> **Tip:** With a dummy token, GitHub API calls will fail with a 401.
> But the entire discovery + watch + hash + format logic works.
> Replace with a real PAT to see actual comments posted on PRs.

---

## 5 — Send fake events

A set of test scripts in `tests/scripts/` lets you simulate a full
Crossplane lifecycle without real providers.

> **Important:** You need **cluster-admin** rights to create CRDs.
> Use a local cluster:
>
> ```bash
> kind create cluster   # recommended
> ```

### 5.1 — Create a fake CRD and claim

In a **second terminal**:

```bash
kubectl apply -f tests/scripts/fake-crd.yaml
kubectl apply -f tests/scripts/fake-claim.yaml
```

Expected operator logs (within 60 seconds or at next discovery cycle):

```
[info ] discovered resources    group=homelab.crossplane.io kinds=['FakeResource']
[info ] starting watch          kind=FakeResource group=homelab.crossplane.io
[debug] no conditions yet, skipping  kind=FakeResource name=test-claim namespace=default
```

The claim has no `status.conditions` yet — that is expected.

### 5.2 — Simulate condition changes

Run the interactive script:

```bash
./tests/scripts/simulate-events.sh
```

Press Enter between each step. Expected operator logs:

**Step 1 — Provisioning in progress** (`Ready=False`, reason `Creating`):

```
[info ] condition changed, notifying github  hash=87ee88b1f159  kind=FakeResource  name=test-claim
[error] github notification failed           error='401 Unauthorized'
```

The hash changes, the operator tries to POST a comment. The 401 is
expected with a dummy token.

**Step 2 — Error** (`Ready=False`, reason `ReconcileError`):

```
[info ] condition changed, notifying github  hash=51d79f5ce9ab  kind=FakeResource  name=test-claim
[error] github notification failed           error='401 Unauthorized'
```

Different hash → new notification attempt.

**Step 3 — Success** (`Ready=True`, reason `Available`):

```
[info ] condition changed, notifying github  hash=d2cf45f6e1b1  kind=FakeResource  name=test-claim
[error] github notification failed           error='401 Unauthorized'
```

Different hash again → new notification attempt.

**Step 4 — Same state again** (anti-spam test):

With a **real** GitHub token, step 3 would have saved the hash on the
claim and step 4 would log:

```
[debug] state unchanged, skipping  hash=d2cf45f6e1b1  kind=FakeResource  name=test-claim
```

With a dummy token, GitHub fails → the hash is never saved →
the operator retries. This is by design: if notification fails,
the operator must retry on the next event.

### 5.3 — Clean up

```bash
kubectl delete -f tests/scripts/fake-claim.yaml
kubectl delete -f tests/scripts/fake-crd.yaml
kind delete cluster   # optional: remove the local cluster
```

---

## 6 — Debug: task call graph

The operator exposes a live task dump via `SIGUSR1` (Python 3.14).
Send the signal to print the asyncio call graph to stderr at any time,
without restarting the process.

**On Kubernetes:**

```bash
kubectl exec -it <pod> -- sh -c 'kill -USR1 $(pgrep -f cwo.main)'
kubectl logs <pod>
```

**Locally (`task up`):**

```bash
kill -USR1 $(pgrep -f cwo.main)
```

Expected output (one block per active watch task):

```
Task 'watch-XStackVM' (running)
  └─ watcher.py:145 watch_resource()
     └─ kubernetes_asyncio/watch.py:87 __anext__()

Task 'watch-XS3Bucket' (suspended)
  └─ watcher.py:145 watch_resource()
     └─ asyncio/tasks.py:639 sleep()
```

> The `simulate-events.sh` script sends `SIGUSR1` automatically between
> steps so you can observe the call graph during a local test run.

---

## 7 — Configuration reference

All variables use the `CWO_` prefix (Crossplane Watcher Operator).
They are validated by Pydantic at startup.

| Variable | Required | Default | Description |
|---|---|---|---|
| `CWO_GITHUB_TOKEN` | yes | — | GitHub PAT (`public_repo` scope) |
| `CWO_API_GROUP` | no | `homelab.crossplane.io` | Kubernetes API group to watch |
| `CWO_LOG_LEVEL` | no | `INFO` | Minimum log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `CWO_DISCOVERY_INTERVAL_SECONDS` | no | `60` | Seconds between CRD re-discovery |
| `CWO_KUBE_CONTEXT` | no | current-context | Kubernetes context to use (ignored in-cluster) |
