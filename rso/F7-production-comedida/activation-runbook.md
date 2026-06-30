# F7 Activation Runbook - gated

This runbook records the remaining activation sequence. It is not approval to apply production.

## Current safe state

- Branch: `codex/competitor-crawler-F7-production-comedida`
- Crawler Deployment: prepared, `replicas: 0`, image pinned by immutable digest `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:4a8d993694dd95007cb6f7f2229b232c0e6764b9fc9bc6fe517e683a3663afeb`.
- Prober Deployment: prepared, `replicas: 0`, image pinned by immutable digest `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:b5ceac612a5a71f614756efe4be99438b403491efc5b624ce14ae528cd9bc697`.
- Crawler CronJobs: prepared and live-synced for tier1/tier2/tier3; tier1/tier2 remain `suspend: true`; tier3 is active with `suspend: false`, schedule `0 4 * * 3`, `timeZone: Europe/Madrid`; all use the same pinned crawler digest and `backoffLimit: 0` to avoid repeated live traffic after an anti-bot/challenge failure.
- NetworkPolicy: crawler and prober default-deny egress.
- Brain push auth: implemented with `BRAIN_API_KEY` and `REQUIRE_BRAIN_API_KEY=true`.
- Observability: one-shot runner exposes opt-in `/metrics`; CronJobs set `METRICS_PORT=9090` and `METRICS_LINGER_SECONDS=45`; `VMPodScrape` is prepared for VictoriaMetrics.
- CI: smoke build and manifest validation passing.
- Live DB: `competitor_intel` exists and migration `001_f3_history.sql` is applied.
- Live crawler/prober resources: present through Argo Application with Deployments still safe-disabled (`skirmshop-competitor-crawler` and `skirmshop-stock-prober` Deployments are `0/0`); crawler CronJobs tier1/tier2 are `suspend: true`; crawler CronJob tier3 is `suspend: false`.
- Argo status: Application exists, targets this branch, and is `Synced/Healthy`.
- GitOps reconciliation: infra PR #15 and gitops PR #11 are merged.
- Production activation: PASS for tier3-only production comedida after rso6 and post-sync verification. Tier1 remains blocked by anti-bot/challenge evidence. Tier2 was tested in rso2: `powair6.com` passed the data path with 497 rows and Brain push `sent=497 failed=0`, but full tier2 activation remains blocked by `challenge_body` on `begadi.com` and `aa-store.at`.

## Gate 1 - publish image

Required evidence:

- [x] Release workflow available. Evidence: `.github/workflows/release.yml`.
- [x] Release path verified by tag trigger. Evidence: branch
  `workflow_dispatch` returned HTTP 404 because the workflow is not on the
  default branch, so the approved path was tag trigger. Tag `f7-b19cfa8`
  created release run `28297927525`.
- [x] Release run publishes a crawler image tag and digest. Evidence: GitHub
  Actions release run `28414167044` completed success on commit
  `ccf85a3b8c487723cac975a29a2204031c593bef`; `crane digest` on both
  `harbor.e-dani.com/homelab/skirmshop-competitor-crawler:f7-ccf85a3` and
  `harbor.lan.e-dani.com/homelab/skirmshop-competitor-crawler:f7-ccf85a3`
  returns `sha256:6332c7ff14a2c7ec3c8323240edb10bfcdb24600effc513421d8516e8388f4a1`.
- [x] Manifest pins the published digest, not `:pending`. Evidence:
  `k8s/manifest.yaml` and `k8s/crawler-cronjobs.yaml` use
  `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:6332c7ff14a2c7ec3c8323240edb10bfcdb24600effc513421d8516e8388f4a1`.
- [x] CI confirms image build smoke before release. Evidence: GitHub Actions CI
  run `28414122080` PASS on commit `ccf85a3`.
- [x] Superseding image with auth-route and metrics-status hardening is pinned
  live. Evidence: commit `fbd03f9` pins crawler Deployment and tier1/tier2/tier3
  CronJobs to
  `harbor.e-dani.com/homelab/skirmshop-competitor-crawler@sha256:4a8d993694dd95007cb6f7f2229b232c0e6764b9fc9bc6fe517e683a3663afeb`;
  release `28429187546` PASS for tag `f7-de04ea5`; CI `28429333532` PASS;
  Argo `Synced Healthy fbd03f9`.

Gate 1 is PASS for the crawler image. This does not activate production and does not cover the prober image.

## Gate 2 - one-shot runner

Required evidence:

- [x] A bounded crawler command exists and exits 0/1 after one tier/window. Evidence: `src/run_once.py`; `/tmp/crawler-f7-venv/bin/python -m pytest -q` -> 192 passed.
- [x] Tests cover success, failure and no-doc/no-push behavior. Evidence: `tests/test_run_once.py`; `tests/test_scheduler.py`.
- [x] CronJob command uses the one-shot runner, not `python -m src.main`. Evidence: `k8s/crawler-cronjobs.yaml` command `python -m src.run_once --tier <tier> --config /app/config.yaml`.
- [x] `concurrencyPolicy: Forbid`, low resources, history limits and no automatic retry are configured. Evidence: `k8s/crawler-cronjobs.yaml` sets `backoffLimit: 0`; `kubectl apply --dry-run=server -k k8s` PASS; CI run `28409410223` PASS; Argo revision `5f4635e20948ace566e94589ccd95494aafdaa77` `Synced Healthy`; live CronJobs tier1/tier2/tier3 show `suspend=true`, `backoffLimit=0`.

Remaining blockers for activation: prober live transport/image/egress/runner and clean live night evidence.

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
- [x] Prober live gate is passed for the approved AirsoftQuimera path while
  steady-state remains disabled. Evidence: B1+B2 implemented `src/prober/http_transport.py`,
  `src/prober/airsoftquimera.py` and `src/prober/run_once.py`, release
  `28412115494` published digest
  `sha256:b5ceac612a5a71f614756efe4be99438b403491efc5b624ce14ae528cd9bc697`,
  live prober remains `replicas=0`, permanent `k8s/prober-networkpolicy.yaml`
  remains `egress: []`, and B3 used a deleted temporary one-job NetworkPolicy
  for DNS/Postgres/public-443. B3 evidence: Job `prober-b3-aq-20260630-005056`
  logged add/remove `200 OK`, `cleanup=clean`, `inserted=1 skipped=0`, and
  independent SQL `count=1 stock_method=cart_probe`.

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
- [x] Partial tier failures are reported as error status, not a green run.
  Evidence: commit `de04ea5` makes `src/run_once.py` call
  `metrics.finish_run(..., status=error)` when a tier returns `failed > 0`;
  focused metrics/run_once tests passed and full suite returned `239 passed`;
  image digest `sha256:4a8d993694dd95007cb6f7f2229b232c0e6764b9fc9bc6fe517e683a3663afeb`
  is live.
- [x] CronJobs are scrapeable when unsuspended. Evidence: `k8s/crawler-cronjobs.yaml` exposes named port `metrics`, `METRICS_PORT=9090`, `METRICS_LINGER_SECONDS=45`; `k8s/crawler-vmpodscrape.yaml`; `kubectl apply --dry-run=server -k k8s` PASS including `vmpodscrape.operator.victoriametrics.com/skirmshop-competitor-crawler created (server dry run)`.
- [x] Dashboard or equivalent read-only query captured in F7 evidence. Evidence:
  rso6 authenticated Brain/RAG Service query
  `/instances/skirmshop/prices/comparison?status=active&filter=has_comp&limit=1`
  returned HTTP 200 with `total=435`, `count=1`.
- [x] Blocked-domain count, retry/failure reasons and history writes captured
  from real run evidence. Evidence: `live-night-tier1-failclosed.report.md`
  captures the blocked tier1 failure mode; `live-night-tier3-rso6.report.md`
  captures clean tier3 metrics/history/push evidence with no challenge/CAPTCHA
  and `push_failed=0`.

## Gate 7 - live night

Required evidence:

- [x] One real nocturnal run completes. Evidence: manual tier3 Job
  `skirmshop-competitor-crawler-tier3-rso6-20260630013804`, created from the
  live CronJob template, completed `Succeeded exit=0`.
- [x] `competitor_crawl_block_total` has no sustained increase for the cleared
  tier3 candidate. Evidence: rso6 logs have no challenge/CAPTCHA/403/429/503 or
  fetch-blocked lines; push failures are 0.
- [x] Logs show no ban/challenge/CAPTCHA escalation for tier3. Evidence:
  negative log grep in `live-night-tier3-rso6.report.md`.
- [x] Brain `/prices/comparison` remains populated. Evidence: service query
  returned `total=435`, `count=1`.
- [x] Postgres history has new observations for the run. Evidence: SQL readback
  for `run_id='tier3:20260630T013825797218Z'` returned 67 rows / 67 distinct
  products for `fullmetal.es`.
- [x] Tier3-only activation was committed, synced and verified live. Evidence:
  commit `7a7cf47`; CI `28414840927` PASS; Argo revision
  `7a7cf47b6654d5f9a8d3540a068bdadfa79b638f` `Synced Healthy`; live tier3
  `suspend=false`; tier1/tier2 `suspend=true`; all CronJobs `backoffLimit=0`;
  crawler/prober Deployments `replicas=0`; no immediate automatic Job appeared
  after sync.
- [blocked: challenge_body] Tier2 live data gate was attempted and remains
  blocked. Evidence: `live-night-tier2-rso2.report.md`; Job
  `skirmshop-competitor-crawler-tier2-rso2-20260630074224` collected 497
  `powair6.com` rows and Brain push `sent=497 failed=0`, but
  `begadi.com` and `aa-store.at` returned `challenge_body`; summary
  `pushed=497 failed=2`; pod `Failed exit=1`; tier2 remains `suspend=true`.

Remediation prepared after the aborted run:

- `src/extractor.py` skips basket/cart/compare/return/search/captcha/challenge paths before BFS.
- `src/fetcher.py` fails closed on 403/429/503/challenge/captcha and does not invoke Firecrawl for blocked pages.
- `src/crawler.py` aborts the affected store via `FetchBlockedError` so `--fail-on-push-errors` can fail the job.
- `k8s/crawler-cronjobs.yaml` sets `backoffLimit: 0` so a failed live window does not repeat competitor traffic automatically.

F7 activation caveat: gates above are PASS for tier3-only production comedida,
and tier3 is now live. Tier1/tier2 are not cleared by this evidence; tier1
previously failed closed on anti-bot/challenge signals, and tier2 rso2 remains
blocked by `challenge_body` on `begadi.com` and `aa-store.at` despite a clean
`powair6.com` data path.
