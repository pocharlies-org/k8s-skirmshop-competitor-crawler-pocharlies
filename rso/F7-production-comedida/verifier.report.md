# F7 Verifier Report - current prepared state

**Owner:** `rho-verifier` independent read-only pass, reconciled by Codex RSO/PMO.
**Date:** 2026-06-27T16:56:37+02:00.
**Branch/commit audited:** `codex/competitor-crawler-F7-production-comedida` at `18f869f`.

## Verdict

- Prepared-but-inactive F7 state: **PASS**.
- F7 phase completion: **NOT PASS / BLOCKED**.

The repository now contains a safe, inactive production-prep shape: Deployments stay at `replicas: 0`, CronJobs are `suspend: true`, images are still `:pending`, egress is default-deny, and no Argo/prod activation was performed.

F7 cannot close because the master gate requires a real nocturnal run with logs, metrics, Brain/API evidence and SQL history. That evidence does not exist yet.

## Independent verifier findings

- Branch and HEAD were inspected from git metadata: F7 branch at `18f869f`.
- `k8s/crawler-cronjobs.yaml` defines 3 CronJobs, all `suspend: true`.
- CronJobs use `python -m src.run_once --tier <tier> --config /app/config.yaml`.
- CronJobs are staggered in `Europe/Madrid`: tier1 `0 2 */2 * *`, tier2 `0 3 * * 1`, tier3 `0 4 * * 3`.
- `config.yaml` tier names align with CronJob `--tier` values.
- Deployments remain inert: `k8s/manifest.yaml` and `k8s/prober-deployment.yaml` use `replicas: 0`.
- `src/push_client.py` uses `X-API-Key` from `BRAIN_API_KEY` and fail-closes when `REQUIRE_BRAIN_API_KEY` is truthy.
- `src/run_once.py` is bounded and exits with `0/1/2`; it reuses `crawl_tier`.
- Pod hardening is present on Deployments and CronJobs.
- Crawler and prober NetworkPolicies remain `egress: []`.
- Observability is not ready: `competitor_crawl_block_total` exists only as an in-memory metric name in `src/prober/metrics.py`; no `/metrics` or `start_http_server` scrape endpoint exists.

## PMO re-executed evidence

- `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> `159 passed`.
- `/tmp/crawler-f7-venv/bin/python -m compileall src tests` -> PASS.
- `/tmp/crawler-f7-venv/bin/python -m src.run_once --tier nope --config config.yaml` -> exit `2`.
- `/tmp/crawler-f7-venv/bin/python -m src.run_once --config config.yaml` -> exit `2`.
- `kubectl kustomize k8s` -> PASS; rendered 3 CronJobs with `suspend: true`.
- `kubectl apply --dry-run=server -k k8s` -> PASS; API server accepted Deployments, ExternalSecret, NetworkPolicies and CronJobs tier1/tier2/tier3.
- GitHub Actions CI run `28292526816` at commit `18f869f` -> success; `Lint and validate manifests` 24s, `Build images` 41s.
- `git status --short --branch` before this report batch -> clean on `codex/competitor-crawler-F7-production-comedida...origin/codex/competitor-crawler-F7-production-comedida`.

## Blockers to F7 PASS

- [blocked] Published image tag/digest is missing; manifests still use `:pending`.
- [blocked] `competitor_intel` is not live and SQL migration is not applied live.
- [blocked] Argo app is still disabled in GitOps.
- [blocked] CronJobs are intentionally suspended; no live nocturnal run has occurred.
- [blocked] Egress allowlist is missing; current NetworkPolicies are default-deny.
- [blocked] Prober live transport and domain allowlist are absent.
- [blocked] Observability endpoint/dashboard is absent.
- [blocked] No real-night logs/metrics/API/SQL evidence exists.

## Checklist

- [x] Prepared state matches repository claims. Evidence: independent file inspection + PMO commands above.
- [x] No production activation found. Evidence: `replicas: 0`, `suspend: true`, `:pending`, default-deny egress.
- [x] Current code/manifests pass local and CI validation. Evidence: PMO commands + CI `28292526816`.
- [blocked] Full F7 verifier PASS. Blocker: live activation/night evidence does not exist and should not be produced until image, DB, egress, secrets, observability and Argo gates pass.
