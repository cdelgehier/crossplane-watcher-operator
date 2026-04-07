#!/bin/bash
# Simulate Crossplane condition changes on the fake claim.
# Usage: ./tests/scripts/simulate-events.sh

set -euo pipefail

RESOURCE="fakeresources.homelab.crossplane.io"
NAME="test-claim"
NS="default"

echo "=== 1. Provisioning in progress (Ready=False, Synced=True) ==="
kubectl patch "$RESOURCE/$NAME" -n "$NS" --type=merge --subresource=status -p '{
  "status": {
    "conditions": [
      {"type": "Ready", "status": "False", "reason": "Creating", "message": "Provisioning in progress", "lastTransitionTime": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"},
      {"type": "Synced", "status": "True", "reason": "ReconcileSuccess", "message": "", "lastTransitionTime": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}
    ]
  }
}'
echo "→ Check operator logs: should see 'condition changed, notifying github'"
echo ""
read -rp "Press Enter to dump the asyncio task graph (SIGUSR1)..."

echo ""
echo "=== 1b. Asyncio call graph (Python 3.14) ==="
WATCHER_PID=$(pgrep -f "cwo.main" | head -1 || true)
if [ -n "$WATCHER_PID" ]; then
  kill -USR1 "$WATCHER_PID"
  echo "→ Sent SIGUSR1 to PID $WATCHER_PID — check stderr for the task call graph"
else
  echo "→ Operator process not found (is 'task up' running?)"
fi
echo ""
read -rp "Press Enter to simulate next event..."

echo ""
echo "=== 2. Error state (Ready=False, Synced=False) ==="
kubectl patch "$RESOURCE/$NAME" -n "$NS" --type=merge --subresource=status -p '{
  "status": {
    "conditions": [
      {"type": "Ready", "status": "False", "reason": "ReconcileError", "message": "cannot create EC2 instance: AccessDenied", "lastTransitionTime": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"},
      {"type": "Synced", "status": "False", "reason": "ReconcileError", "message": "apply failed", "lastTransitionTime": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}
    ]
  }
}'
echo "→ Check operator logs: should see another notification (hash changed)"
echo ""
read -rp "Press Enter to simulate next event..."

echo ""
echo "=== 3. Success (Ready=True, Synced=True) ==="
kubectl patch "$RESOURCE/$NAME" -n "$NS" --type=merge --subresource=status -p '{
  "status": {
    "conditions": [
      {"type": "Ready", "status": "True", "reason": "Available", "message": "", "lastTransitionTime": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"},
      {"type": "Synced", "status": "True", "reason": "ReconcileSuccess", "message": "", "lastTransitionTime": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}
    ]
  }
}'
echo "→ Check operator logs: should see final notification (Ready=True ✅)"
echo ""
read -rp "Press Enter to simulate duplicate (anti-spam test)..."

echo ""
echo "=== 4. Same state again (should be skipped — anti-spam) ==="
kubectl patch "$RESOURCE/$NAME" -n "$NS" --type=merge --subresource=status -p '{
  "status": {
    "conditions": [
      {"type": "Ready", "status": "True", "reason": "Available", "message": "", "lastTransitionTime": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"},
      {"type": "Synced", "status": "True", "reason": "ReconcileSuccess", "message": "", "lastTransitionTime": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}
    ]
  }
}'
echo "→ Check operator logs: should see 'state unchanged, skipping'"

echo ""
echo "=== Done! ==="
echo "Cleanup: kubectl delete -f tests/scripts/fake-claim.yaml && kubectl delete -f tests/scripts/fake-crd.yaml"
