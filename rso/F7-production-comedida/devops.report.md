# F7 DevOps Report - disabled runtime hardening

**Role:** Claude CLI `rho-devops` attempted twice and timed out with no stdout.  
**Integration:** Codex PMO exception limited to disabled manifests and CI validation.  
**No production activation:** replicas remain `0`; no CronJob added; no Argo move; no `kubectl apply` real.

## RHO Checklist

### Directives
- [x] Keep production disabled. Evidence: `k8s/manifest.yaml` and `k8s/prober-deployment.yaml` still have `replicas: 0`; no CronJob file added.
- [x] Do not touch `deploy/prod` or GitOps app enablement. Evidence: only repo-local `.github/workflows/ci.yml`, `k8s/manifest.yaml`, and `k8s/prober-deployment.yaml` changed.
- [x] Fail closed on required Brain auth in crawler runtime. Evidence: `REQUIRE_BRAIN_API_KEY=true`; `competitor-crawler-secrets` `optional: false`.
- [x] Harden disabled pods before future activation. Evidence: pod `runAsNonRoot`, non-root uid/gid/fsGroup, `RuntimeDefault`; container `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, drop all capabilities; `/tmp` backed by `emptyDir`.
- [x] Enable CI Docker build smoke for crawler image. Evidence: `.github/workflows/ci.yml` sets `run_docker_build: true` with one image entry for `skirmshop-competitor-crawler`.
- [x] Prepare release workflow for crawler image. Evidence: `.github/workflows/release.yml` uses `reusable-release.yml@main` on runner `docker-build` for image `skirmshop-competitor-crawler`.

### Verification
- [x] `kubectl kustomize k8s` renders manifests. Evidence: Codex RSO re-run.
- [x] `kubectl apply --dry-run=server -k k8s` passes. Evidence: Codex RSO re-run.
- [x] Existing Python test suite passes after manifest-only change. Evidence: Codex RSO re-run `pytest -q`.

## Remaining Blockers
- [blocked] Image tag is still `:pending`; F7 needs the release workflow to publish a real tag, then k8s must pin tag/digest before activation.
- [blocked] Prober still has `skirmshop-stock-prober:pending` and no live transport/egress allowlist.
- [blocked] `competitor_intel` is not live in CNPG.
- [blocked] Argo app remains in `apps-disabled`.
- [blocked] No CronJob/nocturnal production window exists yet.
