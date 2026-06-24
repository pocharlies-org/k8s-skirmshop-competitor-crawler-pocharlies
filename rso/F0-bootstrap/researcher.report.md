# Researcher Report - F0 Bootstrap

## Scope
Read-only evidence gathering for the competitor-crawler F0 bootstrap. Inspected
three repos plus the deploy host:
- `k8s-skirmshop-competitor-crawler-pocharlies` (this GitOps repo — deploy/manifests).
- The crawler application source on host `sauvage`
  (`/home/ubuntu/skirmshop/skirmshop-competitor-crawler`).
- `skirmshopshopifyapp` — the `CompetitorSource` allowlist / `GET /api/competitors` API.
- `skirmshop-brain-v2` — the graph sink (`CompetitorProduct`/`CompetitorStore`,
  `PRODUCT_MATCH`/`SOLD_BY`/`OFFERED_BY`, prices API, graph indexes).

Goal: map what already exists across the data path
(Shopify allowlist -> crawler -> brain graph) so the implementer lane has a
factual surface to work from. No code written, no business logic changed.

## Commands Run
1. `git -C .../k8s-skirmshop-competitor-crawler-pocharlies status --short --branch && git ... remote -v`
2. `find .../k8s-skirmshop-competitor-crawler-pocharlies -maxdepth 2 -type f | sort`
3. `ssh -o BatchMode=yes -o ConnectTimeout=8 sauvage 'test -d /home/ubuntu/skirmshop/skirmshop-competitor-crawler && find ... -maxdepth 2 -type f | sort | head -80'`
4. `rg -n 'model CompetitorSource|GET /api/competitors|listEnabledDomains|createCompetitorSource|CompetitorSource' .../skirmshopshopifyapp/{prisma,app/routes,app/services/competitors} | head -80`
5. `rg -n 'def ensure_graph_indexes|create_node_range_index|CompetitorProduct|PRODUCT_MATCH|Product\.sku|Product\.id' .../skirmshop-brain-v2/{scripts/business_sources.py,src/schema/ontology.py,src/api/prices.py} | head -120`
6. `git -C .../skirmshop-brain-v2 status --short --branch && git -C .../skirmshopshopifyapp status --short --branch`

All commands above are read-only. **No cart requests and no write/POST requests
were performed.** SimilarWeb was not called (see Risks/Blockers).

## Evidence

### 1. This GitOps repo (deploy-only, no app source)
- Branch / remote (cmd 1):
  - `## codex/competitor-crawler-F0-bootstrap...origin/codex/competitor-crawler-F0-bootstrap`
  - `?? rso/F0-bootstrap/researcher.report.md` (this report, untracked).
  - remote `origin git@github.com:pocharlies-org/k8s-skirmshop-competitor-crawler-pocharlies.git` (fetch+push).
- Tracked files (cmd 2): only docs + manifests, **no application source**:
  - `README.md`, `RSO-MASTER-PLAN.md`
  - `k8s/externalsecret.yaml`, `k8s/kustomization.yaml`, `k8s/manifest.yaml`
  - (the rest under `.git/`)
  - Confirms prior brain note: the crawler code does **not** live in this clone;
    this repo is the GitOps/deploy wrapper only.

### 2. Crawler application source — on host `sauvage` (cmd 3)
`/home/ubuntu/skirmshop/skirmshop-competitor-crawler` exists and is a real Python
service with tests:
- Runtime: `Dockerfile`, `docker-compose.yml`, `config.yaml`, `requirements.txt`.
- `src/`: `crawler.py`, `extractor.py`, `fetcher.py`, `main.py`,
  `promotion_tracker.py`, `push_client.py`, `scheduler.py`, `__init__.py`.
- `tests/`: `test_extractor.py`, `test_promotion_tracker.py`.
- `.pytest_cache/` present (tests have been run on host).
- This is the canonical source-of-truth for the crawler logic; the F0 implementer
  must reconcile this host copy with whatever the GitOps repo expects to build.

### 3. Shopify app — allowlist + read API already implemented (cmd 4)
In `skirmshopshopifyapp`:
- Prisma model `CompetitorSource` at `prisma/schema.prisma:195`.
- Migration `prisma/migrations/20260621130000_add_competitor_source/migration.sql`:
  creates table, unique index on `domain` (`CompetitorSource_domain_key`),
  index on `enabled` (`CompetitorSource_enabled_idx`), and seeds rows via INSERT.
- Service `app/services/competitors/registry.server.ts`: `CompetitorSourceInput`,
  `listCompetitorSources`, `listEnabledDomains` (line 61), `createCompetitorSource`,
  `setCompetitorSourceEnabled`, `updateCompetitorSource`, `deleteCompetitorSource`.
  Header comment: consumed by the synapse over the shared-token API
  (`GET /api/competitors`, `x-catalog-token`).
- Route `app/routes/api.competitors.ts`: server-to-server read endpoint,
  returns `await listEnabledDomains()` (line 21).
- Admin UI `app/routes/app.competitors._index.tsx`: create/enable/delete actions.
- => The "source of truth" allowlist + read endpoint the crawler should consume
  **already exists**; F0 should integrate against it, not re-create it.

### 4. Brain graph sink — schema present, edges empty (cmd 5)
In `skirmshop-brain-v2`:
- `src/schema/ontology.py`: node labels include `CompetitorProduct` (line 28, 67)
  and `CompetitorStore`; edge types include `PRODUCT_MATCH` (Product ->
  CompetitorProduct, line 89), `SOLD_BY` (CompetitorProduct -> CompetitorStore,
  line 90), plus `OFFERED_BY`/`SOURCED_FROM` (lines 130, 158, 182).
- `scripts/business_sources.py:1055` `def ensure_graph_indexes()` ->
  `graph.create_node_range_index(label, prop)` at line 1084 (index bootstrap exists).
- `src/api/prices.py` header (lines 15-16): `OFFERED_BY` / "43k `CompetitorProduct`
  tables (which have no index and time out). Competitor columns stay null until
  `PRODUCT_MATCH` edges exist (today 0)." And line 196: "competitor columns: null
  until PRODUCT_MATCH edges are built (F5)."
- => Graph schema for competitor data is defined, but **PRODUCT_MATCH edges = 0
  today** and the 43k `CompetitorProduct` nodes are **un-indexed and time out** in
  the prices API. Matching/indexing is explicitly deferred to a later phase (F5).

### 5. Git state of sink repos (cmd 6)
- `skirmshop-brain-v2`: `## codex/product-recommendations-20260616...origin/...`
  (clean working tree on a feature branch — another session's branch; do not force).
- `skirmshopshopifyapp`: `## main...origin/main` with uncommitted local changes:
  - ` M app/services/shopify/products.ts`
  - `?? app/lib/shopify-admin-url.ts`
  - `?? app/services/pricing/`
  - `?? test/services/pricing/`
  - => Working tree is dirty on `main`; an in-flight pricing change exists. F0 work
    must not assume a clean tree here and must coordinate before committing.

## Proposed Implementer Scope
(Recommendations for the implementer lane — NOT executed here.)
- **Architect**: define the F0 data contract end-to-end:
  crawler consumes `GET /api/competitors` (`x-catalog-token`) -> pushes via
  `src/push_client.py` -> brain `CompetitorProduct`/`CompetitorStore` +
  `SOLD_BY`/`OFFERED_BY`. Decide where the crawler source lives canonically
  (host `sauvage` copy vs. GitOps repo) and the build/image flow.
- **Backend (crawler)**: reconcile the `sauvage` source into the buildable repo;
  confirm `push_client.py` target schema matches brain ontology node/edge names.
- **Backend (brain)**: ensure `ensure_graph_indexes()` covers `CompetitorProduct`
  (the un-indexed 43k that times out in `prices.py`). `PRODUCT_MATCH` matching is
  out of F0 scope (explicitly F5).
- **DevOps**: validate `k8s/manifest.yaml` + `externalsecret.yaml` +
  `kustomization.yaml` against the `x-catalog-token` secret and the brain push
  endpoint; wire ArgoCD as per `RSO-MASTER-PLAN.md`.
- **Security**: the path uses a shared `x-catalog-token` header — verify the secret
  is sourced via ExternalSecret (not hardcoded) and the `/api/competitors` endpoint
  enforces the token.

## Risks / Blockers
- `[blocked: SimilarWeb MCP no expuesto a esta invocación Claude CLI]` — competitor
  ranking/traffic data could not be queried. **Ranking must NOT be invented**; any
  ranking-dependent prioritization is unverified and out of scope until SimilarWeb
  is available.
- Crawler application source is **not in this GitOps clone** — it lives on host
  `sauvage`. Build/deploy reconciliation is required and is a drift risk.
- `skirmshopshopifyapp` has an **uncommitted dirty tree on `main`** (pricing WIP) —
  parallel session; do not clobber, coordinate before any commit there.
- `skirmshop-brain-v2` is on another session's feature branch
  (`codex/product-recommendations-20260616`) — do not force/rebase onto it.
- `PRODUCT_MATCH` edges = 0 and 43k `CompetitorProduct` nodes are un-indexed and
  time out in `prices.py`. Competitor price columns will stay null until F5;
  this is expected, not a regression to fix in F0.
- Evidence is limited to the exact 6 read-only commands; file bodies (README,
  manifests, push_client) were **not** opened — marked as assumptions where used.

## Checklist

### Directives
- [x] Only the 6 specified read-only commands + this report write were run —
  Evidence: command log above; no other exploratory commands issued.
- [x] No cart requests and no write/POST requests performed —
  Evidence: all 6 commands are `git status`/`find`/`ssh find`/`rg`; report written
  via `cat` heredoc only.
- [x] SimilarWeb not called; ranking not invented —
  Evidence: marked `[blocked: SimilarWeb MCP no expuesto a esta invocación Claude CLI]`.
- [x] No commit, no push, no edits outside the report —
  Evidence: only `rso/F0-bootstrap/researcher.report.md` written (untracked per cmd 1).

### Acceptance criteria
- [x] GitOps repo branch/remote captured —
  Evidence: cmd 1 `codex/competitor-crawler-F0-bootstrap`, `pocharlies-org` remote.
- [x] GitOps repo confirmed deploy-only (no app source) —
  Evidence: cmd 2 lists only README/RSO-MASTER-PLAN + `k8s/*.yaml`.
- [x] Crawler source located on `sauvage` —
  Evidence: cmd 3 lists `src/crawler.py`, `push_client.py`, `scheduler.py`, tests, Dockerfile.
- [x] Shopify `CompetitorSource` model + `GET /api/competitors` API confirmed —
  Evidence: cmd 4 `schema.prisma:195`, migration `20260621130000`, `api.competitors.ts`,
  `registry.server.ts` (`listEnabledDomains`).
- [x] Brain competitor schema + index bootstrap + empty PRODUCT_MATCH confirmed —
  Evidence: cmd 5 `ontology.py` labels/edges, `business_sources.py:1055/1084`,
  `prices.py:15-16,196` ("today 0", "no index and time out", "F5").
- [x] Git state of both sink repos captured (dirty/branch risks) —
  Evidence: cmd 6 brain-v2 on `codex/product-recommendations-20260616`, shopifyapp
  dirty on `main`.

### Specialist checks
- [x] Researcher — scope/evidence/blockers delivered above; read-only.
- [blocked] SimilarWeb ranking verification — Blocker: SimilarWeb MCP not exposed to
  this Claude CLI invocation; ranking left unverified, not invented.
- [ ] Architect / Backend / DevOps / Security implementers — out of researcher scope;
  proposed scope handed off above for the implementer lane.
