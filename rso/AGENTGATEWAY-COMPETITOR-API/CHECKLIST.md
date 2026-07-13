# RHO Checklist - AgentGateway Competitor API

## Objective

- [ ] Publicar las lecturas auditables de Catalog RAG Competitors como herramientas MCP tipadas en AgentGateway `/skirmshop-plugins`, sin exponer operaciones que reclaman, mutan o sincronizan crawling. Evidence: pendiente.

## Directives

- [x] Codex es RSO/PMO/auditor; Claude CLI implementa. Evidence: este checklist y `HANDOFF.md`, 2026-07-13.
- [x] Mantener `GET /api/competitors` compatible: continúa devolviendo sólo el allowlist enabled existente. Evidence: contrato actual en `skirmshopshopifyapp/app/routes/api.competitors.ts`.
- [x] Las herramientas MCP deben ser tipadas y de mínimo privilegio; `skirmshop_plugins_get` o un proxy HTTP genérico no cuentan como publicación de la capability. Evidence: regla persistida en `/home/dibanez/.codex/AGENTS.md` y `/home/dibanez/.claude/CLAUDE.md`, 2026-07-13.
- [x] No publicar `/api/competitors/due`, `POST /backfills`, `PATCH /:id`, `POST /sync-result`, `POST /rescue-result`, calibraciones ni resolución de matches como herramientas normales. Evidence: contrato de seguridad de este handoff.
- [ ] Trabajar mediante PRs; nunca tocar `deploy/prod` directamente ni hacer force-push. Evidence: PR y checks pendientes.

## Acceptance Criteria

- [ ] Existe un índice read-only de fuentes que permite pasar de `domain` a `sourceId`, con campos de estado necesarios para auditoría y sin secretos. Evidence: nuevo `GET /api/competitors/sources` y tests de contrato.
- [ ] Existen herramientas MCP directas, con schemas estrictos y sólo GET: `catalog_rag_competitor_sources`, `catalog_rag_competitor_coverage`, `catalog_rag_competitor_source`, `catalog_rag_competitor_products`, `catalog_rag_competitor_rescue_candidates`. Evidence: `tools/list` de backend y pruebas de cada URL/método.
- [ ] `catalog_rag_competitor_products` acepta sólo `source_id`, `status` enumerado, `q`, `page`, `take<=100`; nunca admite path, method, headers o body controlados por el agente. Evidence: test de validación/rechazo.
- [ ] `catalog_rag_competitor_rescue_candidates` acepta sólo `source_id`, estado, página y `take` limitado. Evidence: test de validación/rechazo.
- [ ] Las herramientas inyectan `CATALOG_SYNC_TOKEN` sólo dentro del backend y no lo reflejan en resultados, logs o mensajes de error. Evidence: test/redacción y revisión de código.
- [ ] El plano normal de AgentGateway no expone `skirmshop_plugins_get`, `skirmshop_plugins_request`, `catalog_rag_api` ni ninguna herramienta competidora mutante. Evidence: `tools/list` con JWT normal y `check-mcp-coverage.py`.
- [ ] La brecha GET-stateful queda cerrada: un cliente normal no puede invocar `/api/competitors/due` ni reclamar sources; un cliente con gate de escritura tampoco recibe una herramienta competidora tipada de mutación por accidente. Evidence: prueba de autorización negativa y logs/DB sin claims durante smoke.
- [ ] Las nuevas herramientas read-only sí se listan y devuelven cobertura/listas reales con un JWT normal en staging y producción. Evidence: smokes MCP `initialize`, `tools/list`, `tools/call`, con redacción de tokens.
- [ ] `GET /api/competitors` legacy, UI Shopify y llamadas Synapse existentes permanecen compatibles. Evidence: suite de app y smoke autorizado `/api/competitors/due` sólo desde el worker, sin cambio de contrato.
- [ ] La documentación de ruta y el guardrail de cobertura MCP declaran las herramientas y su política. Evidence: `docs/route-index.md`, `MCP-TOPOLOGY.md`, `scripts/check-mcp-coverage.py` y tests verdes.

## Specialist Checks

- [ ] Backend/API: endpoint índice de fuentes y pruebas Remix. Owner: Claude. Evidence: rutas/tests.
- [ ] MCP/Gateway: tools tipadas, allowlist y bloqueo del proxy GET genérico. Owner: Claude. Evidence: diff/tests/`tools/list`.
- [ ] Security: no path injection, no token leak, no capability de claim/mutación en plano normal. Owner: Claude + RSO. Evidence: pruebas negativas.
- [ ] Runtime: GitOps Synced/Healthy y ambos smokes de AgentGateway. Owner: Claude; re-ejecución RSO. Evidence: comandos live.

## Status - 2026-07-13

- [x] Diseño y hallazgo de seguridad auditados. Evidence: `skirmshop-plugins-mcp.js` permite `skirmshop_plugins_get` genérico y el perfil `catalog` inyecta `x-catalog-token`; `/api/competitors/due` reclama fuentes pese a ser GET.
- [ ] Implementación/PR/merge/deploy. Blocker: pendiente de ejecución por Claude CLI.
- [ ] Gate RSO final. Blocker: pendiente de evidencia reproducible de Claude y re-ejecución independiente.
