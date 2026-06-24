# F1 Security Audit Report — rho-security (Independent)

**Date:** 2026-06-24  
**Auditor:** rho-security (independent, read-only pass — no product edits, no git ops)  
**Branch:** `codex/competitor-crawler-F1-catalog-price`  
**Scope:** F1 catalog-price adapter stack: `src/adapters/generic_html.py`, `src/adapters/base.py`, `src/dry_run.py`, `src/extractor.py`, `src/fetcher.py`, `rso/F1-catalog-price/pilot-smoke.json`, `k8s/`

---

## Sensitive Surfaces Inspected

| Surface | File |
|---|---|
| HTTP adapter | `src/adapters/generic_html.py` |
| Base adapter / normalizer | `src/adapters/base.py` |
| Dry-run CLI | `src/dry_run.py` |
| Structured extractor | `src/extractor.py` |
| Firecrawl fetcher (F0) | `src/fetcher.py` |
| Smoke output | `rso/F1-catalog-price/pilot-smoke.json` |
| K8s manifests | `k8s/manifest.yaml`, `k8s/externalsecret.yaml`, `k8s/kustomization.yaml` |
| Git status (untracked F1 files) | `git status --short` |

---

## RHO Security Checklist

### Directives
- [x] Read-only audit; no product edits.
- [x] Mark `[x]` only with direct evidence (command output cited).
- [x] No secrets exposed in this report.

---

### Acceptance Criteria

#### AC-1 · dry_run / generic_html uses only direct public GET; no Firecrawl / src.fetcher in adapter; no POST/PUT/PATCH/DELETE

**PASS**

Evidence:
- `src/adapters/generic_html.py` imports `httpx` directly (not `src.fetcher`).
  - Line 24: `# F1 mode: direct httpx GET only -- no Firecrawl, no JS rendering.`
  - Line 47: `resp = await client.get(url)` — only `.get()` call found; zero `.post/.put/.patch/.delete`.
- `rg "fetcher|firecrawl|Firecrawl" src/adapters/generic_html.py src/adapters/base.py src/dry_run.py` → matches only comments/docstrings declaring the absence; zero live import or call.
- `src/fetcher.py` (which has the Firecrawl POST logic) is **not imported** anywhere in the F1 adapter path.
- `grep -n "client\." src/adapters/generic_html.py` → lines 35, 47, 59, 60 — only `client.get()` and `client.aclose()`.

---

#### AC-2 · No cart / checkout / login / account / captcha in F1 code path

**PASS**

Evidence:
- `rg -in "cart|checkout|login|account|captcha" src/adapters/ src/dry_run.py` → **zero matches**.
- `src/extractor.py` contains `SKIP_PATH_HINTS` which explicitly enumerates `/cart`, `/checkout`, `/account`, `/login`, `/register` as paths to **skip** in BFS, not to visit.
- No session cookies, auth tokens, or form-submission logic exists in the F1 adapter stack.

---

#### AC-3 · No Brain push in dry_run / generic_html / BaseSiteAdapter

**PASS**

Evidence:
- `rg -n "brain|push_client|qdrant|Brain" src/adapters/ src/dry_run.py` → **zero matches**.
- `src/dry_run.py` writes output exclusively to a local file (via `output.write_text(...)`); no network push, no import of `push_client` or any Brain/Qdrant client.
- `BaseSiteAdapter.run()` returns an `AdapterResult` dataclass; no side effects beyond that.

---

#### AC-4 · F1 does not expose stock: pilot-smoke.json contains no availability/stock/quantity/qty/in_stock/out_of_stock; BaseSiteAdapter strips stock fields; extractor microdata diff does not extract availability

**PASS with caveat — see residual risk R-1**

Evidence:
- `python3` check on `pilot-smoke.json` → `PASS: no stock fields in products` (42/42 products, zero stock keys at top level or per-product).
- `src/adapters/base.py` line 44–46: `_F1_STOCK_FIELDS = frozenset({"availability","stock","stock_status","quantity","qty","in_stock","out_of_stock"})` and `_normalize()` strips them.
- **Caveat:** `src/extractor.py` `_from_jsonld_product()` (line 61) **does** populate `"availability"` from JSON-LD `offers.availability` before returning the raw dict. That field is then stripped by `BaseSiteAdapter._normalize()`. The strip gate is at the adapter level, not at extraction level. If an adapter ever bypasses `_normalize()` or calls `extract_products` without going through `BaseSiteAdapter.run()`, raw dicts with `availability` would leak. This is **R-1** below.
- Microdata extraction path (Method 3) does **not** extract `availability` — no `itemprop="availability"` lookup. ✓
- OG fallback (Method 2) does **not** extract `availability`. ✓

---

#### AC-5 · No k8s / deploy / prod / scheduler / push_client / config runtime files touched by F1

**PASS**

Evidence:
- `git diff --name-only codex/competitor-crawler-F0-bootstrap...HEAD` → only RSO report files under `rso/F1-catalog-price/` changed in F1 commits.
- `git status --short`: `k8s/`, `docker-compose.yml`, `Dockerfile`, `config.yaml`, `src/scheduler.py`, `src/push_client.py`, `src/main.py` are **unmodified** and not listed as untracked.
- The F1 untracked files are: `src/adapters/`, `src/dry_run.py`, `rso/F1-catalog-price/backend.report.md`, `rso/F1-catalog-price/pilot-smoke.json`, `tests/test_adapters.py`. None are operational/infra files.
- **Note:** `src/extractor.py` shows as `M` (modified, unstaged) — diff not inspected in detail here but it is the extractor, not scheduler/push/k8s.

---

## Findings Summary

| # | Severity | Finding | Status |
|---|---|---|---|
| R-1 | Low | `extractor._from_jsonld_product` populates `"availability"` in raw dict; stripping is deferred to `BaseSiteAdapter._normalize()`. A future adapter that calls `extract_products()` directly without going through `BaseSiteAdapter.run()` could leak availability. | Open — no current leak; architectural note for F2. |
| R-2 | Info | `src/extractor.py` is in `git status` as modified (`M`) but unstaged. Contents audited in working tree; git history shows last committed version may differ. Verifier should confirm diff is benign before merge. | Open — needs committer review of the unstaged diff. |
| R-3 | Info | F1 source files (`src/adapters/`, `src/dry_run.py`, `pilot-smoke.json`, `tests/test_adapters.py`) are **untracked** (not committed to the F1 branch). They exist only in the working tree. No security issue per se, but they are not part of the auditable git history yet. | Open — expected pre-commit state; note for verifier. |

---

## Required Mitigations

- **R-1 (Low):** Add a docstring/assertion in `extract_products()` or a test verifying that the public API contract strips stock fields. Consider moving stock-field stripping into `_from_jsonld_product()` (return early filter) so it is not solely dependent on the adapter layer. Alternatively, mark `_from_jsonld_product()` as internal and document that all callers must go through `BaseSiteAdapter._normalize()`.
- **R-2 (Info):** Before merge, run `git diff src/extractor.py` and confirm the unstaged changes are the intended F1 modifications only (e.g., the `is_product_url` and `SKIP_PATH_HINTS` additions seen in the working tree).
- **R-3 (Info):** Stage and commit F1 source files to make the audit trail complete.

---

## Verification Run

```
rg "fetcher|firecrawl" src/adapters/generic_html.py src/adapters/base.py src/dry_run.py
→ Only comments/docstrings; zero imports or calls.

rg -in "cart|checkout|login|account|captcha" src/adapters/ src/dry_run.py
→ Zero matches.

rg -n "brain|push_client|qdrant|Brain" src/adapters/ src/dry_run.py
→ Zero matches.

python3 -c "... check pilot-smoke.json for stock keys ..."
→ PASS: no stock fields in products; top-level stock keys: none

git diff --name-only codex/competitor-crawler-F0-bootstrap...HEAD
→ Only rso/F1-catalog-price/ report files.

grep -n "client\." src/adapters/generic_html.py
→ Lines 35,47,59,60 — only .get() and .aclose().
```

---

## Residual Risks

| Risk | Severity | Notes |
|---|---|---|
| R-1: availability in raw extractor dict | Low | Mitigated by `_normalize()` today; architectural fragility for F2 adapters |
| R-2: unstaged extractor.py diff | Info | Benign based on inspection; committer must confirm |
| R-3: F1 files untracked | Info | Pre-commit state only; no security impact |

**No critical or high severity residual risks identified.**
