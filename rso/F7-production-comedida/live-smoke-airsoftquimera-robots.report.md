# RHO Live Smoke Report - F7 AirsoftQuimera Robots Image

## Objective
- [x] Verify the released robots/crawl-delay crawler image works live against the approved AirsoftQuimera product without enabling production schedules. Evidence: Job `competitor-crawler-f7-robots-20260627-203211`.

## Directives
- [x] Use only approved domain `airsoftquimera.com`. Evidence: smoke config contains one store with `domain: airsoftquimera.com`.
- [x] Keep crawl bounded. Evidence: `depth: 0`, `max_pages: 1`, `delay_seconds: 1.0`, one direct product URL.
- [x] Use the released robots image. Evidence: Job image `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:ccab2c1508c38cb133a01594c11b5a926673dab660e4e6ca9a9c1b0822cc6193`.
- [x] Do not activate production schedules. Evidence: live Deployment stayed `replicas=0`; CronJobs stayed `suspend=true`.

## Acceptance Criteria
- [x] Temporary smoke resources pass server dry-run. Evidence: `kubectl -n skirmshop apply --dry-run=server -f -` accepted ConfigMap and Job.
- [x] Runtime checks robots.txt before product fetch. Evidence: logs show `GET https://www.airsoftquimera.com/robots.txt "HTTP/1.1 200 OK"` before product `GET`.
- [x] Product fetch succeeds and remains bounded. Evidence: logs show product `GET ... "HTTP/1.1 200 OK"`, `visited=1 products=1`.
- [x] History write succeeds. Evidence: logs show `history write complete: inserted=1 skipped=0`; SQL for `run_id='smoke-robots:20260627T203252168758Z'` returns `airsoftquimera.com|...|1|10.0000|out_of_stock|t`.
- [x] Brain push succeeds. Evidence: logs show Brain ingest `HTTP/1.1 200 OK`, `push-ingest done: sent=1 failed=0`.
- [x] Metrics terminal values are correct. Evidence: `/metrics` returned `competitor_crawler_run_total{status="ok",tier="smoke-robots"} 1`, `competitor_crawler_push_sent_total{tier="smoke-robots"} 1`, `competitor_crawler_push_failed_total{tier="smoke-robots"} 0`, `competitor_crawler_run_active{tier="smoke-robots"} 0`.
- [x] Job exits successfully. Evidence: Job `1 succeeded`; pod `phase=Succeeded exit=0 reason=Completed`.
- [x] No block/bot signal observed in this smoke. Evidence: filtered logs have no `403`, `429`, `challenge`, `captcha`, `ERROR`, or push failure lines.

## Specialist Checks
- [blocked] `rho-verifier` not rerun for this smoke due repeated Claude CLI timeout behavior on this session.
- [x] Codex/RSO PMO verification. Evidence: PMO re-ran logs, metrics, SQL, Job status and live workload checks directly.

## Status
- 2026-06-27T22:36:00+02:00 - PASS for bounded live smoke with robots/crawl-delay image. F7 global remains blocked by GitOps PR merge policy, prober live transport/image if required for full F4 gate, and one real nocturnal run.
