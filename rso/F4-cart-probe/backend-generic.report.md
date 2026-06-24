# F4 Backend Report - Transport + Generic Default-Deny

**Date:** 2026-06-25T01:18:00+02:00
**Role:** `rho-backend` via Claude CLI, audited by Codex RSO
**Result:** PASS for transport + Generic default-deny
**Scope:** mock-only. No live HTTP, no Shopify/Woo, no k8s.

## Checklist

- [x] Transport abstraction implemented. Evidence: `src/prober/transport.py`; `ProbeResponse` and `ProbeTransport` Protocol; tests verify `json()` and protocol shape.
- [x] GenericProber default-deny implemented. Evidence: `src/prober/generic.py`; returns `ProbeStatus.SKIPPED`, `stock_status=unknown`, `stock_qty=None`, `error_code=no_safe_pattern`, `cleanup_status=NOT_NEEDED`.
- [x] Generic does not touch network. Evidence: `tests/test_prober_generic.py::test_generic_default_deny_skips_without_network`; fake transport call list remains empty.
- [x] Metrics increment for skipped generic probe. Evidence: `tests/test_prober_generic.py`; `competitor_probe_total{domain,platform,status=skipped}` increments once.
- [x] Checks passed. Evidence: `pytest -q` -> `70 passed in 0.24s`; `git diff --check` -> PASS; `python3 -m compileall src tests` -> PASS.

## Files Accepted

- `src/prober/transport.py`
- `src/prober/generic.py`
- `src/prober/__init__.py`
- `tests/test_prober_generic.py`

## Residual Risks / Pending Backend

- [blocked] ShopifyProber not implemented yet.
- [blocked] WooProber not implemented yet.
- [blocked] `service.probe_stock` facade not implemented yet.
- [blocked] 403/429/challenge transport response handling remains pending for platform probers.
