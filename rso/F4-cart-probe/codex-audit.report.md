# Codex RSO Audit - F4 Cart-Probe

**Auditor:** Codex RSO/PMO.
**Decision:** **F4 mock/dry-run scope PASS; full F4 gate BLOCKED on live sample-10 calibration.**

Codex did not implement product code in this closeout. Implementation work was delegated to Claude CLI roles; Codex re-ran gates, reviewed reports, and audited evidence.

## Evidence Re-Run by Codex
- [x] `pytest -q` -> `98 passed in 0.25s`.
- [x] `git diff --check` -> exit 0.
- [x] `python3 -m compileall src tests` -> exit 0.
- [x] `kubectl apply --dry-run=server -k k8s` -> server dry-run accepted the crawler Deployment, prober Deployment, ExternalSecret, and prober NetworkPolicy.
- [x] Security scan of `src/prober`, `tests/test_prober_*`, `k8s`, and F4 reports found no live HTTP client, checkout/login/CAPTCHA solver, cookie/raw-HTML logging, or secret values.
- [x] `rho-security` returned PASS for mock-only security scope.
- [x] `rho-verifier` independently re-ran tests/diff/compileall/k8s dry-run and returned PASS for mock-only scope.

## What Passed
- [x] F4 prober contract and F3 mapper.
- [x] Shopify mock prober: 422 quantity parsing, bounded search, unavailable, blocked, cleanup, unexpected status handling.
- [x] Woo mock prober: `quantity_limits.maximum`, qty unknown, unavailable, blocked, cleanup, unexpected status handling.
- [x] Generic default-deny policy.
- [x] Domain cooldown/kill-switch and metrics.
- [x] Disabled prober manifests plus default-deny egress NetworkPolicy.
- [x] No F6/F7 comparison/scheduling scope was touched.

## Blocking Gate
- [blocked] **Live sample-10 calibration.** Current approved targets do not include a safe green Shopify/Woo domain. All green targets in `fingerprint.json` are `generic_html`; the WooCommerce targets are red/captcha and must not be probed. Generic probing is explicitly default-deny until a per-domain safe pattern is approved and tested.

## RSO Decision
F4 is not closed as full PASS and F6 is not opened from this branch. The next valid move is one of:
- find/approve a safe green Shopify/Woo live target and run a limited sample-10 calibration with cleanup evidence; or
- amend the master acceptance criteria to accept mock-only F4 and move live calibration into a later, explicit phase.

Until one of those is done, the project may keep F4 artifacts merged as disabled/mock-ready, but the production cart-probe gate remains closed.
