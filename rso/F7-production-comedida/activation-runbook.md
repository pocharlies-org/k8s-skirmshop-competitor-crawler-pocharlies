# F7 Activation Runbook - gated

This runbook records the remaining activation sequence. It is not approval to apply production.

## Current safe state

- Branch: `codex/competitor-crawler-F7-production-comedida`
- Crawler Deployment: prepared, `replicas: 0`, image pinned by immutable digest `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:dbcf0f207e85e3c8fab185e6a318c644bcbc3ec0d2a3f1ee97cde883cfbcb4b6`.
- Prober Deployment: prepared, `replicas: 0`, image `:pending`.
- Crawler CronJobs: prepared in manifests for tier1/tier2/tier3, all `suspend: true`, image pinned by the same crawler digest.
- NetworkPolicy: crawler and prober default-deny egress.
- Brain push auth: implemented with `BRAIN_API_KEY` and `REQUIRE_BRAIN_API_KEY=true`.
- Observability: one-shot runner exposes opt-in `/metrics`; CronJobs set `METRICS_PORT=9090` and `METRICS_LINGER_SECONDS=45`; `VMPodScrape` is prepared for VictoriaMetrics.
- CI: smoke build and manifest validation passing.
- Live DB: `competitor_intel` exists and migration `001_f3_history.sql` is applied.
- Live crawler/prober resources: present through Argo Application, but still safe-disabled (`skirmshop-competitor-crawler` and `skirmshop-stock-prober` Deployments are `0/0`; crawler CronJobs tier1/tier2/tier3 are `suspend: true`).
- Argo status: Application exists, targets this branch, and is `Synced/Healthy`.
- GitOps reconciliation: infra PR #15 and gitops PR #11 are merged.
- Production activation: blocked until prober gate and a clean live run evidence pass.

## Gate 1 - publish image

Required evidence:

- [x] Release workflow available. Evidence: `.github/workflows/release.yml`.
- [x] Release path verified by tag trigger. Evidence: branch
  `workflow_dispatch` returned HTTP 404 because the workflow is not on the
  default branch, so the approved path was tag trigger. Tag `f7-b19cfa8`
  created release run `28297927525`.
- [x] Release run publishes a crawler image tag and digest. Evidence: GitHub
  Actions release run `28408371096` completed success on commit
  `d546a28b132e5dcc9700ff57d4f0fd76ee306fc8`; `crane digest` on both
  `harbor.e-dani.com/homelab/skirmshop-competitor-crawler:f7-d546a28` and
  `harbor.lan.e-dani.com/homelab/skirmshop-competitor-crawler:f7-d546a28`
  returns `sha256:dbcf0f207e85e3c8fab185e6a318c644bcbc3ec0d2a3f1ee97cde883cfbcb4b6`.
- [x] Manifest pins the published digest, not `:pending`. Evidence:
  `k8s/manifest.yaml` and `k8s/crawler-cronjobs.yaml` use
  `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:dbcf0f207e85e3c8fab185e6a318c644bcbc3ec0d2a3f1ee97cde883cfbcb4b6`.
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
- [x] GitOps reconciliation is merged. Evidence: PR `https://github.com/pocharlies-org/k8s-infra-pocharlies/pull/15` merged at `2026-06-29T22:52:55Z`, merge commit `6cf28b818b7baf7c6dd1c9c63e8446e72396860b`; live DB remains `APPLIED true`.

## Gate 4 - secrets

Required evidence:

- [x] `ExternalSecret/competitor-crawler-secrets` is synced. Evidence: `kubectl -n skirmshop get externalsecret competitor-crawler-secrets` Ready `True`, reason `SecretSynced`.
- [x] Resulting Secret exists and includes required keys by name only. Evidence: `kubectl -n skirmshop get secret competitor-crawler-secrets competitor-crawler-db-credentials -o json | jq ...` -> `competitor-crawler-secrets BRAIN_API_KEY`; `competitor-crawler-db-credentials password,username`.
- [x] No secret value appears in repo, logs, reports or shell output. Evidence: only key names were printed.

> Source-path fix (2026-06-27, rho-devops): `competitor-crawler-secrets` previously
> used `dataFrom.extract key=secret/skirmshop/competitor-crawler`, which does not
> exist in Vault, so the ExternalSecret could not sync. It now maps the single
> required key explicitly:
> `data[0].secretKey=BRAIN_API_KEY` <- `remoteRef.key=skirmshop-brain/prod/app`,
> `property=dashboard_api_key` (the Brain's own KV mount, same source other
> Skirmshop services use for Brain auth). `competitor-crawler-db-credentials`
> is unchanged. See `devops-secret.report.md`. Live sync was confirmed on
> 2026-06-30.

## Gate 5 - egress allowlists

Required evidence:

- [x] Crawler application guard blocks off-domain fetches. Evidence:
  `backend-egress.report.md`; `src/egress_guard.py`; `src/fetcher.py` blocks
  forbidden URL before direct fetch/Firecrawl and discards off-domain redirects;
  `src/crawler.py` no longer uses `domain in netloc`; `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> 198 passed.
- [x] Crawler has a compensating network egress control. Evidence:
  `k8s/crawler-networkpolicy.yaml` allows DNS, Brain API, Firecrawl API, CNPG
  Postgres and public TCP 80/443 excluding private/link-local ranges;
  `kubectl apply --dry-run=server -k k8s` PASS. Blocker removed as a native
  NetworkPolicy gate only under the accepted compensating model: standard
  Kubernetes `NetworkPolicy` cannot express competitor FQDNs, so FQDN allowlist
  enforcement remains in `src.egress_guard.py`.
- [ ] Prober remains disabled unless a domain-specific allowlist is approved.
  Evidence: `src/prober/transport.py` is still protocol-only and
  `k8s/prober-networkpolicy.yaml` has `egress: []`.

## Gate 5b - history runtime

Required evidence:

- [x] Runtime writes F3 observations during crawler runs. Evidence:
  `src/history_runtime.py`; `src/scheduler.py`; tests `205 passed`.
- [x] Runtime fails closed when history is enabled but PG env is missing.
  Evidence: `tests/test_history_runtime.py`.
- [x] Runtime is wired to Kubernetes without exposing secrets. Evidence:
  `ExternalSecret/competitor-crawler-db-credentials`; `PGUSER`/`PGPASSWORD`
  `secretKeyRef`; `kubectl apply --dry-run=server -k k8s` PASS.

## Gate 6 - observability

Required evidence:

- [x] Runner metrics expose job success and push sent/failed counts. Evidence: `src/metrics_exporter.py` exports `competitor_crawler_run_total{tier,status}`, `competitor_crawler_push_sent_total{tier}`, `competitor_crawler_push_failed_total{tier}`, `competitor_crawler_run_active{tier}`; `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> 192 passed.
- [x] CronJobs are scrapeable when unsuspended. Evidence: `k8s/crawler-cronjobs.yaml` exposes named port `metrics`, `METRICS_PORT=9090`, `METRICS_LINGER_SECONDS=45`; `k8s/crawler-vmpodscrape.yaml`; `kubectl apply --dry-run=server -k k8s` PASS including `vmpodscrape.operator.victoriametrics.com/skirmshop-competitor-crawler created (server dry run)`.
- [ ] Dashboard or equivalent read-only query captured in F7 evidence. Blocker: no pod target exists while CronJobs are `suspend: true`; verify vmagent target and dashboard during the first approved unsuspended run.
- [ ] Blocked-domain count, retry/failure reasons and history writes captured from real run evidence. Blocker: requires live night run and DB/historical writes.

## Gate 7 - live night

Required evidence:

- [blocked] One real nocturnal run completes. Evidence: manual tier1 job `skirmshop-competitor-crawler-tier1-rso-20260629225442` was aborted after anti-bot/cart-path evidence; see `live-night-aborted-anti-bot.report.md`.
- [blocked] `competitor_crawl_block_total` has no sustained increase. Blocker: the run encountered `captcha.php` 503 before clean completion.
- [blocked] Logs show no ban/challenge/CAPTCHA escalation. Blocker: logs showed `https://www.taiwangun.com/captcha.php?from=%2Fen` HTTP 503.
- [ ] Brain `/prices/comparison` remains populated.
- [ ] Postgres history has new observations for the run.

Remediation prepared after the aborted run:

- `src/extractor.py` skips basket/cart/compare/return/search/captcha/challenge paths before BFS.
- `src/fetcher.py` fails closed on 403/429/503/challenge/captcha and does not invoke Firecrawl for blocked pages.
- `src/crawler.py` aborts the affected store via `FetchBlockedError` so `--fail-on-push-errors` can fail the job.

F7 PASS requires all gates above.
