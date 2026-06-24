# Codex RSO Audit Report - F5 Product Match

**Date:** 2026-06-24T16:56:29+02:00
**Role:** Codex RSO/PMO auditor
**RSO branch:** `codex/competitor-crawler-F5-product-match`
**Brain branch:** `codex/product-recommendations-20260616`
**Verdict:** Implemented dry-run scope PASS; F5 gate BLOCKED

## Scope

F5 opened only matching dry-run work. No F3 history, F4 cart-probe, F6 comparison, F7 scheduling, deploy/prod branches, k8s manifests, or CronJobs were opened.

Claude CLI executed:

- `rho-researcher`: `researcher.report.md`
- `rho-architect`: `architect.report.md`
- `rho-backend`: Brain matcher + RSO artifacts + `backend.report.md`
- `rho-security`: `security.report.md`
- `rho-verifier`: `verifier.report.md`

Codex did not edit product code. Codex edited only RSO checklist/audit documentation.

## Product Code Touched By Claude

Brain repo `/home/dibanez/k8s/skirmshop-brain-v2`:

- `src/matchers/__init__.py` (new)
- `src/matchers/product_match.py` (new dry-run matcher)
- `tests/unit/test_product_matcher.py` (new)
- `src/stores/falkordb.py` (adds `Variant.barcode` to index tuple only)

RSO repo:

- `rso/F5-product-match/match-candidates.json`
- `rso/F5-product-match/confusion-matrix.md`
- specialist reports

## Evidence Re-Executed By Codex

```bash
python3 -m py_compile \
  src/matchers/__init__.py src/matchers/product_match.py \
  src/stores/falkordb.py tests/unit/test_product_matcher.py
```

Result: PASS (exit 0).

```bash
python3 -m pytest tests/unit/test_product_matcher.py -q
```

Result: `32 passed, 1 warning in 0.05s`. Warning: unrelated pytest config `asyncio_mode`.

```bash
git diff --check
```

Result: PASS in Brain repo and RSO repo.

JSON validation of `match-candidates.json`:

```text
TOP_KEYS_OK=True
SUMMARY_KEYS_OK=True
DRY_RUN=True
SUMMARY={"auto_link": 3, "blocked_ean": 25, "embedding_skipped": 21, "rejected_count": 0, "review": 1, "total_pairs_evaluated": 25}
AUTO_LINK=3
REVIEW=1
```

Security/scope grep:

- `src/matchers/product_match.py` has no FalkorDB store import at module level.
- No apply path was implemented.
- `prices.py` and `intel.py` were not modified.
- `match-candidates.json` is synthetic and `dry_run=true`.

## Acceptance Reconciliation

- Topology research: PASS.
- Edge contract: PASS.
- Dry-run matcher: PASS.
- Multi-signal cascade: PASS with `[BLOCKED-EAN]`; EAN/GTIN cannot run until `CompetitorProduct.ean/barcode` exists.
- MatchReview for doubtful matches: PASS for F5 dry-run artifact; durable Prisma `MatchReview` remains blocked.
- Precision gate: BLOCKED. Current matrix is `synthetic_fixture`, not a real manual review of >=50 live pairs.
- PRODUCT_MATCH edges: BLOCKED. No `APPLY APPROVED`, no safe non-prod graph target, no before/after count.
- Consumers `prices.py`/`intel.py`: BLOCKED/F6 scope. They remain untouched.
- Security/data: PASS.
- Tests: PASS.

## Blockers

1. **Precision gate:** Needs live read-only candidate generation and manual/RSO-reviewed sample of >=50 pairs with precision >=0.90.
2. **Apply gate:** Only prod FalkorDB is visible; no edge writes until RSO emits explicit `APPLY APPROVED` after precision gate.
3. **Durable MatchReview:** Prisma model does not exist. F5 uses JSON artifact only.
4. **Consumers:** F6 must update `prices.py` and `intel.py` after real edges exist.
5. **EAN/GTIN:** `Variant.barcode` exists on our side, but `CompetitorProduct` has no `ean/barcode` field.

## Verdict

Do not open F3 or F6. F5 is not complete; it is safely staged at dry-run PASS and gate BLOCKED.
