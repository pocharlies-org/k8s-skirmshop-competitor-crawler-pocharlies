# F7 Security PMO Audit - partial

**Role:** Codex PMO audit after `rho-security` timeout with no stdout.  
**Mode:** read-only checks only; no production writes, no deploy.

## RHO Checklist

### Directives
- [x] Do not expose secrets. Evidence: grep found only env var names plus `test-secret` fixture in `tests/test_push_client.py`; no real API key values.
- [x] Do not activate production. Evidence: rendered kustomize keeps both deployments at `replicas: 0`; no `CronJob` is rendered.
- [x] Fail closed for Brain auth. Evidence: rendered crawler env has `REQUIRE_BRAIN_API_KEY=true`, `competitor-crawler-secrets optional: false`; backend tests cover missing-key failure before POST.
- [x] Pod/container hardening present. Evidence: rendered manifests include `runAsNonRoot`, uid/gid/fsGroup `10001`, `seccompProfile: RuntimeDefault`, `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, and drop all capabilities.
- [x] Prober egress remains blocked while live transport is absent. Evidence: `k8s/prober-networkpolicy.yaml` renders `egress: []`.

### Residual Security Blockers
- [blocked] Independent `rho-security` report is missing due CLI timeout.
- [blocked] Crawler egress is now default-deny, but F7 still needs an explicit allowlist before live activation.
- [blocked] Prober live transport/allowlist is not implemented; no production cart-probe activation is allowed.
- [blocked] Release image/digest is not yet published/pinned; `:pending` must not be activated.
- [blocked] `competitor_intel` live DB/migration and least-privilege DB credentials remain unresolved.

## Evidence Commands
- `rg -n "kubectl apply|replicas: [1-9]|kind: CronJob|schedule:|checkout|login|captcha|BRAIN_API_KEY=.*|X-API-Key: [A-Za-z0-9]|test-secret" .github k8s src tests rso/F7-production-comedida -S`
- `kubectl kustomize k8s | rg -n "replicas:|CronJob|optional:|REQUIRE_BRAIN_API_KEY|securityContext|readOnlyRootFilesystem|allowPrivilegeEscalation|runAsNonRoot|image:"`
- `pytest -q tests/test_push_client.py`
- `kubectl apply --dry-run=server -k k8s`
