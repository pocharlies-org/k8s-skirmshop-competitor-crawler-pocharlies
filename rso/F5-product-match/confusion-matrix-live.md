# F5 Live Confusion Matrix - PENDING

Generated: 2026-06-24T15:38:44+00:00
Source: live read-only existing `PRODUCT_MATCH` edges from sanitized target `skirmshop_v2 via redis://10.43.157.14:6379 (ClusterIP aiops-falkordb, sanitized, read-only)`.

## Status
- [blocked] Real precision cannot be computed yet because every `human_verdict` in `match-review-artifact-live.json` is `null`.
- [x] Review artifact prepared with 60 live pairs. Evidence: `match-review-artifact-live.json` parses and `sample_size=60`.
- [x] No apply was performed. Evidence: artifacts have `apply_performed=false`; only read-only `MATCH ... RETURN` queries were executed.

## Live Counts
```json
{
  "competitor_product_count": 43497,
  "competitor_sku_nonempty_count": 0,
  "product_count": 21477,
  "product_match_edge_count": 453,
  "product_sku_nonempty_count": 17435,
  "variant_barcode_nonempty_count": 16
}
```

## F5 Pairwise Decision On Existing Live Edges
```json
{
  "auto_link": 49,
  "blocked_ean": 453,
  "edge_pairs_evaluated": 453,
  "embedding_skipped_or_reject": 331,
  "human_review_status": "pending",
  "no_candidate": 331,
  "review": 73
}
```

## Confusion Matrix
Pending artifact review. Required next action: fill `human_verdict` for at least 50 records in `match-review-artifact-live.json` using `true_positive|false_positive|uncertain`, then recompute precision. `uncertain` must not be counted as a true positive.
