# F7 DevOps Report — suspended per-tier crawler CronJobs

**Role:** `rho-devops` (delegated implementer, invoked by Codex PMO).
**Date:** 2026-06-27.
**Branch:** `codex/competitor-crawler-F7-production-comedida`.
**No production activation:** every CronJob ships `suspend: true`; image stays
`:pending`; no `kubectl apply` real, no Argo move, no replicas/CronJob unsuspended.

## Scope

Prepare Kubernetes `CronJob` manifests for the bounded one-shot crawler runner,
**suspended by default**, wired into the existing kustomize overlay, with pod
hardening identical to the disabled Deployment. Activation stays gated by the
F7 activation runbook (image, DB, secrets, egress, verification, night).

Allowed scope honored exactly:
- `k8s/**` — added `crawler-cronjobs.yaml`, edited `kustomization.yaml`.
- `rso/F7-production-comedida/devops-cronjob.report.md` — this file.
- `rso/F7-production-comedida/CHECKLIST.md` — appended one dated status entry.

Not touched: `deploy/prod`, Argo apps, real secrets, Deployment `replicas`,
published images, `db/migrations/**`, source code, NetworkPolicies.

## Files inspected

- `k8s/manifest.yaml` (crawler Deployment, `replicas: 0`, `:pending`) — hardening source of truth.
- `k8s/prober-deployment.yaml`, `k8s/crawler-networkpolicy.yaml`, `k8s/prober-networkpolicy.yaml`.
- `k8s/kustomization.yaml`, `k8s/externalsecret.yaml`.
- `src/run_once.py` (one-shot runner: `--tier`/`--all`/`--config`, exit `0/1/2`).
- `config.yaml` (tier1/tier2/tier3 definitions and informational schedules).
- `Dockerfile` (`WORKDIR /app`, `CMD python -m src.main`, `config.yaml` at `/app/config.yaml`).
- `rso/F7-production-comedida/{CHECKLIST,HANDOFF,architect,devops,activation-runbook}.md`.

## Files touched (diff)

`git status --short`:
```
 M k8s/kustomization.yaml
?? k8s/crawler-cronjobs.yaml
```

- `k8s/crawler-cronjobs.yaml` (new): 3 `CronJob` resources, one per tier.
- `k8s/kustomization.yaml`: added `- crawler-cronjobs.yaml` to `resources`
  (between `manifest.yaml` and `prober-deployment.yaml`).

## Design decisions

| Field | Value | Rationale |
|---|---|---|
| Resources | 1 `CronJob` per tier (tier1/tier2/tier3) | maps to `--tier` selection; enables staggered nocturnal schedules |
| `command` | `python -m src.run_once --tier <tier> --config /app/config.yaml` | bounded one-shot runner; exits `0/1/2` for clean Job history; NOT `src.main` (daemon) |
| `suspend` | `true` | prepared-not-activated; activation = flip to false after gates |
| `schedule` (Madrid) | tier1 `0 2 */2 * *`, tier2 `0 3 * * 1`, tier3 `0 4 * * 3` | nocturnal + staggered (02:00 / 03:00 / 04:00), disjoint start times |
| `timeZone` | `Europe/Madrid` | explicit local nocturnal window (CronJob TZ, GA since k8s 1.27) |
| `concurrencyPolicy` | `Forbid` | a slow tier run never overlaps its next slot |
| `startingDeadlineSeconds` | `300` | skip a missed slot rather than backfill a burst |
| `backoffLimit` | `1` | low backoff: at most one retry on transient failure |
| `activeDeadlineSeconds` | `3600` | hard 1h cap per tier run (anti-runaway / anti-DoS) |
| `ttlSecondsAfterFinished` | `86400` | auto-GC finished Jobs after 24h |
| `successfulJobsHistoryLimit` / `failedJobsHistoryLimit` | `3` / `3` | bounded audit history |
| `restartPolicy` | `Never` | one pod per attempt → clean per-attempt logs |
| `image` | `harbor.e-dani.com/homelab/skirmshop-competitor-crawler:pending` | unpublished; pin tag/digest before activation |

Schedule note: `config.yaml`'s per-tier `schedule:` field is **informational
only** — `src.run_once` ignores it (selection is explicit via `--tier`). The
CronJob `schedule` is the authoritative trigger. The CronJob values are kept
aligned with `config.yaml` to avoid operator confusion.

Anti-DoS posture: the three tiers crawl **disjoint** competitor domains and
never share a start time, so there is no per-domain or edge-node-resource
overlap; `Forbid` + `activeDeadlineSeconds` bound each run; low concurrency is
inherited from the runner (`crawl_tier` runs stores sequentially).

## Pod hardening parity (vs `k8s/manifest.yaml`)

Identical to the disabled crawler Deployment:
- pod `securityContext`: `runAsNonRoot: true`, uid/gid/fsGroup `10001`, `seccompProfile: RuntimeDefault`.
- container `securityContext`: `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities.drop: [ALL]`.
- `automountServiceAccountToken: false`, `enableServiceLinks: false`.
- `imagePullSecrets: [harbor-pull]`, `nodeSelector {role: edge, kubernetes.io/arch: amd64}`, edge toleration.
- `envFrom secretRef competitor-crawler-secrets optional: false` (fail closed).
- `REQUIRE_BRAIN_API_KEY=true`, same `BRAIN_URL`/`BRAIN_INSTANCE`/`FIRECRAWL_URL`/`PUSH_BATCH_SIZE`/`LOG_LEVEL`.
- `resources` requests `100m`/`256Mi`, limit `1Gi`; `/tmp` `emptyDir` (writable temp under read-only rootfs).

## RHO Checklist — DevOps F7 CronJob prep

### Directives
- [x] Implement directly within scope, no re-delegation. Evidence: this report; only `k8s/**` + 2 RSO files changed (`git status --short`).
- [x] Keep production disabled. Evidence: `crawler-cronjobs.yaml` all `suspend: true`; Deployments untouched at `replicas: 0`; image `:pending`.
- [x] No `deploy/prod`, Argo, real secrets, or live `kubectl apply`. Evidence: no such files touched; live commands not run (and blocked by harness, see Verification).
- [x] Fail-closed Brain auth in the scheduled path too. Evidence: `REQUIRE_BRAIN_API_KEY=true` + `secretRef optional: false` in every CronJob.

### Acceptance criteria
- [x] **(1)** CronJobs per tier use `python -m src.run_once --tier <tier> --config /app/config.yaml`. Evidence: `k8s/crawler-cronjobs.yaml` `command:` block of each of the 3 CronJobs (tier1/tier2/tier3).
- [x] **(2)** `suspend: true` by default. Evidence: `spec.suspend: true` in all 3 CronJobs.
- [x] **(3)** `concurrencyPolicy: Forbid`, low backoff, history limits, `timeZone: Europe/Madrid`, staggered nocturnal schedules. Evidence: `concurrencyPolicy: Forbid`, `backoffLimit: 1`, `successfulJobsHistoryLimit: 3`/`failedJobsHistoryLimit: 3`, `timeZone: Europe/Madrid`, schedules `0 2 */2 * *` / `0 3 * * 1` / `0 4 * * 3` (02:00/03:00/04:00).
- [x] **(4)** Pod hardening equivalent to Deployment, `secretRef optional: false`, `REQUIRE_BRAIN_API_KEY=true`, image pending unpublished. Evidence: see "Pod hardening parity"; `image: ...:pending`.
- [x] **(5)** kustomization includes the resources. Evidence: `k8s/kustomization.yaml` `resources:` now lists `crawler-cronjobs.yaml`.
- [x] **(6)** `kubectl kustomize k8s` + `kubectl apply --dry-run=server -k k8s` PASS by Codex PMO. Evidence: PMO re-ran both commands; server dry-run accepted Deployments, ExternalSecret, both NetworkPolicies, and CronJobs `skirmshop-competitor-crawler-tier1`, `tier2`, `tier3`.

## Verification

- [x] Manifests authored via tool writes (Write/Edit succeeded; would error on failure). Evidence: `crawler-cronjobs.yaml` created; `kustomization.yaml` edit applied.
- [x] kustomization references resolve to on-disk files. Evidence: all 6 entries (`externalsecret.yaml`, `crawler-networkpolicy.yaml`, `manifest.yaml`, `crawler-cronjobs.yaml`, `prober-deployment.yaml`, `prober-networkpolicy.yaml`) exist in `k8s/`.
- [x] Acceptance criteria 1–5 verified by direct file inspection (Read) against the written content.
- [x] PMO dry-run gate passed after the delegated lane returned. Evidence:
  `kubectl kustomize k8s` rendered all 3 suspended CronJobs with `suspend: true`;
  `kubectl apply --dry-run=server -k k8s` returned `cronjob.batch/skirmshop-competitor-crawler-tier1 created (server dry run)`, `tier2 created`, `tier3 created`, plus the existing disabled Deployments, ExternalSecret and NetworkPolicies.

## Deploy / activation notes (gated — do NOT run yet)

Activation is one explicit, reversible flip per tier **after** the F7 gates pass
(published image tag/digest, live CNPG `competitor_intel`, synced
`competitor-crawler-secrets`, explicit egress allowlist replacing
`crawler-networkpolicy.yaml` `egress: []`, Codex verification):

1. Pin a real image (replace `:pending` with published tag/digest in
   `k8s/manifest.yaml` and `k8s/crawler-cronjobs.yaml`).
2. Enable the Argo app (currently in `apps-disabled`) — Codex/PMO only.
3. Unsuspend one tier first (canary):
   `kubectl -n skirmshop patch cronjob skirmshop-competitor-crawler-tier1 -p '{"spec":{"suspend":false}}'`
   — or set `suspend: false` in the manifest and let Argo sync.
4. Optional immediate canary run:
   `kubectl -n skirmshop create job --from=cronjob/skirmshop-competitor-crawler-tier1 crawler-tier1-canary`.

### Rollback / stop
- Re-suspend: `kubectl -n skirmshop patch cronjob <name> -p '{"spec":{"suspend":true}}'` (or revert `suspend: true` in git / Argo). Already-running Jobs keep running; cancel with `kubectl -n skirmshop delete job <job>`.
- `activeDeadlineSeconds: 3600` auto-kills a runaway tier run.
- `backoffLimit: 1` bounds retries; non-zero `run_once` exit (1/2) marks the Job failed without a retry storm.
- Full stop: delete the CronJobs (`kubectl -n skirmshop delete cronjob -l app.kubernetes.io/component=crawler-cronjob`) or remove `crawler-cronjobs.yaml` from kustomization.

## Residual operational risks

1. **Egress still default-deny** (`crawler-networkpolicy.yaml` `egress: []`): an unsuspended CronJob pod would have zero egress and fail. The egress allowlist (DNS, Brain, Firecrawl, Postgres, approved competitor domains) is a hard pre-activation gate (Security owns).
2. **`competitor_intel` not live** and **image `:pending`**: unsuspending now would crash-loop (ImagePullBackOff / DB errors). Suspended state is the only safe state until gates pass.
3. **Manifest duplication**: the hardened pod spec is repeated across the Deployment + 3 CronJobs. Matches the repo's "fully spelled out" house style (Deployment vs prober-deployment) and maximizes per-resource auditability, but a future kustomize component/patch could DRY it to cut drift risk.
4. **Brain push-ingest auth secret** must contain `BRAIN_API_KEY` at runtime; `REQUIRE_BRAIN_API_KEY=true` makes the job fail-closed if absent (intended), so secret sync is a hard activation dependency.
