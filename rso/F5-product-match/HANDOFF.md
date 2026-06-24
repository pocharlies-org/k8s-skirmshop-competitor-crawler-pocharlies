# HANDOFF - F5 Product Match

ROL: Claude CLI = EJECUTOR. Codex = RSO/PMO/auditor. Implementa directamente dentro del scope que te toque; no re-delegues salvo roles `rho-*` solicitados por Codex.

REPO RSO: `/home/dibanez/k8s/k8s-skirmshop-competitor-crawler-pocharlies`
RAMA RSO: `codex/competitor-crawler-F5-product-match`

REPOS CANDIDATOS A INVESTIGAR:
- `/home/dibanez/k8s/skirmshop-brain-v2`
- `/home/dibanez/k8s/skirmshopshopifyapp`
- este repo RSO para reportes/checklist

ANTES:
1. En cada repo que vayas a tocar: `git fetch origin && git pull --rebase --autostash`.
2. Si el repo ya esta en rama `codex/*`, trabaja esa rama; si no, usa una rama F5 `codex/competitor-crawler-F5-product-match` o equivalente.
3. Lee `RSO-MASTER-PLAN.md`, `rso/F5-product-match/CHECKLIST.md`, `rso/F2-visible-stock/codex-audit.report.md`.
4. Investiga `skirmshop-brain-v2/src/schema/ontology.py`, `src/api/prices.py`, `src/api/intel.py`, `src/services/shopify_order_lines.py`, `src/extractors/competitor.py`, tests relacionados y `skirmshopshopifyapp/prisma/schema.prisma`.

OBJETIVO F5:
Poblar/validar `PRODUCT_MATCH` para conectar nuestros productos Shopify con `CompetitorProduct`, registrando `match_confidence` y `match_method`, con cascada EAN/GTIN -> SKU -> marca+modelo normalizado -> embeddings BGE/reranker. Auto-link solo por encima de umbral alto; tramo medio a `MatchReview`; nunca alimentar consumidores con match dudoso.

SCOPE PERMITIDO:
- Codigo/tests de matching en `skirmshop-brain-v2` si ahi vive el grafo/matcher.
- Prisma/schema de `skirmshopshopifyapp` solo si `MatchReview` falta y el research lo justifica.
- `rso/F5-product-match/**` para reportes, matrices, muestras y auditoria.
- Scripts CLI de dry-run/apply controlado si siguen patrones del repo.

PROHIBIDO:
- `deploy/prod`, k8s manifests, CronJobs, produccion nocturna.
- Historico/F3, cart-probe/F4, comparacion viva/F6, scheduling/F7.
- Crear edges dudosos como `PRODUCT_MATCH`.
- Escribir en produccion real sin target explicito, dry-run previo, before/after counts e idempotencia demostrada. Si solo hay prod, reporta `[blocked]`.
- Exponer secretos/tokens o datos personales en logs/reportes.

REQUISITOS:
- Primero escribe `rso/F5-product-match/researcher.report.md` con topologia, target de datos, comandos read-only, riesgos y propuesta de contrato.
- Define contrato `PRODUCT_MATCH`: direccion, claves idempotentes, propiedades, metodos (`ean_gtin`, `sku`, `brand_model`, `embedding_rerank` o equivalentes), umbrales.
- Implementa dry-run que emita candidatos con senales, score y decision (`auto_link|review|reject`) sin writes.
- Implementa apply solo si hay target permitido y seguro; debe ser idempotente y producir count before/after.
- Produce muestra revisada y matriz de confusion. Si no hay muestra real suficiente, genera artifact de review y marca blocker parcial.
- Tests: matcher unitario, normalizacion NFKD/ASCII/hyphen->space, umbrales, no-link de dudosos, idempotencia, consumidor `prices.py`/`intel.py` si aplica.

COMANDOS ESPERADOS:
- Tests relevantes del repo Brain (`pytest ...`) y `git diff --check`.
- Dry-run F5 con output `rso/F5-product-match/match-candidates.json`.
- Matriz `rso/F5-product-match/confusion-matrix.json` o `.md`.
- Count de `PRODUCT_MATCH` before/after si se hace apply permitido.
- Validacion de que `MatchReview` recibe dudosos o artifact equivalente si schema aun no existe.

SALIDA ESPERADA:
Reportes `researcher.report.md`, `architect.report.md`, `backend.report.md`, `security.report.md`, `verifier.report.md` segun rol; resumen, archivos tocados, comandos+resultados, checklist PASS/FAIL y riesgos residuales. NO empieces F3/F4/F6/F7.
