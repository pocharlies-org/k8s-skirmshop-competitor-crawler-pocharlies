# F5 Product Match — Confusion Matrix

> **IMPORTANT: synthetic_fixture** — This matrix was generated from the dry-run
> synthetic fixture (5 products × 5 competitors = 25 pairs).
> It is NOT derived from a manual human-labelled sample of ≥50 pairs.
> The precision gate (≥ 0.90) CANNOT be marked as full PASS until a real
> manual review sample is available.  RSO must not approve APPLY on this
> matrix alone.

## Sample metadata

| Field | Value |
|---|---|
| Sample type | `synthetic_fixture` |
| Products | 5 (hand-crafted, representative SKU/brand_model/no-match cases) |
| Competitors | 5 (hand-crafted per above) |
| Total pairs evaluated | 25 |
| Date | 2026-06-24 |
| Matcher version | 1.0.0 |
| EAN step | `blocked_ean` — not evaluated |

## Decision distribution

| Decision | Count | % |
|---|---|---|
| `auto_link` | 3 | 12% |
| `review` | 1 | 4% |
| `embedding_skipped` (fallback, no result) | 21 | 84% |
| `rejected` | 0 | 0% |
| `blocked_ean` | 25 (counter, all pairs) | — |

## Signal breakdown (auto_link only)

| Signal | Count | Confidence |
|---|---|---|
| `sku` | 1 | 0.95 |
| `brand_model` (Jaccard ≥ 0.85) | 2 | 0.88 |
| `embedding_rerank` | 0 (skipped) | — |

## Confusion matrix — synthetic verdicts

Human verdicts assigned manually for the 4 decided pairs
(auto_link=3, review=1):

| Pair | Method | Confidence | Decision | Human verdict | TP/FP/FN/TN |
|---|---|---|---|---|---|
| prod-001 → cp-001 | sku | 0.95 | auto_link | ACCEPT (correct SKU match) | TP |
| prod-002 → cp-002 | brand_model | 0.88 | auto_link | ACCEPT (same product, word order differs) | TP |
| prod-003 → cp-003 | brand_model | 0.88 | auto_link | ACCEPT (same product, "Pistol" suffix only diff) | TP |
| prod-005 → cp-005 | brand_model | 0.71 | review | ACCEPT (same product, "Full Metal" suffix) | TP (review band correct) |

All other 21 pairs (embedding_skipped = no decision): no ground truth label
available from synthetic fixture.

## Metrics (synthetic only — NOT precision gate)

| Metric | Value | Gate threshold | Status |
|---|---|---|---|
| Precision (auto_link) | 3/3 = 1.00 | ≥ 0.90 | synthetic PASS (not real PASS) |
| False positive rate (auto_link) | 0/3 = 0.00 | ≤ 0.10 | synthetic PASS (not real PASS) |
| Review band ≥1 example per signal | 1 brand_model review entry | ≥ 1 | PASS |

## Blocked — Precision gate

- `[blocked]` Precision gate is **NOT full PASS** because the sample is
  `synthetic_fixture`, not a real manual review of ≥50 pairs spanning live
  FalkorDB data.
- Evidence requirement: rho-verifier must confirm ≥50 pairs from live dry-run
  output, with human verdicts, before APPLY APPROVED.

## Next step to unblock

1. Run matcher against live FalkorDB data (read-only Cypher to fetch Products
   and CompetitorProducts), with `skip_embedding=True` for the first pass.
2. Export `match-candidates.json` with live data.
3. Human reviewer labels ≥50 auto_link pairs.
4. rho-verifier recomputes this matrix with real verdicts.
5. If precision ≥ 0.90 → RSO may approve APPLY.
