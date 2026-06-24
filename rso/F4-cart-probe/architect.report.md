# F4 Architect Report - Cart-Probe Contract

**Date:** 2026-06-25T00:58:00+02:00
**Role:** `rho-architect` via Claude CLI read-only
**Result:** PASS for architecture; live calibration remains BLOCKED
**Scope:** contract/design only. No files edited by Claude, no live probe.

## Checklist

- [x] Data contract defined. Evidence: proposed `ProbeResult` with `domain`, `product_key`, `variant_id`, `url`, `platform`, `observed_at`, `probe_status`, `stock_qty`, `stock_status`, `stock_method=cart_probe`, `block_reason`, `cleanup_status`, and `error_code`.
- [x] F3 integration defined. Evidence: one-way mapper `probe_result_to_observation()` to existing F3 `Observation`; `history_writer.py` already accepts `stock_method="cart_probe"` and numeric/nullable `stock_qty`; no F3 schema change required.
- [x] In-repo module architecture defined. Evidence: proposed `src/prober/` package: `contract.py`, `transport.py`, `killswitch.py`, `metrics.py`, `shopify.py`, `woo.py`, `generic.py`, `service.py`.
- [x] Operational isolation defined. Evidence: dedicated disabled Deployment (`replicas:0`) plus required NetworkPolicy before any live probe; no CronJob in F4.
- [x] Shopify algorithm defined. Evidence: `/cart/add.js`, parse 422 quantity where possible, bounded binary search fallback, `/cart/clear.js` in `finally`, 403/429/challenge kill-switch.
- [x] WooCommerce algorithm defined. Evidence: prefer `quantity_limits.maximum`, fallback to safe add-to-cart responses, cleanup/remove item in `finally`, 403/429/challenge kill-switch.
- [x] Generic policy defined. Evidence: default-deny `skipped/no_safe_pattern` unless an explicit per-domain add-to-cart pattern is allowlisted and covered by mock tests.
- [x] Kill-switch/cooldown/metrics defined. Evidence: `DomainGuard` state `OK -> TRIPPED(reason, until_ts)`, default cooldown 36h, metric `competitor_crawl_block_total{domain,reason}` plus `competitor_probe_total{domain,platform,status}`.
- [x] Backend acceptance tests defined. Evidence: T1-T20 matrix in architect output, including cleanup-on-failure, kill-switch, metrics, F3 mapper, red/captcha skip, and illegal state validation.
- [blocked] Live sample-10 calibration. Blocker: no green Shopify/Woo target and no NetworkPolicy egress isolation.

## RSO Decisions

- F4 proceeds in the current repo as `src/prober/` plus disabled prober deployment, not as a new remote repository.
- `block_reason` and `cleanup_status` stay in structured logs/metrics for F4; they are not added to F3 `price_stock_observation` to avoid F3 schema drift.
- Generic probing is default-deny. A generic domain may only be probed after a safe per-domain pattern is allowlisted and covered by tests.
- Uncapped Shopify inventory may return `probe_status=probed`, `stock_status=in_stock`, `stock_qty=None`; backend must make this explicit so it is not confused with an exact quantity.

## Backend Test Matrix Required

- Shopify: 422 parse, binary-search max, uncapped in-stock, unavailable, 403, 429, challenge, cleanup-on-success, cleanup-on-add-failure, cleanup-failure dirty escalation.
- WooCommerce: `quantity_limits.maximum`, add-to-cart success, out-of-stock error, limit-absent unknown, remove-item cleanup success/fail.
- Generic: default-deny, allowlisted/tested pattern only.
- DomainGuard: trip on 403/429/challenge, subsequent cooldown block, metric labels.
- F3 mapper: valid `Observation`, `stock_method=cart_probe`, fake-connection idempotency.
- Red/captcha tier: silverback/novritsch never probed.

## Residual Risks

- [blocked] Live calibration target unavailable with current fingerprint.
- [blocked] NetworkPolicy/egress isolation absent until DevOps implements it.
- [blocked] F4 must keep writes mock-only until live CNPG/migration/role is approved.
