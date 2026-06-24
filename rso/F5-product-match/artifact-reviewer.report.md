# F5 Artifact Reviewer Report

**Role:** Codex RSO artifact reviewer (fallback after Claude verifier invocation produced no usable output).
**Date:** 2026-06-24T15:43:26+00:00
**Input:** `match-review-artifact-live.json`
**Output:** `match-review-artifact-live-reviewed.json`, `confusion-matrix-live-reviewed.md`

## RHO Checklist

### Directives
- [x] Review only local artifact. Evidence: no live command was needed for review; labels derive from public fields already in JSON.
- [x] Be conservative on variants. Evidence: color mismatch and hammer-vs-housing mismatch marked false; version/model ambiguity marked uncertain.
- [x] No product code or DB writes. Evidence: only RSO `*reviewed*` artifacts written.

### Acceptance Criteria
- [x] Reviewed JSON parseable and same sample size. Evidence: `sample_size=60`.
- [x] At least 50 records reviewed. Evidence: `60` labels.
- [x] Reasons recorded per item. Evidence: `artifact_review_reason` on every item.
- [x] Precision computed. Evidence: conservative precision `0.9167`; excluding uncertain `0.9649`.
- [blocked] F5 apply/consumer gate. Evidence: no apply approval/write; `prices.py`/`intel.py` untouched.

## Summary
- True positives: 55
- False positives: 2
- Uncertain: 3
- Conservative precision: 0.9167
- Precision excluding uncertain: 0.9649

## False Positive / Uncertain Items
- `F5-LIVE-033` false_positive: Color mismatch: our product title/id says DE, competitor title says black.
- `F5-LIVE-041` uncertain: Possible variant mismatch: our product says 1-4x24SE, competitor says 1-4x24 without SE.
- `F5-LIVE-043` uncertain: Competitor is specifically for TM M&P9; our product title lacks platform/model.
- `F5-LIVE-051` false_positive: Product is stainless steel hammer; competitor is stainless steel hammer housing.
- `F5-LIVE-053` uncertain: Likely AAP01 enhanced piston head, but competitor says V2 and our title omits version.

## Residual Risks
- This is an RSO artifact review, not a storefront/web-page fetch for every item.
- The sample validates existing live `PRODUCT_MATCH` edges, not a newly approved F5 apply run.
- F5 remains blocked for apply/idempotent write audit and F6 consumers.
