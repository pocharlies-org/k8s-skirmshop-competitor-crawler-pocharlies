# F7 DevOps Report — VictoriaMetrics observability wiring for suspended crawler CronJobs

**Role:** `rho-devops` (implementer lane, delegated by Codex PMO).
**Date:** 2026-06-27.
**Objective:** Wire VictoriaMetrics observability to the three per-tier crawler
CronJobs **without activating production** — expose the one-shot runner's
`/metrics` endpoint on a named port, give it a final-scrape linger window, and
declare an operator-native scrape that targets only the crawler-cronjob pods.

## Scope (exact, as assigned)
- `k8s/crawler-cronjobs.yaml` — add named `metrics` port + `METRICS_PORT` /
  `METRICS_LINGER_SECONDS` env to all three tier containers.
- `k8s/crawler-vmpodscrape.yaml` — **new** `VMPodScrape` (CRD
  `operator.victoriametrics.com/v1beta1`).
- `k8s/kustomization.yaml` — include the new resource.
- `rso/F7-production-comedida/devops-observability.report.md` — this report.
- `rso/F7-production-comedida/CHECKLIST.md` — evidence + status log.

**Out of scope / untouched (by constraint):** `src/**`, `tests/**`,
`deploy/prod`, ArgoCD apps, real secrets, the `:pending` image, replicas,
`suspend`, and any real `kubectl apply`. No production activation.

## What was wired

### 1. CronJob containers — named port + opt-in metrics env (all 3 tiers)
Added to each `containers[0]` (tier1/tier2/tier3) in `k8s/crawler-cronjobs.yaml`:

```yaml
ports:
  - name: metrics
    containerPort: 9090
    protocol: TCP
env:
  # ... existing env ...
  - name: METRICS_PORT
    value: "9090"
  - name: METRICS_LINGER_SECONDS
    value: "45"
```

- `METRICS_PORT=9090` activates the backend's opt-in endpoint. `src/run_once.py`
  reads `METRICS_PORT` as the fallback for `--metrics-port`
  (`_resolve_metrics_port`, run_once.py L120-139) and only constructs the stdlib
  `MetricsServer` when it is set (`_maybe_start_metrics`, L279-297). Off-by-default
  behavior elsewhere (local/test) is preserved — the value is supplied **only**
  here, on the CronJob pods.
- The named `metrics` container port (9090) is what the `VMPodScrape` references
  by name, so the two stay in lockstep regardless of the numeric value.
- `METRICS_LINGER_SECONDS=45` keeps `/metrics` serving for 45s **after** the tier
  finishes (`run()` `finally` block, run_once.py L263-276). The terminal
  `competitor_crawler_run_total{status}` / `push_*_total` counters are only
  written at `finish_run()`, so a final scrape must land *after* completion; 45s
  is one full scrape interval (30s) plus margin, while remaining tiny against the
  `activeDeadlineSeconds: 3600` job budget. It never affects the job exit code
  (backend contract).

### 2. `k8s/crawler-vmpodscrape.yaml` (new) — operator-native scrape
```yaml
apiVersion: operator.victoriametrics.com/v1beta1
kind: VMPodScrape
metadata:
  name: skirmshop-competitor-crawler
spec:
  namespaceSelector:
    matchNames: [skirmshop]
  selector:
    matchLabels:
      app.kubernetes.io/name: skirmshop-competitor-crawler
      app.kubernetes.io/component: crawler-cronjob
  podMetricsEndpoints:
    - port: metrics
      path: /metrics
      scheme: http
      interval: 30s
      scrapeTimeout: 10s
```

- **`VMPodScrape`, not `VMServiceScrape`:** the targets are ephemeral CronJob
  pods with no backing Service/ClusterIP. Pod service-discovery is the correct
  mechanism for per-run pods.
- **Selector targets only crawler-cronjob pods.** Label topology verified by
  direct file inspection:
  - disabled Deployment `skirmshop-competitor-crawler` pod template carries only
    `app.kubernetes.io/name=skirmshop-competitor-crawler` (no component label) —
    `k8s/manifest.yaml` L12-15 → **excluded**;
  - `skirmshop-stock-prober` carries `name=skirmshop-stock-prober` —
    `k8s/prober-deployment.yaml` L12-15 → **excluded**;
  - only the three tier CronJob pod templates carry **both** `name=...` and
    `component=crawler-cronjob` (`k8s/crawler-cronjobs.yaml` L53-56 etc.) →
    **selected**.
- `port: metrics` references the named container port (decouples from the numeric
  9090). `interval: 30s` < the 45s linger, guaranteeing a post-completion scrape.

### 3. `k8s/kustomization.yaml`
Added `crawler-vmpodscrape.yaml` to `resources` (between `crawler-cronjobs.yaml`
and `prober-deployment.yaml`). The existing `labels` transformer uses
`includeSelectors: false`, so the common labels are added to the VMPodScrape's
`metadata.labels` but **not** injected into `spec.selector.matchLabels` — the
selector stays precise (exactly the two labels above).

## RHO Checklist (this lane)

### Directives
- [x] Stay strictly within assigned scope. Evidence: `git diff --stat` →
  `k8s/crawler-cronjobs.yaml` (+51), `k8s/kustomization.yaml` (+1);
  `git ls-files --others` → `k8s/crawler-vmpodscrape.yaml`. No `src/**`,
  `tests/**`, `deploy/prod`, Argo, secrets touched.
- [x] No production activation. Evidence: all three CronJobs remain
  `suspend: true` (crawler-cronjobs.yaml L41 and the two siblings); image stays
  `harbor.e-dani.com/homelab/skirmshop-competitor-crawler:pending` (L80 etc.); no
  real `kubectl apply` run; the VMPodScrape is inert while pods never spawn.
- [x] Root cause, no workarounds. Evidence: uses the backend's documented
  `METRICS_PORT`/`METRICS_LINGER_SECONDS` contract and an operator-native
  `VMPodScrape` (no annotation hacks, no sidecar, no pushgateway shim).
- [x] No secrets exposed. Evidence: only a port + two plain integer env values
  added; `/metrics` exposes aggregate counters/gauge only.

### Acceptance criteria (from task)
- [x] **(1) CronJobs remain `suspend: true` and `:pending`.** Evidence:
  `k8s/crawler-cronjobs.yaml` L41 `suspend: true` (+ tier2/tier3 siblings
  unchanged — not in any edit's old/new string); image `...:pending` L80 etc.;
  edits added only `ports`/`env`, never touched `suspend`/`image`.
- [x] **(2) Each CronJob exposes a named `metrics` port + `METRICS_PORT` and a
  small `METRICS_LINGER_SECONDS`.** Evidence: `crawler-cronjobs.yaml` L90-95
  (`ports: - name: metrics / containerPort: 9090 / protocol: TCP`), L116-119
  (`METRICS_PORT=9090`, `METRICS_LINGER_SECONDS=45`), replicated to all three
  tiers (diff `+51 = 3 × 17` identical lines).
- [x] **(3) VictoriaMetrics scrape via the available CRD, selector = crawler
  pods only.** Evidence: `k8s/crawler-vmpodscrape.yaml` —
  `apiVersion: operator.victoriametrics.com/v1beta1`, `kind: VMPodScrape`,
  `selector.matchLabels` = `name=skirmshop-competitor-crawler` +
  `component=crawler-cronjob` (only the CronJob pods carry both),
  `podMetricsEndpoints[0].port: metrics`.
- [x] **(4) Kustomization includes the resource.** Evidence:
  `k8s/kustomization.yaml` `resources:` now lists `crawler-vmpodscrape.yaml`.
- [blocked] **(5) `kubectl kustomize` and server dry-run pass.** Blocker: the
  session permission classifier denies **all** `kubectl`, `kustomize`, and
  `python3`-with-file-IO invocations (each returns "This command requires
  approval"). I could not execute the render or the server dry-run myself.
  Commands to run (PMO/cluster context):
  ```bash
  cd /home/dibanez/k8s/k8s-skirmshop-competitor-crawler-pocharlies
  kubectl kustomize k8s
  kubectl apply --dry-run=server -k k8s
  ```
  Expected: render emits the 3 CronJobs (each with the `metrics` port + metrics
  env) + 1 `VMPodScrape`; server dry-run accepts the `VMPodScrape` (proves the
  `operator.victoriametrics.com/v1beta1` CRD is installed and the schema matches).
- [x] **(6) Report with evidence + risks.** Evidence: this file.

### Checks I could run (sandbox-permitted)
- [x] `git diff --stat` → `k8s/crawler-cronjobs.yaml | 51 ++++`,
  `k8s/kustomization.yaml | 1 +`; untracked `k8s/crawler-vmpodscrape.yaml`.
- [x] Direct `Read` of `k8s/crawler-cronjobs.yaml` (tier1 fully) confirms
  `suspend: true`, `:pending`, named `metrics` port, `METRICS_PORT`/
  `METRICS_LINGER_SECONDS`, and `component=crawler-cronjob` pod-template label.
- [x] Direct `Read` of `k8s/manifest.yaml` and `k8s/prober-deployment.yaml`
  confirms the selector excludes the disabled Deployment and the prober.

### Checks I could NOT run (blocked — must be done by PMO)
- [blocked] `kubectl kustomize k8s` — classifier denied.
- [blocked] `kubectl apply --dry-run=server -k k8s` — classifier denied.
- [blocked] `python3 -c "import yaml; ..."` YAML parse — classifier denied any
  python that opens repo files. YAML correctness rests on `Read`-level inspection
  only; a CI `kubeconform`/`kustomize build` will be the authoritative gate.

## Files touched
- `k8s/crawler-cronjobs.yaml` — +51 lines: named `metrics` port + 2 metrics env
  vars on each of tier1/tier2/tier3 containers. `suspend`/`image` untouched.
- `k8s/crawler-vmpodscrape.yaml` — **new** `VMPodScrape` (v1beta1).
- `k8s/kustomization.yaml` — +1 line resource include.

## Residual risks / blockers
### PMO verification update - 2026-06-27T18:29:52+02:00

Codex/RSO re-ran the commands that were blocked inside the delegated DevOps lane:

- [x] `kubectl explain vmpodscrape.spec --api-version=operator.victoriametrics.com/v1beta1` PASS.
- [x] `kubectl explain vmpodscrape.spec.podMetricsEndpoints --api-version=operator.victoriametrics.com/v1beta1` confirms `port`, `interval`, `path`, `scheme` and `scrapeTimeout`.
- [x] `kubectl explain vmpodscrape.spec.namespaceSelector --api-version=operator.victoriametrics.com/v1beta1` confirms `matchNames`.
- [x] `kubectl kustomize k8s` PASS and renders the 3 suspended CronJobs with image `:pending`, `METRICS_PORT`, `METRICS_LINGER_SECONDS`, named `metrics` port and one `VMPodScrape`.
- [x] `kubectl apply --dry-run=server -k k8s` PASS, including `vmpodscrape.operator.victoriametrics.com/skirmshop-competitor-crawler created (server dry run)`.
- [x] `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> 192 passed.
- [x] `/tmp/crawler-f7-venv/bin/python -m compileall src tests` PASS.
- [x] `git diff --check` PASS.

This clears the lane's render/schema blocker. F7 still remains blocked for production activation by live gates: published/pinned image, live `competitor_intel` DB/migration, egress allowlists, Argo enable, vmagent target/dashboard evidence and one real nocturnal run.

1. **Render + server dry-run blocker cleared by PMO.** Evidence: `kubectl
   kustomize k8s` PASS and `kubectl apply --dry-run=server -k k8s` PASS,
   including the `VMPodScrape`.
2. **vmagent must actually select this `VMPodScrape`.** If the cluster vmagent is
   not `selectAllByDefault: true`, it needs a `podScrapeNamespaceSelector` /
   `podScrapeSelector` matching ns `skirmshop` + these labels. Verify at the first
   real (unsuspended) night via `kubectl -n skirmshop get vmpodscrape` and the
   vmagent `/targets` page. (Out of this repo's scope — cluster monitoring stack.)
3. **No data until activation (expected).** While `suspend: true`, no pod runs, so
   the scrape has no target. The wiring is declarative-ready; the "Live night /
   scrape green" criterion stays open until a tier is unsuspended.
4. **Scrape ingress vs NetworkPolicy.** `k8s/crawler-networkpolicy.yaml` sets only
   `policyTypes: [Egress]` (egress default-deny), so it does **not** block ingress
   scrapes. But if a namespace-wide default-deny-**ingress** policy exists in
   `skirmshop`, vmagent→pod:9090 would be blocked and an explicit ingress-allow
   (from the monitoring ns to the `metrics` port) would be needed at activation. I
   did **not** add an ingress policy (it changes activation posture and is not in
   the F7 observability-wiring criteria); flagged for the activation runbook.
5. **Linger cost.** Each run is +45s wall-clock at the end; negligible vs
   `activeDeadlineSeconds: 3600`, and the pod's resource cost during linger is the
   idle Python process only.
6. **Unauthenticated `/metrics` bound on `0.0.0.0`** (backend default). Exposes
   only aggregate run counters/gauge — no secrets/PII/URLs. Acceptable for
   in-cluster scrape; bound by NetworkPolicy posture at activation.
