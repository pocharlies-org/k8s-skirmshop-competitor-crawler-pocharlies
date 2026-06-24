# F5 Existing Writer Audit - PRODUCT_MATCH Baseline

**Date:** 2026-06-24T18:08:00+02:00
**Role:** Codex RSO/PMO auditor
**Scope:** Read-only audit of the already-deployed `PRODUCT_MATCH` writer and live edges. No DB writes, no deploy changes.

## RHO Checklist

### Directives
- [x] Keep this pass read-only. Evidence: only `MATCH ... RETURN` Cypher, `kubectl get/exec` reads, and repo file reads were used.
- [x] Do not implement product code. Evidence: Brain and GitOps product repos were only inspected; RSO artifacts only.
- [x] Do not treat live writes as Codex-approved apply. Evidence: this report distinguishes existing writer baseline from new RSO apply.
- [x] Preserve F6 gate unless F5 edge baseline is explicitly documented. Evidence: F6 is not opened by this report.

### Acceptance Criteria
- [x] Existing live edges are countable and deduplicated. Evidence: `product-match-edge-baseline-audit.json` shows `edge_count=510`, `distinct_pair_count=510`, `duplicate_pair_count=0`.
- [x] Existing live edges carry required properties. Evidence: `missing_method_count=0`, `missing_confidence_count=0`, `missing_matched_at_count=0`, `confidence_out_of_range_count=0`.
- [x] Existing live edge confidence is within threshold. Evidence: method distribution is `llm: 510`, `min_confidence=0.9`, `max_confidence=1.0`.
- [x] Runtime writer path exists. Evidence: running Brain pod image contains `src/extractors/competitor_match.py`, which emits `(Product)-[:PRODUCT_MATCH]->(CompetitorProduct)` from `metadata.source="competitor_match"`.
- [x] Runtime ingest is idempotent by relation MERGE. Evidence: running Brain pod `src/pipeline/ingest.py` calls `upsert_relations_merge`; `src/stores/falkordb.py` uses `MERGE (source)-[rel:\`{label}\`]->(target) SET rel += $props`.
- [x] Consumer prices path exists in deployed runtime. Evidence: running Brain pod `src/api/prices.py` has `OPTIONAL MATCH (p)-[:PRODUCT_MATCH]->(cp:CompetitorProduct)`.
- [x] Runtime unit tests for extractor pass. Evidence: `kubectl exec ... python -m pytest tests/unit/test_extractors.py -q` -> `36 passed, 1 warning in 1.81s`.
- [blocked] Exact live run provenance is not fully reconstructable from Kubernetes events. Evidence: `rag-competitor-llm-matcher` CronJob exists with `APPLY=1`, created `2026-06-24T14:39:07Z`, but `.status.lastScheduleTime` is empty and no matching job/pod/event remains. Live edge `matched_at` values show writes through `2026-06-24T15:56:17Z`.

## Evidence Summary

### Live Edge Audit

Artifact: `product-match-edge-baseline-audit.json`

```json
{
  "edge_count": 510,
  "distinct_pair_count": 510,
  "duplicate_pair_count": 0,
  "missing_method_count": 0,
  "missing_confidence_count": 0,
  "missing_matched_at_count": 0,
  "confidence_out_of_range_count": 0,
  "method": "llm",
  "min_confidence": 0.9,
  "max_confidence": 1.0
}
```

### Deployed Writer

- GitOps repo: `/home/dibanez/k8s/k8s-skirmshopshopifyapp-pocharlies`
- GitOps commit inspected: `5a29e30 deploy(rag): v1.5.69 (competitor column) + competitor-llm-matcher cron`
- Live CronJob: `skirmshop/rag-competitor-llm-matcher`
- Cron env: `APPLY=1`, `MODEL=tooling`, `MIN_CONF=0.9`, `TOPK=6`, `BATCH=200`, `CONC=6`
- Schedule: `30 5 * * *`, timezone `Europe/Madrid`, `suspend=false`
- Source script: `k8s/competitor-llm-matcher.js`
- Important behavior: skips products already decided by `competitor_checked_at` or existing `PRODUCT_MATCH`; pushes only strict LLM-confirmed matches and no-match markers to Brain.

### Runtime Brain

- Deployed image: `ghcr.io/pocharlies-org/skirmshop-brain-v2:sha-9a3e753bad0d`
- Runtime extractor: `CompetitorMatchExtractor`
- Runtime idempotent edge write: `upsert_relations_merge`
- Runtime price consumer: `prices.py` expands `PRODUCT_MATCH`

## Risk Notes

- This writer is not the dry-run cascade built in `skirmshop-brain-v2` branch `codex/product-recommendations-20260616`; it is a deployed LLM matcher path from GitOps/Brain runtime.
- Prior Brain memory from 2026-04-20 / 2026-04-25 documents historical false-positive risk in older `PRODUCT_MATCH` systems, including SRS/accessory mismatches. The current 60-pair artifact sample passed conservative precision, but the LLM writer remains high-risk and should keep review sampling.
- Edge count changed from `453` to `510` during the RSO session without Codex apply. Treat live edge count as dynamic while `rag-competitor-llm-matcher` or manual runs can write.

## Verdict

**PASS** for live baseline edge audit and runtime idempotency evidence.

**BLOCKED** for exact run provenance and for declaring any new Codex-controlled apply. If F5 is accepted as "existing deployed writer + audited baseline", F6 can be opened as an audit of the already-deployed `prices.py` consumer. If the requirement is "Codex/Claude F5 branch must own the apply", then F5 remains blocked pending explicit `APPLY APPROVED` and a controlled before/after run.
