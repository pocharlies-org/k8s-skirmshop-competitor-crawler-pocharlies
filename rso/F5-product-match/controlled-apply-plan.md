# F5 Option B - Controlled Apply Plan

**Date:** 2026-06-24T19:35:00+02:00
**Role:** Codex RSO/PMO auditor
**Decision from user:** choose Option B: require controlled apply instead of accepting the existing baseline as-is.

## RHO Checklist

### Directives
- [x] Do not execute production graph/API writes without explicit `APPLY APPROVED`. Evidence: this pass ran read-only graph queries and `APPLY=0` dry-runs only.
- [x] Use Claude CLI specialists first. Evidence: `rho-researcher`, `rho-architect`, and `rho-security` were invoked read-only with 60s timeouts.
- [blocked] Claude CLI specialist reports. Evidence: all three invocations exited `124` with no report; Codex PMO continued direct read-only audit and records this limitation.
- [x] Use the deployed writer as runtime truth, not local dirty files. Evidence: live ConfigMap `rag-competitor-llm-matcher-script-h9dktt5f5c` differs from the dirty GitOps checkout; preflight used the live ConfigMap script piped into `rag-app`.
- [x] Preserve unrelated dirty work. Evidence: `/home/dibanez/k8s/k8s-skirmshopshopifyapp-pocharlies` has local changes in `k8s/competitor-llm-matcher.js`; Codex did not edit or revert them.

### Acceptance Criteria For A Real Option B Close
- [x] Current live state captured. Evidence: `PRODUCT_MATCH` count 510, products 510, competitor nodes 437, duplicate pairs 0.
- [x] Current writer pending-target state captured. Evidence: deployed writer dry-run with `APPLY=0 LIMIT=4 BATCH=4` returned `targets(active es>0, undecided)=0`, `matched=0`, `nomatch=0`, `nocand=0`.
- [x] Apparent graph discrepancy explained. Evidence: direct graph showed 4 active unmatched/unchecked AGM Global Vision nodes, but each is a duplicate `Product.id` where a sibling vendor `AGM` node already has `competitor_checked_at`; the writer's id-level `decided` set therefore skips them.
- [blocked] Choose the controlled-apply variant. Evidence: normal writer apply would be no-op; a true write requires explicit selection and approval of one of the variants below.
- [blocked] Execute write with before/after counts. Evidence: pending `APPLY APPROVED` after variant selection.
- [blocked] Independent verifier/auditor after write. Evidence: pending post-apply.

## Preflight Evidence

### Live Counts

```json
{
  "PRODUCT_MATCH": {
    "edges": 510,
    "products": 510,
    "competitors": 437,
    "duplicate_pairs": 0
  },
  "active_priced_products": 2892,
  "products_with_competitor_checked_at": 2892,
  "writer_targets_via_deployed_script": 0
}
```

### Deployed Writer Dry-Run

Command shape: live ConfigMap script piped into `rag-app` with `APPLY=0`, no graph/API writes.

```text
competitor-llm-matcher start APPLY=false MODEL=tooling MIN_CONF=0.9 TOPK=6 BATCH=4 BRAND='*' LIMIT=4
competitor_nodes=21743
targets(active es>0, undecided)=0 decided_skip=2892

MATCHES (matched=0 nomatch=0 nocand=0 of 0):

DRY - would push 0 PRODUCT_MATCH + 0 markers
```

### Four Direct-Graph "Unmatched" Nodes

These are not actionable targets for the deployed writer because each duplicated `Product.id` has a sibling already marked checked:

```json
[
  {
    "id": "agm-eyepiece-for-rattler-c-v-converts-unit-into-thermal-monocular-6328xer21",
    "nodes": [
      {"vendor": "AGM", "checked": "2026-06-24T14:30:00Z"},
      {"vendor": "AGM Global Vision", "checked": null}
    ]
  },
  {
    "id": "agm-helmet-mount-g50s-for-shroud-mini-rail-interface-compatible-with-nvg-40-50-with-auto-shut-off-6103hs51",
    "nodes": [
      {"vendor": "AGM", "checked": "2026-06-24T14:31:43Z"},
      {"vendor": "AGM Global Vision", "checked": null}
    ]
  },
  {
    "id": "agm-ne-charger-for-rattler-v2-battery-charger-base-and-charging-cord-6308r44c1",
    "nodes": [
      {"vendor": "AGM", "checked": "2026-06-24T14:31:43Z"},
      {"vendor": "AGM Global Vision", "checked": null}
    ]
  },
  {
    "id": "agm-pvs-14-binocular-bridge-6104xp4b1",
    "nodes": [
      {"vendor": "AGM", "checked": "2026-06-24T14:31:43Z"},
      {"vendor": "AGM Global Vision", "checked": null}
    ]
  }
]
```

## Controlled-Apply Variants

### Variant B1 - Controlled Writer No-Op

Run the deployed writer with `APPLY=1 LIMIT=4 BATCH=4 CONC=1` from the live ConfigMap, after before-counts.

Expected result:
- `targets=0`
- no `push-ingest` calls
- before/after `PRODUCT_MATCH` count remains 510
- duplicate pairs remain 0

What it proves:
- The currently deployed writer is safely exhausted/idempotent at this moment.
- There is no pending work in the writer's own input feed.

What it does **not** prove:
- It does not create a new edge under Codex/RSO control.
- It does not replace the historical provenance of the existing 510 edges.

Risk:
- Lowest. No expected graph writes.

### Variant B2 - Controlled Idempotent Re-Ingest Of One Reviewed True Positive

Re-push one reviewed true-positive `competitor_match` document through Brain `push-ingest` with the same product/competitor pair, then verify `MERGE` keeps edge count unchanged.

Expected result:
- before/after `PRODUCT_MATCH` count remains 510
- the selected edge exists with props complete
- no duplicates

What it proves:
- Brain `competitor_match` materialization path is write-safe and idempotent.
- A controlled write path can be audited end-to-end.

What it does **not** prove:
- It does not exercise the LLM matching decision path.
- It still relies on a reviewed existing pair.

Risk:
- Low/medium. It is a real Brain write, but should be idempotent.

### Variant B3 - Destructive Recreate Of One Reviewed Edge

Temporarily remove one reviewed true-positive `PRODUCT_MATCH` edge or its source doc, run the deployed writer to recreate it, and rollback/reinsert if recreation fails.

Expected result:
- before count 510
- controlled temporary removal count 509
- writer recreate count 510
- reviewed pair restored and logged

What it proves:
- Full writer path can create a `PRODUCT_MATCH` under RSO control.

Risk:
- Highest. It requires destructive graph/API action and a rollback path.
- It can temporarily affect Prices comparison for the selected product.
- It may fail if the writer skips the product due to checked markers or if LLM output changes.

## RSO Recommendation

Do **not** run B3 unless the user explicitly wants destructive proof.

For a strict but low-risk Option B, use:
1. B1 first, to prove the deployed writer has no pending targets.
2. If a real write is mandatory, B2 on one reviewed true-positive pair.

Required approval phrase before any write:

```text
APPLY APPROVED: ejecuta B1 no-op del writer desplegado; si no escribe nada, ejecuta B2 re-ingesta idempotente de 1 true positive revisado; no ejecutar B3 destructivo.
```

Alternative destructive approval, only if desired:

```text
APPLY APPROVED DESTRUCTIVE: ejecuta B3 sobre 1 edge true-positive revisado con rollback documentado.
```
