# Architect Report - F0 Bootstrap

## Scope

Architecture/index/fingerprint review for F0. This report is written by Claude CLI after the free-form architect invocation timed out; the evidence below was collected by Codex/PMO with read-only commands and supplied closed-form to avoid further CLI stalls. No code was changed, no commit/push performed, no F1 work started, and no competitor requests were made.

## Evidence

- `skirmshop-brain-v2/scripts/business_sources.py` has `ensure_graph_indexes()` around lines 1055-1084. It creates indexes for `Product.id` and `Product.sku`, plus many other labels, but it does not include `CompetitorProduct` or `CompetitorStore`.
- `skirmshop-brain-v2/src/schema/ontology.py` defines `CompetitorProduct` with `SOLD_BY -> CompetitorStore`; prior researcher evidence also found `PRODUCT_MATCH` as `Product -> CompetitorProduct`.
- `skirmshop-brain-v2/src/api/prices.py` states targeted queries avoid scans because the `OFFERED_BY` / 43k `CompetitorProduct` tables have no index and time out; competitor columns remain null until `PRODUCT_MATCH` edges exist in F5.
- `skirmshop-brain-v2` is currently on `codex/product-recommendations-20260616`, an existing parallel `codex/*` branch.
- Imported crawler `config.yaml` has 14 hardcoded domains grouped as `tier1/tier2/tier3` schedules. These are cadence tiers, not approved SimilarWeb top10 ES/top20 EU and not antibot `green/yellow/red` tiers.
- Imported `src/push_client.py` posts documents to `/instances/{BRAIN_INSTANCE}/push-ingest` with adapter `competitor`; no auth header is present in the code.
- SimilarWeb MCP is not exposed to this Claude CLI invocation; ranking must remain blocked rather than invented.

## Fingerprint Schema Recommendation

F0 `fingerprint.json` should be an array or map keyed by domain, with one record for every target `CompetitorSource` domain:

```json
{
  "domain": "example.com",
  "url": "https://example.com/",
  "platform": "shopify|woocommerce|generic_html|unknown",
  "tier": "green|yellow|red",
  "has_structured_data": true,
  "has_visible_stock": false,
  "robots_crawl_delay": null,
  "antibot": "none|cloudflare|captcha|rate_limit|unknown",
  "evidence": {"method": "http|firecrawl|manual", "status": 200},
  "observed_at": "ISO-8601"
}
```

The `tier` field must be anti-bot/readiness risk (`green/yellow/red`), not the current schedule names in `config.yaml`. `silverback-airsoft.com` must remain `red` if Cloudflare/CAPTCHA evidence is reproduced.

## Required Graph Indexes

F0 needs `ensure_graph_indexes()` (or equivalent startup code) extended to include competitor labels used before F5:

- `CompetitorProduct`: `id`, `domain`, `url`, and any stable `source_id`/`sku`/`brand` property actually written by the extractor.
- `CompetitorStore`: `id`, `domain`.
- `Product`: existing `id`, `sku` already covered.

Do not mark this complete until direct Cypher/index-list evidence or code diff plus test evidence proves the indexes exist.

## Registry Flow

Crawler F0/F1 should stop treating imported `config.yaml` hardcoded stores as authoritative. The approved flow is `CompetitorSource` in `skirmshopshopifyapp` -> `GET /api/competitors` with `x-catalog-token` -> crawler registry/fingerprint input. The hardcoded 14-domain YAML may be used only as legacy discovery evidence, not as the final approved top10/top20 registry.

## Blockers / Risks

- [blocked: SimilarWeb MCP unavailable] Top10 Spain / top20 Europe cannot be derived or validated from traffic evidence in this invocation. Ranking must not be invented.
- [blocked: brain repo on parallel codex branch] `skirmshop-brain-v2` is on `codex/product-recommendations-20260616`; modifying index startup there would mix F0 with another active branch unless PMO creates a coordinated branch/worktree or gets explicit coordination.
- [blocked: fingerprint not generated] Without the approved target list, `fingerprint.json` cannot truthfully cover 100% of target domains.
- Risk: `src/push_client.py` has no auth header for brain push-ingest; security/devops must validate cluster/network/auth before any live run.

## Checklist

- [x] Existing index bootstrap located. Evidence: `business_sources.py` `ensure_graph_indexes()` creates `Product.id` and `Product.sku`.
- [blocked: missing competitor indexes] Evidence: same function does not include `CompetitorProduct` or `CompetitorStore`; `prices.py` documents 43k `CompetitorProduct` scans timing out.
- [x] Fingerprint schema proposed. Evidence: schema above maps required F0 fields from the plan.
- [blocked: SimilarWeb unavailable] Evidence: researcher/security lane found no MCP exposed to Claude CLI; no ranking generated.
- [blocked: brain branch coordination] Evidence: `git status` showed `skirmshop-brain-v2` on `codex/product-recommendations-20260616`.
- [x] No F1/product code changes by architect. Evidence: this report only.

No global F0 PASS asserted.
