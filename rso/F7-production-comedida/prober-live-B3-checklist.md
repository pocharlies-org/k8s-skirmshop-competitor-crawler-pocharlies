# RHO Checklist - F7 Prober B3 Live Smoke

Timestamp: 2026-06-30T02:55:00+02:00

## Objective
- [x] Close the B3 live-smoke gate for the F7 stock prober with one approved
  AirsoftQuimera target, proving bounded live cart-probe behavior, cleanup,
  append-only Postgres history, and return to safe-disabled state. Evidence:
  Job `prober-b3-aq-20260630-005056`, SQL check
  `prober-b3-sqlcheck-20260630-005056`, and post-cleanup workload checks.

## Directives
- [x] Use only the approved domain `airsoftquimera.com`. Evidence: user approval
  exists in session; F4 calibration evidence is
  `rso/F4-cart-probe/live-calibration-airsoftquimera-evidence.md`.
- [x] Use only the documented AirsoftQuimera paths:
  `/cacc_4_50_1_<product_id>_<qty>_0/` and
  `/cacc_4_50_2_<product_id>_0_0/`. Evidence: B1 adapter
  `src/prober/airsoftquimera.py`.
- [x] Run one target only, concurrency 1, honest UA, bounded timeout and
  `max_qty=1` to exercise add+cleanup rather than quantity escalation.
  Evidence: Job args used `--max-targets 1 --max-qty 1 --write-history`.
- [x] Use an ephemeral NetworkPolicy only for this Job: DNS, CNPG Postgres, and
  public TCP 443 with private ranges excluded. Evidence: server dry-run accepted
  ports `53 53 5432 443`; live NetworkPolicy had
  `policyTypes=["Egress"]`.
- [x] Do not scale the `skirmshop-stock-prober` Deployment and do not unsuspend
  crawler CronJobs. Evidence: post-smoke live prober `replicas=0`; tier1/tier2/tier3
  CronJobs `suspend=true backoffLimit=0`.
- [x] Do not print secret values. Use Secret refs only. Evidence: Job spec used
  `secretKeyRef` for `PGUSER`/`PGPASSWORD`; logs printed no secret values and
  negative grep found no `password|secret`.

## Acceptance Criteria
- [x] **B3 server dry-run PASS.** Temporary ConfigMap, Job and smoke
  NetworkPolicy are accepted by the API server before apply. Evidence:
  `kubectl -n skirmshop apply --dry-run=server -f -` returned
  ConfigMap/NetworkPolicy/Job `created (server dry run)`.
- [x] **B3 Job completes or fails closed with one target.** Evidence:
  `job.batch/prober-b3-aq-20260630-005056 condition met`; pod
  `phase=Succeeded exit=0 reason=Completed`; Job `1 succeeded`, `backoffLimit=0`.
- [x] **B3 live prober touches only approved paths.** Evidence: logs show the
  AirsoftQuimera add/remove result and contain no checkout/login/account/payment
  paths:
  `GET https://www.airsoftquimera.com/cacc_4_50_1_22046_1_0/` and
  `GET https://www.airsoftquimera.com/cacc_4_50_2_22046_0_0/`, both `200 OK`.
- [x] **B3 cleanup is clean.** Evidence: prober result log reports
  `cleanup=clean`.
- [x] **B3 history write succeeds append-only.** Evidence: logs report
  `history write complete: inserted=1 skipped=0`, and SQL readback for the
  run_id returns one `airsoftquimera.com` row with `stock_method=cart_probe`.
  Independent SQL check returned
  `count=1 domain=airsoftquimera.com product_key=competitor:airsoftquimera.com:22046 stock_status=in_stock stock_method=cart_probe crawl_success=True`.
- [x] **B3 no anti-bot escalation.** Evidence: logs contain no `403`, `429`,
  `503`, `challenge`, `captcha`, `blocked`, or dirty cleanup.
- [x] **B3 cleanup of ephemeral resources.** Evidence: temporary Job,
  ConfigMap and smoke NetworkPolicy are deleted after evidence capture.
- [x] **B3 safe-disabled state preserved.** Evidence: live
  `skirmshop-stock-prober` remains `replicas=0`; tier1/tier2/tier3 CronJobs
  remain `suspend=true backoffLimit=0`; Argo remains `Synced Healthy`;
  permanent `skirmshop-stock-prober-egress` remains `policyTypes=["Egress"]`
  with no egress rules rendered by jsonpath.

## Specialist Checks
- [x] **Architect/PMO** - scope is one approved target and no production
  activation. Evidence: Job target file had one `airsoftquimera.com` target;
  Deployment/CronJobs stayed disabled.
- [x] **Backend** - runner, adapter, cleanup and history behavior. Evidence:
  logs show add/remove 200, `cleanup=clean`, `history write complete`.
- [x] **DevOps** - ephemeral resources, NetworkPolicy, DB env and cleanup.
  Evidence: server dry-run PASS; smoke egress ports `53/5432/443`; resources
  deleted by label and verified absent.
- [x] **Security** - no forbidden paths, no secrets, no CAPTCHA bypass, egress
  limited by app guard plus smoke NetworkPolicy.
- [x] **Verifier/Auditor** - independently re-run logs/status/SQL/live state and
  declare PASS/BLOCKED. Evidence: separate SQL check Job
  `prober-b3-sqlcheck-20260630-005056`; negative log grep for forbidden terms
  returned no matches; post-cleanup live checks passed.

## Status
- 2026-06-30T02:55:00+02:00 - OPEN: B3 live-smoke gate opened for one
  AirsoftQuimera target after B1+B2 PASS. F7 global remains NOT PASS until B3
  and clean live-night evidence pass.
- 2026-06-30T02:56:00+02:00 - B3 PASS: one-target AirsoftQuimera prober smoke
  completed with add/remove `200 OK`, `cleanup=clean`, `inserted=1 skipped=0`,
  independent SQL `count=1`, no anti-bot/forbidden-path log hits, ephemeral
  resources deleted, and permanent workloads preserved safe-disabled. F7 global
  remains NOT PASS pending clean live-night evidence.
