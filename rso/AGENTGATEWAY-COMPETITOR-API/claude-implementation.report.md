# Claude Implementation Report — AgentGateway Competitor API

## RSO Live Closure Addendum - 2026-07-13

The pre-deploy report below is retained as implementation history. Codex re-ran the operational gate after merge and GitOps reconciliation.

| Gate | Result | Direct evidence |
|---|---|---|
| App and gateway delivery | PASS | App PR #94 and AgentGateway PRs #4, #6, #7 and #8 merged. PR #8 made the authorization harness deterministic; both CI attempts passed. |
| Public MCP inventory | PASS | Authenticated live `tools/list` exposed exactly 12 tools. The public list contains the five typed competitor reads and no generic Catalog RAG proxy, crawler claim, write, private or Cypher tool. |
| Typed competitor reads | PASS | `catalog_rag_competitor_source` with legacy live id `airsoft-autopilot-17` returned Powair6 coverage `10804/10596/208/98.07`. `catalog_rag_competitor_products` with `matched_auto` returned real Shopify SKU/competitor-price/URL rows. |
| Client consumption | PASS | Codex executed the source tool; Claude executed the products tool; OpenClaw `skirmshop` probed 12 tools and delivered the read-only result to Skirmshop ES OP General. |
| Normal-plane separation | PASS | `/skirmshop-plugins-admin` is a separate backend. Direct unauthenticated initialization returned `401`; the normal discovery plane contains only the 12 read-only public tools. |

### Important corrections and remaining risk

- `source_id` supports both Prisma CUIDs and legacy opaque ids matching `[a-z0-9][a-z0-9-]{0,62}[a-z0-9]`; the historical CUID-only description below was replaced by AgentGateway PR #6 so existing configured sources remain queryable.
- The OpenClaw talk helper now uses its configured Telegram account `default` and Skirmshop ES OP General thread `1`. A former account id and retired thread `584` were operationally invalid; neither required exposing a token.
- This is an API/access gate, not a crawler-completeness gate. Powair6 is currently 98.07% covered with 208 missing URLs, so F7/decommission remains open.

- **Rol**: Claude CLI = EJECUTOR. Codex = RSO/PMO/auditor. **No declaro el gate final.**
- **Fecha**: 2026-07-13
- **Resumen**: Publicadas las lecturas del crawling de competidores como 5 herramientas MCP tipadas read-only, y cerrada la brecha del proxy GET genérico que podía reclamar jobs de crawl. Dos PRs abiertos, sin merge ni deploy.

## Branches / commits / PRs

| Repo | Rama | Commit | PR |
|---|---|---|---|
| `skirmshopshopifyapp` | `claude/competitor-sources-api` | `e1af571` | https://github.com/pocharlies-org/skirmshopshopifyapp/pull/94 |
| `k8s-agentgateway-pocharlies` | `claude/competitor-mcp-readonly` | `b0baa7a` | https://github.com/pocharlies-org/k8s-agentgateway-pocharlies/pull/4 |

Ambas ramas: 1 commit sobre `origin/main` (merge-base == `origin/main`, 0 commits por detrás). Worktrees usados para no tocar los clones compartidos:
- `/home/dibanez/k8s/_wt-app-competitor`
- `/home/dibanez/k8s/_wt-agw-competitor`

**Orden de merge**: primero el PR de la app (#94), luego el del gateway (#4). `catalog_rag_competitor_sources` da 404 hasta que exista `GET /api/competitors/sources`.

## Archivos

### App (skirmshopshopifyapp) — +322 líneas
- `app/routes/api.competitors.sources.ts` (nuevo) — loader `GET /api/competitors/sources`, `x-catalog-token`, envelope `{ ok, count, sources }`, filtro opcional `?enabled=true|false`.
- `app/services/competitors/audit.server.ts` — `COMPETITOR_SOURCE_INDEX_SELECT` (allowlist de columnas) + `listCompetitorSourceIndex()` (construye la respuesta campo a campo, NO `...row`; `lastCounts` via `parseCompetitorCounts`; `lastError` truncado a 300).
- `test/routes/api.competitors.sources.test.ts` (nuevo, 6 casos).
- `test/routes/api.competitors.legacy-contract.test.ts` (nuevo, 2 casos) — bloquea el contrato `{ok,domains}`.

### Gateway (k8s-agentgateway-pocharlies) — +577 / -12
- `k8s/base/skirmshop-plugins-mcp/skirmshop-plugins-mcp.js` — 5 schemas estrictos + 5 tools + handlers; `assertCompetitorSourceId` (cuid + `encodeURIComponent`); `assertReadOnlyPath` (denylist `/api/competitors/due`); `normalizeCompetitorArgs` (clamp `take<=100`, enum status, drop de claves no declaradas); guarda del arranque stdio bajo `require.main` + `module.exports` para test.
- `k8s/base/skirmshop-plugins-mcp/skirmshop-plugins-mcp.test.js` (nuevo, 15 casos `node:test`).
- `k8s/base/agentgateway-config.yaml` — 5 tools read-only añadidas al plano abierto; **`skirmshop_plugins_get` movido a `GATEWAY_WRITE`+rol** `agentgateway-write`.
- `k8s/base/manifest.yaml` — `checksum/config` actualizado (rollout del ConfigMap).
- `scripts/check-mcp-coverage.py` — inventario + gate de `plugins_get` + guardrail anti tool de claim/mutación de competidores.
- `docs/route-index.md`, `MCP-TOPOLOGY.md` — política documentada.
- `.github/workflows/ci.yml` — step `node --test` del shim.

## Comandos ejecutados + resultados (todo en local, verde)

### App
```
npx vitest run test/routes/                      -> 42 passed (8 files)
npx vitest run test/services/competitors/        -> 47 passed (5 files)
npx tsc --noEmit -p tsconfig.typecheck.json      -> 52 errores (todos PREEXISTENTES en origin/main:
                                                    baseline limpio = 52; con mis cambios = 52;
                                                    NINGUNO en los ficheros tocados)
npx eslint <ficheros tocados>                     -> clean
npm run build                                     -> ok
```
Precedencia de ruta (estática `sources` vs dinámica `:id`) verificada con el resolvedor del propio build (`@remix-run/dev` `UNSAFE_flatRoutes`): `sources` resuelve como hijo estático hermano de `:id`, misma posición estructural que `coverage`/`due` (que hoy funcionan en prod). React Router rankea estático > dinámico entre hermanos.

### Gateway
```
node --test k8s/base/skirmshop-plugins-mcp/skirmshop-plugins-mcp.test.js
                                                  -> # tests 15  # pass 15  # fail 0
python3 scripts/check-mcp-coverage.py             -> passed: 17 routes, 301 audited tools
kubectl kustomize k8s/overlays/prod               -> render OK (skirmshop_plugins_get sale gateado)
kubectl kustomize k8s/overlays/stg               -> render OK
python3 -c "yaml.safe_load_all(agentgateway-config.yaml)"  -> parses
grep -RnEI 'Bearer …{16,}' k8s/ argocd/ scripts/  -> clean (regla de secret-scan de CI)
bash -n scripts/smoke-write-role.sh; node -c shim  -> ok
```

### Guardrails probados adversarialmente (revertidos tras probar)
- Reabrir `skirmshop_plugins_get` en el plano normal → `check-mcp-coverage.py` FALLA: *"skirmshop_plugins_get must be gated by GATEWAY_WRITE"* + *"must require the signed agentgateway-write realm role"*.
- Añadir `catalog_rag_competitor_due_claim` → FALLA: *"competitor claim/mutation tool is forbidden in the MCP plane"*.

### CI de los PRs
- App PR #94: `CI_Node_20.19.0`, `CI_Node_22`, `CI_Node_24` → **PASS** (3/3).
- Gateway PR #4: el run `push` (mismo SHA `b0baa7a`) → **PASS**, incluyendo el step nuevo `Unit-test the skirmshop-plugins MCP shim` (`# pass 15`). El run `pull_request` falló SOLO en `Install kustomize` (`tar: Cannot open kustomize_v*.tar.gz` — descarga de GitHub, flake de infra ajeno al diff); rerun lanzado.

## Cómo se cierra la brecha (defensa en 2 capas)
1. **Config** (`agentgateway-config.yaml`): `skirmshop_plugins_get` pasa a requerir `$GATEWAY_WRITE` + rol firmado `agentgateway-write`, igual que `_request`/`_call`. Motivo: AgentGateway autoriza por NOMBRE de tool y no ve el path; "GET" no implica read-only, y `GET /api/competitors/due` reclama un lease de crawl con el `CATALOG_SYNC_TOKEN` que inyecta el perfil `catalog`.
2. **Backend** (`skirmshop-plugins-mcp.js`): `assertReadOnlyPath` rechaza `/api/competitors/due` en cualquier llamada proxy read-only, robusto a mayúsculas/slash final/query. Así el gate no se deshace por drift de config solo.

Las 5 tools tipadas no aceptan path/method/headers/body/query/token (`additionalProperties:false`); `source_id` validado como cuid y `encodeURIComponent`; `take` acotado a 100 en el handler (upstream `/rescue-candidates` NO acota). `/due`, backfills, PATCH, `sync-result`, `rescue-result`, calibraciones y match resolution NO son tools.

## Limitaciones / pendiente (NO simulado)
- **Smokes LIVE** (`initialize` / `tools/list` / `tools/call` con JWT en staging y prod): **PENDIENTE**. No ejecutables sin merge + deploy GitOps; el ejecutor no despliega. Cubierto en local por `node --test` y por que el módulo exporta exactamente las 5 tools.
- **Prueba negativa LIVE** (JWT normal no alcanza `/api/competitors/due`; DB sin claims ni cambio de `lastSyncAt` durante el smoke): **PENDIENTE** (requiere cluster). Cubierta estáticamente por config + `assertReadOnlyPath` + tests.
- **Compat Synapse `/due` desde el worker** en vivo: **PENDIENTE** (requiere deploy). El contrato no cambia (sin diff en `api.competitors.due.ts`).
- **Rerun del check `pull_request`** del gateway en curso (flake de `Install kustomize`).
- **Typecheck del repo app**: 52 errores preexistentes en `origin/main` (no introducidos por este cambio).

## Nota de proceso
- Este repo RSO está en la rama `codex/competitor-crawler-F7-production-comedida` (otra sesión). Por la regla de seguridad, NO commiteé/pusheé sobre rama ajena: `CHECKLIST.md` y este informe quedan en el working tree para que Codex (dueño de la rama) los versione.
- No se declaró PASS del gate RSO. No se buscaron ni mostraron secretos. No se hizo merge, deploy ni `kubectl apply`.

## RSO Addendum - 2026-07-13

La auditoría independiente encontró un P1 después del primer push: `catalog_rag_competitor_source` apuntaba al endpoint legado `GET /api/competitors/:id`, que serializa la fila completa de `CompetitorSource` y sus runs. No era apto para AgentGateway porque podía incluir `recipeConfig`, `notes` y el lease `syncClaimedAt`.

La corrección quedó incorporada antes de aceptar la evidencia de implementación:

- PR #94 añade `GET /api/competitors/sources/:id` y `getCompetitorSourceIndexEntry()` en commit `b95ed37`. Reutiliza el select allowlist del índice y construye la respuesta campo a campo; no devuelve configuración opaca, notas, lease ni runs.
- PR #4 cambia la tool al endpoint seguro, restringe `source_id` a CUID Prisma `^c[a-z0-9]{24}$` y actualiza su contrato en `bf73457` y `54b1b3a`.
- RSO reejecutó: 17/17 Vitest de contratos de ruta, 16/16 `node:test` del shim, `check-mcp-coverage.py` (PASS: 17 rutas, 301 tools) y `kubectl kustomize k8s/overlays/prod`.

El gate sigue bloqueado sólo por el paso correcto de operación: merge ordenado (app antes que gateway), reconciliación GitOps y smoke read-only live con JWT normal. No se ha desplegado ni se declara PASS final.
