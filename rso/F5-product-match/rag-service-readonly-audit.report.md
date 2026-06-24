# F5/F6 RAG Service Read-Only Audit

**Date:** 2026-06-24T18:45:00+02:00
**Role:** Codex RSO/PMO auditor
**Authorization:** user allowed use of the RAG service. This pass used only GET/POST read-only queries and Kubernetes reads. No DB writes, no `push-ingest`, no deploy/restart.

## RHO Checklist

### Directives
- [x] Use the RAG service only as live verification. Evidence: calls were limited to `/health/quick`, `/instances/skirmshop/prices/position/...`, `/instances/skirmshop/prices/comparison?...`, and `/graph/skirmshop/cypher` read queries.
- [x] Do not print secrets. Evidence: commands only printed `BRAIN_API_KEY=present`/HTTP summaries, never token values.
- [x] Do not mutate production. Evidence: no `kubectl delete/rollout/apply`, no API writes, no `push-ingest`.
- [blocked] Independent Claude CLI verifier. Evidence: `rho-verifier` invocation with 75s timeout exited `124` without report.

### Acceptance Criteria
- [x] RAG app wiring to Brain identified. Evidence: `rag-app` image `harbor.lan.e-dani.com/homelab/skirmshopshopifyapp:v1.5.69`; env `POCHARLIES_RAG_URL=http://skirmshop-brain.skirmshop-brain-prod.svc.cluster.local`; `BRAIN_API_KEY` present in pod.
- [x] RAG-to-Brain health path works through the service. Evidence: from `rag-app`, `GET /health/quick` via service returned HTTP 200 in 199 ms and via ClusterIP in 104 ms.
- [x] Runtime `prices.py` consumes `PRODUCT_MATCH`. Evidence: live Brain pod `/app/src/api/prices.py` contains `OPTIONAL MATCH (p)-[:PRODUCT_MATCH]->(cp:CompetitorProduct)`, `competitor_min`, `competitor_max`, `competitor_count`, and `prices/position` competitor aggregation.
- [x] One healthy Brain pod returns competitor price data through the RAG-authorized path. Evidence: from `rag-app` to pod `10.42.3.80`, `GET /instances/skirmshop/prices/position/1-4x24se-tactical-scope` returned HTTP 200 in 132 ms with `our_price=94.95`, `min_competitor=79.23`, `competitors_count=1`, `position=most_expensive`.
- [x] Graph data itself is fast and present. Evidence: direct read-only FalkorDB queries: `PRODUCT_MATCH` count 510 in 175.9 ms; targeted sample match in 34.5 ms; `prices/position` equivalent Cypher in 361.1 ms.
- [blocked] RAG service data routes are not stable enough for F6 PASS. Evidence: via service or bad pod, `prices/position` aborted at 30,013 ms, `graph/skirmshop/cypher` aborted at 30,010 ms, and `prices/comparison?status=active&filter=has_comp&limit=3` aborted at 60,022 ms. Pod `10.42.6.151` timed out on `/health/quick` at 5,013 ms and on `prices/position` at 12,017 ms.
- [blocked] Brain deployment/pod readiness is inconsistent. Evidence: deployment reported `replicas=1/2 updated=2 available=1`; both pods were listed `READY 1/1`, but endpoints included both `10.42.3.80` and `10.42.6.151`; pod `skirmshop-brain-56d9f4d8c8-hwz25` events showed repeated readiness/liveness probe timeouts.

## Evidence Summary

### Service/Runtime Wiring

- RAG service: `skirmshop/rag-app`
- RAG image: `harbor.lan.e-dani.com/homelab/skirmshopshopifyapp:v1.5.69`
- Brain service: `skirmshop-brain-prod/skirmshop-brain` (`10.43.206.194:80 -> pods :5001`)
- Brain runtime image: `ghcr.io/pocharlies-org/skirmshop-brain-v2:sha-9a3e753bad0d`
- Brain API pods:
  - `skirmshop-brain-56d9f4d8c8-sztct` / `10.42.3.80`: data route OK in the targeted test.
  - `skirmshop-brain-56d9f4d8c8-hwz25` / `10.42.6.151`: health and data route timed out in targeted tests.

### Product Match Consumer Proof

Good-pod `prices/position` returned competitor data for an audited match:

```json
{
  "slug": "1-4x24se-tactical-scope",
  "id": "1-4x24se-tactical-scope",
  "sku": "SP-AIM-AO3044-BK",
  "title": "1-4x24SE Tactical Scope",
  "vendor": "Aim-O",
  "our_price": 94.95,
  "min_competitor": 79.23,
  "max_competitor": 79.23,
  "avg_competitor": 79.23,
  "competitors_count": 1,
  "position": "most_expensive"
}
```

Direct FalkorDB equivalent:

```json
{
  "count_edges_ms": 175.9,
  "edge_count": 510,
  "targeted_match_ms": 34.5,
  "position_equivalent_ms": 361.1,
  "product": "1-4x24se-tactical-scope",
  "our_price": 94.95,
  "comp_min": 79.23,
  "comp_count": 1
}
```

## Verdict

**PASS** for proving that the deployed `prices.py` runtime can consume `PRODUCT_MATCH` and return competitor price data when traffic lands on a healthy Brain API pod.

**BLOCKED** for F6 operational PASS: the Brain service currently has at least one endpoint/pod path that times out while still being included in service endpoints. Do not declare RAG/Prices competitor comparison production-ready until the pod/service health issue is remediated and `prices/position` plus `prices/comparison?filter=has_comp` pass repeatedly through the service, not just a known-good pod IP.
