# HANDOFF - AgentGateway Competitor API

ROL: Claude CLI = EJECUTOR. Codex = RSO Master Harness / PMO / auditor.

## Objetivo

Publica las lecturas auditables del crawling de competidores de Catalog RAG como herramientas MCP tipadas en AgentGateway. Hazlo en la misma entrega que elimina el bypass del proxy GET genérico que puede alcanzar endpoints GET con efectos de estado.

## Repos y ramas

- App Catalog RAG: `/home/dibanez/k8s/skirmshopshopifyapp`
- AgentGateway/GitOps: `/home/dibanez/k8s/k8s-agentgateway-pocharlies`
- RSO: `/home/dibanez/k8s/k8s-skirmshop-competitor-crawler-pocharlies/rso/AGENTGATEWAY-COMPETITOR-API/`

Antes de editar cada repo: `git fetch origin`, rebase de tu rama contra su remoto/base actual, crea una rama `claude/*` o continúa una `codex/*` existente compartida sólo si ya es la rama de esta tarea. No force-push. No toques `deploy/prod` directamente. Un PR por repo si los repos no pueden compartir PR.

Lee primero `CHECKLIST.md`, `MCP-TOPOLOGY.md`, `docs/route-index.md`, `scripts/check-mcp-coverage.py` y el código actual de `skirmshop-plugins-mcp`.

## Diseño obligatorio

1. En la app añade `GET /api/competitors/sources` read-only, protegido por `x-catalog-token`.
   - Mantén `GET /api/competitors` sin cambios semánticos: `{ ok, domains }` con sólo dominios enabled.
   - Devuelve una lista auditable de fuentes con al menos `id`, `domain`, `enabled`, `tier`, `baseUrl`, `siteRecipe`, `crawlIntervalSec`, `publicCrawlMode`, `lastSyncAt`, `lastSyncStatus`, `lastCounts` y `lastError`.
   - No devuelvas secretos, headers, tokens, credenciales, HTML crudo ni callbacks.
   - Añade tests de contrato y de auth. La ruta estática `sources` debe preceder correctamente a la ruta dinámica `:id`.

2. En `k8s-agentgateway-pocharlies/k8s/base/skirmshop-plugins-mcp/skirmshop-plugins-mcp.js`, implementa herramientas directas con rutas y método fijados:
   - `catalog_rag_competitor_sources({ enabled? })` -> `GET /api/competitors/sources`
   - `catalog_rag_competitor_coverage()` -> `GET /api/competitors/coverage`
   - `catalog_rag_competitor_source({ source_id })` -> `GET /api/competitors/:id`
   - `catalog_rag_competitor_products({ source_id, status?, q?, page?, take? })` -> `GET /api/competitors/:id/products`
   - `catalog_rag_competitor_rescue_candidates({ source_id, status?, page?, take? })` -> `GET /api/competitors/:id/rescue-candidates`
   - Usa `encodeURIComponent` para `source_id`; schemas estrictos; `take` máximo 100; estado de productos limitado a `observed|missing|blocked|matched_manual|matched_auto|unmatched`; no aceptes `path`, `method`, `headers`, `body` ni URL desde el agente.
   - Conserva el token únicamente en el backend mediante el perfil `catalog`. No lo serialices en la salida.

3. Cierra el bypass:
   - `skirmshop_plugins_get` es genérico y open actualmente, mientras el perfil `catalog` le inyecta el token; puede llamar `GET /api/competitors/due`, que reclama jobs. Ponlo bajo `GATEWAY_WRITE` como mínimo y actualiza documentación/guardrail. No uses el proxy genérico como la interfaz normal de competidores.
   - Mantén `skirmshop_plugins_request`, `catalog_rag_api`, los callbacks y toda herramienta mutante fuera del plano normal.
   - No añadas herramienta para `/due`, backfills, PATCH, `sync-result`, `rescue-result`, calibraciones, match resolution ni cualquier acción que haga crawling o cambie estado.

4. Actualiza `k8s/base/agentgateway-config.yaml`, `scripts/check-mcp-coverage.py`, `docs/route-index.md` y `MCP-TOPOLOGY.md` para que las cinco herramientas sean read-only abiertas y las genéricas/mutantes sean gated.

## Verificación obligatoria

1. Tests unitarios del endpoint y del MCP. Añade tests si el backend no tiene harness de pruebas; no declares PASS sólo con inspección.
2. `python3 scripts/check-mcp-coverage.py` y validación Kustomize/CI del repo AgentGateway.
3. Staging, después producción por GitOps/PR: `initialize` + `tools/list` con JWT normal.
   - Deben aparecer las cinco herramientas `catalog_rag_competitor_*`.
   - No debe aparecer `skirmshop_plugins_get`, `skirmshop_plugins_request`, `catalog_rag_api` ni herramientas competidoras mutantes.
4. `tools/call` read-only contra fuentes/cobertura/productos/rescates con IDs reales conocidos. Captura sólo conteos y campos no sensibles.
5. Prueba negativa: un JWT normal no puede invocar `/api/competitors/due`; verifica además que no creó claims, runs ni cambios de `lastSyncAt`.
6. Prueba de compatibilidad: Synapse sigue llamando `/api/competitors/due` con su token desde el worker; `GET /api/competitors` legacy no cambia respuesta.
7. Re-ejecuta los smokes tras deploy y registra SHA/PR, Argo Sync/Health, tools list y resultados redacted.

## Entregables

- PR(s) con commits atómicos y push inmediato.
- Informe en `rso/AGENTGATEWAY-COMPETITOR-API/claude-implementation.report.md` con paths, comandos, resultados, hashes, URLs de PR y riesgos.
- `CHECKLIST.md` actualizado: sólo marca `[x]` con evidencia directa; deja cualquier bloqueo explícito.
- No declares el gate final; Codex lo audita re-ejecutando comandos.
