# F4 Backend Report - ShopifyProber Mock

**Date:** 2026-06-25T01:31:00+02:00
**Role:** `rho-backend` via Claude CLI, audited by Codex RSO
**Result:** PASS for Shopify mock prober
**Scope:** mock-only. No live HTTP/cart-probe.

## Checklist

- [x] Shopify 422 quantity parse. Evidence: `tests/test_prober_shopify.py::test_422_leaks_exact_stock_no_cleanup`.
- [x] Shopify unavailable/sold-out. Evidence: `test_422_sold_out_is_unavailable`.
- [x] Bounded binary search fallback. Evidence: `test_binary_search_fallback_finds_max`.
- [x] Uncapped in-stock support. Evidence: `test_high_qty_accepted_uncapped` returns `stock_qty=None`.
- [x] 403/429/challenge kill-switch. Evidence: `test_antibot_blocks_and_trips_cooldown`.
- [x] Cleanup always after dirty cart; cleanup failure is ERROR/DIRTY. Evidence: `test_cleanup_failure_after_add_is_error_dirty`.
- [x] Unexpected statuses are ERROR, not false stock/unavailable. Evidence: `test_unexpected_status_on_fallback_is_error_no_cleanup` and `test_unexpected_status_during_binary_search_is_error_with_cleanup`.
- [x] Checks passed. Evidence: `pytest -q` -> `81 passed in 0.20s`; `git diff --check` -> PASS; `python3 -m compileall src tests` -> PASS.

## Files Accepted

- `src/prober/shopify.py`
- `src/prober/__init__.py`
- `tests/test_prober_shopify.py`

## Residual Risks / Pending Backend

- [blocked] WooProber not implemented yet.
- [blocked] `service.probe_stock` facade not implemented yet.
- [blocked] No live Shopify calibration target exists in current green domain set.
