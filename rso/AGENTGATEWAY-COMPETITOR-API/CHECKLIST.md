# RHO Checklist - AgentGateway Competitor API

## Current RSO Status - 2026-07-13 (supersedes the historic pre-deploy notes below)

- [x] The Catalog RAG competitor read API is published on the normal AgentGateway plane as typed, read-only MCP tools. Evidence: app PR #94 and AgentGateway PRs #4, #6, #7 and #8 are merged; Argo Application `agentgateway-mcp` was `Synced/Healthy` at revision `c895895d` during the live audit, with the public bridge ready.
- [x] The public `/skirmshop-plugins` tool inventory contains exactly 12 tools, including the five `catalog_rag_competitor_*` reads. Evidence: live `tools/list` through the authenticated local client route, 2026-07-13; no generic Catalog RAG proxy, crawler claim, write, private, or Cypher tool is present.
- [x] Live typed calls return real data. Evidence: `catalog_rag_competitor_source({source_id:"airsoft-autopilot-17"})` returned Powair6 `coverageTarget=10804`, `coverageSeen=10596`, `coverageMissing=208`, `coveragePct=98.07`; `catalog_rag_competitor_products(..., status:"matched_auto", take:5)` returned matched Shopify SKU/competitor-price rows.
- [x] Codex, Claude and the OpenClaw `skirmshop` agent can consume the same public tools. Evidence: Codex executed the source tool live; Claude executed the products tool live; OpenClaw probe lists all 12 tools and the final agent reply was delivered to Skirmshop ES OP General (Telegram account `default`, thread `1`) with three Powair6 matches and current coverage.
- [x] The normal plane is least-privilege. Evidence: `/skirmshop-plugins-admin` is a separate route and direct unauthenticated initialization returned `401`; normal tool inventory does not expose private/admin/Cypher or mutation tools. Gateway authz harness PR #8 was merged after two green CI runs.
- [ ] Competitor data coverage is not declared complete. Evidence: Powair6 remains at 98.07% with 208 discovered-but-missing URLs and `lastSyncStatus=queued`; this API gate does not close crawler F7 or authorize retiring the standalone runtime.

## Objective

- [x] Publicar las lecturas auditables de Catalog RAG Competitors como herramientas MCP tipadas en AgentGateway `/skirmshop-plugins`, sin exponer operaciones que reclaman, mutan o sincronizan crawling. Evidence: live tools/list and typed calls, GitOps `agentgateway-mcp` Synced/Healthy, 2026-07-13.

## Directives

- [x] Codex es RSO/PMO/auditor; Claude CLI implementa. Evidence: este checklist y `HANDOFF.md`, 2026-07-13.
- [x] Mantener `GET /api/competitors` compatible: continúa devolviendo sólo el allowlist enabled existente. Evidence: contrato actual en `skirmshopshopifyapp/app/routes/api.competitors.ts`.
- [x] Las herramientas MCP deben ser tipadas y de mínimo privilegio; `skirmshop_plugins_get` o un proxy HTTP genérico no cuentan como publicación de la capability. Evidence: regla persistida en `/home/dibanez/.codex/AGENTS.md` y `/home/dibanez/.claude/CLAUDE.md`, 2026-07-13.
- [x] No publicar `/api/competitors/due`, `POST /backfills`, `PATCH /:id`, `POST /sync-result`, `POST /rescue-result`, calibraciones ni resolución de matches como herramientas normales. Evidence: contrato de seguridad de este handoff.
- [x] Trabajar mediante PRs; nunca tocar `deploy/prod` directamente ni hacer force-push. Evidence: PR #94 y #4 abiertos contra `main`; no hubo merge, deploy ni `kubectl apply`.

## Acceptance Criteria

- [x] Existe un índice y detalle read-only de fuentes que permiten pasar de `domain` a `sourceId` sin secretos. Evidence: `api.competitors.sources.ts` y `api.competitors.sources.$id.ts`; `listCompetitorSourceIndex` y `getCompetitorSourceIndexEntry` usan el mismo select explícito y mapper campo a campo. `recipeConfig`, `notes`, `syncClaimedAt` y `runs` no cruzan el boundary. RSO reejecutó 17 tests de rutas en PR #94, commits `e1af571` + `b95ed37`.
- [x] Existen herramientas MCP directas, con schemas estrictos y sólo GET: las cinco `catalog_rag_competitor_*`. Evidence: cada handler fija plugin+method=GET+path; `catalog_rag_competitor_source` apunta exclusivamente a `/api/competitors/sources/:id`, no al endpoint legado con fila completa. `source_id` exige CUID Prisma `^c[a-z0-9]{24}$`; RSO reejecutó `node --test` 16/16 en PR #4, commits `b0baa7a` + `bf73457` + `54b1b3a`. NOTA: `tools/list` con JWT en staging/prod es PENDIENTE (necesita deploy).
- [x] `catalog_rag_competitor_products` acepta sólo `source_id`, `status` enumerado, `q`, `page`, `take<=100`; nunca admite path/method/headers/body. Evidence: `COMPETITOR_PRODUCTS_SCHEMA` `additionalProperties:false`; tests "competitor tools take no agent-controlled path...", "an off-enum product status is refused", "undeclared keys are dropped", "take is clamped to 100".
- [x] `catalog_rag_competitor_rescue_candidates` acepta sólo `source_id`, estado, página y `take` limitado. Evidence: `COMPETITOR_RESCUE_SCHEMA` + `normalizeCompetitorArgs` clamp a 100 en el handler (upstream rescue-candidates NO acota); test "take is clamped to 100 even though upstream rescue-candidates does not clamp".
- [x] Las herramientas inyectan `CATALOG_SYNC_TOKEN` sólo dentro del backend y no lo reflejan en resultados/logs/errores. Evidence: `injectDefaultAuth` añade el header; `addHeaderIfMissing` empuja SOLO el NOMBRE a `injectedAuthHeaders`. Tests "the token value is never serialized into a tool result" y "fail closed ... leak nothing".
- [x] El plano normal de AgentGateway no expone `skirmshop_plugins_get`, `skirmshop_plugins_request`, `catalog_rag_api` ni herramienta competidora mutante. Evidence: `agentgateway-config.yaml` los tres bajo `GATEWAY_WRITE`+rol; `check-mcp-coverage.py` PASS (17 rutas, 301 tools) y FALLA al reabrir plugins_get (probado revirtiendo). NOTA: confirmación por `tools/list` live = PENDIENTE (deploy).
- [x] La brecha GET-stateful queda cerrada (defensa en 2 capas). Evidence: (config) plugins_get gateado; (backend) `assertReadOnlyPath` rechaza `/api/competitors/due` en cualquier proxy read-only. Tests "skirmshop_plugins_get cannot claim crawl jobs via /due", "a read-only proxy call cannot reach /api/competitors/due", denylist robusto a case/slash/encoding. NOTA: prueba negativa LIVE con JWT + DB sin claims = PENDIENTE (deploy).
- [blocked: requiere deploy] Las nuevas herramientas read-only se listan y devuelven cobertura/listas reales con JWT normal en staging y producción. Blocker: smokes MCP live `initialize`/`tools/list`/`tools/call` no ejecutables sin merge+deploy; el ejecutor no despliega. Cubierto en local por `node --test` + módulo exporta 5 tools.
- [x] `GET /api/competitors` legacy permanece compatible. Evidence: sin cambios en `app/routes/api.competitors.ts`; nuevo test `test/routes/api.competitors.legacy-contract.test.ts` bloquea el envelope `{ok,domains}` (enabled-only) y la query Prisma exacta. Compat Synapse `/due` (sólo worker) sin cambios de contrato. NOTA: smoke live `/due` desde worker = PENDIENTE (deploy).
- [x] Documentación de ruta y guardrail declaran las herramientas y su política. Evidence: `docs/route-index.md` (fila + línea de decisión), `MCP-TOPOLOGY.md` (fila + sección "a GET tool is not automatically a read tool"), `scripts/check-mcp-coverage.py` (inventario + gate + guardrail anti claim/mutación). RSO reejecutó guardrail PASS (17 rutas, 301 tools) y `kubectl kustomize k8s/overlays/prod`.

## Specialist Checks

- [x] Backend/API: índice y detalle seguro de fuentes, conservando el endpoint legado para Synapse. Owner: Claude, auditado por RSO. Evidence: 17/17 Vitest reejecutado; el RSO detectó que la primera versión MCP apuntaba al detalle legado y exigió `GET /api/competitors/sources/:id` en `b95ed37`.
- [x] MCP/Gateway: tools tipadas, allowlist y bloqueo del proxy GET genérico. Owner: Claude, auditado por RSO. Evidence: `node --test` 16/16, `check-mcp-coverage.py` PASS y render prod OK. `skirmshop_plugins_get` sólo queda tras `GATEWAY_WRITE` + rol firmado.
- [x] Security: no path injection, token leak ni capability de claim/mutación en plano normal. Owner: Claude, auditado por RSO. Evidence: `assertCompetitorSourceId` exige CUID real y codifica URI; `/due` se deniega en el proxy read-only; test de ruta confirma que el detalle MCP usa `/sources/:id`.
- [blocked: requiere deploy] Runtime: GitOps Synced/Healthy y ambos smokes de AgentGateway. Owner: Claude; re-ejecución RSO. Blocker: no merge/deploy por el ejecutor.

## Status - 2026-07-13

- [x] Diseño y hallazgo de seguridad auditados. Evidence: `skirmshop-plugins-mcp.js` permite `skirmshop_plugins_get` genérico y el perfil `catalog` inyecta `x-catalog-token`; `/api/competitors/due` reclama fuentes pese a ser GET.
- [x] Implementación/PR y remediación P1. Evidence: skirmshopshopifyapp PR #94 (rama `claude/competitor-sources-api`, `e1af571`, `b95ed37`); agentgateway PR #4 (rama `claude/competitor-mcp-readonly`, `b0baa7a`, `bf73457`, `54b1b3a`). RSO reejecutó los tests y el render tras la remediación. CI gateway PASS; CI app está en curso para el último SHA. NO merge, NO deploy.
- [blocked: requiere deploy] Merge/deploy + smokes live + gate RSO final. Blocker: pendiente de re-ejecución independiente por Codex/RSO tras merge y despliegue GitOps. Ver `claude-implementation.report.md`.
