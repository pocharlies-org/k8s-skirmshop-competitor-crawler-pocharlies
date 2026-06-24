# F4 Backend Foundation Report - Contract, Guard, Metrics

**Date:** 2026-06-25T01:08:00+02:00
**Role:** `rho-backend` via Claude CLI, audited by Codex RSO
**Result:** PASS for backend foundation only
**Scope:** mock-only contract/mapper/kill-switch/metrics. No live HTTP, no k8s, no DB live.

## Checklist

- [x] `ProbeResult` contract implemented. Evidence: `src/prober/contract.py`; validation matrix covers probed exact qty, uncapped in-stock (`stock_qty=None`), blocked/skipped/error states, and illegal combos.
- [x] F3 mapper implemented. Evidence: `probe_result_to_observation(result, run_id)` maps to `src.history_writer.Observation` with `stock_method="cart_probe"`; tests verify fake `write_observations` idempotency.
- [x] DomainGuard cooldown implemented. Evidence: `src/prober/killswitch.py`; default cooldown 36h; tests verify 429 trip, cooldown blocked result, cooldown expiry.
- [x] In-memory metrics implemented. Evidence: `src/prober/metrics.py`; tests verify label-independent `competitor_crawl_block_total` and `competitor_probe_total`.
- [x] Scope cleanup performed. Evidence: Claude generated out-of-scope scaffold files (`base.py`, `transport.py`, `shopify.py`) were removed by Codex RSO because they were not covered and referenced non-existent guard methods.
- [x] Checks passed. Evidence: `pytest -q` -> `64 passed in 0.22s`; `git diff --check` -> PASS; `python3 -m compileall src tests` -> PASS.

## Files Accepted

- `src/prober/__init__.py`
- `src/prober/contract.py`
- `src/prober/killswitch.py`
- `src/prober/metrics.py`
- `tests/test_prober_contract.py`

## Residual Risks / Pending Backend

- [blocked] ShopifyProber not implemented yet.
- [blocked] WooProber not implemented yet.
- [blocked] GenericProber default-deny not implemented yet.
- [blocked] Actual 403/429/challenge conversion from transport responses into DomainGuard trip must be tested in platform probers.
- [blocked] No live calibration target; still blocked by research.
