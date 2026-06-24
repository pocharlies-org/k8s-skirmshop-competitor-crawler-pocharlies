# F3 Researcher Report - History Append-Only

**Date:** 2026-06-24T22:15:00+02:00  
**Role:** Codex RSO/PMO research exception after Claude CLI timeout  
**Scope:** read-only inspection of crawler RSO repo, `k8s-infra-pocharlies`, `skirmshop-brain-v2`, `k8s-skirmshopshopifyapp-pocharlies`, and Kubernetes resource names/status. No code edits, no DDL, no secrets read.

## RHO Checklist

### Directives
- [x] Start with Claude CLI researcher. Evidence: `timeout 180s env RSO_DELEGATED_ROLE=rho-researcher claude ... --agent rho-researcher` exited `124` with no output.
- [x] Continue read-only as PMO exception. Evidence: commands used were `rg`, `sed`, `find`, `git status`, `kubectl get`, and read-only `psql SELECT`.
- [x] Do not expose secrets. Evidence: only Secret/ExternalSecret names and remoteRef keys/properties were inspected; no Secret data decoded or printed.
- [x] Do not mutate infra/product systems. Evidence: no `kubectl apply/delete/patch`, no SQL DDL/DML, no product code edits.

### Findings
- [x] F3 gate ordering is allowed. Evidence: `RSO-MASTER-PLAN.md` order is `F0 -> F1 -> (F2 || F5) -> F3 -> F4 -> F6 -> F7`; F5 checklist objective is `[x]` with post-prune baseline `PRODUCT_MATCH=437`.
- [x] Existing crawler Kubernetes resources are not live. Evidence: `kubectl -n skirmshop get deploy,externalsecret,secret skirmshop-competitor-crawler competitor-crawler-secrets` returned no resources; repo `k8s/kustomization.yaml` has namespace `skirmshop` and labels `e-dani.com/activation: disabled`; `k8s/manifest.yaml` has `replicas: 0`, image `...:pending`.
- [x] CNPG shared Postgres exists and is healthy. Evidence: `kubectl get clusters.postgresql.cnpg.io -A` returned `databases/postgres-shared`, `INSTANCES 2`, `READY 2`, `STATUS Cluster in healthy state`, primary `postgres-shared-3`.
- [x] Live Postgres service target exists. Evidence: `kubectl -n databases get svc` shows `postgres-shared-rw` on port `5432`.
- [x] `competitor_intel` DB does not currently exist. Evidence: read-only `psql -U postgres -tAc "SELECT datname FROM pg_database ..."` inside `postgres-shared-3` listed `affiliate`, `app`, `back_in_stock`, `bundles`, `collections_tree`, `document_intake`, `firecrawl`, `labels`, `litellm`, `n8n`, `n8n_stg`, `pocharlies`, `postgres`, `product_ai`, `serial_numbers`, `sii`, `skirmbooks`, `skirmshop`, `synapse`, `teslamate`, `translations`, `whatsappmcp`; no `competitor_intel`.
- [x] No existing F3 table/view found. Evidence: read-only loop over all non-template DBs found no `price_stock_observation` or `estimated_sales_daily` in `information_schema.tables`.
- [x] CNPG Database CR pattern exists. Evidence: `k8s-infra-pocharlies/databases/postgres-shared/app-databases.yaml` defines `kind: Database` resources under cluster `postgres-shared`; current DBs are applied live with `kubectl -n databases get database.postgresql.cnpg.io`.
- [x] Existing app DB credentials pattern exists. Evidence: `k8s-infra-pocharlies/databases/postgres-shared/cluster.yaml` has managed role `skirmshop` using `skirmshop-db-credentials`; `k8s-skirmshopshopifyapp-pocharlies/README.md` and CronJobs use `postgres-shared-rw.databases.svc.cluster.local/skirmshop` with Secret `shared-postgres-app`.
- [x] `shared-postgres-app` secret is available in `skirmshop`. Evidence: `kubectl -n skirmshop get secret shared-postgres-app -o name` returned `secret/shared-postgres-app`; ExternalSecret maps Vault `secret/skirmshop/postgres` properties `app-username` and `app-password`.
- [x] S3 snapshot credential source exists for future raw snapshots. Evidence: `kubectl -n skirmshop get externalsecret skirmshop-drive-s3-app -o yaml` shows target Secret `skirmshop-drive-s3-app` and keys `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET`, `S3_ENDPOINT`, etc.; values were not read.
- [x] Current crawler data path can produce F1/F2 records but strips numeric stock. Evidence: `src/dry_run.py` writes products from adapters; `src/adapters/base.py` normalizes to `stock_status`/`stock_method` and strips raw numeric stock fields including `stock_qty`, `quantity`, `qty`, `units_left`; tests assert stripping.
- [x] Current push path is Brain-only, not historical Postgres. Evidence: `src/push_client.py` posts batches to `/instances/{BRAIN_INSTANCE}/push-ingest`; no Postgres dependency exists in crawler `requirements.txt`.
- [x] Infra repo has unrelated dirty work. Evidence: `git -C /home/dibanez/k8s/k8s-infra-pocharlies status --short --branch` showed `deploy/prod...origin/deploy/prod [behind 4]`, `M platform/keycloak-next/RUNBOOK.md`, and untracked `platform/keycloak-next/oauth2-proxy-tomorrowland.yaml`. F3 must not edit this worktree directly without isolation.

## Architectural Implications

- F3 needs a new persistence target. The approved plan says DB `competitor_intel` in CNPG; live state confirms it is absent.
- Two safe implementation paths remain for Architect/DevOps to choose:
  - Add a CNPG `Database` CR with `spec.name: competitor_intel`, likely under `databases/postgres-shared/app-databases.yaml`, plus migration/init mechanism.
  - Or use an isolated schema inside existing `skirmshop`; this diverges from the approved DB wording and should be justified if chosen.
- A dedicated role/secret would be cleaner least-privilege, but existing pattern often reuses `skirmshop`/`shared-postgres-app`. Architect/Security must decide before any live DDL.
- Because the crawler resources are not live, F3 can implement/test writer locally and prepare GitOps, but live scheduled ingestion is not part of F3 and must not activate F7.

## Blockers / Risks

- [blocked] Claude researcher did not produce a report. Evidence: timeout `124`.
- [blocked] Live apply target for DDL is not yet approved by Architect/DevOps. Evidence: no `competitor_intel` DB exists and infra repo is dirty on `deploy/prod`; use a clean branch/worktree or separate repo plan before applying.
- [blocked] Numeric `stock_qty` is not produced by F2. Evidence: F2 adapter intentionally strips quantity fields. F3 view/tests can prove delta via fixtures or future F4 data, but real sales estimates from live F2-only crawls will be `indeterminate` until F4/cart-probe or another numeric source supplies `stock_qty`.

## Suggested Next Roles

1. `rho-architect`: decide DB vs schema, role/secret strategy, table/view contract including `crawl_success` or equivalent required by the plan's `last_success`.
2. `rho-devops`: propose clean GitOps branch/worktree for CNPG Database/migration without touching dirty `deploy/prod`.
3. `rho-backend`: implement local SQL/writer tests against ephemeral Postgres or SQLite-compatible SQL only if Architect confirms portability; otherwise use Postgres test container.
4. `rho-security`: validate least privilege, snapshot URI handling, no secrets/PII/no cart.
