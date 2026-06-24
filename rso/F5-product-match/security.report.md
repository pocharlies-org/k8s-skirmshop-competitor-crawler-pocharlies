# F5 Product Match — Security Report

**Role:** rho-security (independent auditor)
**Date:** 2026-06-24
**Scope:** `src/matchers/product_match.py`, `src/stores/falkordb.py`, `tests/unit/test_product_matcher.py`, RSO artifact `match-candidates.json`
**Repos inspected:**
- Brain: `/home/dibanez/k8s/skirmshop-brain-v2`
- RSO:   `/home/dibanez/k8s/k8s-skirmshop-competitor-crawler-pocharlies`

---

## Directives

- [x] Read-only execution only — no writes, commits, or pushes performed.
- [x] No F3/F4/F6/F7 files opened or analyzed.
- [x] Evidence required for every `[x]` item; no claim without tool output.
- [x] No secrets exposed in this report.

---

## Acceptance Checklist

### 1. No FalkorDB writes in matcher (MERGE/CREATE/DELETE/apply)

- [x] **PASS** — `grep -n "MERGE\|CREATE\|DELETE\|apply\|graph_store\|falkordb\|stores\."` on `product_match.py` → **zero matches**.
- Evidence: grep returned empty output (confirmed in session tool run).

### 2. No module-level import of `src.stores.falkordb` in matcher

- [x] **PASS** — AST import scan of `product_match.py` (lines L25–L220) shows only:
  - `logging`, `datetime`, `enum`, `typing` (stdlib)
  - `src.services.shopify_order_lines` (lazy, inside function bodies at L86, L220)
  - `src.config` (lazy, inside `_embedding_rerank_score` body at L123)
  - `httpx` (lazy, inside `_embedding_rerank_score` at L128)
  - **No** `src.stores.*` import at any level.
- Confirmed independently by `TestNoWrites.test_no_falkordb_store_import_in_matcher` (passes).

### 3. No secrets/tokens/env values in artifacts or reports

- [x] **PASS** — `grep -n "TOKEN\|SECRET\|PASSWORD\|API_KEY\|Bearer\|sk-\|key="` across `match-candidates.json`, `CHECKLIST.md`, `backend.report.md` → **zero matches**.
- `match-candidates.json` contains only synthetic product/competitor titles (`Cyma AEG MP5 Black`, `G&G M4 Combat Machine Tan`, etc.) and internal IDs (`prod-001`, `cp-001`). No real Shopify IDs, credentials, or env values.

### 4. No PII / no customer/order data in artifact

- [x] **PASS** — `grep -n "email\|phone\|customer\|order\|address\|@"` on `match-candidates.json` → **zero matches**.
- Fields present: `product_id`, `product_sku`, `product_title`, `competitor_product_id`, `competitor_title`, `competitor_domain`. All synthetic.

### 5. HTTP POST only to TEI inference, not executed by default (`skip_embedding=True`)

- [x] **PASS** — `run_dry_run` signature: `def run_dry_run(..., *, skip_embedding: bool = True)`.
  Default is `True`. The `httpx.post` calls inside `_embedding_rerank_score` are only reached when `skip_embedding=False` AND TEI URL is configured AND `ProductMatcher._skip_embedding` is False.
  The TEI URLs are read from `get_settings().tei_dense_url` / `tei_reranker_url` — if absent, `EmbeddingUnavailable` is raised before any HTTP call, and the caller logs `embedding_skipped`.
- No Brain/DB write path exists in the embedding branch.

### 6. `prices.py` / `intel.py` not touched (F6 boundary)

- [x] **PASS** — `grep -rn "prices\|intel" product_match.py` returns only the docstring comment `"No prices.py / intel.py changes (F6 boundary)"` at line 22. No import or call.
- `git status` on both files: not listed as modified, added, or untracked.

### 7. `falkordb.py` change limited to `Variant.barcode` index tuple; no connection/prod target changed

- [x] **PASS** — `git diff HEAD -- src/stores/falkordb.py`:
  ```diff
  -    "Variant": ("id", "sku"),
  +    "Variant": ("id", "sku", "barcode"),  # barcode added pre-emptively for F5-v2 EAN signal
  ```
  Single line change. `get_property_graph_store()`, `falkordb_url`, `graph_database_for()` — unchanged. No new connection target, no credential change, no MERGE/CREATE/DELETE added.

### 8. `match-candidates.json` is synthetic, `dry_run=true`, no PII, no customer/order data

- [x] **PASS** — Top-level: `"dry_run": true`. IDs are sequential synthetic (`prod-001..005`, `cp-001..005`). Domains are `rival.es`/`other.es` (fictional). `human_verdict: null` throughout. No customer/order fields present.
- Evidence: file read directly, confirmed contents above.

### 9. Tests pass (32/32) and diff checks clean

- [x] **PASS** — `pytest tests/unit/test_product_matcher.py -q` → **32 passed, 0 failed** (1 unrelated pytest config warning).
- [x] **PASS** — `git diff --check` on both repos → clean (`DIFF_CLEAN`, `RSO_DIFF_CLEAN`).

### 10. `product_match.py` compiles without error

- [x] **PASS** — `python3 -m py_compile src/matchers/product_match.py` → `COMPILE_OK`.

---

## Files / Artifacts Inspected

| File | Status | Notes |
|---|---|---|
| `src/matchers/product_match.py` | Untracked (new) | No writes, no falkordb imports, clean compile |
| `src/stores/falkordb.py` | Modified (M) | Single-line index tuple addition only |
| `tests/unit/test_product_matcher.py` | Untracked (new) | 32 tests, all pass |
| `rso/F5-product-match/match-candidates.json` | Committed | Synthetic, dry_run=true, no PII |
| `rso/F5-product-match/CHECKLIST.md` | Committed | No secrets |
| `rso/F5-product-match/backend.report.md` | Committed | No secrets |

---

## Residual Security Risks

| Risk | Severity | Status |
|---|---|---|
| `_embedding_rerank_score` sends text (normalized product titles) to TEI via HTTP. If TEI URL is misconfigured to point outside the cluster, titles leak to external service. | Low | Mitigated by `skip_embedding=True` default and EmbeddingUnavailable guard. Caller must explicitly opt in. No auth header/token is added to TEI request — acceptable for internal service; note for future if TEI is exposed externally. |
| `Variant.barcode` index will be created on next `ensure_graph_indexes` startup call against production FalkorDB. This is a DDL operation (index creation), not a data write; idempotent. | Negligible | Correct and intended; no data risk. |
| `product_match.py` is untracked — not yet part of any branch. If merged without review, the HTTP path (skip_embedding=False) could be triggered by a misconfigured caller. | Low | Blocked by current untracked state. Recommend: enforce `skip_embedding=True` at any Celery/queue task call site when TEI service is not validated. |

---

## Overall Verdict

**PASS — No security blocking issues found.**

All 10 acceptance criteria verified with direct evidence. The F5 matcher is a pure dry-run computation. Zero FalkorDB writes, zero secrets exposure, zero PII in artifacts, and 32/32 unit tests green.
