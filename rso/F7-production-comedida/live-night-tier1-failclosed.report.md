# RHO PMO Report - F7 Tier1 Live Run Fail-Closed

Timestamp: 2026-06-30T01:23:00+02:00

## Objective
- [blocked] Validate a live nocturnal tier1 crawler run from the production CronJob template. Blocker: the run completed as a Kubernetes Job failure because 4/5 tier1 stores returned anti-bot/challenge signals and the crawler failed closed with zero pushes.

## Scope
- Namespace: `skirmshop`
- Job: `skirmshop-competitor-crawler-tier1-rso3-20260629231925`
- Source template: `cronjob/skirmshop-competitor-crawler-tier1`
- Image: `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:ee04c7db4a785cc56fb259e7fb5a9db5e6bd28e75994a954e163992d1f042fd0`
- Activation state preserved: CronJobs remained `suspend=true`; this was a manual one-shot Job only.

## Direct Evidence
- [x] Job used the latest anti-bot image. Evidence: `kubectl -n skirmshop get job skirmshop-competitor-crawler-tier1-rso3-20260629231925 -o wide` showed image digest `sha256:ee04c7db4a785cc56fb259e7fb5a9db5e6bd28e75994a954e163992d1f042fd0`.
- [x] First pod failed closed with no Brain pushes. Evidence: pod `...-lhdl5` logs showed run_id `tier1:20260629T231944324497Z`, `done - pushed=0 failed=4`, `run_once exiting non-zero: 4 document(s) failed to push (--fail-on-push-errors)`.
- [x] Second pod repeated because the CronJob template still had `backoffLimit: 1`. Evidence: `kubectl -n skirmshop describe job ...` showed `Backoff Limit: 1`, two failed pods `...-lhdl5` and `...-vptsq`, and event `BackoffLimitExceeded`.
- [x] Challenge pages were not scraped through Firecrawl fallback. Evidence: logs show `fetch blocked` followed by `blocked by anti-bot/challenge ... aborting store` for Gunfire, Taiwangun, Evike-Europe and Redwolf.
- [x] No cart/checkout/compare/return BFS was observed in the remediated run. Evidence: log scan for the two pods found challenge aborts and Bunker501 category pages only; no `basketedit.php`, product compare or return fetch lines appeared.
- [x] Bunker501 stayed bounded. Evidence: logs showed `max_pages=25 reached; queued URLs left=14852`, `crawl done - visited=25 products=0`, `history inserted=0 skipped=0`.
- [x] Live resources remained safe-disabled after the run. Evidence: `kubectl -n skirmshop get deploy ...` showed crawler/prober `replicas=0`; `kubectl -n skirmshop get cronjob ...` showed tier1/tier2/tier3 `suspend=true`.

## Store Outcomes
- [blocked] `gunfire.com`: `challenge_body` at root; store aborted.
- [blocked] `taiwangun.com`: HTTP 503 final URL `/captcha.php?from=%2Fen`; `challenge_path`; store aborted.
- [x] `bunker501.nl`: crawled 25 pages, produced 0 products and 0 history rows.
- [blocked] `evike-europe.com`: `challenge_body` at root; store aborted.
- [blocked] `redwolfairsoft.com`: `challenge_body` at root; store aborted.

## PMO Decision
- [blocked] F7 Live night PASS cannot be granted.
- [x] Anti-bot fail-closed behavior is verified on live tier1 traffic.
- [x] Automatic retry is unsafe for the current F7 calibration state and must be disabled. Remediation: set all crawler CronJob `backoffLimit` values to `0` before any further live-night attempts.

## RHO Checklist
- [x] Latest image in live Job. Evidence: job image digest `sha256:ee04c7db4a785cc56fb259e7fb5a9db5e6bd28e75994a954e163992d1f042fd0`.
- [x] Fail-closed on anti-bot/challenge. Evidence: four stores logged `FetchBlockedError` and job exited non-zero.
- [x] No production schedule enabled. Evidence: CronJobs remained `suspend=true`.
- [x] Retry risk identified. Evidence: two failed pods with `BackoffLimitExceeded`.
- [blocked] Clean live night. Blocker: 4/5 tier1 domains challenged/blocked and no data was pushed.

## Status
- 2026-06-30T01:23:00+02:00 - BLOCKED: remediated tier1 live run proved fail-closed behavior, but failed the F7 live-night data gate. Backoff remediation required before next manual/live run.
