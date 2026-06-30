# RHO DevOps Report - F7 Prober Live B2 Prepared

Timestamp: 2026-06-30T02:38:25+02:00

## Scope
- [x] Publish an immutable runtime artifact containing B1 code. Evidence: Release Production run `28412115494` for tag `f7-5c19b85` completed `success`.
- [x] Verify digest in both Harbor endpoints. Evidence: `crane digest harbor.e-dani.com/homelab/skirmshop-competitor-crawler:f7-5c19b85` and LAN endpoint both returned `sha256:b5ceac612a5a71f614756efe4be99438b403491efc5b624ce14ae528cd9bc697`.
- [x] Choose packaging path. Evidence: `k8s/prober-deployment.yaml` uses the existing crawler image digest with explicit command override `python -m src.prober.run_once`; this keeps logical Deployment isolation without adding a second image pipeline.
- [x] Keep runtime safe-disabled. Evidence before commit: rendered manifest keeps `skirmshop-stock-prober` `replicas: 0`, crawler CronJobs `suspend: true`, `backoffLimit: 0`, and prober NetworkPolicy `egress: []`.

## Evidence
- CI before release: `28412072803` success on commit `5c19b85d89ca8c1faf927bd03576639b55ae400a`.
- Release: `28412115494` success, job `release / Build and publish tagged images`.
- Digest: `sha256:b5ceac612a5a71f614756efe4be99438b403491efc5b624ce14ae528cd9bc697`.
- Render check:
  - `kubectl kustomize k8s > /tmp/f7-b2-kustomize.yaml`
  - rendered prober image: `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:b5ceac612a5a71f614756efe4be99438b403491efc5b624ce14ae528cd9bc697`
  - rendered command includes `src.prober.run_once`
  - rendered args include `/app/prober-targets/targets.json`
  - rendered prober `replicas: 0`
  - rendered CronJobs `suspend: true`, `backoffLimit: 0`
  - rendered prober egress `[]`
- Server dry-run: `kubectl apply --dry-run=server -k k8s` -> PASS.
- Diff whitespace: `git diff --check` -> PASS.

## Pending Post-Commit Verification
- [ ] Commit/push the manifest pin.
- [ ] Wait for CI on the manifest pin commit.
- [ ] Verify Argo `skirmshop-competitor-crawler` `Synced Healthy` on the pin commit.
- [ ] Verify live Deployment remains `replicas=0` and uses the pinned digest/command.
- [ ] Verify live CronJobs remain `suspend=true`, `backoffLimit=0`.

## Residual Risks
- [blocked] B3 live smoke remains blocked by default-deny prober egress and absence of approved live smoke Job/target ConfigMap in this subcycle.
- [blocked] F7 global remains NOT PASS until a clean live night and prober B3 decision.
