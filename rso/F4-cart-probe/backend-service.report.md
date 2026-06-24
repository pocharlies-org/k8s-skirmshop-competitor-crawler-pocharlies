# F4 Backend Report - Service Facade

**Date:** 2026-06-25T01:50:00+02:00
**Role:** `rho-backend` via Claude CLI, audited by Codex RSO
**Result:** PASS for backend mock-only service facade
**Scope:** mock-only. No live HTTP/cart-probe.

## Checklist

- [x] `probe_stock` facade implemented. Evidence: `src/prober/service.py`.
- [x] Shopify dispatch. Evidence: `tests/test_prober_service.py` scripted 422 qty dispatches to `ShopifyProber` and increments one `probed` metric.
- [x] Woo dispatch and alias. Evidence: `tests/test_prober_service.py` covers `woocommerce` and `woo`.
- [x] Generic/unknown platform default-deny. Evidence: `generic_html` and `bigcommerce` tests return `SKIPPED/no_safe_pattern` with zero transport calls.
- [x] Cooldown before Shopify blocks without network. Evidence: service cooldown test returns `BLOCKED/cooldown_active` and fake transport call list remains empty.
- [x] Checks passed. Evidence: `pytest -q` -> `98 passed in 0.27s`; `git diff --check` -> PASS; `python3 -m compileall src tests` -> PASS.

## Files Accepted

- `src/prober/service.py`
- `src/prober/__init__.py`
- `tests/test_prober_service.py`

## Backend Residual Risks

- [blocked] Live calibration remains blocked: no green Shopify/Woo target and Generic remains default-deny without approved pattern.
- [blocked] DevOps NetworkPolicy/egress isolation not yet implemented.
