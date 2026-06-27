# RHO Live Smoke Report - F7 AirsoftQuimera Write

## Objective
- [x] Verify the prepared F7 crawler image can crawl one authorized AirsoftQuimera product, write append-only history, push to Brain ingest, expose terminal metrics, and exit successfully without enabling production schedules. Evidence: Job `competitor-crawler-f7-write-20260627-200703`.

## Directives
- [x] Use only the explicitly approved domain `airsoftquimera.com`. Evidence: smoke ConfigMap had one store, `domain: airsoftquimera.com`.
- [x] Keep scope non-DoS and bounded. Evidence: `depth: 0`, `max_pages: 1`, `delay_seconds: 1.0`, one direct product URL.
- [x] Use production-equivalent env/secret/DB/Brain wiring but do not unsuspend CronJobs. Evidence: Job used image digest `sha256:b4481879aecc9b82fe822d0f9de0abddb9dfb60e1c8488d811a479f35fed77f1`, `BRAIN_URL=http://skirmshop-brain-ingest.skirmshop-brain-prod.svc.cluster.local`, `REQUIRE_BRAIN_API_KEY=true`, `HISTORY_ENABLED=true`, DB secret refs, and the CronJobs remained `suspend=true`.
- [x] Do not print secret values. Evidence: logs/report contain only key names and service URLs.

## Acceptance Criteria
- [x] Server dry-run accepted the temporary smoke resources. Evidence: `kubectl -n skirmshop apply --dry-run=server -f -` returned ConfigMap and Job created in server dry-run.
- [x] Job completed successfully. Evidence: `kubectl -n skirmshop get job competitor-crawler-f7-write-20260627-200703` -> `1 succeeded`; pod `phase=Succeeded exit=0 reason=Completed`.
- [x] Crawler fetched exactly the authorized product URL successfully. Evidence: logs show `GET https://www.airsoftquimera.com/cargador-midcap-para-m4-200bbs-tornado-p-4-50-15229/ "HTTP/1.1 200 OK"` and `visited=1 products=1`.
- [x] History append-only write succeeded. Evidence: logs show `history write complete: inserted=1 skipped=0`; SQL for `run_id='smoke-write:20260627T200731540940Z'` returns `airsoftquimera.com|...|1|10.0000|out_of_stock|t`.
- [x] Brain push-ingest succeeded. Evidence: logs show `POST http://skirmshop-brain-ingest.skirmshop-brain-prod.svc.cluster.local/instances/skirmshop/push-ingest "HTTP/1.1 200 OK"` and `push-ingest done: sent=1 failed=0`.
- [x] Metrics terminal values are correct. Evidence: pod `/metrics` returned `competitor_crawler_run_total{status="ok",tier="smoke-write"} 1`, `competitor_crawler_push_sent_total{tier="smoke-write"} 1`, `competitor_crawler_push_failed_total{tier="smoke-write"} 0`, `competitor_crawler_run_active{tier="smoke-write"} 0`.
- [x] Brain readback exposes the pushed competitor price. Evidence: read-only Brain cypher check returned `count=1` with `domain=airsoftquimera.com`, title `Cargador Mid-cap para M4 200bbs Tornado Negro`, `price=10.0`, URL `/cargador-midcap-para-m4-200bbs-tornado-negro-p-4-50-15229/`.
- [x] No block/bot signal observed in this smoke. Evidence: logs have no `403`, `429`, `challenge`, `captcha`, or push retry/failure lines; Job events show `SuccessfulCreate` and `Completed`.

## Specialist Checks
- [blocked] `rho-verifier` independent read-only check. Evidence: Claude CLI verifier timed out with code `124` and no stdout.
- [x] Codex/RSO PMO verifier pass. Evidence: PMO re-ran kubectl logs, metrics, job status, SQL and Brain cypher readback directly.

## Status
- 2026-06-27T22:14:34+02:00 - PASS for bounded live smoke write. This does not close F7 global PASS because the nocturnal CronJobs remain suspended, prober live transport/image remain blocked, GitOps PRs are still open, and a real night window has not run.
