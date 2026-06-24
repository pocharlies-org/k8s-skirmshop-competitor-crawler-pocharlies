# RHO Checklist - F2 Visible Stock

> Fase **F2** del `RSO-MASTER-PLAN.md`.
> Gate previo: F1 PASS en commit `262674f` (`codex/competitor-crawler-F1-catalog-price`), confirmado por Codex con remoto alineado.
> Marca `[x]` SOLO con `Evidence:` directa (comando/archivo/log/output). No abrir F3/F4/F6/F7 sin PASS de Codex.

## Objective
- [x] Implementar stock visible para dominio piloto `green` (`leopard.es`) sin cart-probe: cada producto del dry-run debe exponer `stock_status in {in_stock,out_of_stock,unknown}` y `stock_method in {visible,unknown}`, con 10 fichas inspeccionadas manualmente y coincidencia extractor vs muestra etiquetada. Evidence: Codex re-ejecuto `/tmp/f1venv/bin/python -m src.dry_run --domain leopard.es --limit 50 --output rso/F2-visible-stock/pilot-visible-stock.json` -> 42 productos, 0 fallos, 0 descartes; validacion JSON -> 42/42 con contrato F2; `visible-stock-sample.json` -> 10/10 match.

## Directives
- [x] Claude CLI = EJECUTOR; Codex = RSO/PMO/auditor. Claude implementa y prueba; Codex re-ejecuta evidencia antes de abrir F3/F4/F6/F7. Evidence: backend/security/verifier reportes escritos por Claude; Codex re-ejecuto compile, pytest, dry-run y validaciones JSON.
- [x] No tocar `deploy/prod`, k8s manifests, imagenes, CronJobs ni produccion nocturna en F2. Evidence: `git status -sb --untracked-files=all` y diff limitado a `src/adapters/base.py`, `src/extractor.py`, `src/stock.py`, `tests/*`, `rso/F2-visible-stock/*`.
- [x] F2 es **stock visible**. Prohibido historico append-only (F3), cart-probe/cantidad exacta/carrito (F4), matching `PRODUCT_MATCH` (F5), comparacion viva (F6), scheduling nocturno (F7). Evidence: `rho-security` y `rho-verifier` grep de scope creep PASS; no k8s/deploy/prod/CronJob.
- [x] Hacia competidores: solo `GET` de catalogo/producto publico. Prohibido `cart`, `checkout`, `login`, `account`, POST/PUT/PATCH/DELETE o resolver CAPTCHA. Evidence: `src/adapters/generic_html.py` usa `client.get(url)`; `SKIP_PATH_HINTS` excluye rutas prohibidas; `rho-security` PASS.
- [x] No inferir agotado por ausencia de dato: si no hay evidencia visible/estructurada, `stock_status=unknown`. Evidence: `tests/test_stock.py::test_unknown_variants` y `tests/test_adapters.py::test_normalize_unknown_when_no_availability`; pytest 53 passed.
- [x] No exponer `stock_qty`, `quantity`, `qty` ni stock numerico en F2. Solo estado visible normalizado. Evidence: `tests/test_adapters.py::test_normalize_strips_extended_raw_stock_aliases`; Codex JSON validation -> `BANNED_FIELD_HITS=0`.
- [x] Mantener cambios pequenos y testeables; preservar F1 catalogo+precio. Evidence: `py_compile` OK, `pytest` 53 passed, dry-run 42 productos con `price != null`.
- [x] Git: rama `codex/competitor-crawler-F2-visible-stock`; `fetch`+rebase antes de commit; push inmediato; nunca force-push. Evidence: rama creada/pushed en `f9a89cc`; pendiente commit final F2 con fetch+rebase inmediatamente antes del commit.

## Acceptance Criteria
- [x] **Contrato visible stock definido.** `stock_status` normalizado a `in_stock|out_of_stock|unknown`; `stock_method` a `visible|unknown`; no `stock_qty`/cantidad. Evidence: `src/stock.py` + `tests/test_stock.py` 26 tests (all variants incl. absence=unknown). Codex `/tmp/f1venv/bin/python -m pytest tests/ -q` -> 53 passed.
- [x] **Extractor/adaptador F2 implementado.** `generic_html`/`BaseSiteAdapter` preserva precio/catalogo F1 y anade stock visible normalizado desde JSON-LD/microdata/HTML publico sin cart. Evidence: `src/extractor.py` (microdata availability href/content), `src/adapters/base.py` (`_normalize` calls `normalize_availability`). Fix: `<meta itemprop="name/price">` content-first extraction.
- [x] **Dry-run F2 auditable.** Existe comando para `leopard.es` que escribe `rso/F2-visible-stock/pilot-visible-stock.json` sin push a Brain. Evidence: `python3 -m src.dry_run --domain leopard.es --limit 50 --output rso/F2-visible-stock/pilot-visible-stock.json` → "Wrote 42 products".
- [x] **Stock visible funciona en piloto.** Dry-run devuelve 42 productos con `title`, `url`, `price != null`, `domain`, `source_id`, `stock_status`, `stock_method`; discard_ratio=0.0, failures=0. Evidence: validation script → "PILOT OK: 42 products, all required fields, no banned fields".
- [x] **Muestra etiquetada de 10 fichas.** `rso/F2-visible-stock/visible-stock-sample.json` contiene 10 URLs reales con `expected_stock_status`, `evidence_snippet` (microdata `<link itemprop="availability" href="http://schema.org/InStock">`), `extracted_stock_status`, `match=true`; coincidencia 10/10. Evidence: validation script → "SAMPLE OK: 10/10 match=true".
- [x] **Cero cart/write.** `SKIP_PATH_HINTS` en `extractor.py` incluye `/cart`,`/checkout`,`/login`,`/account`. No POST/PUT/PATCH/DELETE. No `push_client` en `dry_run.py`. Evidence: grep `src/extractor.py` lines 141-147; `src/dry_run.py` imports.
- [x] **Tests locales pasan.** 53 passed, 0 failed. Tests cubren: `availability→stock_status` (26 parametrized), microdata/JSON-LD, `unknown` por ausencia, no cantidad, F2 contract en adapter y stripping de aliases raw (`stock_qty`, `qty_available`, `units_left`, etc.). Evidence: Codex `/tmp/f1venv/bin/python -m pytest tests/ -q` -> `53 passed in 0.25s`.
- [x] **Sin regresion F1.** `py_compile` OK, `pytest` 53/53, dry-run 42 productos con `price!=null`, `git diff --check` clean. Evidence: Codex re-ejecuto py_compile, pytest, dry-run y `git diff --check` con exit 0.

## Specialist Checks
- [x] **rho-architect** - contrato `stock_status`/`stock_method`, frontera F2 vs F4, compatibilidad F1. Evidence: `rso/F2-visible-stock/architect.report.md`; Codex RSO corrigio mapping documental de `PreOrder`/`BackOrder` para alinearlo con handoff/codigo (`unknown`).
- [x] **rho-backend** - implementacion, tests, dry-run, muestra 10 fichas. Evidence: `rso/F2-visible-stock/backend.report.md` + patch backend stdout; 53 tests pass, 42 productos piloto, 10/10 sample match, git diff --check clean.
- [x] **rho-security** - confirma cero cart/write/login y solo GET publico. Evidence: `rso/F2-visible-stock/security.report.md` -> SECURITY PASS; dry-run sin `push_client`, path F2 solo GET publico.
- [x] **rho-verifier** - verificacion independiente de comandos, artefactos, diff y no-F3/F4/F6/F7. Evidence: `rso/F2-visible-stock/verifier.report.md` -> F2 PASS; re-ejecuto py_compile, pytest, dry-run, JSON validation y `git diff --check`.
- [x] **Codex/RSO auditor** - re-ejecuta evidencia y marca PASS/BLOCKED. Evidence: `rso/F2-visible-stock/codex-audit.report.md`; py_compile OK, pytest 53 passed, dry-run 42 productos, pilot/sample validation PASS, anti-cart/write PASS, diff check OK.

## Status (log datado, append-only)
- 2026-06-24T15:58:00+02:00 - OPEN: F2 abierta tras F1 PASS (`262674f`). Pendiente ejecucion Claude CLI.
- 2026-06-24T16:26:21+02:00 - PASS: backend/security/verifier completados; Codex re-ejecuto evidencia y valida F2. Riesgos residuales: muestra viva solo `in_stock`; `push_client.py` preexistente fuera de path F2 debe auditarse antes de F7.
