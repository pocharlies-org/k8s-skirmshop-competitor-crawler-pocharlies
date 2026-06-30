# RHO PMO Report - F7 Tier3 Live Data Gate PASS

Timestamp: 2026-06-30T03:55:00+02:00

## Objective
- [x] Validate a real tier3 live run from the production CronJob template after
  the PrestaShop listing-card/frontier remediation. Evidence: Job
  `skirmshop-competitor-crawler-tier3-rso6-20260630013804`, logs, metrics,
  Postgres SQL readback, Brain/RAG service readback and safe-state checks.

## Directives
- [x] Use only the live CronJob template. Evidence:
  `kubectl -n skirmshop create job skirmshop-competitor-crawler-tier3-rso6-20260630013804 --from=cronjob/skirmshop-competitor-crawler-tier3`.
- [x] Do not unsuspend schedules during the gate. Evidence: post-run
  tier1/tier2/tier3 CronJobs remain `suspend=true`.
- [x] No retry amplification. Evidence: Job and CronJob use `backoffLimit=0`.
- [x] Preserve safety controls. Evidence: robots disallow for `mi-cuenta`,
  `carrito`, `busqueda`; no GET to those paths; `max_pages=25` stopped
  FullMetal with queued URLs left.
- [x] Do not expose secrets. Evidence: RAG/Brain readbacks used `secretKeyRef`
  env injection in ephemeral pods and logs show no secret values.

## Acceptance Criteria
- [x] **Job uses the released listing-card image.** Evidence: Job image
  `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:6332c7ff14a2c7ec3c8323240edb10bfcdb24600effc513421d8516e8388f4a1`.
- [x] **Job completes successfully.** Evidence: Job `1 succeeded`, pod
  `skirmshop-competitor-crawler-tier3-rso6-20260630013804-m98g5`
  `Succeeded exit=0 reason=Completed`.
- [x] **FullMetal product discovery works.** Evidence: logs show direct product
  GETs such as `/armas-de-airsoft/.../ec-mcx-aeg-spear-lt-103-etu...`, then
  `crawl done - visited=25 products=67`.
- [x] **Postgres history contains new observations.** Evidence: logs
  `history write complete: inserted=67 skipped=0`; SQL aggregate for
  `run_id='tier3:20260630T013825797218Z'` returned
  `67|67|2.00|770.00|67|67|fullmetal.es`
  (`rows|distinct_products|min_price|max_price|priced|success|domains`).
- [x] **Brain push-ingest succeeds.** Evidence: four Brain ingest POSTs returned
  `HTTP/1.1 200 OK`; final log `push-ingest done: sent=67 failed=0`.
- [x] **Brain/RAG service readback works.** Evidence: service
  `/health/quick` returned `status=alive`; authenticated
  `/instances/skirmshop/prices/comparison?status=active&filter=has_comp&limit=1`
  returned `total=435`, `count=1`; authenticated graph cypher readback returned
  `fullmetal.es` `CompetitorProduct count=653`, `max_price=770.0`,
  `min_price=2.0`.
- [x] **Metrics terminal values are correct.** Evidence: `/metrics` during
  linger returned `competitor_crawler_run_total{status="ok",tier="tier3"} 1`,
  `competitor_crawler_push_sent_total{tier="tier3"} 67`,
  `competitor_crawler_push_failed_total{tier="tier3"} 0`,
  `competitor_crawler_run_active{tier="tier3"} 0`.
- [x] **No anti-bot/forbidden-path escalation.** Evidence: negative log grep
  for `captcha|challenge|403|429|503|fetch blocked|push-ingest exhausted`;
  negative grep for `HTTP Request: GET .*?(mi-cuenta|carrito|busqueda|checkout|login|payment)`.
- [x] **Safe-disabled state preserved.** Evidence: crawler/prober Deployments
  `replicas=0`; tier1/tier2/tier3 CronJobs `suspend=true backoffLimit=0`;
  crawler digest `sha256:6332...`; prober digest `sha256:b5ce...`.

## Store Outcomes
- [blocked] `mundoreplicas.com`: DNS/robots still failed with `Name or service
  not known`; Firecrawl fallback returned 0 products. This did not fail the
  tier but remains a target-quality blocker for that store.
- [x] `fullmetal.es`: PASS. Fetched allowed pages/product URLs, extracted 67
  products, wrote 67 history rows and pushed 67 documents to Brain.
- [blocked] `cazatacticas.com`: DNS/robots still failed with `Name or service
  not known`; Firecrawl fallback returned 0 products. This did not fail the
  tier but remains a target-quality blocker for that store.

## Brain Service Remediation
- [x] Timed-out Brain API pod remediated under prior operator authorization.
  Evidence: pod `skirmshop-brain-848846cd6d-zqz9z` timed out on
  `/health/quick`; PMO deleted it; Deployment rolled out successfully; endpoints
  became `10.42.5.149:5001,10.42.6.30:5001`; API pods
  `skirmshop-brain-848846cd6d-fsnbh` and `skirmshop-brain-848846cd6d-qqqbj`
  are `Running` and ready.
- [x] Service readback after remediation passed. Evidence:
  `/health/quick` returned `alive`; `/prices/comparison` returned HTTP 200 and
  `total=435`.

## Specialist Checks
- [x] **Backend** - product extraction/history/push semantics. Evidence:
  product logs, `products=67`, history inserted 67, push sent 67 failed 0.
- [x] **DevOps** - live image/source/backoff/safe state. Evidence: Argo
  `Synced Healthy d19cfc6`, live CronJob image `sha256:6332...`,
  `backoffLimit=0`, schedules still suspended.
- [x] **Security** - no forbidden GETs/secrets/challenge escalation. Evidence:
  negative greps and secretKeyRef-only RAG check.
- [x] **Verifier/Auditor** - independent readbacks. Evidence: PMO re-ran logs,
  metrics, SQL, Brain service/cypher, Job status and live safe-state checks.

## Status
- 2026-06-30T03:55:00+02:00 - PASS for the tier3 live data gate. F7 global
  should only activate as a tier3-only candidate unless/until tier1/tier2 target
  quality and anti-bot blockers are separately cleared.
