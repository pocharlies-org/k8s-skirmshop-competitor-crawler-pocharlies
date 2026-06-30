# RHO DevOps - F7 crawler image release/pin report

## Scope
- Owner: `rho-devops` lane plus Codex PMO audit.
- Files changed: `k8s/manifest.yaml`, `k8s/crawler-cronjobs.yaml`, `rso/F7-production-comedida/CHECKLIST.md`, `rso/F7-production-comedida/activation-runbook.md`, `rso/F7-production-comedida/devops-release.report.md`.
- Production activation: none. No real `kubectl apply`, no Argo app move, no replica increase, no CronJob unsuspend.

## Evidence
- Current release run: GitHub Actions `28414167044` completed `success` for tag `f7-ccf85a3`, commit `ccf85a3b8c487723cac975a29a2204031c593bef`.
- Registry digest: `crane digest harbor.e-dani.com/homelab/skirmshop-competitor-crawler:f7-ccf85a3` and `crane digest harbor.lan.e-dani.com/homelab/skirmshop-competitor-crawler:f7-ccf85a3` both returned `sha256:6332c7ff14a2c7ec3c8323240edb10bfcdb24600effc513421d8516e8388f4a1`.
- Manifest pin: crawler Deployment and all three crawler CronJobs use `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:6332c7ff14a2c7ec3c8323240edb10bfcdb24600effc513421d8516e8388f4a1`.
- Safe disabled state preserved in manifests: crawler Deployment remains `replicas: 0`; crawler CronJobs remain `suspend: true` with `backoffLimit: 0`; prober Deployment remains `replicas: 0` and continues using digest `sha256:b5ceac612a5a71f614756efe4be99438b403491efc5b624ce14ae528cd9bc697`.

## Checklist
- [x] Crawler image is published by release workflow. Evidence: GitHub Actions release run `28414167044` success.
- [x] Published image digest is independently verified. Evidence: `crane digest` on public and LAN Harbor hosts returned the same SHA256.
- [x] Crawler manifests pin digest instead of mutable/pending tag. Evidence: `k8s/manifest.yaml` and `k8s/crawler-cronjobs.yaml`.
- [x] Production remains inactive. Evidence: `replicas: 0`, `suspend: true`, no real apply.
- [x] Prober remains excluded from crawler repin. Evidence: `k8s/prober-deployment.yaml` still uses digest `sha256:b5ceac612a5a71f614756efe4be99438b403491efc5b624ce14ae528cd9bc697`.
- [blocked] F7 global activation. Blocker: clean live-night/data-gate evidence remains unresolved.

## Notes
The Claude `rho-devops` invocation applied the manifest pin but returned no final report. Codex PMO completed this report and checklist as a documented RSO exception, then re-ran verification gates before commit.
