# RHO Backend Report - F7 robots.txt and Crawl-delay

## Objective
- [x] Close the crawler no-DoS code gap by respecting `robots.txt` disallow rules and `Crawl-delay` before broad F7 activation. Evidence: `src/robots.py`, `src/crawler.py`, `tests/test_crawler_robots.py`.

## Directives
- [x] Do not activate production. Evidence: no k8s manifests changed.
- [x] Do not add external dependencies. Evidence: implementation uses stdlib `urllib.robotparser` plus existing `httpx`.
- [x] Keep missing/transient robots.txt fail-open but preserve configured app delay. Evidence: `load_robots_policy` returns allow policy on fetch error or non-authoritative missing status.
- [x] Treat explicit robots 401/403 conservatively. Evidence: `load_robots_policy` returns a disallow-all policy for 401/403.

## Acceptance Criteria
- [x] Disallowed start URL is skipped before `fetch_page`. Evidence: `tests/test_crawler_robots.py::test_crawl_store_skips_start_url_disallowed_by_robots`.
- [x] Disallowed discovered links are never fetched. Evidence: `tests/test_crawler_robots.py::test_crawl_store_skips_disallowed_links`.
- [x] Effective polite delay is `max(config.delay_seconds, robots Crawl-delay)`. Evidence: `tests/test_crawler_robots.py::test_crawl_store_uses_max_of_configured_delay_and_robots_delay`.
- [x] Robots fetch failure is fail-open and still bounded by configured delay. Evidence: `tests/test_crawler_robots.py::test_crawl_store_robots_fetch_failure_fails_open`.
- [x] Full test and compile gates pass. Evidence: `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> `211 passed in 2.37s`; `/tmp/crawler-f7-venv/bin/python -m compileall src tests` PASS.
- [x] Kubernetes manifests still validate and remain inactive. Evidence: `kubectl apply --dry-run=server -k k8s` PASS; no k8s manifests changed in this code commit.

## Specialist Checks
- [blocked] `rho-backend` delegated implementer. Evidence: Claude CLI timed out with code `124` and no stdout/diff.
- [x] Codex/RSO PMO exception scoped to backend no-DoS code/tests/report. Evidence: `src/robots.py`, `src/crawler.py`, `tests/test_crawler_robots.py`, this report.

## Status
- 2026-06-27T22:31:00+02:00 - Prepared as PMO exception after Claude timeout.
- 2026-06-27T22:36:00+02:00 - PMO validation PASS: robots tests plus egress tests `12 passed`; full suite `211 passed`; compileall PASS; server dry-run PASS. Pending release/pin because live image digest does not contain this code yet.
- 2026-06-27T22:28:24Z - Release PASS: GitHub Actions run `28300857935` published tag `f7-6199575`; both Harbor endpoints returned digest `sha256:ccab2c1508c38cb133a01594c11b5a926673dab660e4e6ca9a9c1b0822cc6193`. Manifests prepared to pin that digest.
