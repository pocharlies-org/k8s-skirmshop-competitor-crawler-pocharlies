# RSO Audit - Global Competitor Price Comparison

**Status:** HOLD - executor quota exhausted; no product commit, PR, deploy, or OpenClaw policy change.

**Audited:** 2026-07-13 Europe/Madrid

## Intended delivery

- Catalog RAG: `GET /api/competitors/products/search` for an indexed, read-only
  cross-source comparison selected by `market=all|spain|outside_spain` and/or
  opaque source IDs.
- AgentGateway: one normal-plane typed MCP tool,
  `catalog_rag_competitor_price_comparison`.
- History database: only the indexes actually required by the bounded query.

## Evidence retained from the interrupted executor run

| Area | Worktree | Evidence | Result |
| --- | --- | --- | --- |
| Catalog RAG app | `catalog-global-search-app` | Three focused Vitest suites: 61 tests passed. | Partial; uncommitted. |
| AgentGateway | `catalog-global-search-gw` | 40 MCP tests, coverage check, authz matrix, and `git diff --check` passed. | Partial; uncommitted. |
| Synapse index artifact | `synapse-global-search-index` | 22 static migration tests passed. | Rejected by RSO findings below; uncommitted. |
| App typecheck | `catalog-global-search-app` | `npm run typecheck` failed with existing broad repository failures; no error from the new global-search file was reported. | Whole-repo typecheck gate is not green. |

Claude CLI returned `You've hit your weekly limit · resets Jul 15, 4am
(Europe/Madrid)` before commits/PRs. Codex did not replace Claude as a product
implementer.

## Blocking findings

### P1 - Duplicate latest-observation index

The proposed Synapse artifact creates
`price_stock_observation_domain_key_observed_idx` on
`(domain, product_key, observed_at DESC)`. The canonical history migration
already creates the same access path:

`db/migrations/001_f3_history.sql:75`:

```sql
CREATE INDEX IF NOT EXISTS idx_pso_domain_key_observed_at_desc
  ON competitor_intel.price_stock_observation (domain, product_key, observed_at DESC);
```

Creating a duplicate btree wastes disk and adds write amplification to the
append-only crawl history. The index work must move to the owner of the
canonical history schema or explicitly prove a different database/table before
any migration is committed. Keep only a justified new index.

### P1 - Endpoint does not validate source IDs independently

The new app parser de-duplicates and trims `source_id`, but it does not apply
the opaque-ID rule enforced by AgentGateway. Direct callers can therefore pass
a URL/path/traversal-shaped selector and receive an implicit empty selection
instead of HTTP 400. The app endpoint must use the same strict ID validation as
the MCP contract and add route tests for invalid IDs.

### P1 - Literal NUL byte in TypeScript source

`app/services/competitors/global-search.server.ts` uses a literal NUL byte as a
map-key separator. Tools treat the TypeScript file as binary. Replace it with a
safe textual separator or an escaped representation, then rerun lint/typecheck
for the touched files.

### P2 - URL search has no proven supporting index

The app query filters both `price_stock_observation.product_key` and
`crawl_inventory.url` with `ILIKE`. The proposed GIN index only covers
`price_stock_observation.product_key`; its assertion that every URL is embedded
in that key does not make the `crawl_inventory.url` predicate indexed. Before
an index PR, inspect the real inventory schema and query plan. Either remove
the unindexed predicate through a proven normalized key strategy or add the
minimal correct inventory URL index, including partition/locking evidence.

### P2 - Country validation is format-only

The partial app accepts any two capital letters. The gate calls for ISO 3166-1
alpha-2 values, not merely the shape of one. Use an authoritative finite list
or document the accepted registry and test rejection of invalid codes such as
`ZZ`.

## Acceptance gate

- [ ] Remove the duplicate index proposal; establish the real schema owner and
  add only justified, query-backed indexes.
- [ ] App validates every direct `source_id` with the same opaque-ID rule as
  AgentGateway.
- [ ] Remove the literal NUL byte.
- [ ] Verify URL query plan/index or constrain the query to a proven indexed
  representation.
- [ ] Resolve or explicitly baseline the app whole-repo TypeScript failures;
  touched-file typechecking/lint must be green.
- [ ] Executor performs fetch/rebase, commits atomically, pushes, and opens
  draft PRs for app and AgentGateway only after the preceding checks pass.
- [ ] RSO re-runs tests and reviews diffs. No deploy, AgentGateway rollout, or
  OpenClaw prompt change before the two PRs pass review and are merged through
  the required PR workflow.

## Restart handoff for Claude CLI

> Resume the global competitor price-comparison work from the existing cleanly
> separated worktrees. Do not discard uncommitted changes. First repair the
> five findings in `rso/GLOBAL-PRICE-COMPARISON/AUDIT.md`, especially the
> duplicate history index already present in `db/migrations/001_f3_history.sql`.
> The app endpoint must validate opaque source IDs itself, URL search must have
> a real supporting plan/index, and TypeScript source may not contain NUL
> bytes. Re-run focused tests plus touched-file lint/type checks, fetch/rebase,
> then make atomic commits, push, and open draft PRs. Do not deploy or alter
> OpenClaw policy.
