# RHO Checklist - F2 Visible Stock

> Fase **F2** del `RSO-MASTER-PLAN.md`.
> Gate previo: F1 PASS en commit `262674f` (`codex/competitor-crawler-F1-catalog-price`), confirmado por Codex con remoto alineado.
> Marca `[x]` SOLO con `Evidence:` directa (comando/archivo/log/output). No abrir F3/F4/F6/F7 sin PASS de Codex.

## Objective
- [ ] Implementar stock visible para dominio piloto `green` (`leopard.es`) sin cart-probe: cada producto del dry-run debe exponer `stock_status in {in_stock,out_of_stock,unknown}` y `stock_method in {visible,unknown}`, con 10 fichas inspeccionadas manualmente y coincidencia extractor vs muestra etiquetada. Evidence:

## Directives
- [ ] Claude CLI = EJECUTOR; Codex = RSO/PMO/auditor. Claude implementa y prueba; Codex re-ejecuta evidencia antes de abrir F3/F4/F6/F7.
- [ ] No tocar `deploy/prod`, k8s manifests, imagenes, CronJobs ni produccion nocturna en F2.
- [ ] F2 es **stock visible**. Prohibido historico append-only (F3), cart-probe/cantidad exacta/carrito (F4), matching `PRODUCT_MATCH` (F5), comparacion viva (F6), scheduling nocturno (F7).
- [ ] Hacia competidores: solo `GET` de catalogo/producto publico. Prohibido `cart`, `checkout`, `login`, `account`, POST/PUT/PATCH/DELETE o resolver CAPTCHA.
- [ ] No inferir agotado por ausencia de dato: si no hay evidencia visible/estructurada, `stock_status=unknown`.
- [ ] No exponer `stock_qty`, `quantity`, `qty` ni stock numerico en F2. Solo estado visible normalizado.
- [ ] Mantener cambios pequenos y testeables; preservar F1 catalogo+precio.
- [ ] Git: rama `codex/competitor-crawler-F2-visible-stock`; `fetch`+rebase antes de commit; push inmediato; nunca force-push.

## Acceptance Criteria
- [ ] **Contrato visible stock definido.** `stock_status` normalizado a `in_stock|out_of_stock|unknown`; `stock_method` a `visible|unknown`; no `stock_qty`/cantidad. Evidence:
- [ ] **Extractor/adaptador F2 implementado.** `generic_html`/`BaseSiteAdapter` preserva precio/catalogo F1 y anade stock visible normalizado desde JSON-LD/microdata/HTML publico sin cart. Evidence:
- [ ] **Dry-run F2 auditable.** Existe comando para `leopard.es` que escribe `rso/F2-visible-stock/pilot-visible-stock.json` sin push a Brain. Evidence:
- [ ] **Stock visible funciona en piloto.** Dry-run devuelve >=10 productos con `title`, `url`, `price != null`, `domain`, `source_id`, `stock_status`, `stock_method`; ratio fallos <20%. Evidence:
- [ ] **Muestra etiquetada de 10 fichas.** `rso/F2-visible-stock/visible-stock-sample.json` contiene 10 URLs reales con `expected_stock_status`, evidencia visible/estructurada (`evidence_snippet` o selector), `extracted_stock_status`, `match=true`; coincidencia 10/10 o blocker explicado. Evidence:
- [ ] **Cero cart/write.** No hay rutas `cart/checkout/login/account`, no POST/PUT/PATCH/DELETE a competidores, no Brain push. Evidence:
- [ ] **Tests locales pasan.** Tests unitarios cubren mapping `availability -> stock_status`, microdata/JSON-LD visible stock, `unknown` por ausencia de dato, y no cantidad. Evidence:
- [ ] **Sin regresion F1.** `py_compile`, `pytest`, dry-run F1/F2 y `git diff --check` pasan; F1 catalogo+precio sigue produciendo >=10 productos. Evidence:

## Specialist Checks
- [ ] **rho-architect** - contrato `stock_status`/`stock_method`, frontera F2 vs F4, compatibilidad F1. Evidence:
- [ ] **rho-backend** - implementacion, tests, dry-run, muestra 10 fichas. Evidence:
- [ ] **rho-security** - confirma cero cart/write/login y solo GET publico. Evidence:
- [ ] **rho-verifier** - verificacion independiente de comandos, artefactos, diff y no-F3/F4/F6/F7. Evidence:
- [ ] **Codex/RSO auditor** - re-ejecuta evidencia y marca PASS/BLOCKED. Evidence:

## Status (log datado, append-only)
- 2026-06-24T15:58:00+02:00 - OPEN: F2 abierta tras F1 PASS (`262674f`). Pendiente ejecucion Claude CLI.
