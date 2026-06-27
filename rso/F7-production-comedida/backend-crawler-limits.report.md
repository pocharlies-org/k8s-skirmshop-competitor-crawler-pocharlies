# Backend Crawler Limits Report - F7

Date: 2026-06-27T21:45:00+02:00
Role: Codex PMO exception after `rho-backend` timed out without stdout or diff.

## Objective

Add hard no-DoS crawl rails before any F7 live smoke: per-domain page limit and configurable polite delay.

## Directives

- [x] No production activation. Evidence: no k8s replica, CronJob or Argo activation changes.
- [x] No secret changes. Evidence: only crawler config/code/tests and RSO report touched.
- [x] Network-free tests only. Evidence: tests monkeypatch `fetch_page` and `asyncio.sleep`.

## Acceptance Criteria

- [x] `crawl_store` has a hard `max_pages` cap. Evidence: `src/crawler.py` stops the loop when `len(visited) >= max_pages`.
- [x] `crawl_store` accepts configurable `delay_seconds`. Evidence: `src/crawler.py` uses `delay_seconds` instead of a fixed `0.5`, and skips sleep when `0`.
- [x] Invalid limits fail closed before any fetch. Evidence: `tests/test_crawler_egress_guard.py` covers `max_pages=0`, non-int `max_pages`, and negative `delay_seconds`.
- [x] Production config declares conservative limits for every domain. Evidence: `config.yaml` sets `max_pages: 25` and `delay_seconds: 0.5` on all 14 stores.
- [x] PMO verification executed. Evidence: `/tmp/crawler-f7-venv/bin/python -m pytest -q tests/test_crawler_egress_guard.py` -> `8 passed`; `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> `207 passed`; `/tmp/crawler-f7-venv/bin/python -m compileall src tests` -> PASS; `kubectl apply --dry-run=server -k k8s` -> PASS; `git diff --check` -> PASS.

## Residual Risks

- `max_pages: 25` is a conservative first F7 limit, not a final product-completeness target.
- The crawler still does not parse `robots.txt`/`Crawl-delay`; this remains a F7 no-DoS gap before broad nightly activation.
