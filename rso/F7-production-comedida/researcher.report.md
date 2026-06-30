# RHO Research Report - F7 Tier3-Only Production State

Timestamp: 2026-06-30T04:18:00+02:00

## Objective
- [x] Reconcile the current F7 production state from live systems and local
  artifacts before final RSO closeout. Evidence: commands below re-run by Codex
  PMO on 2026-06-30.

## Directives
- [x] Treat memory and previous reports as discovery only; rely on direct
  command evidence for current production state. Evidence: Kubernetes, Argo and
  GitHub Actions commands re-run.
- [x] Do not expose secret values. Evidence: checks inspect object status,
  schedules, revisions, image digests and key names only.
- [x] Do not broaden activation beyond the clean data gate. Evidence: tier3 is
  active; tier1/tier2 remain suspended.

## Acceptance Criteria
- [x] **Live CronJob state is known.** Evidence:
  `kubectl -n skirmshop get cronjob skirmshop-competitor-crawler-tier1 skirmshop-competitor-crawler-tier2 skirmshop-competitor-crawler-tier3 -o custom-columns=...`
  returned tier1 `suspend=true`, tier2 `suspend=true`, tier3 `suspend=false`,
  all `backoffLimit=0`, all using crawler digest
  `sha256:6332c7ff14a2c7ec3c8323240edb10bfcdb24600effc513421d8516e8388f4a1`.
- [x] **Deployments remain disabled.** Evidence:
  `kubectl -n skirmshop get deploy skirmshop-competitor-crawler skirmshop-stock-prober -o custom-columns=...`
  returned both `spec.replicas=0`.
- [x] **GitOps is synced to the activation commit.** Evidence:
  `kubectl -n argocd get app skirmshop-competitor-crawler -o jsonpath=...`
  returned `Synced Healthy 7a7cf47b6654d5f9a8d3540a068bdadfa79b638f`.
- [x] **Activation CI passed.** Evidence:
  `gh run view 28414840927 --json status,conclusion,headSha,url,name,updatedAt`
  returned `status=completed`, `conclusion=success`,
  `headSha=7a7cf47b6654d5f9a8d3540a068bdadfa79b638f`.
- [x] **No immediate automatic Job appeared after sync.** Evidence:
  `kubectl -n skirmshop get jobs --no-headers | rg 'skirmshop-competitor-crawler|competitor-crawler'`
  listed only prior manual rso3/rso4/rso5/rso6 Jobs; the label-scoped query for
  CronJob-created jobs returned no rows.

## Specialist Checks
- [x] **Researcher** - current live state audited by direct commands above.
- [x] **DevOps** - active/suspended schedules and Deployment replica counts
  verified.
- [x] **Verifier/Auditor** - CI and Argo status verified independently of local
  report text.

## Status
- 2026-06-30T04:18:00+02:00 - PASS for tier3-only production state. Tier1/tier2
  remain blocked/unproven and must not be inferred as cleared by this report.
