# HANDOFF - F2 Visible Stock

ROL: Claude CLI = EJECUTOR. Codex = RSO/PMO/auditor. Implementa directamente, no re-delegues fuera de los roles `rho-*` si los usas.

REPO: `/home/dibanez/k8s/k8s-skirmshop-competitor-crawler-pocharlies`
RAMA: `codex/competitor-crawler-F2-visible-stock`

ANTES:
1. `git fetch origin && git pull --rebase --autostash`
2. Confirma que estas en `codex/competitor-crawler-F2-visible-stock`.
3. Lee `RSO-MASTER-PLAN.md`, `rso/F2-visible-stock/CHECKLIST.md`, `rso/F1-catalog-price/codex-audit.report.md`, `src/extractor.py`, `src/adapters/base.py`, `src/adapters/generic_html.py`, `src/dry_run.py`, `tests/test_adapters.py`.

OBJETIVO F2:
Implementar **stock visible** para el piloto `leopard.es` sin cart-probe. El dry-run F2 debe exponer `stock_status in {in_stock,out_of_stock,unknown}` y `stock_method in {visible,unknown}` para productos de catalogo/precio, y demostrar coincidencia con una muestra etiquetada de 10 fichas reales.

SCOPE PERMITIDO:
- `src/**`
- `tests/**`
- `rso/F2-visible-stock/**`
- `requirements.txt` solo si imprescindible

PROHIBIDO:
- `deploy/prod`, k8s manifests, imagenes, CronJobs, produccion nocturna.
- Historico/F3, cart-probe/F4, matching/F5, comparacion/F6, scheduling/F7.
- Cualquier `cart`, `checkout`, `login`, `account`, POST/PUT/PATCH/DELETE o CAPTCHA solving contra competidores.
- Push a Brain en el smoke.
- Exponer `stock_qty`, `quantity`, `qty` o stock numerico en F2.

REQUISITOS DE IMPLEMENTACION:
- Define contrato F2: `stock_status = in_stock|out_of_stock|unknown`, `stock_method = visible|unknown`.
- Normaliza `schema.org` availability (`InStock`, `LimitedAvailability`, `OutOfStock`, `SoldOut`, `PreOrder`, etc.) y equivalentes visibles; si no hay evidencia, `unknown`.
- Mantiene F1: `title`, `url`, `price`, `domain`, `source_id` siguen presentes y `price != null` para el piloto.
- El adapter puede preservar raw `availability` internamente si hace falta, pero el artefacto final debe exponer solo `stock_status`/`stock_method`, no raw availability ni cantidad.
- Genera `rso/F2-visible-stock/pilot-visible-stock.json`.
- Genera `rso/F2-visible-stock/visible-stock-sample.json` con 10 URLs reales: `url`, `expected_stock_status`, `evidence_snippet` o selector, `extracted_stock_status`, `match`.
- Escribe reportes en `rso/F2-visible-stock/` (`architect.report.md`, `backend.report.md`, `security.report.md`, `verifier.report.md` segun aplique) y marca Evidence en `CHECKLIST.md`.

COMANDOS ESPERADOS:
- `python -m py_compile src/extractor.py src/adapters/base.py src/adapters/generic_html.py src/dry_run.py tests/test_extractor.py tests/test_adapters.py`
- `pytest tests/ -q`
- `python -m src.dry_run --domain leopard.es --limit 50 --output rso/F2-visible-stock/pilot-visible-stock.json`
- Validacion JSON: >=10 productos, `stock_status`/`stock_method` presentes, sin stock numerico, sample 10/10.
- `git diff --check`

GIT:
`fetch`+rebase antes de commit, commit atomico, push inmediato a `codex/competitor-crawler-F2-visible-stock`, nunca force-push.

SALIDA ESPERADA:
Resumen, archivos tocados, comandos+resultados, checklist PASS/FAIL, riesgos residuales. NO empieces F3/F4/F5/F6/F7.
