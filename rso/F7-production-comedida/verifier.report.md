# F7 Verifier Report - pre-activation

**Owner:** Codex RSO/PMO verifier pass.  
**Date:** 2026-06-27T16:24:50+02:00.  
**Claude status:** `rho-verifier` CLI was retried with a reduced read-only prompt and exited `124` without stdout. This report is a PMO verification exception and is not an independent Claude verifier PASS.

## Commands re-executed

- `pytest -q tests/test_push_client.py`
  - Result: `3 passed in 0.07s`.
- `pytest -q`
  - Result: `142 passed in 0.24s`.
- `python3 -m compileall src tests`
  - Result: PASS; `src`, `src/adapters`, `src/prober`, `tests`, `tests/fixtures` compiled/listed without errors.
- `kubectl kustomize k8s`
  - Result: PASS.
  - Rendered crawler/prober remain `replicas: 0`.
  - Rendered images remain `harbor.e-dani.com/homelab/skirmshop-competitor-crawler:pending` and `harbor.e-dani.com/homelab/skirmshop-stock-prober:pending`.
  - Rendered secrets are referenced by name only: `competitor-crawler-secrets`, `optional: false`.
  - Rendered network policies are default-deny egress for crawler and prober (`egress: []`).
- `kubectl apply --dry-run=server -k k8s`
  - Result: PASS.
  - Server dry-run accepted Deployments, ExternalSecret and both NetworkPolicies.
- `kubectl -n skirmshop get deploy,cronjob,externalsecret,secret,networkpolicy | rg 'skirmshop-competitor-crawler|skirmshop-stock-prober|competitor-crawler-secrets|competitor-crawler' || true`
  - Result: no exact live crawler/prober/secret/networkpolicy resources matched.
- `kubectl -n databases get database competitor-intel -o yaml`
  - Result: `NotFound`; live `competitor_intel` database is not created.
- `gh run view 28291855094 --json status,conclusion,url,headSha,jobs --jq .`
  - Result: CI success on `e1920ba407d246136f7ce70c6c1a06261a7917af`.
  - `standard / Build images`: success in 43s.
  - `standard / Lint and validate manifests`: success in 25s.
- `git diff --check && git status --short --branch`
  - Result before this report batch: clean on `codex/competitor-crawler-F7-production-comedida...origin/codex/competitor-crawler-F7-production-comedida`.

## Pass/fail

- [x] Backend auth tests pass. Evidence: `pytest -q tests/test_push_client.py` -> 3 passed.
- [x] Full local test suite passes. Evidence: `pytest -q` -> 142 passed.
- [x] Kustomize render passes and remains inactive. Evidence: `kubectl kustomize k8s` rendered `replicas: 0`, `:pending`, and default-deny egress.
- [x] Kubernetes server dry-run passes. Evidence: `kubectl apply --dry-run=server -k k8s`.
- [x] HEAD CI prior to this report batch passes. Evidence: GitHub Actions run `28291855094`, commit `e1920ba`.
- [blocked] Independent Claude verifier PASS is missing due CLI timeout.
- [blocked] F7 production PASS is impossible today because no live DB, no published image tag/digest, no active CronJob/runner, no explicit egress allowlists, no observability dashboard, and no real-night evidence.

## Residual risks

- The release workflow exists on this branch, but it does not publish an image until it is available on the runnable workflow path and executed with a release version.
- `src.main` is scheduler/daemon oriented; it is unsuitable as a bounded CronJob command without a one-shot wrapper.
- Default-deny NetworkPolicies are safe for inactive manifests, but activation requires carefully scoped allow rules or pods will not reach Brain/Firecrawl/Postgres/approved competitor domains.
- The prober remains too risky for production until live transport, cleanup, allowlist and kill-switch evidence exist.
