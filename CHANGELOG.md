## v0.4.0 (2026-04-08)

### Feat

- **helm**: add imagePullSecrets support for private registries

### Fix

- **helm**: use time-based liveness probe to detect stuck operator
- **helm**: only add v prefix to numeric image tags
- relax strict X509 validation for self-signed K8s cluster CAs

## v0.3.1 (2026-04-07)

### Fix

- **ci**: install task runner and fix helm-unittest plugin verification

## v0.3.0 (2026-04-07)

### Feat

- **ci**: add CI workflow with python, helm and docker tests

## v0.2.0 (2026-04-07)

### Feat

- initial implementation of crossplane-watcher-operator

### Fix

- **ci**: use bump output version instead of git describe for tag re-annotation
