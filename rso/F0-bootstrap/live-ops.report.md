# Live Ops Report - F0 Bootstrap

## Scope

PMO operational exception for the final F0 live gates. Claude CLI hit a session
limit (`resets 2:40pm Europe/Madrid`), so Codex executed only idempotent internal
registry/index operations. No product code was edited, no deploy/prod branch was
touched, no competitor cart/checkout/login/write requests were made.

## CompetitorSource

- Pre-check: live `rag-app` Prisma count showed `total_competitor_sources 14`
  and `target_count 4` for the 30-domain target list.
- Apply: piped
  `skirmshopshopifyapp/prisma/migrations/20260624140000_competitor_source_airsoft_autopilot_targets/migration.sql`
  into `kubectl -n skirmshop exec -i deploy/rag-app -- npx prisma db execute --stdin --schema prisma/schema.prisma`.
- Apply output: `Script executed successfully.`
- Post-check Prisma: `total_competitor_sources 40`, `target_count 30`.
- Post-check API: `GET http://127.0.0.1:3000/api/competitors` from inside
  `rag-app` with `x-catalog-token` returned `api_ok true`, `domain_count 40`,
  `target_count_in_api 30`, and samples `airsoftpro.es,taiwangun.com,silverback-airsoft.com`.

## FalkorDB Indexes

- Pre-check: live `skirmshop-brain-prod` had `Product ['id', 'sku'] OPERATIONAL`
  but no `CompetitorProduct` or `CompetitorStore` indexes.
- Apply: executed `create_node_range_index` inside `deploy/skirmshop-brain` for
  `CompetitorProduct.id/domain/url/source_id/sku/brand` and
  `CompetitorStore.id/domain`; existing `Product.id/sku` skipped as already present.
- Apply output:
  - `created ['CompetitorProduct.id', 'CompetitorProduct.domain', 'CompetitorProduct.url', 'CompetitorProduct.source_id', 'CompetitorProduct.sku', 'CompetitorProduct.brand', 'CompetitorStore.id', 'CompetitorStore.domain']`
  - `skipped_existing ['Product.id', 'Product.sku']`
  - `errors []`
- Post-check `CALL db.indexes()`:
  - `CompetitorProduct ['brand', 'domain', 'id', 'sku', 'source_id', 'url'] OPERATIONAL`
  - `CompetitorStore ['domain', 'id'] OPERATIONAL`
  - `Product ['id', 'sku'] OPERATIONAL`
  - `missing {}`, `bad_status {}`

## Residual Risks

- SimilarWeb MCP was unavailable; the target list is accepted for F0 under the
  user's explicit autopilot/no-stop directive, with public Similarweb URLs and
  legacy seed provenance in `target-domains.autopilot.json`.
- The Brain startup hook that recreates these indexes lives in branch
  `codex/product-recommendations-20260616` commit `f53b552`; live indexes now
  persist in FalkorDB even before that branch is deployed.
