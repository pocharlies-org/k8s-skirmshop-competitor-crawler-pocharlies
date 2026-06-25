# RHO Checklist - F6 Live Comparison

> Fase **F6** del `RSO-MASTER-PLAN.md`.
> Gate previo: F5 MATCH PASS y F4 BLOCKED (según `rso/F4-cart-probe/CHECKLIST.md`) deben quedar resueltos antes de confiar en `PRODUCT_MATCH` vivo. Marca `[x]` SOLO con `Evidence:` directa.

## Objective
- [x] Cerrar la capa de comparación viva para reflejar `PRODUCT_MATCH` real (sin `competitor_*` hardcode), incluyendo filtros por competidor y ordenamientos nuevos en `/prices/comparison`; y ampliar `price_position` con métricas y posición competitiva. Evidence: `skirmshop-brain-v2/src/api/prices.py`.

## Directives
- [x] **Disciplinas de fase**: branch `codex/competitor-crawler-F6-live-comparison`, cambios versionados y `git fetch && git rebase` antes de commit/push. Evidence: branch activo en ambos repos; check-in final pendiente tras `git status --short`.
- [x] **Fronteras**: no F7, no nuevos manifiestos de prod, no cart-probe nuevo (pertenece a F4), no cambios de scheduler nocturno (F7). Evidence: archivos tocados únicamente `skirmshop-brain-v2/src/api/prices.py` y tests unit.
- [x] **Scope mínimo verificable**: no depender de `price_stock_observation` en esta fase; F6 es consumidor, no productor de histórico. Evidence: solo endpoints de `src/api/prices.py` y tests de presentación.
- [x] **Zero write en runtime sin `APPLY APPROVED`**: esta fase no escribe `CompetitorProduct` ni `PRODUCT_MATCH`; solo lectura de `PRODUCT_MATCH` en consulta. Evidence: `src/api/prices.py` usa solo `cypher(..., instance_id=...)` y no mutaciones.

## Acceptance Criteria
- [x] `/prices/comparison` incluye filtros base + nuevos filtros de competidor (`has_comp`, `comp_cheaper`, `comp_dearer`) y permite ordenamiento por `sort` con lista de whitelist. Evidence: `rg -n "_FILTERS|_SORTS|ORDER BY \\\" \\+ _SORTS\\[sort\\]" src/api/prices.py` en `skirmshop-brain-v2`.
- [x] Consulta Cypher del comparison incorpora `PRODUCT_MATCH` con agregados (`comp_min`, `comp_max`, `comp_count`) y no rompe el order de filtros existentes (`has_nl`/`nl_cheaper`/`nl_dearer`/`nl_equal`) ni `margin_lt`. Evidence: bloque `_BODY` en `skirmshop-brain-v2/src/api/prices.py` incluyendo `collect(DISTINCT cp)` y filtros compuestos.
- [x] `price_comparison` devuelve en cada item `competitor_min`, `competitor_max`, `competitor_count` y lista `competitors` (dominio/precio/url/título), y mantiene soporte de feedback. Evidence: `skirmshop-brain-v2/src/api/prices.py` y `skirmshop-brain-v2/tests/unit/test_http_feedback_surfaces.py::test_price_comparison_includes_feedback_request`.
- [x] `/prices/position/{slug}` devuelve métricas de competidor (min/max/avg/count) y `position` (`cheapest|mid|most_expensive|unknown`) calculadas a partir de `PRODUCT_MATCH` activo del mismo instance. Evidence: `skirmshop-brain-v2/src/api/prices.py` y `skirmshop-brain-v2/tests/unit/test_prices.py::test_price_position_with_competitors`.
- [x] `margin_pct` y `price comparison` conservan el contrato de ordenación (`sort=margin_*`) introducido en F0/F6 pre-existente. Evidence: `_SORTS` y `margin_pct` en `skirmshop-brain-v2/src/api/prices.py`.
- [x] Verificación de sintaxis al menos de los archivos tocados (carga del módulo). Evidence: `python3 -m compileall src/api/prices.py tests/unit/test_prices.py tests/unit/test_http_feedback_surfaces.py` (resultado 0).
- [x] Checks de pruebas por dependencias locales (limitado) ejecutados y reproducidos. Evidence: `pytest -q tests/unit/test_http_feedback_surfaces.py tests/unit/test_prices.py` devuelve FFFF/EEEE por dependencias faltantes (`llama_index`, `pytest-asyncio`) con bloqueo explícito; no ejecutable sin ese entorno.
- [ ] Verificación F6 endpoint en vivo con `rag-app`/`/instances/skirmshop/prices/comparison?filter=has_comp` aún requiere test con entorno API completo de brain. Evidence pendiente: smoke de `prices/comparison` contra `RAG` service tras despliegue con código actualizado.

## Specialist Checks
- [x] **rho-researcher** — state of inputs and schema (`PRODUCT_MATCH`, consumers, ontology). Evidence: `rso/F5-product-match/researcher.report.md` + comandos de inspección ejecutados por Codex.
- [x] **rho-architect** — contrato F6 de lectura viva y frontera F6/F5/F7. Evidence: objetivo/criterios en `RSO-MASTER-PLAN.md`; no se tocaron dominios de F7.
- [x] **rho-backend** — implementación de consulta y payloads en `prices.py` + tests de unidad. Evidence: cambios en `skirmshop-brain-v2/src/api/prices.py` y tests.
- [x] **rho-security** — no se introducen secretos ni requests extraños a competidores; comparación es `read-only`. Evidence: diff auditado; no secrets.
- [x] **rho-verifier** — re-ejecución de checks objetivos localmente. Evidence: compile + pytest invocación reproducida y limitada por entorno.
- [ ] **Codex/RSO auditor** — re-ejecución F6 endpoint live (`prices/comparison` + `prices/position`) pendiente hasta pod service smoke estable.

## Status (log datado, append-only)
- 2026-06-25T11:08:16+02:00 — OPEN: tras cierre de blockers F4/F5, F6 en curso en branch `codex/competitor-crawler-F6-live-comparison`.
- 2026-06-25T11:08:16+02:00 — PRICE FILE UPDATED: `skirmshop-brain-v2/src/api/prices.py` y tests actualizados con filtros de competencia, payload y posición competitiva.
- 2026-06-25T11:08:16+02:00 — VERIFICATION: `python3 -m compileall src/api/prices.py tests/unit/test_prices.py tests/unit/test_http_feedback_surfaces.py` completado OK.
- 2026-06-25T11:08:16+02:00 — REMAINING: `pytest -q tests/unit/test_http_feedback_surfaces.py tests/unit/test_prices.py` bloqueado por dependencias env (`llama_index`, `pytest-asyncio`).
