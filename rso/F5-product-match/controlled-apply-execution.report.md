# F5 Option B - Controlled Apply Execution

**Date:** 2026-06-24T21:33:07+02:00  
**Role:** Codex RSO/PMO auditor  
**Authorization:** user approved **B1+B2**. B3 destructive recreate was **not** approved and was **not** executed.

## RHO Checklist

### Directives
- [x] Execute only approved non-destructive variants B1 and B2. Evidence: B1 was a writer no-op; B2 re-ingested one reviewed true-positive pair through Brain `push-ingest`; no delete/remove/recreate action was run.
- [x] Do not execute B3. Evidence: no `PRODUCT_MATCH` edge removal was run by Codex; B3 remains unexecuted.
- [x] Verify with live commands, not only reports. Evidence: Codex re-ran Kubernetes health, Brain logs, FalkorDB graph counts, and RAG/Brain price smokes.
- [x] Preserve product/GitOps code. Evidence: no code/manifests edited; only RSO markdown artifacts are changed by this closeout.
- [blocked] Claude CLI independent verifier. Evidence: `timeout 120s env RSO_DELEGATED_ROLE=rho-verifier claude ... --agent rho-verifier` exited `124` with no report/output.

### Acceptance Criteria
- [x] B1 writer no-op executed with zero writes. Evidence from execution transcript:

```text
competitor-llm-matcher start APPLY=true MODEL=tooling MIN_CONF=0.9 TOPK=6 BATCH=4 BRAND='*' LIMIT=4
competitor_nodes=21743
targets(active es>0, undecided)=0 decided_skip=2892

MATCHES (matched=0 nomatch=0 nocand=0 of 0):

APPLIED (incremental): 0 matches + 0 markers pushed.
DONE
```

- [x] B2 selected a reviewed true-positive pair. Evidence: `match-review-artifact-live-reviewed.json` review id `F5-LIVE-001`: product `acetech-ac5000-chronograph` / competitor `competitor:aa-store.at:https://www.aa-store.at/acetech-ac5000-chronograph`.
- [x] B2 reached Brain server-side successfully. Evidence: Brain log on pod `skirmshop-brain-56d9f4d8c8-hwz25`:

```text
2026-06-24T19:24:26.249012955Z INFO:     10.42.0.136:54592 - "POST /instances/skirmshop/push-ingest HTTP/1.1" 200 OK
```

- [x] B2 client caveat recorded. Evidence: the `push-ingest` client attempt timed out with `AbortError` at 90s, but the Brain access log later confirmed HTTP 200 and graph verification passed. No client response body is available.
- [x] Immediate B1+B2 graph outcome was idempotent. Evidence: after B2 server-side 200, Codex verified `PRODUCT_MATCH` still had `edges=510`, `products=510`, `competitors=437`, `duplicate_pairs=0`; selected edge remained `confidence=1.0`, `method=llm`, `matched_at=2026-06-24T14:32:06Z`.
- [x] Final graph state captured after concurrent external change. Evidence: after a separate `competitor-prune` request, final FalkorDB read returned:

```json
{
  "all_product_match_relationships": {"c": 437},
  "product_to_competitorproduct_relationships": {"c": 437},
  "distinct_pairs": {"c": 437},
  "duplicate_pairs": {"c": 0, "rels": 0.0},
  "selected_edge": {
    "product_id": "acetech-ac5000-chronograph",
    "competitor_product_id": "competitor:aa-store.at:https://www.aa-store.at/acetech-ac5000-chronograph",
    "confidence": 1.0,
    "method": "llm",
    "matched_at": "2026-06-24T14:32:06Z"
  }
}
```

- [x] Concurrent external prune identified and separated from B1/B2. Evidence: Brain logs on new image `sha-ff450c3571b8` show:

```text
2026-06-24T19:29:55.487714060Z INFO:     10.42.4.80:57586 - "POST /instances/skirmshop/prices/competitor-prune?dry_run=true HTTP/1.1" 200 OK
2026-06-24T19:29:57.213709719Z INFO src.api.prices: competitor-prune: removed 73 surplus PRODUCT_MATCH edges across 58 collisions
2026-06-24T19:29:57.214032930Z INFO:     10.42.4.80:43064 - "POST /instances/skirmshop/prices/competitor-prune HTTP/1.1" 200 OK
```

`kubectl get pods -A -o wide` mapped `10.42.4.80` to `skirmshop/collections-tree-app-56c9674644-xz5kd`. Codex did not call this endpoint.

- [x] Brain/RAG health and consumer smoke revalidated after rollout. Evidence: Brain deployment rolled out to `ghcr.io/pocharlies-org/skirmshop-brain-v2:sha-ff450c3571b8` and `READY 2/2`; RAG deployment `v1.5.70` `READY 1/1`.
- [x] `prices.py` consumer still reads `PRODUCT_MATCH` after the prune. Evidence via RAG pod to Brain Service with internal API header:

```json
{
  "comparison": {
    "status": 200,
    "ms": 516,
    "total": 437,
    "first": {
      "id": "5ku-10-3-inch-m4-outer-barrel-aluminum",
      "competitor_count": 1,
      "competitor_min": 33.9183
    }
  },
  "position": {
    "status": 200,
    "ms": 117,
    "id": "5ku-10-3-inch-m4-outer-barrel-aluminum",
    "our_price": 29.95,
    "min_competitor": 28.99,
    "competitors_count": 1,
    "position": "most_expensive"
  }
}
```

## Verdict

**PASS for F5 Option B B1+B2.**

What is proven:
- The deployed writer is currently exhausted/no-op under `APPLY=1`.
- Brain `competitor_match` ingestion can safely re-ingest a reviewed true-positive pair idempotently.
- No duplicate `PRODUCT_MATCH` pair was created.
- The selected audited edge remained intact.
- B3 destructive recreate was not run.

Important caveat:
- B2 lacks a client response body because the client timed out; server log 200 plus graph state are the acceptance evidence.

Post-gate state for F6:
- Use **437** as the current post-prune live `PRODUCT_MATCH` baseline, not 510.
- `intel.py` remains an F6 concern; F5 only proves matching plus the `prices.py` consumer smoke.
