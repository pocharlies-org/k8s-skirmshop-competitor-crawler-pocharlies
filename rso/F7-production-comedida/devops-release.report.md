# RHO DevOps - F7 crawler image release/pin report

## Scope
- Owner: `rho-devops` lane plus Codex PMO audit.
- Files changed: `k8s/manifest.yaml`, `k8s/crawler-cronjobs.yaml`, `rso/F7-production-comedida/CHECKLIST.md`, `rso/F7-production-comedida/activation-runbook.md`, `rso/F7-production-comedida/devops-release.report.md`.
- Production activation: none. No real `kubectl apply`, no Argo app move, no replica increase, no CronJob unsuspend.

## Evidence
- Release run: GitHub Actions `28297927525` completed `success` for tag `f7-b19cfa8`, commit `b19cfa8fb38480cf668e6ed61bbe72b683be67c7`.
- Registry digest: `crane digest harbor.e-dani.com/homelab/skirmshop-competitor-crawler:f7-b19cfa8` and `crane digest harbor.lan.e-dani.com/homelab/skirmshop-competitor-crawler:f7-b19cfa8` both returned `sha256:67ccb373aa36ca3822ab59b04b1a88bf113fe3b834d2e59824fdb65fe30f32e4`.
- Manifest pin: crawler Deployment and all three crawler CronJobs use `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:67ccb373aa36ca3822ab59b04b1a88bf113fe3b834d2e59824fdb65fe30f32e4`.
- Safe disabled state preserved: crawler Deployment remains `replicas: 0`; crawler CronJobs remain `suspend: true`; prober image remains `harbor.e-dani.com/homelab/skirmshop-stock-prober:pending`.

## Checklist
- [x] Crawler image is published by release workflow. Evidence: GitHub Actions release run `28297927525` success.
- [x] Published image digest is independently verified. Evidence: `crane digest` on public and LAN Harbor hosts returned the same SHA256.
- [x] Crawler manifests pin digest instead of mutable/pending tag. Evidence: `k8s/manifest.yaml` and `k8s/crawler-cronjobs.yaml`.
- [x] Production remains inactive. Evidence: `replicas: 0`, `suspend: true`, no real apply.
- [x] Prober remains excluded. Evidence: `k8s/prober-deployment.yaml` still uses `skirmshop-stock-prober:pending`.
- [blocked] F7 global activation. Blocker: live CNPG database/migration, network-layer egress control, Argo app enable, prober transport/image, and live-night evidence remain unresolved.

## Notes
The Claude `rho-devops` invocation applied the manifest pin but returned no final report. Codex PMO completed this report and checklist as a documented RSO exception, then re-ran verification gates before commit.
