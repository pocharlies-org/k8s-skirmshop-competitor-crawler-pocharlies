# RHO PMO Report - F7 Tier3-Only Production Activation

Timestamp: 2026-06-30T04:02:00+02:00

## Objective
- [x] Activate the lowest-risk production schedule after a passing live data
  gate, without activating blocked or unproven tiers. Evidence: tier3 CronJob
  `suspend: false`; tier1/tier2 remain `suspend: true`.

## Directives
- [x] Activate only the tier with direct clean evidence. Evidence:
  `live-night-tier3-rso6.report.md` PASS.
- [x] Keep known-problem tiers disabled. Evidence: tier1 remains suspended
  because prior live evidence showed anti-bot/challenge blockers; tier2 remains
  suspended because it has no clean live data gate yet.
- [x] Preserve no-retry/no-overlap controls. Evidence: tier3 retains
  `concurrencyPolicy: Forbid`, `backoffLimit: 0`, `activeDeadlineSeconds: 3600`.
- [x] Keep crawler/prober Deployments disabled. Evidence: manifests keep both
  `replicas: 0`.

## Acceptance Criteria
- [x] **Tier3 schedule is enabled in GitOps manifests.** Evidence:
  `k8s/crawler-cronjobs.yaml` tier3 `suspend: false`, schedule `0 4 * * 3`,
  `timeZone: Europe/Madrid`.
- [x] **Tier1 and tier2 remain disabled.** Evidence:
  `k8s/crawler-cronjobs.yaml` tier1/tier2 `suspend: true`.
- [x] **No automatic retry amplification.** Evidence: tier3 `backoffLimit: 0`.
- [x] **Image is immutable and already live-validated.** Evidence: tier3 image
  digest `sha256:6332c7ff14a2c7ec3c8323240edb10bfcdb24600effc513421d8516e8388f4a1`;
  rso6 used that digest and passed.
- [x] **Next scheduled run is not immediate.** Evidence: schedule is Wednesday
  04:00 Europe/Madrid; activation was prepared Tuesday 2026-06-30 after the
  04:00 window.

## Specialist Checks
- [x] **Backend** - tier3 data path passed before activation. Evidence: rso6
  products=67, history rows=67, Brain push sent=67 failed=0.
- [x] **DevOps** - bounded CronJob activation only. Evidence: one-field suspend
  change for tier3; Deployments remain 0; tier1/tier2 remain suspended.
- [x] **Security** - no expansion to anti-bot tiers. Evidence: tier1/tier2 not
  activated; tier3 rso6 logs had no challenge/CAPTCHA/forbidden GETs.
- [x] **Verifier/Auditor** - post-commit live verification. Evidence:
  CI `28414840927` PASS; Argo `Synced Healthy 7a7cf47`; live tier3
  `suspend=false`, tier1/tier2 `suspend=true`, all `backoffLimit=0`,
  Deployments `replicas=0`.

## Status
- 2026-06-30T04:02:00+02:00 - PREPARED: tier3-only production activation is
  staged in manifests. Pending commit/push, CI, Argo sync and live verification.
- 2026-06-30T04:10:00+02:00 - PASS: commit `7a7cf47` pushed; CI
  `28414840927` PASS; Argo `Synced Healthy 7a7cf47`; live tier3 is
  `suspend=false` on schedule `0 4 * * 3` Europe/Madrid, tier1/tier2 remain
  `suspend=true`, and no Deployments were scaled.
