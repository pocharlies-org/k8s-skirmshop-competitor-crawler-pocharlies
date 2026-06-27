# RHO DevOps Report - F7 Brain Ingest Egress Fix

## Objective
- [x] Restore crawler push-ingest connectivity without activating production scheduling. Evidence: `k8s/manifest.yaml`, `k8s/crawler-cronjobs.yaml`, `k8s/crawler-networkpolicy.yaml`.

## Directives
- [x] Keep crawler production disabled. Evidence: Deployment remains `replicas: 0`; all crawler CronJobs remain `suspend: true`.
- [x] Do not expose secret values. Evidence: only `BRAIN_URL` and NetworkPolicy destination labels/ports changed.
- [x] Route writes to the Brain ingest service, not the Brain read/API service. Evidence: `BRAIN_URL=http://skirmshop-brain-ingest.skirmshop-brain-prod.svc.cluster.local`.
- [x] Match NetworkPolicy egress to the destination pod endpoint port. Evidence: live Brain service endpoints expose ingest pod port `5001`; policy now allows `component=ingest` on TCP `5001`.

- [x] Rendered manifests show all crawler `BRAIN_URL` values pointing to `skirmshop-brain-ingest`. Evidence: `kubectl kustomize k8s | rg -n 'BRAIN_URL|skirmshop-brain-ingest|replicas: 0|suspend: true'` shows Deployment plus tier1/tier2/tier3 using `http://skirmshop-brain-ingest.skirmshop-brain-prod.svc.cluster.local`, with `replicas: 0` and all CronJobs `suspend: true`.
- [x] Rendered NetworkPolicy allows Brain ingest pod egress on TCP `5001`. Evidence: `kubectl kustomize k8s | rg -n 'component: ingest|port: 5001'` shows `app.kubernetes.io/component: ingest` and `port: 5001`.
- [x] Server-side Kubernetes validation passes. Evidence: `kubectl apply --dry-run=server -k k8s` PASS for Deployment, 3 CronJobs, ExternalSecrets, NetworkPolicies and VMPodScrape.
- [x] Local tests still pass. Evidence: `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> `207 passed in 1.57s`; `/tmp/crawler-f7-venv/bin/python -m compileall src tests` PASS.
- [ ] CI passes after commit/push. Evidence: pending GitHub Actions run.
- [ ] Argo syncs the committed revision Healthy. Evidence: pending Argo check.
- [ ] A minimal live write smoke sends one Brain push successfully. Evidence: pending Job logs/metrics.

## Specialist Checks
- [blocked] `rho-devops` delegated implementer. Evidence: Claude CLI invocation on 2026-06-27 produced no stdout and no diff before PMO cancellation.
- [x] Codex/RSO PMO exception scoped to manifests/report only. Evidence: modified only `k8s/manifest.yaml`, `k8s/crawler-cronjobs.yaml`, `k8s/crawler-networkpolicy.yaml`, and this report.

## Status
- 2026-06-27T22:01:53+02:00 - Prepared. Root cause candidate from direct evidence: crawler used Brain API service while push-ingest should target `skirmshop-brain-ingest`; NetworkPolicy allowed `component=api` on TCP `80` while live endpoints target pod port `5001`. Validation and live smoke still pending.
- 2026-06-27T22:04:00+02:00 - PMO validation PASS for prepared manifests: tests `207 passed`, compile PASS, server dry-run PASS, rendered BRAIN_URL values point to Brain ingest and NetworkPolicy targets ingest TCP `5001`. CI, Argo sync and live smoke still pending.
