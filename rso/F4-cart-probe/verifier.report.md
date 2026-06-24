# RHO Verifier Report - F4 Cart-Probe

**Role:** `rho-verifier` delegated by Codex RSO.
**Mode:** read-only; no implementation, no file edits, no live cart-probe, no re-delegation.
**Verdict:** **PASS for F4 mock-only scope**. Live sample-10 calibration remains **BLOCKED**.

## Git Evidence
- [x] Branch: `codex/competitor-crawler-F4-cart-probe`.
- [x] HEAD verified by verifier: `61c7c28 Add F4 prober service and disabled manifests`.
- [x] Working tree was clean and up to date with origin at verifier start.

## Gates Re-Executed
- [x] `pytest -q` -> `98 passed`.
- [x] `git diff --check` -> exit 0.
- [x] `python3 -m compileall src tests` -> exit 0.
- [x] `kubectl apply --dry-run=server -k k8s` -> server dry-run created `skirmshop-competitor-crawler`, `skirmshop-stock-prober`, `competitor-crawler-secrets`, and `skirmshop-stock-prober-egress`.

## Scope Audit
- [x] Diff from F3 touches only F4 scope: `src/prober/*`, `tests/test_prober_*`, `k8s/prober-*`, `k8s/kustomization.yaml`, and `rso/F4-cart-probe/*`.
- [x] No F6/F7 files touched. Evidence: verifier found no `prices.py` or `intel.py`; no live comparison code was changed.
- [x] No deploy/prod or release/ArgoCD paths touched by F4.
- [x] No CronJob or Service added for the prober; Deployment stays `replicas: 0`.

## Security Smoke
- [x] No live HTTP in `src/prober`; transport is a protocol and tests use scripted fakes.
- [x] No checkout/login/CAPTCHA solver/bypass code path.
- [x] Generic/unknown platforms default to `SKIPPED/no_safe_pattern` with zero network calls.
- [x] Cleanup failure maps to `ERROR/cart_cleanup_failed` and `CleanupStatus.DIRTY`.
- [x] `403`, `429`, and challenge responses trip cooldown and block later probes with zero network.
- [x] K8s disabled plus default-deny egress is rendered and server dry-run accepted.

## Calibration Gate
- [blocked] **Sample-10 live calibration is not passable from current targets.** Evidence: `data/competitors/fingerprint.json` has 5 green domains and all are `generic_html`; there are zero green Shopify domains; WooCommerce domains are `novritsch.com` and `silverback-airsoft.com`, both red/captcha and excluded. `researcher.report.md` marks this as blocked.

## Residual Risks
- The Shopify and Woo inventory oracles are proven by mock/unit tests only; no real storefront has been calibrated.
- `DomainGuard` and `Metrics` are in-memory; acceptable for disabled/mock F4, but must be reconsidered before production activation.
- The prober image tag is `:pending`; no build/release is part of F4.
