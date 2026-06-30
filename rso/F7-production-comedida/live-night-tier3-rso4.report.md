# RHO PMO Report - F7 Tier3 Live-Night Attempt

Timestamp: 2026-06-30T03:10:00+02:00

## Objective
- [blocked] Validate one real nocturnal crawler window from the production CronJob
  template without enabling schedules. Evidence: manual Job, logs, SQL/Brain or
  explicit fail-closed blockers. Blocker: the window was operationally clean
  but produced `pushed=0` and `history inserted=0`, so it does not satisfy the
  F7 data gate.

## Directives
- [x] Use only an existing production CronJob template. Evidence:
  `kubectl -n skirmshop create job skirmshop-competitor-crawler-tier3-rso4-20260630010920 --from=cronjob/skirmshop-competitor-crawler-tier3`.
- [x] Keep production safe-disabled. Evidence: post-run tier1/tier2/tier3 remain
  `suspend=true`, crawler/prober Deployments remain `replicas=0`.
- [x] No retry amplification. Evidence: source CronJob and created Job have
  `backoffLimit=0`.
- [x] Keep crawler safety controls active: robots/crawl-delay, max pages,
  challenge fail-closed, no cart/compare/return/search/captcha BFS, no Firecrawl
  on challenge pages. Evidence: logs show robots disallow for `mi-cuenta`,
  `carrito` and `busqueda` without fetching them; `fullmetal.es` stopped at
  `max_pages=25`; no challenge/captcha/fetch-blocked lines appeared.
- [x] Do not print secret values. Evidence: logs contain no secret values; Job
  used the CronJob secret refs.

## Acceptance Criteria
- [x] **Job created from live tier3 CronJob.** Evidence: `job.batch/skirmshop-competitor-crawler-tier3-rso4-20260630010920 created`; source template showed `suspend=true`, `backoffLimit=0`, image digest `sha256:ee04c7db4a785cc56fb259e7fb5a9db5e6bd28e75994e163992d1f042fd0`.
- [x] **Job completes successfully.** Evidence: Job `1 succeeded`, pod
  `phase=Succeeded exit=0 reason=Completed`.
- [x] **No anti-bot escalation.** Evidence: logs have no `403`, `429`, `503`,
  `challenge`, `captcha`, or `FetchBlockedError`.
- [x] **No forbidden path crawl.** Evidence: logs show those links only as
  `robots disallow`; actual GET list contains allowed `fullmetal.es` category
  paths and no cart/basket/checkout/compare/return/login/account/search fetches.
- [blocked] **History and Brain evidence exist.** Evidence: logs show
  `mundoreplicas.com history inserted=0 skipped=0`, `fullmetal.es history inserted=0 skipped=0`,
  `cazatacticas.com history inserted=0 skipped=0`, and tier summary
  `pushed=0 failed=0`. No SQL/Brain data row exists to validate.
- [x] **Metrics/readiness evidence captured.** Evidence: `/metrics` during linger
  returned `competitor_crawler_run_total{status="ok",tier="tier3"} 1`,
  `competitor_crawler_push_sent_total{tier="tier3"} 0`,
  `competitor_crawler_push_failed_total{tier="tier3"} 0`, and
  `competitor_crawler_run_active{tier="tier3"} 0`.
- [x] **Safe-disabled state preserved after run.** Evidence: Deployments
  `replicas=0`, CronJobs `suspend=true backoffLimit=0`, Argo `Synced Healthy`.

## Store Outcomes
- [blocked] `mundoreplicas.com`: public DNS did not resolve (`getent hosts`
  found no `mundoreplicas.com`/`www.mundoreplicas.com` records); runtime robots
  fetch failed with `Name or service not known`; Firecrawl fallback returned 0
  products.
- [blocked] `fullmetal.es`: runtime fetched robots and 25 allowed category/help
  pages with HTTP 200, skipped disallowed account/cart/search links, but
  extracted 0 products before `max_pages=25`.
- [blocked] `cazatacticas.com`: public DNS did not resolve (`getent hosts`
  found no `cazatacticas.com`/`www.cazatacticas.com` records); runtime robots
  fetch failed with `Name or service not known`; Firecrawl fallback returned 0
  products.

## Remediation Prepared
- [x] Product URL discovery for FullMetal improved. Evidence:
  `src/extractor.py` now treats deep Spanish product paths containing
  `/armas-de-airsoft/` as product candidates; `tests/test_extractor.py` covers
  the FullMetal URL shape.
- [x] PrestaShop product fallback added. Evidence: `src/extractor.py` extracts
  product title, price, brand, image and availability from common PrestaShop
  product pages with `body.page-product` / `product-id-*` and `.current-price`;
  tests cover product page extraction and category non-extraction.
- [x] Validation passed before release. Evidence:
  `/tmp/crawler-f7-venv/bin/python -m pytest -q tests/test_extractor.py tests/test_crawler_egress_guard.py tests/test_crawler_robots.py`
  -> `24 passed`; `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> `236 passed`;
  `/tmp/crawler-f7-venv/bin/python -m compileall src tests` PASS; `git diff --check` PASS;
  `kubectl apply --dry-run=server -k k8s` PASS.

## Specialist Checks
- [x] **DevOps** - live Job/source template/backoff/cleanup/state. Evidence:
  Job from live CronJob, `backoffLimit=0`, post-run safe-disabled state.
- [blocked] **Backend** - logs, history, push semantics, exit code. Evidence:
  exit 0 and push failures 0, but no products/history rows were produced.
- [x] **Security** - no forbidden paths, no secrets, anti-bot fail-closed.
  Evidence: negative challenge/HTTP error grep; forbidden URLs only appeared as
  robots-disallowed, not GET requests.
- [blocked] **Verifier/Auditor** - independent status/log/readback/state review.
  Evidence: PMO re-ran status/log/metrics/state; F7 PASS denied because
  history/Brain data evidence is absent.

## Status
- 2026-06-30T03:10:00+02:00 - OPEN: tier3 manual live-night attempt is the next
  safe F7 gate after prober B3 PASS. F7 remains NOT PASS until evidence is real.
- 2026-06-30T03:12:00+02:00 - BLOCKED: tier3 live-night attempt was safe and
  exited 0, but it is not a F7 PASS because the run produced no competitor
  documents, no history rows and no Brain pushes. Next safe work is target
  quality/product-discovery remediation before another data-gate attempt.
- 2026-06-30T03:18:00+02:00 - REMEDIATION PREPARED: FullMetal product path
  discovery and PrestaShop extraction fallback implemented and verified locally.
  Pending: commit/push, CI, release/pin new crawler image, Argo sync and repeat
  tier3 data-gate attempt.
