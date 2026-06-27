# F7 Activation Runbook - gated

This runbook records the remaining activation sequence. It is not approval to apply production.

## Current safe state

- Branch: `codex/competitor-crawler-F7-production-comedida`
- Crawler Deployment: prepared, `replicas: 0`, image `:pending`.
- Prober Deployment: prepared, `replicas: 0`, image `:pending`.
- Crawler CronJobs: prepared in manifests for tier1/tier2/tier3, all `suspend: true`, image `:pending`.
- NetworkPolicy: crawler and prober default-deny egress.
- Brain push auth: implemented with `BRAIN_API_KEY` and `REQUIRE_BRAIN_API_KEY=true`.
- Observability: one-shot runner exposes opt-in `/metrics`; CronJobs set `METRICS_PORT=9090` and `METRICS_LINGER_SECONDS=45`; `VMPodScrape` is prepared for VictoriaMetrics.
- CI: smoke build and manifest validation passing.
- Live DB: not present.
- Live crawler/prober resources: not present in namespace `skirmshop`.
- Production activation: blocked.

## Gate 1 - publish image

Required evidence:

- Release workflow available and runnable.
- Release run publishes `harbor.e-dani.com/homelab/skirmshop-competitor-crawler:<tag>` or digest.
- Manifest pins the published tag/digest, not `:pending`.
- CI or release log confirms image push.

Blocked until either the release workflow is merged to the branch/default path where GitHub can run it, or an explicitly approved manual image publish path is used.

## Gate 2 - one-shot runner

Required evidence:

- [x] A bounded crawler command exists and exits 0/1 after one tier/window. Evidence: `src/run_once.py`; `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> 192 passed.
- [x] Tests cover success, failure and no-doc/no-push behavior. Evidence: `tests/test_run_once.py`; `tests/test_scheduler.py`.
- [x] CronJob command uses the one-shot runner, not `python -m src.main`. Evidence: `k8s/crawler-cronjobs.yaml` command `python -m src.run_once --tier <tier> --config /app/config.yaml`.
- [x] `concurrencyPolicy: Forbid`, low resources, history limits and backoff are configured. Evidence: `k8s/crawler-cronjobs.yaml`; `kubectl apply --dry-run=server -k k8s` PASS.

Remaining blocker for activation: image tag/digest, DB live, egress allowlist, Argo enable and live night evidence.

## Gate 3 - DB and migration

Required evidence:

- CNPG `Database` resource `competitor-intel` exists live in namespace `databases`.
- Migration `db/migrations/001_f3_history.sql` is applied to `competitor_intel`.
- Read-only SQL verifies tables/partitions/view used by F3/F7.
- Credentials are least-privilege and delivered through secrets without value disclosure.

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
