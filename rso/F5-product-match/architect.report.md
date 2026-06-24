# F5 Product Match — Architect Report

**Role:** rho-architect
**Date:** 2026-06-24
**Branch RSO:** `codex/competitor-crawler-F5-product-match`
**Input:** `researcher.report.md` (rho-researcher PASS), `ontology.py`, `falkordb.py`, `prices.py`, `intel.py`, `shopify.py`, `competitor.py`, `shopify_order_lines.py`, `tei.py`, `schema.prisma`

---

## RHO Checklist

### Directives
- [x] Read-only; no code edits to product repos, no commits, no writes to Brain/DB/API.
- [x] No scope creep into F3/F4/F6/F7.
- [x] Resolve the EAN/GTIN contradiction explicitly (decision + rationale).
- [x] Define edge direction and properties.
- [x] Define thresholds auto_link/review/reject and precision gate.
- [x] Define MatchReview strategy (artifact vs schema vs FalkorDB candidate).
- [x] Define apply guard (dry-run → RSO → MERGE idempotent).
- [x] Separate F5 scope from F6 scope explicitly.
- [x] No mark [x] without direct evidence.

### Acceptance Criteria — Architect scope

- [x] **EAN/GTIN contradiction resolved.** Decision documented with rationale and partial-blocker defined. Evidence: section 1 below.
- [x] **PRODUCT_MATCH edge contract finalized.** Direction, idempotency key, all properties (types, enums, nullability), and index additions specified. Evidence: section 2 below.
- [x] **Matching cascade with thresholds finalized.** Each signal, condition, confidence value, and auto_link/review/reject decision specified, including the EAN partial-blocker path. Evidence: section 3 below.
- [x] **MatchReview strategy for F5 decided.** Durable store, artifact format, and no-create-edge-for-dubious rule specified. Evidence: section 4 below.
- [x] **Apply guard specified.** Dry-run output contract, RSO gate, before/after Cypher count, MERGE idempotency cypher pattern, and rollback path. Evidence: section 5 below.
- [x] **F5 vs F6 consumer boundary explicit.** Which files F5 touches (new matcher only) and which F6 owns (prices.py/intel.py Cypher extension). Evidence: section 6 below.
- [x] **Pre-existing intel/gaps SAME_AS bug flagged.** Scope assignment (F6) documented. Evidence: section 6.2 below.
- [x] **Residual risks listed.** Evidence: section 7.

---

## 1. EAN/GTIN Contradiction — Decision

**Contradiction:** `Variant.barcode` (brain-v2 `shopify.py:116`) stores the EAN/GTIN from Shopify on our side. `CompetitorProduct` has **no `ean`, `barcode`, or `gtin` field** anywhere — not in `competitor.py:22-33`, not in `falkordb.py:54` indices, not in the ontology. The crawler (F1/F2) currently does not push any EAN field from competitor site payloads.

**Decision: F5 OMITS the EAN/GTIN signal with an explicit partial blocker.**

Rationale:
- The EAN cascade step requires both sides of the signal to be populated. Our side (`Variant.barcode`) is available but with unknown population rate. The competitor side has no field to match against at all.
- Extending `CompetitorProduct` with `ean`/`barcode` requires: (a) crawler adapter changes to extract EAN from product pages/JSON-LD, (b) `CompetitorExtractor.py` changes, (c) a new FalkorDB index. These are all F1/F2 scope changes, not F5.
- Adding them in F5 would be scope creep and would require a non-trivial crawler re-run against live sites before F5 can even be tested.
- The remaining signals (SKU exact, brand+model normalized, embedding/reranker) provide a complete fallback cascade adequate for F5 precision targets.

**Partial blocker registered:**

```
[BLOCKED-EAN] EAN/GTIN cascade step cannot be implemented until:
  1. CompetitorProduct gains an `ean` (or `barcode`) field (CompetitorExtractor + GRAPH_INDEXES).
  2. At least one crawler adapter extracts EAN/GTIN from product pages/JSON-LD.
  3. A re-crawl populates the field for ≥1 domain.
  4. Variant.barcode population rate in prod FalkorDB confirmed via read-only Cypher.
Owner: F1 (crawler adapter) re-scope, confirmed by RSO before unblocking EAN in F5-v2 or F6.
```

**Consequence for F5:** The cascade starts at SKU and degrades gracefully. EAN becomes an additive signal in F5-v2 or a natural upgrade in F6. Precision is not sacrificed — SKU+brand_model+embedding provides ≥3 discriminating signals.

---

## 2. PRODUCT_MATCH Edge Contract

### 2.1 Direction (confirmed)

```
(p:Product)-[r:PRODUCT_MATCH]->(cp:CompetitorProduct)
```

Confirmed in `ontology.py:89` and `SCHEMA:158`. Direction is canonical and is not changed.

### 2.2 Properties

| Property | Type | Required | Notes |
|---|---|---|---|
| `match_confidence` | `Float` | ✓ | 0.0 – 1.0 |
| `match_method` | `String` | ✓ | Enum (see 2.3) |
| `matched_at` | `String` | ✓ | ISO-8601 UTC, e.g. `2026-06-24T14:00:00Z` |
| `matcher_version` | `String` | ✓ | Semver `MAJOR.MINOR.PATCH`, e.g. `1.0.0` |
| `source` | `String` | ✓ | Enum: `f5-batch` \| `manual` |
| `status` | `String` | ✓ | Enum: `active` \| `superseded` \| `rejected` |

**Nullability rule:** All properties are required on CREATE/MERGE. The matcher MUST NOT create the edge without all 6 properties set. If any property cannot be determined (e.g. confidence undefined), the candidate must go to MatchReview instead.

### 2.3 `match_method` Enum

```
ean_gtin         — EAN/GTIN exact match (BLOCKED in F5, reserved for F5-v2/F6)
sku              — SKU exact match (normalized)
brand_model      — NFKD-normalized brand+title text match (exact or high-confidence fuzzy)
embedding_rerank — TEI BGE-M3 dense embedding + reranker score
```

### 2.4 Idempotency Key

```cypher
MERGE (p:Product {id: $product_id})-[r:PRODUCT_MATCH]->(cp:CompetitorProduct {id: $competitor_product_id})
ON CREATE SET r.matched_at    = $matched_at,
              r.match_method  = $match_method,
              r.match_confidence = $match_confidence,
              r.matcher_version  = $matcher_version,
              r.source           = $source,
              r.status           = 'active'
ON MATCH SET  r.match_confidence = $match_confidence,
              r.match_method     = $match_method,
              r.matched_at       = $matched_at,
              r.matcher_version  = $matcher_version
-- status is NOT overwritten on MATCH to preserve manual overrides
```

**Idempotency guarantee:** Re-running the matcher for the same `(Product.id, CompetitorProduct.id)` pair updates properties but does NOT create a duplicate edge. FalkorDB MERGE on node+edge pattern is idempotent.

### 2.5 Required Index Additions

The following indices must be added to `falkordb.py` `GRAPH_INDEXES` before the matcher runs (read-only Cypher works today; indices needed for batch performance at scale):

| Node | Property | Reason |
|---|---|---|
| `Variant` | `barcode` | EAN lookup (currently unindexed — add now for future unblock, zero cost) |
| `CompetitorProduct` | `ean` | Reserved for EAN cascade (field doesn't exist yet; index added when field added) |

For F5: only the `Variant.barcode` index addition is needed (pre-emptive, harmless). The `CompetitorProduct.ean` index waits until the field exists.

**Note:** `Product.sku` and `CompetitorProduct.sku` are already indexed (`falkordb.py:35-56`). No additional index needed for the SKU signal.

---

## 3. Matching Cascade — Finalized

### 3.1 Signal Priority and Thresholds

The cascade evaluates signals in order. **The first signal that produces a decision terminates the cascade for that pair.** All signals that produce `auto_link` write an edge; `review` produces a MatchReview artifact entry; `reject` is discarded silently (with count).

```
Signal 1: EAN/GTIN      [BLOCKED in F5 — skip entirely, log as blocked_ean]
Signal 2: SKU exact
Signal 3: brand_model normalized
Signal 4: embedding_rerank (fallback, only if signals 2-3 produce no auto_link)
```

### 3.2 Per-Signal Decision Rules

#### Signal 2: SKU exact

```
Precondition: Product.sku IS NOT NULL AND CompetitorProduct.sku IS NOT NULL
Normalization: NFKD + ASCII + lowercase + strip (reuse title_match_key from shopify_order_lines.py:166-170)
Condition: normalized(Product.sku) == normalized(CompetitorProduct.sku)
Decision: auto_link
Confidence: 0.95
Rationale: SKU exact match is high-precision but imperfect (different vendors may reuse SKUs).
           0.95 (not 1.0) allows a human to spot false positives in the review muestra.
```

**Cascade short-circuit:** If SKU exact match found → write edge, skip signals 3 and 4 for this pair.

#### Signal 3: brand_model normalized

```
Precondition: (Product.vendor OR brand) IS NOT NULL AND (Product.title OR CompetitorProduct.title) IS NOT NULL
Normalization:
  key(node) = title_match_key(f"{brand} {title}") where title_match_key is NFKD+ASCII+lower+punctuation-fold
Exact match:
  key(Product) == key(CompetitorProduct) → auto_link, confidence 0.90
Token-level overlap (Jaccard on word tokens):
  jaccard >= 0.85 → auto_link, confidence 0.88
  0.65 <= jaccard < 0.85 → review, confidence jaccard (stored for human inspection)
  jaccard < 0.65 → reject (no edge, no review entry)
```

**Note on `brand` source:** `Product.vendor` is the Shopify vendor. `CompetitorProduct.brand` is from `competitor.py:23`. Both are normalized identically.

**Cascade short-circuit:** If brand_model produces auto_link → write edge, skip signal 4.

#### Signal 4: embedding_rerank (fallback)

```
Precondition: TEI env vars configured AND signals 2-3 produced no auto_link for this pair.
Input text:
  Our product:     f"{Product.vendor} {Product.title}" (normalized)
  Competitor:      f"{CompetitorProduct.brand} {CompetitorProduct.title}" (normalized)
Step 1 — dense embedding: BGE-M3 cosine similarity
  Score < 0.60 → reject immediately (skip reranker call, save latency)
Step 2 — reranker cross-encoder score (only if cosine >= 0.60):
  reranker_score >= 0.85 → auto_link, confidence reranker_score
  0.65 <= reranker_score < 0.85 → review, confidence reranker_score
  reranker_score < 0.65 → reject
Offline/stub mode: if TEI unavailable → skip embedding step entirely, log as embedding_skipped
```

### 3.3 Precision Gate

Before the apply phase, rho-backend must sample a **manual review muestra** of ≥50 candidate pairs (across all three available signals, including at least 10 per signal type) and produce:

| Metric | Required threshold |
|---|---|
| Precision (auto_link only) | ≥ 0.90 |
| False positive rate | ≤ 0.10 |
| Review band coverage | ≥ 1 example per signal in the [review] band |

The precision gate is evaluated by rho-verifier, not self-assessed by rho-backend. If precision < 0.90, thresholds must be raised before apply.

### 3.4 Pairing Strategy

The matcher does NOT attempt all N×M pairs (O(N×M) cartesian). Strategy:

1. **Index-assisted exact signals:** Cypher query using indexed `Product.sku` and `CompetitorProduct.sku` fields → O(M) queries, not O(N×M).
2. **brand_model:** Group by `CompetitorProduct.domain` + `brand` prefix to limit candidate set. For each `Product`, query CompetitorProducts with matching `brand` (indexed) first, then compare titles.
3. **embedding fallback:** Only run for Products that have no match yet after signals 2-3. Batch embed + rerank against top-K candidates per domain (K=20, tunable).

---

## 4. MatchReview Strategy

### 4.1 Decision: File Artifact for F5 Dry-Run Phase

**Chosen option:** Local JSON artifact `rso/F5-product-match/match-candidates.json` (committed to this repo).

Rationale:
- `MatchReview` Prisma model does not exist. Creating it requires a Prisma migration against the production Shopify app DB — this is out of F5 scope and requires separate RSO approval.
- A file artifact is safe, auditable, version-controlled, and sufficient for the human review step needed to validate precision before apply.
- The file lives in the RSO repo (this repo), not in brain-v2 or the Shopify app. No prod writes.

### 4.2 Artifact Schema

```jsonc
// rso/F5-product-match/match-candidates.json
{
  "generated_at": "ISO-8601",
  "matcher_version": "1.0.0",
  "summary": {
    "total_pairs_evaluated": 0,
    "auto_link": 0,
    "review": 0,
    "reject": 0,
    "blocked_ean": 0,
    "embedding_skipped": 0
  },
  "auto_link": [
    {
      "product_id": "string",
      "product_sku": "string",
      "product_title": "string",
      "competitor_product_id": "string",
      "competitor_title": "string",
      "competitor_domain": "string",
      "match_method": "sku|brand_model|embedding_rerank",
      "match_confidence": 0.95,
      "signals_evaluated": ["sku"]
    }
  ],
  "review": [
    {
      "product_id": "string",
      "product_sku": "string",
      "product_title": "string",
      "competitor_product_id": "string",
      "competitor_title": "string",
      "competitor_domain": "string",
      "match_method": "brand_model|embedding_rerank",
      "match_confidence": 0.72,
      "signals_evaluated": ["sku", "brand_model"],
      "review_reason": "jaccard_0.72_below_auto_link_threshold",
      "human_verdict": null  // filled by human reviewer: "accept" | "reject"
    }
  ]
}
```

### 4.3 Prisma MatchReview — Schema Proposal (for F6 or post-F5 apply)

This is a **proposal only** — no migration is run in F5. Backend or a future phase may implement:

```prisma
model MatchReview {
  id                    String   @id @default(cuid())
  productShopifyId      String   // our product's Shopify ID
  competitorProductId   String   // FalkorDB CompetitorProduct.id
  competitorDomain      String
  matchMethod           String   // brand_model | embedding_rerank
  matchConfidence       Float
  matcherVersion        String
  reviewReason          String
  humanVerdict          String?  // "accept" | "reject" | null (pending)
  reviewedBy            String?
  reviewedAt            DateTime?
  createdAt             DateTime @default(now())
  updatedAt             DateTime @updatedAt

  @@index([productShopifyId])
  @@index([competitorProductId])
  @@index([humanVerdict])
}
```

**No migration is run in F5.** This model is provided so rho-backend and RSO can plan F6 without needing another architecture pass.

---

## 5. Apply Guard

### 5.1 Phases

```
Phase A: Dry-Run  → produces match-candidates.json only; zero FalkorDB writes
Phase B: Review   → human (or RSO) sets human_verdict on review entries; approves auto_link list
Phase C: RSO Gate → RSO must explicitly emit "APPLY APPROVED" in audit log before Phase D
Phase D: Apply    → writes only auto_link edges + any review entries with human_verdict=accept
```

### 5.2 Pre-Apply Checks (rho-backend must run before Phase D)

```cypher
-- Before count
MATCH ()-[r:PRODUCT_MATCH]->() RETURN count(r) AS before_count;

-- Verify no existing edges for target pairs (idempotency pre-check)
MATCH (p:Product {id: $id})-[r:PRODUCT_MATCH]->(cp:CompetitorProduct {id: $cpid})
RETURN count(r);
```

### 5.3 Apply Cypher Pattern (MERGE idempotent)

See section 2.4. The `status` field is intentionally NOT overwritten on MATCH so manual overrides (`status: 'rejected'`) survive re-runs.

### 5.4 Post-Apply Verification

```cypher
-- After count
MATCH ()-[r:PRODUCT_MATCH]->() RETURN count(r) AS after_count;

-- Sample 5 edges for audit
MATCH (p:Product)-[r:PRODUCT_MATCH]->(cp:CompetitorProduct)
RETURN p.id, p.sku, cp.id, cp.domain, r.match_method, r.match_confidence, r.matched_at
LIMIT 5;

-- Re-run idempotency test: run apply again, count must remain identical
MATCH ()-[r:PRODUCT_MATCH]->() RETURN count(r) AS idempotent_count;
```

Expected: `idempotent_count == after_count`. If not, the MERGE pattern is broken — STOP and report.

### 5.5 Rollback Path

FalkorDB does not support transactions, but:

```cypher
-- Rollback: delete all edges from this matcher version
MATCH ()-[r:PRODUCT_MATCH {matcher_version: '1.0.0', source: 'f5-batch'}]-()
DELETE r;
```

This is safe because: (a) no pre-existing `PRODUCT_MATCH` edges exist today (researcher confirmed count=0), (b) `matcher_version + source` scopes the delete to F5 batch edges only, preserving any future manual edges.

### 5.6 Blocked-Until Conditions for Phase D

- [blocked] Phase D is BLOCKED until: (1) Phase A dry-run JSON artifact committed, (2) precision gate PASS per rho-verifier, (3) RSO explicit "APPLY APPROVED" in CHECKLIST.md Status log.
- [blocked] Write target is prod FalkorDB only. No staging/test graph available (researcher confirmed). RSO must acknowledge this in their approval.

---

## 6. F5 vs F6 Consumer Boundary

### 6.1 F5 Scope (this phase)

| File | Action |
|---|---|
| `skirmshop-brain-v2/src/matchers/product_match.py` | **NEW** — matcher implementing cascade, dry-run output, apply guard |
| `skirmshop-brain-v2/src/stores/falkordb.py` | **ADD** `Variant.barcode` index to `GRAPH_INDEXES` (pre-emptive, harmless) |
| `rso/F5-product-match/match-candidates.json` | **NEW** — dry-run output artifact (this RSO repo) |

F5 does NOT touch `prices.py`, `intel.py`, or any endpoint. F5 only populates the edges.

### 6.2 F6 Scope (NOT F5)

| File | Action | Reason |
|---|---|---|
| `src/api/prices.py` | Add `OPTIONAL MATCH (p)-[:PRODUCT_MATCH]->(cp:CompetitorProduct)` Cypher + populate `competitor_min/max/count` | Needs edges to exist first (F5 gate) |
| `src/api/intel.py` | Fix `intel/gaps` to use `PRODUCT_MATCH` instead of `SAME_AS` | Pre-existing bug; F5 does not introduce it |

**Pre-existing `intel/gaps` SAME_AS bug** (researcher.report.md §3, intel.py:74-79): `intel/gaps` queries `[:SAME_AS]` but `SAME_AS` in ontology is `Customer → Person`. This endpoint will remain broken after F5 even if `PRODUCT_MATCH` edges exist, because it queries the wrong relation. **F6 must fix this.** F5 explicitly does NOT touch `intel.py`.

### 6.3 Unlock Contract

After F5 PASS (edges in FalkorDB with `status=active`), F6 can:
1. Extend `prices.py` Cypher to expand `PRODUCT_MATCH` — no architectural change needed, only Cypher addition.
2. Fix `intel/gaps` to query `PRODUCT_MATCH` — straightforward relation rename in the Cypher, plus removing the dead `SAME_AS` path.

---

## 7. Residual Risks

| # | Risk | Severity | Mitigation / Owner |
|---|---|---|---|
| R1 | `Variant.barcode` population rate in prod FalkorDB unknown. EAN step blocked; if rate is high (>50%), significant signal lost. | Medium | rho-backend: run read-only Cypher `MATCH (v:Variant) WHERE v.barcode IS NOT NULL RETURN count(v)` in dry-run phase and report rate. |
| R2 | Only prod FalkorDB available as write target. No staging. | High | **[BLOCKED]** — RSO must explicitly acknowledge in APPLY APPROVED gate. Rollback Cypher defined (section 5.5). |
| R3 | `Product` node duplicate issue (prices.py:54-60). Matcher must deduplicate by `Product.id`. | Medium | rho-backend: fetch Products using `MATCH (p:Product) WHERE p.id IS NOT NULL RETURN DISTINCT p.id, p.sku, p.title`. Do NOT use node identity; always use `p.id` as idempotency key. |
| R4 | `CompetitorProduct.sku` population rate unknown — may be sparse for many domains. SKU cascade coverage may be low. | Medium | Expected behavior. Cascade degrades to brand_model + embedding. No action needed, but rho-verifier should report SKU hit rate in dry-run artifact. |
| R5 | TEI embedding service is env-config. If not available in dry-run environment, embedding signal skipped silently. | Low | rho-backend: mock TEI in unit tests; log `embedding_skipped` count in dry-run artifact. |
| R6 | `intel/gaps` SAME_AS pre-existing bug. After F5, gaps endpoint still broken. | Low-Medium | Flagged. F6 fix confirmed (section 6.2). No action in F5. |
| R7 | brand+model Jaccard threshold (0.65 review floor) may produce many review entries with no human bandwidth to review. | Medium | rho-backend: report review count in dry-run artifact. If >500 review candidates, RSO to decide whether to raise the review floor to 0.75 before apply. |
| R8 | FalkorDB has no transactions. A partial apply (crash mid-run) leaves a mix of edges. | Low | Rollback Cypher by `matcher_version + source` handles this (section 5.5). rho-backend must implement apply as a single committed batch, or at least checkpoint progress. |

---

## Files Inspected

| File | Key evidence |
|---|---|
| `RSO-MASTER-PLAN.md` | F5 objective, F5/F6 boundary, cascade signals required |
| `rso/F5-product-match/CHECKLIST.md` | Acceptance criteria, specialist checks |
| `rso/F5-product-match/researcher.report.md` | All topology findings, risks, proposed contract |
| `skirmshop-brain-v2/src/schema/ontology.py:89,158` | PRODUCT_MATCH direction, schema |
| `skirmshop-brain-v2/src/stores/falkordb.py:35-56` | GRAPH_INDEXES — Variant.barcode NOT indexed |
| `skirmshop-brain-v2/src/extractors/competitor.py:22-33` | CompetitorProduct fields — no ean/barcode |
| `skirmshop-brain-v2/src/extractors/shopify.py:116` | Variant.barcode populated |
| `skirmshop-brain-v2/src/api/prices.py:196-200` | Competitor columns null, no PRODUCT_MATCH expansion |
| `skirmshop-brain-v2/src/api/intel.py:74-79` | SAME_AS bug confirmed |
| `skirmshop-brain-v2/src/services/shopify_order_lines.py:166-170` | title_match_key NFKD normalization reusable |
| `skirmshop-brain-v2/src/embeddings/tei.py:117-119` | TEI BGE-M3 + reranker infra confirmed |
| `skirmshopshopifyapp/prisma/schema.prisma` | MatchReview absent; Prisma proposal deferred |

---

## Status

- [x] rho-researcher — PASS. Evidence: `researcher.report.md`.
- [x] rho-architect — PASS. Evidence: this report. Edge contract, thresholds, EAN decision, MatchReview artifact, apply guard, F5/F6 boundary, residual risks all defined.
- [ ] rho-backend — pending.
- [ ] rho-security — pending.
- [ ] rho-verifier — pending.
- [ ] Codex/RSO auditor — pending.
