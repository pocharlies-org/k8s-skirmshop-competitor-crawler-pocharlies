# RAG Service Remediation / Revalidation

**Date:** 2026-06-24T19:05:00+02:00
**Role:** Codex RSO/PMO auditor
**Authorization:** user explicitly authorized remediation: restart the Brain API pod that timed out and revalidate RAG prices via Service.

## RHO Checklist

### Directives
- [x] Limit prod action to the authorized Brain API remediation. Evidence: no manifests changed, no rollout restart, no DB/API writes.
- [x] Prefer the smallest safe operational action. Evidence: restart was skipped because pre-checks showed the previously bad pod had recovered and Service-level smokes passed.
- [x] Do not expose secrets. Evidence: commands used in-pod env only and printed HTTP summaries, never token values.
- [blocked] Claude CLI DevOps implementer. Evidence: `rho-devops` invocation with 90s timeout exited `124` with no report.
- [x] PMO exception recorded. Evidence: Codex performed read-only validation directly and did not execute a destructive/remediating command because it was no longer needed.

### Acceptance Criteria
- [x] Pre-remediation cluster state captured. Evidence: `skirmshop-brain` deployment reported `ready=2/2 updated=2 available=2`; endpoints listed both `10.42.3.80` and `10.42.6.151`.
- [x] Previously bad pod rechecked before deletion. Evidence: from `rag-app`, direct health to `10.42.6.151` returned HTTP 200 in 102 ms; direct health to `10.42.3.80` returned HTTP 200 in 101 ms.
- [x] No unnecessary restart performed. Evidence: no `kubectl delete pod` was run after healthy pre-checks.
- [x] Brain Service health validated repeatedly from RAG app. Evidence: `/health/quick` via `POCHARLIES_RAG_URL` returned HTTP 200 five times with latencies 207 ms, 107 ms, 22 ms, 18 ms, 20 ms.
- [x] `prices/position` validated repeatedly through Service. Evidence: five HTTP 200 responses for `1-4x24se-tactical-scope`; each returned `our_price=94.95`, `min_competitor=79.23`, `competitors_count=1`, `position=most_expensive`.
- [x] `prices/comparison?has_comp` validated through Service. Evidence: HTTP 200 in 527 ms for `status=active&filter=has_comp&limit=3&offset=0`; response `total=510`, `count=3`, sample rows have `competitor_count=1` and non-null `competitor_min`.
- [x] Deployment remains healthy after validation. Evidence: final closeout re-run showed `deploy ready=2/2 updated=2 available=2`; pods `skirmshop-brain-56d9f4d8c8-hwz25` and `skirmshop-brain-56d9f4d8c8-sztct` both `READY 1/1`; endpoints still include both pod IPs.

## Evidence Summary

### Health via Service

```json
[
  {"i":1,"status":200,"ms":207},
  {"i":2,"status":200,"ms":107},
  {"i":3,"status":200,"ms":22},
  {"i":4,"status":200,"ms":18},
  {"i":5,"status":200,"ms":20}
]
```

### `prices/position` via Service

```json
[
  {"i":1,"status":200,"ms":249,"id":"1-4x24se-tactical-scope","our_price":94.95,"min_competitor":79.23,"competitors_count":1,"position":"most_expensive"},
  {"i":2,"status":200,"ms":117,"id":"1-4x24se-tactical-scope","our_price":94.95,"min_competitor":79.23,"competitors_count":1,"position":"most_expensive"},
  {"i":3,"status":200,"ms":30,"id":"1-4x24se-tactical-scope","our_price":94.95,"min_competitor":79.23,"competitors_count":1,"position":"most_expensive"},
  {"i":4,"status":200,"ms":25,"id":"1-4x24se-tactical-scope","our_price":94.95,"min_competitor":79.23,"competitors_count":1,"position":"most_expensive"},
  {"i":5,"status":200,"ms":29,"id":"1-4x24se-tactical-scope","our_price":94.95,"min_competitor":79.23,"competitors_count":1,"position":"most_expensive"}
]
```

### `prices/comparison` via Service

```json
{
  "status": 200,
  "ms": 527,
  "total": 510,
  "count": 3,
  "sample": [
    {"id": "5ku-10-3-inch-m4-outer-barrel-aluminum", "competitor_count": 1, "competitor_min": 28.99, "competitor_avg": 28.99},
    {"id": "5ku-11-5-inch-m4-outer-barrel-aluminum", "competitor_count": 1, "competitor_min": 21.72, "competitor_avg": 21.72},
    {"id": "5ku-14-5-outer-barrel-aluminum-m4", "competitor_count": 1, "competitor_min": 28.99, "competitor_avg": 28.99}
  ]
}
```

## Verdict

**PASS** for the authorized RAG/Brain Service revalidation: the previously observed operational blocker was not present at remediation time, and Service-level `prices/position` plus `prices/comparison?filter=has_comp` passed.

**No restart performed** because the target pod was healthy before remediation. This is intentional risk control, not a missed action.

F5 remains governed by the baseline/apply decision; this report removes the RAG Service operational blocker observed in `rag-service-readonly-audit.report.md`.
