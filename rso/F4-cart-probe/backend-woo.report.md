# F4 Backend Report - WooProber Mock

**Date:** 2026-06-25T01:41:00+02:00
**Role:** `rho-backend` via Claude CLI, audited by Codex RSO
**Result:** PASS for WooCommerce mock prober
**Scope:** mock-only. No live HTTP/cart-probe.

## Checklist

- [x] Woo `quantity_limits.maximum` path. Evidence: `tests/test_prober_woo.py::test_quantity_limit_maximum_leaks_stock_with_cleanup`.
- [x] Woo in-stock with unknown finite cap. Evidence: `test_200_without_maximum_is_probed_qty_none_with_cleanup`.
- [x] Woo out-of-stock errors. Evidence: `test_out_of_stock_error_is_unavailable_no_cleanup`.
- [x] 403/429/challenge kill-switch. Evidence: `test_antibot_blocks_and_trips_cooldown`.
- [x] Cleanup failure is ERROR/DIRTY. Evidence: `test_cleanup_failure_after_add_is_error_dirty`.
- [x] Unexpected statuses and transport errors are ERROR. Evidence: `test_unexpected_status_is_error_no_cleanup`, `test_transport_exception_before_add_is_error_no_cleanup`.
- [x] Checks passed. Evidence: `pytest -q` -> `91 passed in 0.31s`; `git diff --check` -> PASS; `python3 -m compileall src tests` -> PASS.

## Files Accepted

- `src/prober/woo.py`
- `src/prober/__init__.py`
- `tests/test_prober_woo.py`

## Residual Risks / Pending Backend

- [blocked] `service.probe_stock` facade not implemented yet.
- [blocked] No live Woo calibration target exists in current green domain set.
