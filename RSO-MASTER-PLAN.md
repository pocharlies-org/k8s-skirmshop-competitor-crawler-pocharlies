# RSO Master Plan — Skirmshop Competitor Crawler (airsoft: precio · stock · histórico)

> **Propietario del documento:** Codex (PMO/auditor RSO). Versionado y auditable en el repo del crawler.
> **Ejecutor:** Claude (Engineering Constitution de `/home/dibanez/k8s/CLAUDE.md`).
> **Fuente de verdad de este plan:** plan aprobado `/home/dibanez/.claude/plans/haz-uan-auditoria-completa-majestic-cherny.md`.
> No se inventan fases ni criterios fuera del plan aprobado. Cada fase cierra con auditoría independiente de Codex que **re-ejecuta** la evidencia (no lee solo el texto).

---

## 1. Objetivo global

Monitorizar a los competidores airsoft de Skirmshop (**top 10 España + top 20 Europa**) para:

1. Tener la lista de **todos** sus productos con precios.
2. Saber si nosotros tenemos ese mismo producto y comparar precios (matching producto↔producto).
3. Crawlear cada noche (scheduling nocturno escalonado, no-DoS).
4. Saber si tienen stock — por **stock visible** o, si no, **probando cuántas unidades deja añadir al carrito vía JS** (límite = stock).
5. Construir un **histórico de stock** para estimar ventas (delta de stock entre noches ≈ unidades vendidas).

**Hallazgo central de la auditoría:** no se construye desde cero. Existe ya un esqueleto sustancial
(Firecrawl headless en prod, crawler de competidores k8s desactivado `replicas:0`/img `:pending`,
brain v2 con 43.497 `CompetitorProduct`, endpoint de comparación de precios esperando datos,
registry `CompetitorSource`). El trabajo es **reactivar/extender** el crawler, **añadir detección de
stock**, **añadir histórico temporal real** y **poblar el matching producto↔producto**.

---

## 2. Modelo operativo Codex (PMO/auditor) ↔ Claude (ejecutor)

- **Codex (PMO/auditor):** scope, descomposición, criterios de aceptación, decisiones de riesgo
  (¿cart-probe en dominio X?), gate entre fases, auditoría independiente. **No implementa código de producto.**
- **Claude (ejecutor):** research read-only primero; implementación con subagentes `rho-*` cuando la
  fase toca ≥2 especialidades; tests + evidencia reproducible. **Security** obligatorio
  (anti-bot/egress/secrets); **DevOps** obligatorio (k8s/CronJob/ESO/ArgoCD); **Architect** para
  contratos de datos/API.
- **Usuario:** hace de **relé** del `HANDOFF.md` de cada fase entre Codex y Claude.

### 2.1 Ciclo por fase
1. Codex planifica fase N → escribe/actualiza `RSO-MASTER-PLAN.md` + `rso/F{N}-<slug>/CHECKLIST.md`
   (criterios en `[ ]`) + `rso/F{N}-<slug>/HANDOFF.md`; commit+push.
2. **Usuario relé:** pasa el `HANDOFF.md` a Claude.
3. Claude: `fetch`+rebase → research read-only → implementación por especialidad
   (`rho-architect/backend/devops/security`) → tests → marca `[x]` con `Evidence:` +
   escribe `rso/F{N}-<slug>/<rol>.report.md`; commit+push inmediato.
4. Codex (auditor): `fetch` → **re-ejecuta los comandos de evidencia** (no lee el texto),
   inspecciona estado real (Cypher, manifiesto aplicado, secreto por nombre) → `Status: PASS`
   y abre F{N+1}, o devuelve a `[ ]`/`[blocked]` con motivo.

### 2.2 Artefactos por fase (en este repo, versionados)
- `RSO-MASTER-PLAN.md` — este documento (objetivo global, fases, orden, gates). Propiedad de Codex.
- `rso/F{N}-<slug>/CHECKLIST.md` — formato RHO: `Objective / Directives / Acceptance Criteria
  [ ]·[x]·[blocked] con Evidence: / Specialist Checks / Status (log datado append-only)`.
- `rso/F{N}-<slug>/HANDOFF.md` — el mensaje que el usuario relé a Claude.
- `rso/F{N}-<slug>/<rol>.report.md` — evidencia detallada del ejecutor
  (architect/backend/devops/security/verifier).

---

## 3. Arquitectura objetivo (resumen — fronteras que condicionan las fases)

- **EXTENDER** `skirmshop-competitor-crawler` (traer fuente de sauvage → clon local → repo) a
  catálogo + precio + stock visible, refactorizado a `BaseSiteAdapter` JSON-first
  (`ShopifyAdapter` `/products.json`, `WooCommerceAdapter` Store API, `GenericHtmlAdapter` BFS+JSON-LD).
- **NUEVO microservicio `skirmshop-stock-prober`** (cart-probe Playwright): coupling distinto
  (sesión-carrito/riesgo de ban) → blast-radius y egress aislados.
- **NUEVA DB Postgres append-only `competitor_intel`** (histórico, particionada por mes). El grafo es
  solo "último estado".
- **REUTILIZAR:** grafo brain v2 (estado vigente), `prices.py`/`intel.py` (lectura/alertas),
  `CompetitorSource` (registry), matcher SKU/título + TEI BGE/reranker (matching).

**Frontera dura:** histórico → **solo Postgres append-only**; grafo → **solo precio/stock vigente**;
ventas estimadas → delta sobre Postgres. Nunca inferir "agotado" por ausencia de dato
(`stock_status: in_stock|out_of_stock|unknown` con timestamps).

**Postura anti-bot por tiers:** Tier 0 datos estructurados públicos (preferido) → Tier 1 render
headless de catálogo público → Tier 2 cart-probe (solo donde T0/T1 no dan stock, con rails
no-DoS). Cloudflare con CAPTCHA interactivo = `red`: no forzar, marcar `blocked_by_antibot`, escalar.

---

## 4. Fases, orden y gates

> Cada fase cierra con auditoría independiente de Codex re-ejecutando la evidencia.
> El detalle testable de cada fase vive en su `rso/F{N}-<slug>/CHECKLIST.md`.

### F0 — Bootstrap + lista + fingerprint + índices **(GATE)**
Traer fuente del crawler de `sauvage:/home/ubuntu/skirmshop/skirmshop-competitor-crawler` → clon local.
Derivar top10 ES/top20 EU con MCP SimilarWeb + curación del usuario → poblar `CompetitorSource`.
Fingerprint de cada dominio: `platform, tier(green/yellow/red), has_structured_data, has_visible_stock,
robots_crawl_delay, antibot`. Definir/crear índices del grafo al arrancar el brain
(`Product.id/sku`, `CompetitorProduct.*`).
**Gate/evidencia:** `fingerprint.json` cubre 100% dominios; `silverback-airsoft.com = red`; recuento
por tier; índices creados (Cypher); **cero** requests de escritura/cart en F0.

### F1 — Catálogo + precio (BaseSiteAdapter)
Crawl de 1 dominio piloto `green` devuelve ≥N productos con `price != null`, ratio de fallos < umbral.
**Evidencia:** count + 5 ejemplos.

### F2 — Stock visible
`stock_status` extraído coincide con inspección manual de 10 fichas.
**Evidencia:** muestra etiquetada.

### F3 — Histórico append-only
DB `competitor_intel` + tabla `price_stock_observation` particionada por mes + vista
`estimated_sales_daily`; 2 corridas → ≥2 observaciones/producto y `delta` correcto, gaps
`indeterminate`. **Evidencia:** queries de 3 productos incl. caso con gap.

### F4 — Cart-probe (`skirmshop-stock-prober`)
Calibración vs stock visible (muestra 10) + búsqueda binaria a cantidad exacta + limpieza de carrito
verificada + kill-switch ante 403/429. **Evidencia:** tabla probe vs visible + log de cleanup + smoke
de kill-switch.

### F5 — Matching `PRODUCT_MATCH`
Matcher puebla edges con `match_confidence`; precisión ≥ umbral en muestra revisada; dudosos a
`MatchReview`. **Evidencia:** matriz de confusión + count de edges. *(Desbloquea `prices.py`/`intel.py`.)*

### F6 — Comparación viva + push sin precio fantasma
`/prices/comparison` muestra `competitor_{min,max,count}` poblados; simular crawl fallido
(`price=None`) → conserva precio anterior y `stock_status=unknown`, no 0.
**Evidencia:** respuesta API + Cypher antes/después.

### F7 — Producción comedida
`CronJob` nocturno activo (crawler `replicas` según cola), métricas verdes, cero `block_total`
sostenido, IP egress no baneada. **Evidencia:** dashboard Prometheus + log de una noche real.

### Orden y reglas de gate
```
F0 → F1 → (F2 ∥ F5) → F3 → F4 → F6 → F7
```
- **Nunca F6 antes de F5** (la comparación viva depende de `PRODUCT_MATCH`).
- **Nunca activar el nocturno (F7) sin PASS F0–F6.**
- No avanzar de fase sin `Status: PASS` emitido por la auditoría independiente de Codex.

---

## 5. Disciplina git (dos agentes, mismos clones)

- Rama por fase `codex/competitor-crawler-F{N}-<slug>` (y análogas en `skirmshop-brain-v2`,
  `k8s-gitops-pocharlies` si aplica). Ambos agentes pushean a ELLA.
- Si el clon está en rama `codex/*` de otra sesión → trabajar y pushear ESA rama, no cambiarla.
- `git fetch`+rebase **antes de cada commit**; **push inmediato** tras validar; commits atómicos por
  criterio; **nunca** force-push a ramas compartidas ni tocar `deploy/prod`.
- Solo Codex abre PR `codex/F{N}`→`main` y `main`→`deploy/prod` (ArgoCD sigue `deploy/prod`).

---

## 6. Archivos críticos (referencia, no se tocan en bootstrap)

- **Crawler (este repo):** `RSO-MASTER-PLAN.md` + `rso/F*/…`; `src/adapters/{base,shopify,woocommerce,generic_html}.py`,
  `src/fetcher.py`, `src/push_client.py`, `config.yaml`; `k8s/manifest.yaml` (hoy `replicas:0`, img `:pending`).
- **Nuevo microservicio:** `skirmshop-stock-prober` (repo + k8s).
- **brain v2 (`skirmshop-brain-v2`):** `src/extractors/competitor.py`, `src/extractors/_base.py`,
  `src/api/prices.py` + `src/api/intel.py`, `src/schema/ontology.py`.
- **Infra:** `k8s-infra-pocharlies/databases/postgres-shared/cluster.yaml` (DB `competitor_intel`);
  ESO/Vault; `skirmshopshopifyapp/prisma/schema.prisma` (`CompetitorSource` ampliado + `MatchReview`).
