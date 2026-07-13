# HANDOFF - OpenClaw Catalog RAG First

ROL: Claude CLI = EJECUTOR. Codex = RSO/PMO/AUDITOR.

## Objective

Make the live `skirmshop` OpenClaw agent use indexed Catalog RAG competitor
evidence before Browser/web research for every price, stock, availability or
competitor-comparison request.

## Live Source Of Truth

The live Telegram Skirmshop agent is the Kubernetes deployment in namespace
`openclaw-qwen36`. Its durable global instruction is rendered from:

`/home/dibanez/k8s/k8s-openclaw-qwen36-pocharlies/helm/openclaw-qwen36/files/global-agents.md`

It is mounted in the live pod as `/data/AGENTS.md` through ConfigMap
`openclaw-qwen36-global-agents`. Do not edit the similarly named workspace on
`sauvage`: it is a divergent copy and is not evidence that the live agent has
changed.

## Execution Constraints

1. Use a dedicated `claude/*` branch and a PR against `main`; fetch and rebase
   on `origin/main` before commit. Push immediately. Never force-push.
2. Do not modify `deploy/prod`, apply manifests manually, restart pods by hand,
   change model/allowlists, or expose mutations.
3. The current public MCP plane contains source-scoped competitor reads only:
   `catalog_rag_competitor_sources`, `_coverage`, `_source`, `_products`, and
   `_rescue_candidates`. It does not yet contain global product search.
4. A separate delivery may add `catalog_rag_competitor_search`; do not instruct
   the agent to call it until its app and AgentGateway PRs are merged, deployed,
   and visible in live `tools/list`.

## Prompt To Insert

Append this section to `files/global-agents.md`, scoped explicitly to the
`skirmshop` agent. Preserve all existing global directives.

```md
## Datos de competencia: Catalog RAG primero (skirmshop)

Para cualquier pregunta de precio, stock, disponibilidad, comparativa o
posicionamiento de competidores:

1. Extrae primero la referencia del fabricante, SKU de Skirmshop, handle y/o
   dominio de la tienda competidora.
2. Antes de usar Browser, Web Search o abrir una web, consulta las herramientas
   de solo lectura `skirmshop-plugins__catalog_rag_competitor_*`. Esas
   herramientas devuelven observaciones indexadas; no hacen crawling ni web
   search.
3. Si el operador da un dominio, llama primero
   `skirmshop-plugins__catalog_rag_competitor_sources`, resuelve su `source_id`
   y llama a `skirmshop-plugins__catalog_rag_competitor_products` con `q` y un
   `take` pequeno. Devuelve, cuando existan: dominio, URL competidora,
   precio/moneda, stock, momento de observacion, provenance/metodo y cobertura
   de la fuente.
4. Si no hay dominio, la capacidad actual no permite buscar una referencia de
   forma global y eficiente. Llama a `catalog_rag_competitor_sources` para
   comprobar las fuentes disponibles, pero no simules que todas se han
   consultado y no uses Browser automaticamente. Pide el dominio preferido o
   explica que no hay evidencia indexada global con la capacidad actual.
5. Si Catalog RAG no devuelve filas, responde: "No hay observacion indexada en
   Catalog RAG para <identificador>; no significa que el producto no exista."
   Nunca inventes precio o stock, ni presentes una pagina web como resultado
   del crawler.
6. Solo usa Browser/Web si el operador pide expresamente una "busqueda web
   actual" o acepta el fallback despues de que Catalog RAG no tenga evidencia.
   Separa y etiqueta ese bloque exactamente como:
   "Investigacion web actual (no Catalog RAG)". Nunca mezcles sus valores con
   observaciones indexadas.
7. No inicies crawl, backfill, rescue, cart, checkout, login, probe ni ninguna
   mutacion al responder una consulta.
8. Mantiene la respuesta compacta y trazable: fuente, URL, hora de observacion,
   precio/stock y cobertura o limitacion conocida.
```

## Prompt Delta After Global Search Is Live

Only after `catalog_rag_competitor_search` appears in the normal live
`/skirmshop-plugins` `tools/list`, replace rule 4 with:

```md
4. Si no hay dominio, llama primero a
   `skirmshop-plugins__catalog_rag_competitor_search` con la referencia, SKU,
   handle o titulo. Informa las fuentes consultadas y su cobertura. Si `total`
   es cero, no concluyas que el producto no existe: declara que no hay una
   observacion indexada y ofrece el fallback web solo bajo la regla 6.
```

## Acceptance Criteria

- [ ] The PR changes only the GitOps instruction source and documentation
  necessary for its rollout. Evidence: scoped diff and rendered Helm output.
- [ ] The rendered ConfigMap contains the `Catalog RAG primero` section.
  Evidence: `helm template` plus ConfigMap text.
- [ ] After merge and Argo sync, the live pod `/data/AGENTS.md` contains the
  section. Evidence: `kubectl exec` read-only hash and contextual grep.
- [ ] A non-delivered `openclaw agent --agent skirmshop` test for
  `20190901G2` invokes or considers `catalog_rag_competitor_sources` before
  any Browser/Web tool and clearly reports the no-global-search limitation.
  Evidence: transcript/trace with no Browser/Web call.
- [ ] With an explicit competitor domain, the agent calls `sources` followed by
  `products` and labels output as indexed evidence with observation time.
  Evidence: trace and result fields.
- [ ] A request explicitly asking for current web research produces a separate
  `Investigacion web actual (no Catalog RAG)` block and never relabels it as
  crawler output. Evidence: transcript.
- [ ] No crawler job, admin MCP tool, generic HTTP proxy, credentials, cart,
  login, checkout or private data becomes reachable. Evidence: live tools/list
  and negative trace.

## Current RSO Status - 2026-07-13

BLOCKED pending Claude CLI quota recovery. Investigation established that the
current live per-workspace Skirmshop `AGENTS.md` is a generic seed and the
customised `sauvage` workspace is divergent. No prompt has been applied and no
live claim is permitted until the above GitOps PR and live agent traces pass.
