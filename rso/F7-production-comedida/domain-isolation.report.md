# RHO PMO Report - F7 Domain Isolation

Timestamp: 2026-06-30T10:25:00+02:00

## Objective
- [x] Prepare a safe path to run clean domains without activating a full tier
  that contains known anti-bot blockers. Evidence: `src.run_once` domain filter,
  live `tier2-powair6` gate PASS, dedicated CronJob synced active, CI
  `28448373752` PASS, and Argo `Synced/Healthy b104ac0`.

## Directives
- [x] Do not activate tier1 or full tier2. Evidence: live tier1 and full tier2
  remain `suspend=true`; only dedicated `tier2-powair6` is prepared for
  activation after its isolated gate.
- [x] Keep crawler behavior identical when no domain filter is supplied.
  Evidence: existing runner tests still pass.
- [x] Do not crawl blocked domains as part of this preparation. Evidence:
  tests are in-memory; no live Job is launched by this report.

## Acceptance Criteria
- [x] Runner can limit selected tier(s) to configured domain(s). Evidence:
  `src/run_once.py` adds repeatable `--domain`; tests cover tier and `--all`
  filtering.
- [x] Unknown domains fail as usage errors before any crawl. Evidence:
  `tests/test_run_once.py::test_unknown_domain_exits_usage_error`.
- [x] Isolated windows can use a distinct run/metrics label. Evidence:
  `--run-label` is accepted only when a single window remains after filtering;
  tests cover success and rejection.
- [x] No scheduler/crawler/push/history behavior is forked. Evidence:
  `run_selected()` still calls `crawl_tier(tier_name, stores)`.
- [x] Image with these flags is released and pinned in manifests. Evidence:
  commit `47d75a5`; CI `28447075834` PASS; release `28447156761` PASS for tag
  `f7-47d75a5`; Harbor public/LAN digest
  `sha256:2315e965b6129e26c2aeaa948cba9d470d8801c6ca5a645629b95d231f040f88`;
  `k8s/manifest.yaml` and `k8s/crawler-cronjobs.yaml` prepared with that
  digest.
- [x] `powair6.com` isolated live gate is run from the pinned image. Evidence:
  Job `skirmshop-competitor-crawler-tier2-powair6-rso1-20260630132013`
  `Succeeded`; container `exitCode=0`; logs show `products=497`, history
  `inserted=497 skipped=0`, Brain push `sent=497 failed=0`, `run_once complete`
  `pushed=497 failed=0`; SQL returned
  `497|497|0.0000|1999.0000|powair6.com`.
- [x] Metrics evidence captured for the isolated run. Evidence:
  VictoriaMetrics `last_over_time` returned
  `competitor_crawler_run_total{tier="tier2-powair6",status="ok"} 1`,
  `competitor_crawler_push_sent_total{tier="tier2-powair6"} 497`,
  `competitor_crawler_push_failed_total{tier="tier2-powair6"} 0`, and
  `competitor_crawler_run_active{tier="tier2-powair6"} 0`.
- [x] Dedicated production CronJob is synced active without activating blocked
  domains. Evidence: commit `b104ac0`; CI `28448373752` PASS; Argo
  `skirmshop-competitor-crawler` `Synced/Healthy` at
  `b104ac002611eea98f66a94fdd300d06a2c6bff4`; live
  `skirmshop-competitor-crawler-tier2-powair6`, schedule `15 3 * * 1`,
  command `--tier tier2 --domain powair6.com --run-label tier2-powair6`,
  `suspend=false`, `backoffLimit=0`; full `tier2` remains separate and
  suspended.

## Specialist Checks
- [x] **Backend** - scoped CLI filtering only. Evidence:
  `.venv/bin/pytest -q tests/test_run_once.py` -> `42 passed`.
- [x] **Verifier** - regression suite unchanged. Evidence:
  `.venv/bin/pytest -q` -> `246 passed`; `.venv/bin/python -m compileall src tests`
  PASS.
- [x] **DevOps** - release and manifest pin prepared. Evidence: release
  `28447156761`; digest `sha256:2315e965...`.
- [x] **Security** - blocked domains were not included. Evidence: negative log
  grep for `begadi`, `aa-store`, auth/login/checkout/cart/basket/challenge/
  CAPTCHA/403/429/503 returned no matches for the isolated Job.

## Status
- 2026-06-30T10:25:00+02:00 - PREPARED IN CODE: `src.run_once` supports
  domain-filtered execution and isolated run labels. No production schedule was
  opened in this step.
- 2026-06-30T15:16:00+02:00 - IMAGE RELEASED: tag `f7-47d75a5` published
  digest `sha256:2315e965b6129e26c2aeaa948cba9d470d8801c6ca5a645629b95d231f040f88`.
  Manifests are prepared to pin this digest; Argo/live sync pending.
- 2026-06-30T15:29:00+02:00 - LIVE GATE PASS: manual isolated Job
  `skirmshop-competitor-crawler-tier2-powair6-rso1-20260630132013` completed
  with 497 rows/products, Brain push `sent=497 failed=0`, metrics ok, and no
  blocked-domain/auth/challenge signals.
- 2026-06-30T15:35:00+02:00 - PRODUCTION ISOLATION PREPARED: dedicated
  `tier2-powair6` CronJob added for weekly Monday 03:15 Europe/Madrid. Full
  tier2 remains suspended.
- 2026-06-30T15:43:00+02:00 - PRODUCTION ISOLATION ACTIVE: commit `b104ac0`
  pushed, CI `28448373752` PASS, and Argo
  `skirmshop-competitor-crawler` `Synced/Healthy` at
  `b104ac002611eea98f66a94fdd300d06a2c6bff4`. Live state:
  `tier1 suspend=true`, full `tier2 suspend=true`, `tier2-powair6
  suspend=false` Monday 03:15 Europe/Madrid, `tier3 suspend=false` Wednesday
  04:00 Europe/Madrid, crawler/prober Deployments `replicas=0`.
