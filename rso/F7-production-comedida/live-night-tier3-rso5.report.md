# RHO PMO Report - F7 Tier3 Repeat Data-Gate Attempt

Timestamp: 2026-06-30T03:29:29+02:00

## Objective
- [blocked] Repeat tier3 from the live suspended CronJob after the first
  FullMetal product-discovery remediation. Evidence: manual Job
  `skirmshop-competitor-crawler-tier3-rso5-20260630012310`, logs, metrics and
  live safe-state checks. Blocker: the Job succeeded safely but still produced
  `products=0`, `history inserted=0` and `pushed=0`, so F7 live-night remains
  NOT PASS.

## Directives
- [x] Use live CronJob template only; do not unsuspend schedules. Evidence:
  `kubectl -n skirmshop create job skirmshop-competitor-crawler-tier3-rso5-20260630012310 --from=cronjob/skirmshop-competitor-crawler-tier3`.
- [x] Keep retry amplification disabled. Evidence: Job image/status readback
  showed `backoffLimit=0`.
- [x] Keep production safe-disabled. Evidence: post-run Deployments
  `skirmshop-competitor-crawler` and `skirmshop-stock-prober` remain
  `replicas=0`; tier1/tier2/tier3 CronJobs remain `suspend=true backoffLimit=0`.
- [x] Do not print secrets. Evidence: negative log grep for
  `password|secret` returned no matches.

## Acceptance Criteria
- [x] **Job source image is the remediated digest.** Evidence: Job template
  image `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:caddac10af5a8120654715eafb9e5dcf10d19bd47fef497b800aa2a9c1ca4db0`.
- [x] **Job completes without Kubernetes retry.** Evidence: Job status
  `1 succeeded`, pod
  `skirmshop-competitor-crawler-tier3-rso5-20260630012310-t75r9`
  `Succeeded 0 Completed`.
- [x] **Crawler runtime remains safe.** Evidence: logs show robots disallow for
  forbidden paths, no challenge/captcha/403/429/503/fetch-blocked matches, and
  `fullmetal.es` stopped at `max_pages=25`.
- [blocked] **Data gate passes with real documents/history/Brain push.**
  Evidence: logs show `mundoreplicas.com history inserted=0 skipped=0`,
  `fullmetal.es history inserted=0 skipped=0`, `cazatacticas.com history
  inserted=0 skipped=0`, and summary `done - pushed=0 failed=0`.
- [x] **Metrics captured during linger.** Evidence: `/metrics` returned
  `competitor_crawler_run_total{status="ok",tier="tier3"} 1`,
  `competitor_crawler_push_sent_total{tier="tier3"} 0`,
  `competitor_crawler_push_failed_total{tier="tier3"} 0`,
  `competitor_crawler_run_active{tier="tier3"} 0`.
- [x] **Safe-disabled state preserved after run.** Evidence: crawler/prober
  Deployments `replicas=0`; tier1/tier2/tier3 CronJobs `suspend=true`,
  `backoffLimit=0`, crawler digest still `sha256:caddac10...`.

## Findings
- [blocked] FullMetal still consumed the 25-page budget on categories before
  producing product documents. Evidence: logs fetched allowed categories through
  `https://fullmetal.es/escopetas-muelle`, then
  `max_pages=25 reached; queued URLs left=6040`, `visited=25 products=0`.
- [blocked] `mundoreplicas.com` and `cazatacticas.com` still did not yield
  products. Evidence: each visited 1 fallback page and wrote `history inserted=0`.

## Remediation Prepared After RSO5
- [x] PrestaShop listing-card extraction implemented. Evidence:
  `src/extractor.py` extracts `article.product-miniature` /
  `.js-product-miniature` cards with same-domain URL, title and price; test
  `test_extract_products_prestashop_listing_cards` covers FullMetal-like cards
  and off-domain rejection.
- [x] Detail URL priority implemented. Evidence: `src/extractor.py` adds
  `is_priority_product_url`; `src/crawler.py` puts priority detail URLs ahead
  of already queued shallow category URLs; test
  `test_crawl_store_prioritizes_detail_links_over_shallow_categories` proves a
  deep FullMetal product is fetched within `max_pages=3`.
- [x] Local validation passed. Evidence:
  `pytest tests/test_extractor.py tests/test_crawler_egress_guard.py` ->
  `23 passed`; `.venv/bin/pytest` -> `239 passed`; `.venv/bin/python -m
  compileall src tests` PASS; `git diff --check` PASS; `kubectl apply
  --dry-run=server -k k8s` PASS.

## Specialist Checks
- [x] **Backend** - root cause and scoped remediation. Evidence: code/tests
  above; rso5 live logs prove previous remediation was insufficient.
- [x] **DevOps** - live Job/source/safe state. Evidence: Job from suspended
  CronJob, `backoffLimit=0`, no schedule activation, post-run safe state.
- [x] **Security** - no forbidden paths/secrets/challenge escalation. Evidence:
  negative grep for challenge/error/secret terms and preserved egress policy.
- [blocked] **Verifier/Auditor** - F7 data gate. Evidence: PMO direct
  re-execution of logs/status/metrics/state denies PASS because data is absent.

## Status
- 2026-06-30T03:29:29+02:00 - BLOCKED: rso5 is operationally safe but not a
  F7 PASS. Next gate is release/pin the listing-card + priority-frontier image,
  Argo sync it while remaining safe-disabled, then repeat tier3 data gate.
