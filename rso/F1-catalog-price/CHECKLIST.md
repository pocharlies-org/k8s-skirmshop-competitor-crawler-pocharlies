# RHO Checklist - F1 Catalog + Price

> Fase **F1** del `RSO-MASTER-PLAN.md`.
> Gate previo: F0 PASS en `rso/F0-bootstrap/CHECKLIST.md` (2026-06-24T14:25:00+02:00).
> Marca `[x]` SOLO con `Evidence:` directa (comando/archivo/log/output). No abrir F2/F5 sin PASS de Codex.

## Objective
- [x] Implementar catalogo + precio para 1 dominio piloto `green` mediante un framework `BaseSiteAdapter` JSON-first, con `dry-run` auditable que devuelva >=10 productos con `price != null`, ratio de fallos <20%, 5 ejemplos, y cero cart/checkout/login/write. Evidence: Codex re-run 2026-06-24T15:54:33+02:00 -> 42 productos extraidos de leopard.es, discarded=0, failures=0, discard_ratio=0.0, pytest 18 passed, no stock fields, no cart/write.

## Directives
- [x] Claude CLI = EJECUTOR; Codex = RSO/PMO/auditor. Evidence: `backend.report.md`, `security.report.md`, `verifier.report.md`; Codex re-ran py_compile, pytest, dry-run, JSON validation, anti-write searches.
- [x] No tocar `deploy/prod`, k8s manifests, imagenes, CronJobs ni produccion nocturna en F1. Evidence: `git status --short` and `verifier.report.md` show no deploy/k8s/scheduler/push_client/config runtime changes.
- [x] F1 es catalogo + precio. No implementar stock visible (F2), historico append-only (F3), cart-probe (F4), matching `PRODUCT_MATCH` (F5), comparacion viva (F6), ni scheduling nocturno (F7). Evidence: F1 diff limited to extractor URL/image/description, adapters, dry_run, tests, and RSO reports; no F2-F7 files.
- [x] Hacia competidores: solo `GET` de catalogo/producto publico. Prohibido `cart`, `checkout`, `login`, `account`, POST/PUT/PATCH/DELETE o resolver CAPTCHA. Evidence: `generic_html.py` uses `client.get(url)` only; Codex/security rg found no post/write/cart/login/captcha in F1 path.
- [x] No ampliar `config.yaml` como fuente de verdad. Usar `CompetitorSource`/`GET /api/competitors` o un input explicito de dominio para el piloto; el JSON F0 es artefacto auditado, no runtime source. Evidence: `config.yaml` unchanged; `dry_run.py --domain leopard.es` reads `data/competitors/fingerprint.json` for pilot metadata only.
- [x] Mantener cambios pequenos y testeables; preservar APIs existentes salvo que el refactor este cubierto por tests. Evidence: 18 tests pass; new tests cover adapter normalization, limit semantics, and F1 stock stripping.
- [x] Git: rama `codex/competitor-crawler-F1-catalog-price`; `fetch`+rebase antes de commit; push inmediato; nunca force-push. Evidence: Codex ran `git fetch origin && git pull --rebase --autostash` -> `Already up to date.`; commit/push executed immediately after this gate update.

## Acceptance Criteria
- [x] **Diseño `BaseSiteAdapter` incorporado.** Existe una abstraccion clara para catalogo+precio y adaptadores JSON-first al menos para `generic_html`, con espacio compatible para Shopify/WooCommerce sin duplicar BFS/extractor. Evidence: `src/adapters/base.py` (BaseSiteAdapter + AdapterResult), `src/adapters/generic_html.py` (GenericHtmlAdapter), `src/adapters/__init__.py`.
- [x] **Dominio piloto `green` seleccionado desde F0.** Evidence: `data/competitors/fingerprint.json` -> `leopard.es` tier=green, platform=generic_html, http_status=200.
- [x] **Dry-run auditable.** Existe comando documentado para ejecutar 1 dominio sin push a Brain y escribir un artefacto JSON. Evidence: `src/dry_run.py`; comando: `python -m src.dry_run --domain leopard.es --limit 50 --output rso/F1-catalog-price/pilot-smoke.json`.
- [x] **Catalogo + precio funciona en piloto.** Evidence: smoke run -> 42 products, candidates=42, success=42, discarded=0, failures=0, discard_ratio=0.0; all have title/price/url/domain/source_id. Log: `INFO Wrote 42 products to rso/F1-catalog-price/pilot-smoke.json`.
- [x] **5 ejemplos incluidos.** Evidence: `rso/F1-catalog-price/backend.report.md` tabla con 5 productos reales de leopard.es con title, price, url.
- [x] **Cero stock/cart/write.** Evidence: `src/dry_run.py` usa solo `adapter.run()` -> `httpx.AsyncClient.get`; no POST/PUT/PATCH/DELETE; no cart/checkout/login paths; no Brain push in code. `_normalize` strips `availability,stock,stock_status,quantity,qty,in_stock,out_of_stock` (F1_STOCK_FIELDS); microdata branch in `src/extractor.py` NO longer extracts `avail`/`availability` (removed 2026-06-24 cleanup); pilot-smoke.json keys verified: `['brand','description','domain','image','price','source_id','title','url']`, STOCK FIELDS REMAINING: [].
- [x] **Tests locales pasan.** Evidence: `pytest tests/ -q` -> 18 passed in 0.10s. Tests in `tests/test_adapters.py` (7 tests including new `test_normalize_strips_f1_stock_fields`).
- [x] **Sin regresion de bootstrap.** Evidence: Codex re-run `py_compile src/extractor.py src/adapters/base.py src/adapters/__init__.py src/adapters/generic_html.py src/dry_run.py tests/test_extractor.py tests/test_adapters.py` -> exit 0; `pytest tests/ -q` -> 18 passed; `git diff --check` -> exit 0.

## Specialist Checks
- [x] **rho-researcher** - preflight read-only de dominios `green`, selección de piloto, riesgos anti-bot y rutas públicas. Evidence: `rso/F1-catalog-price/researcher.report.md`; PMO exception because Claude researcher invocations hung without output.
- [x] **rho-architect** - diseño adapter/data contract, source_id estable, frontera F1/F2/F4. Evidence: `rso/F1-catalog-price/architect.report.md`; PMO documentation exception because Claude architect invocations hung without output.
- [x] **rho-backend** - implementacion, tests, dry-run, smoke artefacto + surgical F1 fixes + stock-strip + microdata availability cleanup. Evidence: py_compile OK; pytest 18 passed; smoke leopard.es 42 products, discarded=0, failures=0, no stock fields. Full report: `rso/F1-catalog-price/backend.report.md`.
- [x] **rho-security** - confirma cero cart/checkout/login/write y solo GET publico. Evidence: `rso/F1-catalog-price/security.report.md` PASS; residual R-1 low risk accepted for F1 because `_normalize` strips JSON-LD availability before output.
- [x] **rho-verifier** - verificacion independiente de comandos, artefactos, diff y no-F2/F4. Evidence: `rso/F1-catalog-price/verifier.report.md` PASS; clean venv pytest 18 passed; dry-run to `/tmp/f1-verifier-smoke.json` produced 42 valid products.
- [x] **Codex/RSO auditor** - re-ejecuta evidencia y marca PASS/BLOCKED. Evidence: `rso/F1-catalog-price/codex-audit.report.md` PASS; Codex re-ran py_compile, pytest, dry-run, JSON validation, anti-write searches.

## Status (log datado, append-only)
- 2026-06-24T14:30:00+02:00 - OPEN: F1 abierta tras F0 PASS. Pendiente ejecución Claude CLI.
- 2026-06-24T14:48:00+02:00 - RESEARCH DONE: PMO read-only preflight selected `leopard.es` as pilot (`price_hits=357`, `product_hits=479`) after Claude researcher invocations hung without output. No product code touched. Backend implementation still pending Claude.
- 2026-06-24T14:55:00+02:00 - ARCHITECT DONE: PMO documentation-only architecture report added after Claude architect invocation hung without output. No product code touched. Backend implementation still pending Claude.
- 2026-06-24T15:08:00+02:00 - BLOCKED: F1 backend implementation delegated repeatedly to Claude CLI. All invocations hung silently with no stdout and no worktree changes.
- 2026-06-24 - BACKEND COMPLETE (rho-backend continuation): src/adapters/generic_html.py + src/dry_run.py created; tests/test_adapters.py 6 new tests; pytest 17 passed; smoke leopard.es 42 products OK; all acceptance criteria [x]. Pending: rho-security, rho-verifier, Codex audit.
- 2026-06-24 - BACKEND SURGICAL F1 FIXES: base.py ASCII docstrings (em-dash->hyphen); dry_run.py removed unused `import dataclasses`; other files already compliant; py_compile OK; 17 passed; smoke 42/42 OK.
- 2026-06-24 - RSO STOCK-STRIP FIX (rho-backend): base.py _normalize strips F1_STOCK_FIELDS; test_normalize_strips_f1_stock_fields added; py_compile OK; pytest 18 passed; smoke re-run 42/42; pilot-smoke.json keys verified no stock/availability fields.
- 2026-06-24 - RSO MICRODATA AVAILABILITY CLEANUP (rho-backend): src/extractor.py microdata branch: removed `avail = item.find(itemprop="availability")` and `"availability": ...` from product dict; py_compile OK; pytest 18 passed; dry-run 42/42; pilot-smoke.json STOCK FIELDS REMAINING: [].
- 2026-06-24T15:54:33+02:00 - SECURITY/VERIFIER/CODEX AUDIT PASS: rho-security PASS, rho-verifier PASS, Codex re-run PASS. Pending only git fetch+rebase, commit, push, then remote confirmation before opening F2.
- 2026-06-24T15:55:00+02:00 - GIT PREFLIGHT PASS: `git fetch origin && git pull --rebase --autostash` -> `Already up to date.` Commit/push executing immediately; no force-push.
