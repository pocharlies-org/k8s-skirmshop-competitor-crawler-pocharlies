# F4 Researcher Report - Cart-Probe

**Date:** 2026-06-25T00:52:00+02:00
**Role:** `rho-researcher` via Claude CLI read-only
**Result:** PASS for research; live calibration target BLOCKED
**Scope:** repo/docs/config inspection only. No edits by Claude, no live cart-probe, no mutating kubectl.

## Checklist

- [x] F4 branch and gates confirmed. Evidence: branch `codex/competitor-crawler-F4-cart-probe`, HEAD `f73fc52`; F3 PASS in `rso/F3-history/codex-audit.report.md`; F5 checklist Objective `[x]`; F4 handoff forbids F6/F7.
- [x] Repo destination researched. Evidence: current repo has `src/adapters/`, `src/fetcher.py`, `src/stock.py`, `src/history_writer.py`, CI/tests, and disabled `k8s/manifest.yaml`. Recommendation: implement `src/prober/` plus dedicated disabled deployment in this repo first; do not create a new remote repo without RSO approval.
- [x] Platform/domain candidates inventoried. Evidence: `data/competitors/fingerprint.json` has 5 green domains, all `generic_html`: `airsoft-legends.nl`, `leopard.es`, `airsoft2go.de`, `specnaarms.com`, `waffencenter-gotha.de`.
- [blocked] Green Shopify/Woo live calibration target. Blocker: no green Shopify domains; WooCommerce detected only on `novritsch.com` and `silverback-airsoft.com`, both red/captcha and excluded.
- [x] Reusable code identified. Evidence: `BaseSiteAdapter`, `GenericHtmlAdapter`, `fetcher`, `stock.normalize_availability`, and F3 `history_writer.Observation`/`write_observations` are ready for mocked F4 integration.
- [x] DevOps requirements identified. Evidence: current Deployment has `replicas: 0` and `automountServiceAccountToken: false`; no CronJob exists; no NetworkPolicy exists, so egress isolation is a required DevOps gap before live probing.
- [x] Security/legal risks identified. Evidence: F4 must never use checkout/login/CAPTCHA solving; must respect tier/robots/crawl-delay, use cleanup-on-success/fail, and implement 403/429/challenge kill-switch.

## Key Findings

- All green targets are `generic_html`; only `airsoft-legends.nl` and `leopard.es` have visible stock.
- `silverback-airsoft.com` remains red/captcha and must not be probed.
- F3 writer already accepts `stock_method="cart_probe"` and numeric `stock_qty`; no schema change is required for F4 integration.
- The crawler k8s repo has no `NetworkPolicy`; egress isolation must be added before live probe.

## RSO Decision

Proceed with F4 as an in-repo isolated module (`src/prober/`) and disabled deployment/NetworkPolicy, not a new remote repo, until a later RSO decision requires a separate repository. Proceed with mocked Shopify/Woo/Generic probe implementations and kill-switch tests. Keep live calibration `[blocked]` until RSO approves a safe generic target or a new green Shopify/Woo candidate is found.

## Recommended Next Roles

- `rho-architect`: define probe contract, cooldown/metric model, F3 integration, and Generic policy.
- `rho-backend`: implement mocked probe core and tests only; no live calls.
- `rho-devops`: disabled prober deployment + NetworkPolicy/server dry-run; no Cron.
- `rho-security`: no checkout/login/CAPTCHA/dirty cart verification.

## Residual Risks

- [blocked] Live sample-10 calibration cannot close with current target set.
- [blocked] Egress isolation is absent until DevOps adds NetworkPolicy/manifests.
- [blocked] F3 live CNPG migration/role remains a later production gate; F4 must not write live observations yet.
