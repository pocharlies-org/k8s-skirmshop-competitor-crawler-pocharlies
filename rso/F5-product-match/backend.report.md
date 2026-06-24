# F5 Product Match — Backend Report

**Role:** rho-backend
**Date:** 2026-06-24
**Brain branch:** `codex/product-recommendations-20260616`
**RSO branch:** `codex/competitor-crawler-F5-product-match`
**Input:** `researcher.report.md` (PASS), `architect.report.md` (PASS)

---

## RHO Checklist

### Directives
- [x] Implementar directamente en scope dado. No re-delegar. No git commit/push. No writes a Brain/DB/API.
- [x] Prohibido apply/live edge writes.
- [x] EAN/GTIN `[BLOCKED-EAN]`: `CompetitorProduct` sin campo `ean/barcode`. No inventado.
- [x] No tocar `prices.py` / `intel.py` (F6 boundary).
- [x] Cero hacks/workarounds. Root-cause first.

### Acceptance Criteria

- [x] **Matcher implementado con dry-run.** `src/matchers/product_match.py` creado con cascade SKU→brand_model→embedding_stub. `run_dry_run()` produce artifact dict sin FalkorDB writes.
  Evidence: `python3 -m py_compile src/matchers/product_match.py && echo PY_COMPILE OK` → `PY_COMPILE OK`

- [x] **Cascada multi-señal implementada.**
  - EAN: `[BLOCKED-EAN]` — no evaluado; contador `blocked_ean` == total pairs. Evidence: `TestEANBlocked` 2/2 PASS.
  - SKU exact: normalizado NFKD/ASCII/lower; short-circuits a `auto_link(0.95)`. Evidence: `TestSKUExact` 3/3 PASS.
  - brand_model: exact→0.90, Jaccard≥0.85→0.88, [0.65,0.85)→review, <0.65→None. Evidence: `TestBrandModel` 4/4 PASS.
  - embedding: stub raises `EmbeddingUnavailable` cuando TEI absent; matcher lo captura y retorna None (caller cuenta como `embedding_skipped`). Evidence: `TestEmbeddingSkipped` 2/2 PASS.

- [x] **`_normalize_key` reutiliza `title_match_key` de `shopify_order_lines.py`.**
  Zero code duplication. Evidence: `src/matchers/product_match.py:_normalize_key` importa `from src.services.shopify_order_lines import title_match_key`.

- [x] **`Variant.barcode` index añadido pre-emptively a `falkordb.py`.**
  Evidence: `src/stores/falkordb.py` línea `"Variant": ("id", "sku", "barcode"),`. Sin tocar conexión prod (solo la constante GRAPH_INDEXES).

- [x] **`match-candidates.json` generado (synthetic_fixture).**
  Evidence: archivo presente en `rso/F5-product-match/match-candidates.json`.
  Summary: total=25, auto_link=3, review=1, blocked_ean=25, embedding_skipped=21.

- [x] **Confusion matrix generada (synthetic_fixture, no full PASS).**
  Evidence: `rso/F5-product-match/confusion-matrix.md`. Labelled `synthetic_fixture`. Precision gate NOT full PASS.

- [x] **Tests unitarios: 32/32 PASS.**
  Evidence: `pytest tests/unit/test_product_matcher.py -v` → `32 passed, 1 warning in 0.07s`.
  Covers: normalization, SKU exact, brand_model (all bands), EAN blocked, embedding_skipped, artifact schema, no-writes guard, missing-id guard.

- [x] **`git diff --check` PASS en ambos repos.**
  Evidence: Brain repo → `DIFF_CHECK_BRAIN OK`; RSO repo → `DIFF_CHECK_RSO OK`.

- [blocked] **Precision gate ≥ 0.90 con muestra manual ≥ 50 pares reales.**
  Blocker: solo fixture sintético disponible (5×5=25 pares). Requiere run contra FalkorDB prod (read-only) + revisión humana. RSO debe aprobar y proveer acceso read-only antes del próximo pass.

- [blocked] **`MatchReview` durable (Prisma model).**
  Blocker: modelo no existe en `schema.prisma`. Propuesta incluida en `architect.report.md §4.3`. No es necesario para dry-run; requerido antes de APPLY en producción. Fuera de scope F5 dry-run.

- [blocked] **Edges `PRODUCT_MATCH` auditables (before/after count).**
  Blocker: APPLY BLOCKED hasta RSO "APPLY APPROVED". No hay target seguro (solo prod FalkorDB). Cypher MERGE pattern está definido en architect.report.md §2.4 y en el matcher (`run_dry_run` is the dry-run; apply step deliberadamente no implementado sin gate).

- [blocked] **Consumidores desbloqueables (`prices.py`/`intel.py`).**
  Blocker: F6 scope. No tocado en F5. Requiere edges reales en FalkorDB primero.

---

## Files Touched (Brain repo)

| File | Action | Notes |
|---|---|---|
| `src/matchers/__init__.py` | CREATED | Package init, exports public API |
| `src/matchers/product_match.py` | CREATED | Cascade matcher, dry-run helper, EmbeddingUnavailable stub |
| `src/stores/falkordb.py` | MODIFIED (1 line) | `Variant.barcode` added to GRAPH_INDEXES |
| `tests/unit/test_product_matcher.py` | CREATED | 32 unit tests |

## Files Touched (RSO repo)

| File | Action | Notes |
|---|---|---|
| `rso/F5-product-match/match-candidates.json` | CREATED | Synthetic dry-run artifact |
| `rso/F5-product-match/confusion-matrix.md` | CREATED | Synthetic confusion matrix (NOT full PASS) |
| `rso/F5-product-match/backend.report.md` | CREATED | This report |

## Files NOT Touched (as required)

- `src/api/prices.py` — F6 boundary ✓
- `src/api/intel.py` — F6 boundary ✓
- Any deploy/prod/k8s manifest ✓
- Any FalkorDB write (no MERGE/CREATE executed) ✓

---

## Commands Run + Results

```
# py_compile
python3 -m py_compile src/matchers/__init__.py src/matchers/product_match.py
→ PY_COMPILE OK

python3 -m py_compile tests/unit/test_product_matcher.py
→ TEST_COMPILE OK

# tests
python3 -m pytest tests/unit/test_product_matcher.py -v --tb=short
→ 32 passed, 1 warning in 0.07s

# git diff --check (Brain)
git diff --check
→ DIFF_CHECK_BRAIN OK

# git diff --check (RSO)
cd /home/dibanez/k8s/k8s-skirmshop-competitor-crawler-pocharlies && git diff --check
→ DIFF_CHECK_RSO OK
```

---

## Architecture Decisions

1. **`_normalize_key` delegates to `title_match_key`** (shopify_order_lines.py:166-170) via lazy import inside the function to avoid circular import at module load time.

2. **`EmbeddingUnavailable`** is raised (not silenced) so callers can distinguish "no TEI" from "rejected by reranker". `run_dry_run` catches it and increments `embedding_skipped`.

3. **`blocked_ean` counter == total_pairs_evaluated** (not a per-pair flag) because EAN is blocked at the signal level, not per-pair. This is cleaner for the artifact and matches architect spec §1.

4. **`GRAPH_INDEXES` edit is pre-emptive and safe**: adding `barcode` to the Variant tuple only affects `ensure_graph_indexes()` calls (CREATE INDEX IF NOT EXISTS) — no data write, no schema change, harmless if FalkorDB already has no barcode data.

5. **No `apply` function implemented**: deliberately omitted. Apply requires RSO "APPLY APPROVED" gate (CHECKLIST §5.6). The architecture for it (Cypher MERGE, before/after counts, rollback) is documented in architect.report.md §5 and referenced in docstrings.

---

## Residual Risks

| # | Risk | Severity | Status |
|---|---|---|---|
| R1 | Precision gate not validated with real data | High | [blocked] — requires live read-only run + manual review |
| R2 | Write target is prod FalkorDB only | High | [blocked] — RSO gate required |
| R3 | `Variant.barcode` population rate in prod unknown | Medium | Read-only Cypher needed: `MATCH (v:Variant) WHERE v.barcode IS NOT NULL RETURN count(v)` |
| R4 | `CompetitorProduct.sku` sparseness may limit SKU cascade coverage | Medium | Expected; cascade degrades gracefully |
| R5 | TEI not available in dry-run → all pairs fall to embedding_skipped | Low | By design; log count in artifact |
| R6 | `intel/gaps` SAME_AS pre-existing bug (F6 scope) | Low-Medium | Flagged, not touched |

---

## Status

- [x] rho-researcher — PASS. Evidence: `researcher.report.md`
- [x] rho-architect — PASS. Evidence: `architect.report.md`
- [x] rho-backend — PASS/BLOCKED. Dry-run matcher implemented, tests green, artifacts generated. Precision gate and apply BLOCKED (no real data, no RSO approval). Evidence: this report.
- [ ] rho-security — pending
- [ ] rho-verifier — pending
- [ ] Codex/RSO auditor — pending
