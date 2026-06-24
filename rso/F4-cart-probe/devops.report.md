# rho-devops report — F4 Cart-Probe

> Role: rho-devops implementer (delegated by Codex RSO). No commit/push. No live apply.
> Scope: prepare **disabled** manifests for `skirmshop-stock-prober` + basic egress
> isolation. Activate nothing.

## Scope delivered
- Created `k8s/prober-deployment.yaml` — `skirmshop-stock-prober` Deployment, `replicas: 0`.
- Created `k8s/prober-networkpolicy.yaml` — default-deny **Egress** NetworkPolicy.
- Updated `k8s/kustomization.yaml` — added both resources to the resource list.

## Design decisions (consistency with existing crawler manifest)
- Reused the exact pod conventions from `manifest.yaml` (crawler):
  `automountServiceAccountToken: false`, `enableServiceLinks: false`,
  `imagePullSecrets: harbor-pull`, `nodeSelector role=edge/amd64`, edge toleration,
  same resource requests/limits.
- Label scheme follows the crawler: `app.kubernetes.io/name: skirmshop-stock-prober`
  used as selector/template label. The repo-wide `e-dani.com/activation: disabled`
  label is injected by the kustomization `labels` block (with `includeSelectors:
  false`), so the prober inherits the disabled-activation convention automatically —
  no per-resource duplication.
- Image: `harbor.e-dani.com/homelab/skirmshop-stock-prober:pending` — same registry
  pattern as the crawler (`harbor.e-dani.com/homelab/skirmshop-competitor-crawler:pending`),
  tag deliberately `pending` (image not built/activated yet).
- Env: `LOG_LEVEL=INFO` only. `envFrom secretRef competitor-crawler-secrets optional:true`
  reused (identical to crawler, optional so it never blocks render).
- **No `command`/`args`**: per directive, with `replicas: 0` no pod ever starts, so no
  inert sleep loop is needed. Avoids shipping an active loop. If/when activated, the
  image default entrypoint will be revisited by a future RSO gate.
- Namespace `skirmshop` comes from kustomization `namespace:` (not hardcoded), as required.

## Egress isolation
- `prober-networkpolicy.yaml`: `policyTypes: [Egress]`, `egress: []` → **default-deny
  all egress** for pods matching `app.kubernetes.io/name: skirmshop-stock-prober`.
- This documents isolation only. A live allowlist (DNS, green domains, F3 writer
  endpoint) is a future RSO decision before any `replicas:0 -> active` transition.
- No Ingress policy added (out of scope; prober has no Service / no inbound).

## Explicitly NOT done (per scope)
- No CronJob (verified absent).
- No Service.
- No live `kubectl apply`.
- No replicas > 0, no scheduling.

## Verification / evidence
- `grep -rin cronjob k8s/` → no output (no CronJob). **PASS**
- `grep -rn "replicas" k8s/` → `prober-deployment.yaml:8: replicas: 0` and
  `manifest.yaml:8: replicas: 0` (comment-only match in networkpolicy). **PASS**
- `git diff --check` → `DIFFCHECK_OK` (no whitespace/conflict errors). **PASS**
- `kubectl kustomize k8s` → **PASS by Codex RSO re-run**: rendered Deployment
  `skirmshop-stock-prober`, `replicas: 0`, `automountServiceAccountToken: false`,
  activation label inherited, and NetworkPolicy `skirmshop-stock-prober-egress`
  with `policyTypes: [Egress]`, `egress: []`.
- `kubectl apply --dry-run=server -k k8s` → **PASS by Codex RSO re-run**:
  `deployment.apps/skirmshop-stock-prober created (server dry run)` and
  `networkpolicy.networking.k8s.io/skirmshop-stock-prober-egress created (server dry run)`.
- Standalone `kustomize` binary → not installed (`which kustomize` exit 1).
- `python3` YAML lint → also denied by the classifier (`python3 -c` / heredoc / /tmp
  write all blocked). Manifests were authored by hand mirroring the validated crawler
  manifest structure; YAML is syntactically simple and indentation-consistent.

## Residual risks / blockers
- `rho-devops` could not run kubectl due harness classifier, but Codex RSO re-ran
  `kubectl kustomize k8s` and `kubectl apply --dry-run=server -k k8s` successfully.
- Image tag `pending` is intentional; deployment will fail ImagePull **only if
  activated** — safe at `replicas: 0`.
- NetworkPolicy enforcement depends on the cluster CNI supporting NetworkPolicy
  (crawler runs on edge nodes); with `replicas: 0` there is no pod to enforce against
  yet, so this is documentation-of-intent until activation.
