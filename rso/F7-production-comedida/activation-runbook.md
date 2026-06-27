# F7 Activation Runbook - gated

This runbook records the remaining activation sequence. It is not approval to apply production.

## Current safe state

- Branch: `codex/competitor-crawler-F7-production-comedida`
- Crawler Deployment: prepared, `replicas: 0`, image pinned by immutable digest `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:67ccb373aa36ca3822ab59b04b1a88bf113fe3b834d2e59824fdb65fe30f32e4`.
- Prober Deployment: prepared, `replicas: 0`, image `:pending`.
- Crawler CronJobs: prepared in manifests for tier1/tier2/tier3, all `suspend: true`, image pinned by the same crawler digest.
- NetworkPolicy: crawler and prober default-deny egress.
- Brain push auth: implemented with `BRAIN_API_KEY` and `REQUIRE_BRAIN_API_KEY=true`.
- Observability: one-shot runner exposes opt-in `/metrics`; CronJobs set `METRICS_PORT=9090` and `METRICS_LINGER_SECONDS=45`; `VMPodScrape` is prepared for VictoriaMetrics.
- CI: smoke build and manifest validation passing.
- Live DB: not present.
- Live crawler/prober resources: not present in namespace `skirmshop`.
- Production activation: blocked.

## Gate 1 - publish image

Required evidence:

- [x] Release workflow available. Evidence: `.github/workflows/release.yml`.
- [x] Release path verified by tag trigger. Evidence: branch
  `workflow_dispatch` returned HTTP 404 because the workflow is not on the
  default branch, so the approved path was tag trigger. Tag `f7-b19cfa8`
  created release run `28297927525`.
- [x] Release run publishes a crawler image tag and digest. Evidence: GitHub
  Actions release run `28297927525` completed success on commit
  `b19cfa8fb38480cf668e6ed61bbe72b683be67c7`; `crane digest` on both
  `harbor.e-dani.com/homelab/skirmshop-competitor-crawler:f7-b19cfa8` and
  `harbor.lan.e-dani.com/homelab/skirmshop-competitor-crawler:f7-b19cfa8`
  returns `sha256:67ccb373aa36ca3822ab59b04b1a88bf113fe3b834d2e59824fdb65fe30f32e4`.
- [x] Manifest pins the published digest, not `:pending`. Evidence:
  `k8s/manifest.yaml` and `k8s/crawler-cronjobs.yaml` use
  `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:67ccb373aa36ca3822ab59b04b1a88bf113fe3b834d2e59824fdb65fe30f32e4`.
- [x] CI confirms image build smoke before release. Evidence: GitHub Actions CI
  run `28297898411` PASS on commit `b19cfa8`.

Gate 1 is PASS for the crawler image. This does not activate production and does not cover the prober image.

## Gate 2 - one-shot runner

Required evidence:

- [x] A bounded crawler command exists and exits 0/1 after one tier/window. Evidence: `src/run_once.py`; `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> 192 passed.
- [x] Tests cover success, failure and no-doc/no-push behavior. Evidence: `tests/test_run_once.py`; `tests/test_scheduler.py`.
- [x] CronJob command uses the one-shot runner, not `python -m src.main`. Evidence: `k8s/crawler-cronjobs.yaml` command `python -m src.run_once --tier <tier> --config /app/config.yaml`.
- [x] `concurrencyPolicy: Forbid`, low resources, history limits and backoff are configured. Evidence: `k8s/crawler-cronjobs.yaml`; `kubectl apply --dry-run=server -k k8s` PASS.

Remaining blocker for activation: DB live, egress allowlist, Argo enable, prober live transport/image and live night evidence.

## Gate 3 - DB and migration

Required evidence:

- [x] CNPG `Database` resource `competitor-intel` exists live in namespace `databases`. Evidence: `kubectl -n databases get database competitor-intel -o wide` -> `APPLIED true`.
- [x] Migration `db/migrations/001_f3_history.sql` is applied to `competitor_intel`. Evidence: `db-live.report.md`; migration applied with role `skirmshop`.
- [x] SQL verifies tables/partitions/view used by F3/F7. Evidence: schema/table/view/owner query in `db-live.report.md`; smoke transaction produced `3|estimated`, rolled back, and left `0` smoke rows.
- [x] Credentials are delivered through Kubernetes Secret without value disclosure. Evidence: psql used `PGPASSWORD` populated from `secret/skirmshop-db-credentials` without printing the value.
- [blocked] GitOps reconciliation is not merged yet. Evidence: live CR was applied directly; branch `codex/competitor-crawler-F7-db-gitops` commit `9140897` and PR `https://github.com/pocharlies-org/k8s-infra-pocharlies/pull/15` prepare the `deploy/prod` reconciliation without direct `deploy/prod` push.

## Gate 4 - secrets

Required evidence:

- `ExternalSecret/competitor-crawler-secrets` is synced.
- Resulting Secret exists and includes required keys by name only.
- No secret value appears in repo, logs, reports or shell output.

## Gate 5 - egress allowlists

Required evidence:

- [x] Crawler application guard blocks off-domain fetches. Evidence:
  `backend-egress.report.md`; `src/egress_guard.py`; `src/fetcher.py` blocks
  forbidden URL before direct fetch/Firecrawl and discards off-domain redirects;
  `src/crawler.py` no longer uses `domain in netloc`; `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> 198 passed.
- [ ] Crawler can reach only required internal services plus approved competitor
  egress at network layer. Blocker: live cluster exposes only standard
  Kubernetes `NetworkPolicy`; no Cilium/FQDN policy was found. Standard
  `NetworkPolicy` cannot express domain allowlists for competitor FQDNs. Before
  activation choose and verify an egress proxy, Cilium/FQDN-capable policy, or
  another approved network control.
- [ ] Prober remains disabled unless a domain-specific allowlist is approved.
  Evidence: `src/prober/transport.py` is still protocol-only and
  `k8s/prober-networkpolicy.yaml` has `egress: []`.

## Gate 6 - observability

Required evidence:

- [x] Runner metrics expose job success and push sent/failed counts. Evidence: `src/metrics_exporter.py` exports `competitor_crawler_run_total{tier,status}`, `competitor_crawler_push_sent_total{tier}`, `competitor_crawler_push_failed_total{tier}`, `competitor_crawler_run_active{tier}`; `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> 192 passed.
- [x] CronJobs are scrapeable when unsuspended. Evidence: `k8s/crawler-cronjobs.yaml` exposes named port `metrics`, `METRICS_PORT=9090`, `METRICS_LINGER_SECONDS=45`; `k8s/crawler-vmpodscrape.yaml`; `kubectl apply --dry-run=server -k k8s` PASS including `vmpodscrape.operator.victoriametrics.com/skirmshop-competitor-crawler created (server dry run)`.
- [ ] Dashboard or equivalent read-only query captured in F7 evidence. Blocker: no pod target exists while CronJobs are `suspend: true`; verify vmagent target and dashboard during the first approved unsuspended run.
- [ ] Blocked-domain count, retry/failure reasons and history writes captured from real run evidence. Blocker: requires live night run and DB/historical writes.

## Gate 7 - live night

Required evidence:

- One real nocturnal run completes.
- `competitor_crawl_block_total` has no sustained increase.
- Logs show no ban/challenge/CAPTCHA escalation.
- Brain `/prices/comparison` remains populated.
- Postgres history has new observations for the run.

F7 PASS requires all gates above.
