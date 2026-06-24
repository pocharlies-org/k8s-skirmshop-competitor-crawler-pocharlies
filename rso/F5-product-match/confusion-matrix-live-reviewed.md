# F5 Live Confusion Matrix - Reviewed Artifact

Generated: 2026-06-24T15:43:26+00:00
Source artifact: `match-review-artifact-live.json`
Reviewed artifact: `match-review-artifact-live-reviewed.json`
Review type: Codex RSO artifact review from public product/competitor fields; no network, no DB writes, no apply.

## Verdict
- [x] Sample size >= 50. Evidence: `60` reviewed records.
- [x] Precision conservative >= 0.90. Evidence: `55/60 = 0.9167` where `uncertain` counts as not-pass.
- [x] Precision excluding uncertain >= 0.90. Evidence: `55/(55+2) = 0.9649`.
- [blocked] Apply remains blocked. Evidence: no `APPLY APPROVED`, no write query, artifacts read-only.

## Matrix

| Predicted positive source | True positive | False positive | Uncertain | Total | Precision excl. uncertain | Precision conservative |
|---|---:|---:|---:|---:|---:|---:|
| Existing live `PRODUCT_MATCH` sample | 55 | 2 | 3 | 60 | 0.9649 | 0.9167 |

## False Positive / Uncertain Items
- `F5-LIVE-033` false_positive: Color mismatch: our product title/id says DE, competitor title says black.
- `F5-LIVE-041` uncertain: Possible variant mismatch: our product says 1-4x24SE, competitor says 1-4x24 without SE.
- `F5-LIVE-043` uncertain: Competitor is specifically for TM M&P9; our product title lacks platform/model.
- `F5-LIVE-051` false_positive: Product is stainless steel hammer; competitor is stainless steel hammer housing.
- `F5-LIVE-053` uncertain: Likely AAP01 enhanced piston head, but competitor says V2 and our title omits version.

## Scope Note
This validates the reviewed sample of existing live `PRODUCT_MATCH` edges. It does **not** prove an audited apply path, idempotent before/after write, or F6 consumer readiness.
