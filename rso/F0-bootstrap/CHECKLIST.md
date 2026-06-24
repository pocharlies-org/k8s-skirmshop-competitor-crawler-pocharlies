# RHO Checklist — F0 Bootstrap (lista + fingerprint + índices)

> Formato RHO probado. Fase **F0** del `RSO-MASTER-PLAN.md`. Criterios derivados del plan aprobado §6 (F0) y §8.
> Marca `[x]` SOLO con `Evidence:` directa (comando/archivo/log/Cypher). No debilites ni borres criterios.
> La auditoría de Codex/RSO valida re-ejecutando los comandos de evidencia, no leyendo el texto.

## Objective
- [ ] Dejar F0 lista para auditoría: fuente del crawler en clon local, lista top10 ES/top20 EU validada en `CompetitorSource`, `fingerprint.json` al 100% de dominios, índices del grafo definidos/creados al arrancar el brain, y **cero** requests de escritura/cart a competidores.

## Directives
- [ ] Claude = EJECUTOR bajo la Engineering Constitution (`/home/dibanez/k8s/CLAUDE.md`). Codex = PMO/auditor. No avanzar de fase sin PASS.
- [ ] F0 es **read-only salvo bootstrap** de repo/registry: solo escrituras permitidas = traer la fuente al clon local y poblar/curar `CompetitorSource`. Hacia los competidores, **solo lectura**.
- [ ] **Cero** requests de cart-probe o de escritura contra dominios de competidores en F0 (eso es F4).
- [ ] Fingerprint con Firecrawl en **lectura**, respetando `robots.txt`/`Crawl-delay`, UA honesto, sin eludir challenges ni resolver CAPTCHAs.
- [ ] No re-hardcodear dominios: la fuente única de la lista es Prisma `CompetitorSource`.
- [ ] Git: rama `codex/competitor-crawler-F0-bootstrap`; `fetch`+rebase antes de commit; push inmediato; nunca force-push ni tocar `deploy/prod`.
- [ ] Cero hacks/workarounds; si algo se bloquea, documentar `[blocked]` con motivo y escalar a Codex (p.ej. dominio detrás de CAPTCHA interactivo).

## Acceptance Criteria
- [ ] **Fuente del crawler en clon local.** La fuente de `sauvage:/home/ubuntu/skirmshop/skirmshop-competitor-crawler` está traída al clon local del repo (no solo en sauvage). Evidence: ` ` (listado del árbol importado + comando de transferencia/`git status`).
- [ ] **Lista top10 ES / top20 EU derivada por tráfico real + curación.** Derivada con MCP SimilarWeb y validada por el usuario (no inventada). Evidence: ` ` (artefacto de derivación SimilarWeb + lista de validación aprobada por el usuario).
- [ ] **Lista poblada en `CompetitorSource` (fuente única).** Las 30 fuentes (10 ES + 20 EU) curadas están en Prisma `CompetitorSource`, no re-hardcodeadas. Evidence: ` ` (query a `CompetitorSource` / `GET /api/competitors` mostrando los registros).
- [ ] **`fingerprint.json` cubre el 100% de los dominios.** Un registro por cada dominio de la lista, sin omisiones. Evidence: ` ` (recuento `dominios en fingerprint.json` == `dominios en CompetitorSource`).
- [ ] **Cada fingerprint trae todos los campos.** `platform`, `tier(green|yellow|red)`, `has_structured_data`, `has_visible_stock`, `robots_crawl_delay`, `antibot` presentes en cada entrada. Evidence: ` ` (validación de esquema sobre `fingerprint.json`).
- [ ] **`silverback-airsoft.com = red`.** Clasificado `tier=red` por Cloudflare + CAPTCHA interactivo. Evidence: ` ` (entrada de `silverback-airsoft.com` en `fingerprint.json`).
- [ ] **Recuento por tier.** Conteo de dominios por `tier` (green/yellow/red) reportado. Evidence: ` ` (agregación sobre `fingerprint.json`).
- [ ] **Índices del grafo definidos/creados al arrancar el brain.** `Product.id`, `Product.sku`, `CompetitorProduct.*` definidos y creados al startup del brain. Evidence: ` ` (Cypher `SHOW INDEXES` / equivalente mostrando los índices existentes).
- [ ] **Cero requests de escritura/cart a competidores en F0.** Ninguna petición de cart-probe ni de escritura hacia dominios de competidores durante F0. Evidence: ` ` (logs/métricas del run F0 sin requests de cart/escritura; revisión de los comandos ejecutados).

## Specialist Checks
- [ ] **rho-researcher** — inventario de la fuente del crawler en sauvage y su importación al clon local. Evidence: ` ` (`rso/F0-bootstrap/researcher.report.md`).
- [ ] **rho-architect** — esquema de `fingerprint.json` (campos/tipos) + definición de índices del grafo al arranque del brain. Evidence: ` ` (`rso/F0-bootstrap/architect.report.md`).
- [ ] **rho-security** — postura anti-bot/robots: tiers, `silverback=red`, `Crawl-delay` honrado, sin eludir challenges, cero cart/escritura en F0. Evidence: ` ` (`rso/F0-bootstrap/security.report.md`).
- [ ] **Codex (auditor/verifier)** — PASS/FAIL independiente re-ejecutando los comandos de evidencia (no leyendo el texto). Evidence: ` ` (entrada datada en Status con `PASS`/devolución).

## Status (log datado, append-only)
- 2026-06-24T02:06:11+02:00 — OPEN: artefactos F0 bootstrap preparados. Claude CLI produjo `RSO-MASTER-PLAN.md` y `rso/F0-bootstrap/CHECKLIST.md` tras dos intentos inicialmente mudos, pero no devolvió report ni creó `HANDOFF.md`; Codex/RSO completó `rso/F0-bootstrap/HANDOFF.md` como excepción limitada a documentación de orquestación, no código de producto. Todos los criterios F0 siguen en `[ ]`, pendientes de ejecución por Claude y auditoría Codex.
