# RHO Checklist - F1 Catalog + Price

> Fase **F1** del `RSO-MASTER-PLAN.md`.
> Gate previo: F0 PASS en `rso/F0-bootstrap/CHECKLIST.md` (2026-06-24T14:25:00+02:00).
> Marca `[x]` SOLO con `Evidence:` directa (comando/archivo/log/output). No abrir F2/F5 sin PASS de Codex.

## Objective
- [ ] Implementar catálogo + precio para 1 dominio piloto `green` mediante un framework `BaseSiteAdapter` JSON-first, con `dry-run` auditable que devuelva >=10 productos con `price != null`, ratio de fallos <20%, 5 ejemplos, y cero cart/checkout/login/write.

## Directives
- [ ] Claude CLI = EJECUTOR; Codex = RSO/PMO/auditor. Claude implementa, testea, marca evidencia y pushea; Codex re-ejecuta evidencia antes de abrir F2/F5.
- [ ] No tocar `deploy/prod`, k8s manifests, imágenes, CronJobs ni producción nocturna en F1.
- [ ] F1 es catálogo + precio. No implementar stock visible (F2), histórico append-only (F3), cart-probe (F4), matching `PRODUCT_MATCH` (F5), comparación viva (F6), ni scheduling nocturno (F7).
- [ ] Hacia competidores: solo `GET` de catálogo/producto público. Prohibido `cart`, `checkout`, `login`, `account`, POST/PUT/PATCH/DELETE o resolver CAPTCHA.
- [ ] No ampliar `config.yaml` como fuente de verdad. Usar `CompetitorSource`/`GET /api/competitors` o un input explícito de dominio para el piloto; el JSON F0 es artefacto auditado, no runtime source.
- [ ] Mantener cambios pequeños y testeables; preservar APIs existentes salvo que el refactor esté cubierto por tests.
- [ ] Git: rama `codex/competitor-crawler-F1-catalog-price`; `fetch`+rebase antes de commit; push inmediato; nunca force-push.

## Acceptance Criteria
- [ ] **Diseño `BaseSiteAdapter` incorporado.** Existe una abstracción clara para catálogo+precio (`list_products()` o equivalente) y adaptadores JSON-first al menos para `generic_html`, con espacio compatible para Shopify/WooCommerce sin duplicar BFS/extractor. Evidence:
- [ ] **Dominio piloto `green` seleccionado desde F0.** El ejecutor registra el piloto elegido entre los dominios `tier=green` de `data/competitors/fingerprint.json`, con motivo y preflight read-only. Evidence:
- [ ] **Dry-run auditable.** Existe comando documentado para ejecutar 1 dominio sin push a Brain y escribir un artefacto JSON en `rso/F1-catalog-price/pilot-smoke.json` o similar. Evidence:
- [ ] **Catálogo + precio funciona en piloto.** El dry-run del dominio piloto devuelve >=10 productos con `title`, `url`, `price != null`, `domain`, `source_id` estable; ratio de productos descartados/fallidos <20%. Evidence:
- [ ] **5 ejemplos incluidos.** `rso/F1-catalog-price/backend.report.md` incluye 5 productos reales del piloto con `title`, `price`, `url`. Evidence:
- [ ] **Cero stock/cart/write.** F1 no hace cart-probe ni escritura a competidores; no toca checkout/login/account; no hace push a Brain en el smoke salvo que se ejecute explícitamente fuera del gate. Evidence:
- [ ] **Tests locales pasan.** Tests unitarios/capa adapter cubren parsing de precio y extracción; suite relevante pasa. Evidence:
- [ ] **Sin regresión de bootstrap.** `python -m py_compile src/*.py tests/*.py` y `pytest` pasan; `git diff --check` limpio. Evidence:

## Specialist Checks
- [ ] **rho-researcher** - preflight read-only de dominios `green`, selección de piloto, riesgos anti-bot y rutas públicas.
- [ ] **rho-architect** - diseño adapter/data contract, source_id estable, frontera F1/F2/F4.
- [ ] **rho-backend** - implementación, tests, dry-run, smoke artefacto.
- [ ] **rho-security** - confirma cero cart/checkout/login/write y solo GET público.
- [ ] **rho-verifier** - verificación independiente de comandos, artefactos, diff y no-F2/F4.
- [ ] **Codex/RSO auditor** - re-ejecuta evidencia y marca PASS/BLOCKED.

## Status (log datado, append-only)
- 2026-06-24T14:30:00+02:00 - OPEN: F1 abierta tras F0 PASS. Pendiente ejecución Claude CLI.
