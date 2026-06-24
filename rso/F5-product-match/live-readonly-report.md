# F5 Live Read-Only Artifact Report

**Role:** Codex RSO PMO exception after Claude CLI long-running artifact attempts produced no usable output.
**Date:** 2026-06-24T15:38:44+00:00
**Scope:** RSO evidence artifacts only. No product code changed. No DB/API write. No apply.

## RHO Checklist

### Directives
- [x] Read-only live F5 only. Evidence: commands used only `MATCH ... RETURN ... LIMIT` Cypher; artifacts set `apply_performed=false`.
- [x] Do not implement product code. Evidence: only `rso/F5-product-match/*live*` artifacts were written.
- [x] Do not expose secrets. Evidence: target recorded as sanitized ClusterIP/service description; no env dump or API key included in artifacts.
- [x] Keep F6 closed. Evidence: no `prices.py`/`intel.py` changes; this report only documents F5 artifacts.
- [x] Record PMO exception. Evidence: this report documents that two Claude CLI artifact attempts were interrupted due no progress/output; Codex generated evidence artifacts only.

### Acceptance Criteria
- [x] Live counts captured. Evidence: `match-candidates-live.json.live_counts`.
- [x] Existing live `PRODUCT_MATCH` edges sampled read-only. Evidence: `match-candidates-live.json.summary.edge_pairs_evaluated=453`.
- [x] Matcher F5 evaluated pairwise on live existing edge pairs with `skip_embedding=True`. Evidence: `match-candidates-live.json.summary`.
- [x] Review artifact prepared with >=60 records. Evidence: `match-review-artifact-live.json.sample_size=60`.
- [blocked] Precision >= threshold on reviewed sample. Evidence: `confusion-matrix-live.md` marks pending because `human_verdict=null` for every artifact item.
- [blocked] Apply/edge writes. Evidence: no `APPLY APPROVED`; no write query executed.

## Commands / Evidence

```bash
FALKORDB_URL=redis://10.43.157.14:6379 /home/dibanez/k8s/skirmshop-brain-v2/.venv/bin/python <artifact-generator>
```

Read-only Cypher shapes executed:

```cypher
MATCH (n:Product) RETURN count(n) AS c
MATCH (n:CompetitorProduct) RETURN count(n) AS c
MATCH (p:Product) WHERE p.sku IS NOT NULL AND p.sku <> '' RETURN count(p) AS c
MATCH (c:CompetitorProduct) WHERE c.sku IS NOT NULL AND c.sku <> '' RETURN count(c) AS c
MATCH (v:Variant) WHERE v.barcode IS NOT NULL AND v.barcode <> '' RETURN count(v) AS c
MATCH (:Product)-[r:PRODUCT_MATCH]->(:CompetitorProduct) RETURN count(r) AS c
MATCH (p:Product)-[r:PRODUCT_MATCH]->(c:CompetitorProduct) RETURN properties(p) AS p, properties(r) AS r, properties(c) AS c LIMIT 1000
```

Live counts:

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

Summary:

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

## Files Written
- `rso/F5-product-match/live-readonly-report.md`
- `rso/F5-product-match/match-candidates-live.json`
- `rso/F5-product-match/match-review-artifact-live.json`
- `rso/F5-product-match/confusion-matrix-live.md`

## Residual Risks
- Existing live `PRODUCT_MATCH` edges predate this read-only pass; this artifact does not prove who wrote them or that Codex approved apply.
- Current F5 matcher with `skip_embedding=True` has low coverage on existing LLM edges: see `no_candidate` in summary.
- `CompetitorProduct.sku` count is 0 and Variant barcode population is only 16; EAN/SKU matching remains mostly blocked on available competitor data.
- Precision gate remains blocked until at least 50 artifact records have reviewed `human_verdict` labels and precision is recomputed.
