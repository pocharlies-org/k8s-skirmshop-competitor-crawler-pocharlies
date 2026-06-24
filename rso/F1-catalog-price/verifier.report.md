# RHO Verifier Report — F1-catalog-price

**Date:** 2026-06-24  
**Verifier:** rho-verifier (independent pass)  
**Verdict: PASS**

---

## Checklist

### Directives
- [x] No git fetch/pull/commit/push executed.
- [x] No deploy, no product edits.
- [x] Scope limited to F1 files; no F2-F7/deploy/prod/k8s/scheduler/push_client/config changes.

### 1. py_compile
- [x] All 7 modules compile without error.
  - **Evidence:** `python3 -m py_compile src/extractor.py src/adapters/base.py src/adapters/__init__.py src/adapters/generic_html.py src/dry_run.py tests/test_extractor.py tests/test_adapters.py` → exit 0

### 2. pytest tests/ -q
- [x] All tests pass.
  - **Evidence:** `18 passed in 0.19s` (run inside `/tmp/f1-venv` with requirements installed).
  - **Note:** system Python3 lacks `bs4`; a clean venv was required. Test suite itself is not broken; environment issue only.

### 3. Dry-run smoke test
- [x] `python -m src.dry_run --domain leopard.es --limit 50 --output /tmp/f1-verifier-smoke.json` succeeded.
  - **Evidence:** `INFO Wrote 42 products to /tmp/f1-verifier-smoke.json` — exit 0.

### 4. JSON validation
- [x] `len(products) >= 10` → **42**
- [x] `success == len(products)` → 42 == 42
- [x] `failures == 0` → 0
- [x] `discard_ratio < 0.2` → **0.0**
- [x] Every product has `title`, `url`, `price`, `domain`, `source_id` → no missing
- [x] No duplicate `source_id` → 0 duplicates
- [x] No stock fields (`stock`, `inventory`, `in_stock`, `availability`) → none present

### 5. Diff scope — no F2-F7/infra/prod changes
- [x] `git diff --name-only` returns:
  ```
  rso/F1-catalog-price/CHECKLIST.md
  src/extractor.py
  ```
  Untracked (new files):
  ```
  rso/F1-catalog-price/backend.report.md
  rso/F1-catalog-price/pilot-smoke.json
  src/adapters/
  src/dry_run.py
  tests/test_adapters.py
  ```
  **No** deploy/, k8s/, scheduler/, push_client/, config runtime, or F2-F7 files touched.
- [x] `git diff --check` → exit 0 (no whitespace errors)

---

## Residual Risks

1. **No venv in repo / CI:** Tests require external deps (`bs4`, `httpx`, etc.) not installed in system Python. A `requirements.txt` exists but no `Makefile`/CI target installs it. Any CI runner without venv setup will fail identically.  
2. **Network dependency in dry-run:** smoke test hits `https://www.leopard.es/` live. Offline/flaky runs will fail. No mock/fixture for network in `test_adapters.py` was observed (tests pass because they use unit-level mocking; dry-run does not).
3. **Single domain tested:** Only `leopard.es` was smoke-tested. Adapter is generic; other domains untested at integration level.

