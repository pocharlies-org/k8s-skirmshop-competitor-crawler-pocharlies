# RHO Verifier - F7 crawler image gate

## Scope
- Role: `rho-verifier`, read-only.
- Target: audit the F7 crawler image publication/pin gate in the working tree.
- No edits performed by verifier.

## Verdict
PASS for digest pin and safe-disabled state in the working tree.

F7 global remains NOT PASS.

## Checklist
- [x] Crawler Deployment uses digest `sha256:67ccb373aa36ca3822ab59b04b1a88bf113fe3b834d2e59824fdb65fe30f32e4`. Evidence: `k8s/manifest.yaml:38`.
- [x] Three crawler CronJobs use the same digest. Evidence: `k8s/crawler-cronjobs.yaml:83`, `:196`, `:309`.
- [x] No crawler `:pending` image remains in `k8s/`. Evidence: verifier `rg "competitor-crawler:pending" k8s/` returned no matches.
- [x] Prober remains excluded and still uses `:pending`. Evidence: `k8s/prober-deployment.yaml:38`.
- [x] Production remains inactive. Evidence: `k8s/manifest.yaml:8` and `k8s/prober-deployment.yaml:8` keep `replicas: 0`; `k8s/crawler-cronjobs.yaml:44`, `:157`, `:270` keep `suspend: true`.
- [x] F7 global remains NOT PASS. Evidence: checklist keeps objective, DB/migration, prober transport, Argo app, egress network, live night and final verifier gates open.

## Blockers Observed By Verifier
- [blocked] The pin was uncommitted/unpushed at verifier runtime. PMO must commit and push immediately after validation.
- [blocked] Verifier could not run `gh run view 28297927525`, `crane digest`, or `kubectl` because its permission classifier blocked those commands. PMO must provide direct command evidence.
- [blocked] Prior `verifier.report.md` is a historical prepared-state report and still describes the pre-release `:pending` state; use this report plus `devops-release.report.md` for the current image gate.

## PMO Reconciliation
Codex PMO re-ran the blocked evidence directly before commit:
- `gh run view 28297927525` -> release `success`.
- `crane digest` on `harbor.e-dani.com` and `harbor.lan.e-dani.com` -> matching digest `sha256:67ccb373aa36ca3822ab59b04b1a88bf113fe3b834d2e59824fdb65fe30f32e4`.
- `kubectl kustomize k8s` -> crawler digest rendered, prober pending, replicas `0`, CronJobs `suspend: true`.
- `kubectl apply --dry-run=server -k k8s` -> PASS.
- `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> 198 passed.
- `/tmp/crawler-f7-venv/bin/python -m compileall src tests` -> PASS.
- `git diff --check` -> PASS.
