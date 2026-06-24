# F5 Product Match — Researcher Report

**Role:** rho-researcher (read-only)
**Date:** 2026-06-24
**Branch RSO:** `codex/competitor-crawler-F5-product-match`
**Brain-v2 branch:** `codex/product-recommendations-20260616`
**Shopifyapp branch:** `codex/competitor-crawler-F0-bootstrap`

---

## RHO Checklist

### Directives
- [x] Read-only; no code edits, no commits, no writes to Brain/DB/API.
- [x] No scope creep into F3/F4/F6/F7.
- [x] Evidence = file path + line number or command output for every `[x]`.

### Acceptance Criteria

- [x] **Topology research complete.** All repos/services identified. Evidence: sections below.
- [x] **PRODUCT_MATCH edge schema documented.** Direction, existing properties (none), indices. Evidence: `ontology.py:89`, `falkordb.py:35-56`.
- [x] **Shopify barcode/SKU source located.** `Variant.barcode` from Shopify payload. Evidence: `shopify.py:116`. Population unknown from code alone — marked below.
- [x] **CompetitorProduct fields listed.** title, brand, price, url, domain, is_promotion, sku (index only), source_id. Evidence: `competitor.py:22-33`, `falkordb.py:54`.
- [x] **MatchReview existence checked.** Does NOT exist anywhere. Evidence: `rg MatchReview` returns 0 matches in both repos.
- [x] **Consumer APIs documented.** `prices.py` and `intel.py` inspected; competitor columns hardcoded null/0. Evidence: `prices.py:196-200`, `intel.py:56-89`.
- [x] **Embedding/reranker infra documented.** TEI BGE-M3 + reranker available. Evidence: `src/embeddings/tei.py:1,117-119`.
- [x] **Write target risk assessed.** Only target visible is prod FalkorDB. Marked [blocked] in write-target criterion.
- [blocked] **Safe write target available.** The only FalkorDB instance reachable from code is the production graph. No test/staging graph config found. Any `PRODUCT_MATCH` edge write requires RSO approval and dry-run first.

---

## Repos / Branches Inspected

| Repo | Branch | Status |
|------|--------|--------|
| `k8s-skirmshop-competitor-crawler-pocharlies` | `codex/competitor-crawler-F5-product-match` | current |
| `skirmshop-brain-v2` | `codex/product-recommendations-20260616` | read-only, not changed |
| `skirmshopshopifyapp` | `codex/competitor-crawler-F0-bootstrap` | read-only, not changed |

---

## 1. PRODUCT_MATCH Edge — Current Schema

**Direction (ontology.py:89, SCHEMA:158-159):**
```
Product ──[PRODUCT_MATCH]──> CompetitorProduct
```

**Current properties on edge:** NONE. The relation type is registered in `RelationType` and `RELATION_TYPES` and in the `SCHEMA` dict, but **no properties** (`match_confidence`, `match_method`, timestamps) are defined anywhere today.

**No existing `PRODUCT_MATCH` edges in prod** — confirmed by `prices.py:17`:
> "Competitor columns stay null until `PRODUCT_MATCH` edges exist (today 0)."

**FalkorDB indices for nodes (falkordb.py:35-56):**
| Label | Indexed properties |
|-------|-------------------|
| `Product` | `id`, `sku` |
| `Variant` | `id`, `sku` |
| `CompetitorProduct` | `id`, `domain`, `url`, `source_id`, `sku`, `brand` |

**No index on `Variant.barcode`** — must be added for EAN/GTIN signal if used.
**No index on `CompetitorProduct.ean` or `CompetitorProduct.gtin`** — these fields do not exist in current schema.

---

## 2. Shopify Barcode / SKU — Source and Population

### Product node (shopify.py:62-73)
Properties stored: `title`, `sku`, `price`, `vendor`, `product_type`, `status`, `shopify_id`, `url`, `image_url`, `tags`.
**Barcode is NOT on the Product node.** Only `sku` (handle-level, first variant or product-level SKU from payload).

### Variant node (shopify.py:111-118, line 116)
```python
append_entity(node, make_entity("Variant", variant_key, {
    "title": variant.get("title"),
    "sku": variant.get("sku"),
    "price": _to_float(variant.get("price")),
    "inventory_quantity": variant.get("inventory_quantity"),
    "barcode": variant.get("barcode"),   # ← EAN/GTIN lives here
}))
```
**`barcode` is passed through if present in the Shopify payload.** Whether it is actually populated in production data depends on what the Shopify sync pushes — **cannot be confirmed from code alone** (would require a live read-only Cypher query against FalkorDB or inspection of the push payload in the shopifyapp).

**ASSUMPTION (not confirmed):** Barcode population rate in `Variant` nodes is unknown. Could be sparse (many airsoft products lack EAN). The matcher must treat barcode match as opportunistic (high precision when available, low recall).

### CompetitorProduct fields (competitor.py:22-33, falkordb.py:54)
Fields written by `CompetitorExtractor`:
- `title`, `brand`, `price`, `url`, `domain`, `is_promotion`

Fields indexed (falkordb.py:54): `id`, `domain`, `url`, `source_id`, `sku`, `brand`

**`sku` is indexed on CompetitorProduct** (likely populated when crawlers push `sku` metadata). **No `barcode`/`ean`/`gtin` field exists** on `CompetitorProduct` today — neither in extractor nor in indices.

**Consequence for cascade:** EAN/GTIN signal requires:
1. `Variant.barcode` non-null on our side, AND
2. A corresponding `ean`/`barcode` field on `CompetitorProduct` — **does not exist yet**.

So the EAN/GTIN step is **not yet implementable without a schema extension** to `CompetitorProduct` (adding `barcode`/`ean` field and index, populated by the crawler in F1/F2 via the push payload).

---

## 3. Consumer APIs — Current State

### `prices.py` (`/prices/comparison`)
- Returns `competitor_min: None`, `competitor_max: None`, `competitor_count: 0` hardcoded (prices.py:196-200).
- The Cypher in `_BODY` does NOT expand `PRODUCT_MATCH` at all today.
- When `PRODUCT_MATCH` edges exist, this function needs a new `OPTIONAL MATCH` to aggregate competitor prices — the architect must add this.

### `intel.py` (`/intel/gaps`)
- Uses `SAME_AS` relation (`Product -[:SAME_AS]- CompetitorProduct`) at intel.py:74-79.
- **`SAME_AS` is NOT the F5 canonical edge.** `PRODUCT_MATCH` is the canonical one (ontology.py:89, SCHEMA:158). `SAME_AS` in ontology is defined as `Customer -> Person` only (ontology.py:104). The `intel/gaps` endpoint appears to be a v1 artefact using the wrong relation type for the competitor→product link.
- `intel/price-wars` and `intel/stock-alerts` return `{items: []}` with a warning log.
- **Risk:** If F5 builds `PRODUCT_MATCH` edges but `intel/gaps` still queries `SAME_AS`, the gaps endpoint will remain broken even after F5. This is a pre-existing inconsistency to flag to architect.

---

## 4. MatchReview — Does Not Exist

`rg MatchReview` across both repos returns zero hits (confirmed by running the command). **MatchReview is not in:**
- `skirmshopshopifyapp/prisma/schema.prisma` (inspected fully)
- Any brain-v2 source file

**Implication:** The "dubious → MatchReview" flow has no backing store today. Options for the architect:
1. Add `MatchReview` model to `schema.prisma` (Postgres, in `skirmshopshopifyapp`) — requires Prisma migration (needs RSO approval before any write to prod DB).
2. Use a local artifact/JSONL file in `rso/F5-product-match/` for the review queue in the dry-run phase (safe, no prod writes).
3. Store dubious matches as a separate node/property in FalkorDB (e.g. a `MatchReview` node or a `PRODUCT_MATCH_CANDIDATE` edge with `status=review`).

**Recommended for F5:** Use a file artifact (`match-candidates.json`) during dry-run; architect decides on durable store before apply phase.

---

## 5. Normalization Infrastructure Available

`shopify_order_lines.py:166-170` already implements NFKD+ASCII+lowercase+punctuation-fold normalization:
```python
def title_match_key(value: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", title)
    ascii_title = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", ascii_title.lower()).strip()
```
This is reusable as-is for brand+model normalization in the F5 cascade. **Zero code duplication needed.**

---

## 6. Embedding / Reranker Infrastructure

`src/embeddings/tei.py:1,117-119`: TEI BGE-M3 dense embeddings + reranker are available via HTTP to configured URLs (`tei_dense_url`, `tei_reranker_url`). Circuit breaker is wired. The infra exists for the embedding fallback step of the cascade.

**Caveat:** TEI URLs are env-config, not hardcoded. Dry-run tests without a live brain instance will need mocking or stub embedding.

---

## 7. Proposed PRODUCT_MATCH Edge Contract

For rho-architect to validate and finalize:

```
(Product)-[:PRODUCT_MATCH {
  match_confidence: Float,     # 0.0 – 1.0
  match_method:     String,    # enum: ean_gtin | sku | brand_model | embedding_rerank
  matched_at:       String,    # ISO-8601 UTC
  matcher_version:  String,    # semver or git sha
  source:           String     # "f5-batch" | "manual"
}]->(CompetitorProduct)
```

**Cascade with thresholds (proposed — architect to ratify):**

| Signal | Condition | Decision |
|--------|-----------|----------|
| `ean_gtin` | `Variant.barcode == CompetitorProduct.ean` (exact, non-null) | `auto_link` (confidence 1.0) |
| `sku` | `Product.sku == CompetitorProduct.sku` (exact, non-null, normalized) | `auto_link` (confidence 0.95) |
| `brand_model` | `title_match_key(brand+title)` cosine or exact match | ≥ 0.90 → `auto_link`; 0.70–0.90 → `review`; < 0.70 → `reject` |
| `embedding_rerank` | TEI BGE-M3 + reranker score | ≥ 0.85 → `auto_link`; 0.65–0.85 → `review`; < 0.65 → `reject` |

**Idempotency key:** `(Product.id, CompetitorProduct.id)` — MERGE on these two node IDs, SET properties on match.

---

## 8. Write Target Risk

| Target | Type | Available | Risk |
|--------|------|-----------|------|
| FalkorDB prod graph | Graph edges `PRODUCT_MATCH` | ✓ (only option) | **HIGH — prod only** |
| `rso/F5-product-match/*.json` | File artifacts | ✓ | Safe, no prod risk |
| Prisma `MatchReview` table | Postgres (skirmshopshopifyapp DB) | ✗ model doesn't exist | Needs migration → **BLOCKED until schema approved** |

**Write to FalkorDB prod graph must be [blocked] until:**
1. Dry-run artifact reviewed and confirmed.
2. RSO explicit approval.
3. Before/after Cypher counts established.
4. Re-run idempotency demonstrated in dry-run.

---

## 9. Recommended Implementation Plan by Role

| Phase | Role | Scope |
|-------|------|-------|
| **Now** | rho-architect | Finalize edge contract, thresholds, decide MatchReview store (file vs Prisma), flag `intel/gaps` SAME_AS inconsistency, add `CompetitorProduct.barcode` field spec (for later F1 crawler), propose `Variant.barcode` index. |
| **After architect** | rho-backend | Implement dry-run matcher in `skirmshop-brain-v2/src/matchers/product_match.py` (new file): cascaded signals using existing `title_match_key`, TEI stub for offline, emit JSON artifact. Unit tests: normalization, thresholds, no-link on dubious, idempotency. |
| **After dry-run artifact** | rho-backend | Apply step: Cypher MERGE with before/after count; only after RSO approval. |
| **After apply** | rho-backend | Extend `prices.py` `_BODY` Cypher to expand `PRODUCT_MATCH` and populate `competitor_min/max/count`. |
| **Parallel** | rho-security | Confirm no secrets in logs/artifacts; PII scrub; target audit. |
| **After all** | rho-verifier | Re-execute commands, confusion matrix, count before/after, no scope creep. |

---

## 10. Residual Risks and Open Questions

| # | Risk / Question | Severity | Owner |
|---|----------------|----------|-------|
| 1 | `Variant.barcode` population rate in prod FalkorDB is unknown. If sparse, EAN signal is low-recall. | Medium | rho-architect to decide if worth querying live count (read-only Cypher) |
| 2 | `CompetitorProduct` has no `ean`/`barcode` field today. EAN cascade step needs crawler F1 to push it first. | High | Architect must decide: add to crawler push payload + CompetitorExtractor, or skip EAN step for F5. |
| 3 | `intel/gaps` uses `SAME_AS` (wrong relation for competitor matching). Pre-existing bug. | Low-Medium | Architect to flag, fix in F6 scope or as F5 side-fix. |
| 4 | Only prod FalkorDB is available as write target. | High | **[BLOCKED]** until RSO approval + dry-run confirmed. |
| 5 | `MatchReview` model absent. Durable review queue undefined. | Medium | Architect decides store (file artifact safe for F5 dry-run; Prisma model for production). |
| 6 | TEI embedding URLs are env-config; unit tests need mock/stub for offline CI. | Low | rho-backend must mock TEI in tests. |
| 7 | Duplicate `Product` nodes in FalkorDB (noted in prices.py:54–60). Matcher must deduplicate by `Product.id`, not node identity. | Medium | rho-architect to specify Cypher MERGE strategy. |
| 8 | No existing `PRODUCT_MATCH` tests anywhere in brain-v2. Full test suite needed from scratch. | Medium | rho-backend |

---

## Files Inspected

| File | Evidence used |
|------|--------------|
| `RSO-MASTER-PLAN.md` | F5 objective, architecture, gates |
| `rso/F5-product-match/CHECKLIST.md` | Acceptance criteria |
| `rso/F5-product-match/HANDOFF.md` | Scope and prohibitions |
| `rso/F2-visible-stock/codex-audit.report.md` | F2 PASS context |
| `skirmshop-brain-v2/src/schema/ontology.py` | PRODUCT_MATCH direction, properties, SCHEMA |
| `skirmshop-brain-v2/src/api/prices.py` | Consumer: competitor columns null, no Cypher expansion |
| `skirmshop-brain-v2/src/api/intel.py` | Consumer: SAME_AS artefact, gaps endpoint |
| `skirmshop-brain-v2/src/extractors/competitor.py` | CompetitorProduct fields (no barcode/ean) |
| `skirmshop-brain-v2/src/extractors/shopify.py` | Product + Variant fields, barcode at Variant:116 |
| `skirmshop-brain-v2/src/services/shopify_order_lines.py` | title_match_key NFKD normalization |
| `skirmshop-brain-v2/src/stores/falkordb.py` | GRAPH_INDEXES, ensure_graph_indexes |
| `skirmshop-brain-v2/src/embeddings/tei.py` | TEI BGE-M3 + reranker infra |
| `skirmshopshopifyapp/prisma/schema.prisma` | MatchReview absent, CompetitorSource exists |

## Commands Run (read-only)

```bash
git -C skirmshop-brain-v2 branch --show-current          # codex/product-recommendations-20260616
git -C skirmshopshopifyapp branch --show-current          # codex/competitor-crawler-F0-bootstrap
git -C k8s-...-pocharlies branch --show-current           # codex/competitor-crawler-F5-product-match
rg -n "barcode" src/extractors/shopify.py                 # line 116 Variant.barcode
rg -n "PRODUCT_MATCH|MatchReview" src -l                  # ontology.py, prices.py only; MatchReview: 0 hits
rg -n "barcode|sku" src/extractors/competitor.py          # 0 hits
rg -n "CREATE INDEX|index" src/stores/falkordb.py         # GRAPH_INDEXES:35-56
```

---

## Status

- [x] rho-researcher — topology, schema, sources, MatchReview, consumer APIs, write-target risk, proposed contract documented.
- [ ] rho-architect — pending.
- [ ] rho-backend — pending.
- [ ] rho-security — pending.
- [ ] rho-verifier — pending.
- [ ] Codex/RSO auditor — pending.
