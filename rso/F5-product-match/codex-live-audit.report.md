# F5 Live Read-Only Audit - Codex RSO

**Date:** 2026-06-24T17:52:00+02:00
**Scope:** User-authorized live read-only F5 and review-by-artifact.
**Repos:** RSO `codex/competitor-crawler-F5-product-match`; Brain `codex/product-recommendations-20260616`.

## RHO Checklist

### Directives
- [x] Keep Codex as RSO/PMO and avoid product code changes. Evidence: Brain worktree clean; only RSO artifacts/checklist changed.
- [x] Live read-only only; no apply. Evidence: artifacts set `apply_performed=false`; only `MATCH ... RETURN` Cypher shapes documented.
- [x] No deploy/prod/k8s changes. Evidence: RSO diff limited to `rso/F5-product-match/**`.
- [x] Preserve F6 gate. Evidence: `prices.py`/`intel.py` untouched; F6 remains blocked.

### Acceptance Criteria
- [x] Live counts captured. Evidence: `match-candidates-live.json`: `Product=21477`, `CompetitorProduct=43497`, `PRODUCT_MATCH=453`, `CompetitorProduct.sku nonempty=0`, `Variant.barcode nonempty=16`.
- [x] Live artifact generated. Evidence: `match-review-artifact-live.json` has `sample_size=60`, `dry_run=true`, `apply_performed=false`.
- [x] Artifact reviewed. Evidence: `match-review-artifact-live-reviewed.json` has 60 reviewed labels: 55 true positives, 2 false positives, 3 uncertain.
- [x] Precision gate for artifact sample passes. Evidence: `confusion-matrix-live-reviewed.md`; conservative precision `55/60=0.9167`, excluding uncertain `55/(55+2)=0.9649`.
- [x] Verification commands pass. Evidence: JSON validation OK; secret grep on `*live*` artifacts no hits; Brain matcher tests `32 passed in 0.05s`.
- [blocked] F5 full apply gate. Evidence: no `APPLY APPROVED`; existing live edges predate this pass; no before/after apply count or idempotent re-run write proof.

## Claude CLI Delegation Note

Three Claude CLI invocations were attempted for live artifact generation/review/verification. The short smoke command returned `CLAUDE_OK`, but longer artifact/review/verifier invocations produced no usable output and were interrupted to avoid leaving sessions running. Codex therefore made an explicit RSO exception to generate and review evidence artifacts only; no product code or external state was mutated.

## Commands Re-Executed By Codex

```bash
FALKORDB_URL=redis://10.43.157.14:6379 /home/dibanez/k8s/skirmshop-brain-v2/.venv/bin/python <artifact-generator>
python3 -m json.tool rso/F5-product-match/match-candidates-live.json
python3 -m json.tool rso/F5-product-match/match-review-artifact-live.json
python3 -m json.tool rso/F5-product-match/match-review-artifact-live-reviewed.json
# secret-pattern grep over live artifacts and reviewer report returned no hits
/home/dibanez/k8s/skirmshop-brain-v2/.venv/bin/python -m py_compile src/matchers/__init__.py src/matchers/product_match.py tests/unit/test_product_matcher.py
/home/dibanez/k8s/skirmshop-brain-v2/.venv/bin/python -m pytest tests/unit/test_product_matcher.py -q
```

## Verdict

**PASS** for user-authorized live read-only F5 artifact and artifact precision review.

**BLOCKED** for full F5 close: apply/idempotent write audit and F6 consumers remain closed until explicit RSO/user decision. Existing live `PRODUCT_MATCH` edges may be usable evidence, but they were not created by this pass and must not be treated as a newly approved apply.
